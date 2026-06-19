import os
import sys
import time
import yaml
import re
import hashlib
import logging
import datetime
import queue
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore
from core.utils import normalize_node_name, node_id_from_path, _normalize_segment, strip_leading_frontmatter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - FileWatcher - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Edge types NOT derived from markdown files: computed by other workers (the
# Gardener's semantic similarity pass) and therefore exempt from the file-sync
# edge reconciliation, which would otherwise wipe them on every save.
EPHEMERAL_EDGE_TYPES = {"SEMANTICALLY_RELATED"}


def _hash_body(body: str) -> str:
    """Content hash of a node body. Drives re-embed/enrichment decisions instead
    of fragile mtime heuristics: the body is what changes by hand, the
    frontmatter is what the system rewrites, so hashing only the body lets a
    system-triggered frontmatter rewrite be recognised as a no-op."""
    return hashlib.sha256((body or "").encode("utf-8")).hexdigest()


# Syncthing conflict copies are named "name.sync-conflict-DATE-TIME-DEVICE.md":
# they still end in .md, so a bare endswith('.md') would index them as real
# nodes (the OOM incident: 250 conflict files doubled the graph). Exclude them.
SYNC_CONFLICT_MARKER = ".sync-conflict-"


def _is_indexable_md(path: str) -> bool:
    """True for real markdown files, excluding Syncthing conflict copies."""
    name = os.path.basename(path)
    return name.endswith('.md') and SYNC_CONFLICT_MARKER not in name


class WikiSyncHandler(FileSystemEventHandler):
    def __init__(self, kuzu_mgr: KuzuManager, vector_store: VectorStore,
                 knowledge_dir: str, am=None, llm=None):
        super().__init__()
        self.kuzu_mgr = kuzu_mgr
        self.vector_store = vector_store
        self.knowledge_dir = knowledge_dir
        self.am = am
        self.llm = llm
        self._enrich_queue = queue.Queue()
        # Maps normalized basename -> [path_based_node_id, ...].
        # Built during startup; maintained incrementally on create/delete/move.
        self._basename_index: dict = {}
        if llm is not None:
            t = threading.Thread(target=self._run_enrichment_worker, daemon=True)
            t.start()

    def dispatch(self, event):
        """Guard the observer thread: a failure on one file must not tear down the
        whole watcher (which would silently stop indexing every later change)."""
        try:
            super().dispatch(event)
        except Exception as e:
            src = getattr(event, 'src_path', '?')
            logger.error(f"Watcher dispatch error for '{src}': {e}", exc_info=True)

    # ─── Watchdog event handlers ───────────────────────────────────────────────

    def on_modified(self, event):
        if not event.is_directory and _is_indexable_md(event.src_path):
            logger.info(f"File modified: {event.src_path}")
            self._sync_file(event.src_path, is_startup_sync=False)

    def on_created(self, event):
        if not event.is_directory and _is_indexable_md(event.src_path):
            logger.info(f"File created: {event.src_path}")
            node_id, display_name = node_id_from_path(event.src_path, self.knowledge_dir)
            basename_key = _normalize_segment(display_name)
            self._basename_index.setdefault(basename_key, [])
            if node_id not in self._basename_index[basename_key]:
                self._basename_index[basename_key].append(node_id)
            self._sync_file(event.src_path, is_startup_sync=False)

    def on_deleted(self, event):
        if not event.is_directory and _is_indexable_md(event.src_path):
            logger.info(f"File deleted: {event.src_path}")
            node_id, display_name = node_id_from_path(event.src_path, self.knowledge_dir)
            basename_key = _normalize_segment(display_name)
            ids = self._basename_index.get(basename_key, [])
            if node_id in ids:
                ids.remove(node_id)
                if not ids:
                    self._basename_index.pop(basename_key, None)
            self.kuzu_mgr.delete_node(node_id)
            self.vector_store.delete_node(node_id)
            logger.info(f"Node '{node_id}' removed from DBs.")

    def on_moved(self, event):
        if not event.is_directory and _is_indexable_md(event.dest_path):
            logger.info(f"File moved: {event.src_path} -> {event.dest_path}")
            src_id, src_display = node_id_from_path(event.src_path, self.knowledge_dir)
            dst_id, dst_display = node_id_from_path(event.dest_path, self.knowledge_dir)
            if src_id != dst_id:
                # Remove old node from DB and index
                self.kuzu_mgr.delete_node(src_id)
                self.vector_store.delete_node(src_id)
                src_key = _normalize_segment(src_display)
                ids = self._basename_index.get(src_key, [])
                if src_id in ids:
                    ids.remove(src_id)
                    if not ids:
                        self._basename_index.pop(src_key, None)
                # Register new path in index
                dst_key = _normalize_segment(dst_display)
                self._basename_index.setdefault(dst_key, [])
                if dst_id not in self._basename_index[dst_key]:
                    self._basename_index[dst_key].append(dst_id)
            self._sync_file(event.dest_path, is_startup_sync=False)

    # ─── Basename index ────────────────────────────────────────────────────────

    def _build_basename_index(self):
        """Scan knowledge_dir and populate _basename_index.

        Must be called before the cold boot sync pass so that wikilink
        resolution has complete visibility over all nodes. Maps each
        normalized basename to the list of path-based node IDs that share it.
        """
        self._basename_index = {}
        for root, dirs, files in os.walk(self.knowledge_dir):
            for f in files:
                if not _is_indexable_md(f):
                    continue
                fp = os.path.join(root, f)
                node_id, display_name = node_id_from_path(fp, self.knowledge_dir)
                basename_key = _normalize_segment(display_name)
                self._basename_index.setdefault(basename_key, [])
                if node_id not in self._basename_index[basename_key]:
                    self._basename_index[basename_key].append(node_id)
        logger.info(f"Basename index built: {len(self._basename_index)} unique basenames, "
                    f"{sum(len(v) for v in self._basename_index.values())} total entries.")

    def _resolve_wikilink(self, basename: str, source_filepath: str) -> list:
        """Resolve a wikilink target (display basename) to path-based node ID(s).

        Returns a list (usually length 1) of node IDs to create edges toward.

        Resolution rules:
        1. Single match in index: use it.
        2. Multiple matches: prefer the one sharing the same first path segment
           (project folder) as source_filepath.
        3. Still tied: return all candidates (create edges to all).
        4. No match at all: return [basename] as a stub ID so the edge is
           created with a placeholder; when the target file arrives, the watcher
           syncs it under the correct path-based ID.
        """
        norm_base = _normalize_segment(basename)
        candidates = list(self._basename_index.get(norm_base, []))

        if not candidates:
            return [norm_base]  # stub: will be filled when the file is created
        if len(candidates) == 1:
            return candidates

        # Prefer same top-level folder (project) as source
        src_rel = os.path.relpath(os.path.abspath(source_filepath),
                                  os.path.abspath(self.knowledge_dir))
        src_parts = src_rel.replace("\\", "/").split("/")
        src_project = _normalize_segment(src_parts[0]) if src_parts else ""

        preferred = [c for c in candidates if c.startswith(src_project + "__") or c == src_project]
        if len(preferred) == 1:
            return preferred

        logger.debug(f"Wikilink [[{basename}]] ambiguous: {candidates}. Creating edges to all.")
        return candidates

    # ─── Enrichment worker ─────────────────────────────────────────────────────

    def _run_enrichment_worker(self):
        """Background thread: calls LLM to extract relations and writes them to frontmatter."""
        while True:
            item = self._enrich_queue.get()
            if item is None:
                break
            filepath, node_id, display_name, body, context_nodes = item
            try:
                # Re-read current state: file may have been enriched already or deleted
                fm, body_now, _, _ = self._parse_markdown(filepath)
                if fm is None:
                    continue
                if fm.get('enriched_hash') == _hash_body(body_now):
                    continue
                all_nodes = {n['name'] for n in self.kuzu_mgr.get_all_nodes()}
                all_nodes.update(context_nodes)
                _, relationships = self.llm.extract_entities(body_now, context_nodes=sorted(all_nodes), current_node=display_name)
                llm_relations = []
                for rel in relationships:
                    src = normalize_node_name(str(rel.get('source', '')))
                    tgt_raw = str(rel.get('target', ''))
                    tgt_norm = normalize_node_name(tgt_raw)
                    # Resolve tgt to path-based ID if possible
                    resolved = self._resolve_wikilink(tgt_norm, filepath)
                    tgt_id = resolved[0] if resolved else tgt_norm
                    if (src == node_id or src == _normalize_segment(display_name)) \
                            and tgt_id in all_nodes and tgt_id != node_id:
                        llm_relations.append({
                            'target': tgt_raw,
                            'type': str(rel.get('type', 'RELATED_TO')).upper(),
                            'source': 'llm',
                        })
                fm, body_now, _, _ = self._parse_markdown(filepath)
                if fm is None:
                    continue
                existing = fm.get('relations') or []
                user_relations = [r for r in existing if r.get('source') != 'llm']
                fm['relations'] = user_relations + llm_relations
                fm['enriched_at'] = datetime.datetime.now()
                fm['enriched_hash'] = _hash_body(body_now)
                self._write_frontmatter(filepath, fm, body_now)
                logger.info(f"Enrichment: '{node_id}' -> {len(llm_relations)} llm + {len(user_relations)} user relations")
            except Exception as e:
                logger.error(f"Enrichment error for '{node_id}': {e}")
            finally:
                self._enrich_queue.task_done()

    # ─── Markdown helpers ──────────────────────────────────────────────────────

    def _load_folder_defaults(self, filepath: str) -> dict:
        """Read _defaults.yaml from the file's parent folder, if present."""
        defaults_path = os.path.join(os.path.dirname(filepath), '_defaults.yaml')
        if os.path.exists(defaults_path):
            try:
                with open(defaults_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Could not read {defaults_path}: {e}")
        return {}

    def _parse_markdown(self, filepath: str):
        """Extract frontmatter, body, and raw wikilink basenames. Returns has_frontmatter flag."""
        frontmatter, body, wikilinks = {}, "", []
        has_frontmatter = False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
            if yaml_match:
                has_frontmatter = True
                try:
                    frontmatter = yaml.safe_load(yaml_match.group(1)) or {}
                except yaml.YAMLError as e:
                    logger.error(f"Invalid YAML in {filepath}: {e}")
                body = yaml_match.group(2).strip()
            else:
                body = content.strip()

            # Collect wikilink display basenames (not normalized yet; resolution
            # happens in _sync_file using _resolve_wikilink).
            for wl in re.findall(r'\[\[(.*?)\]\]', body):
                target = wl.split('|')[0].strip()
                if target:
                    wikilinks.append(target)

            return frontmatter, body, wikilinks, has_frontmatter
        except Exception as e:
            logger.error(f"Error parsing file {filepath}: {e}")
            return None, None, [], False

    def _write_frontmatter(self, filepath: str, frontmatter: dict, body: str):
        """Write frontmatter + body back to file."""
        body = strip_leading_frontmatter(body)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
            f.write("---\n\n")
            f.write(body)

    # ─── Core sync ────────────────────────────────────────────────────────────

    def _sync_file(self, filepath: str, is_startup_sync: bool = False):
        node_id, display_name = node_id_from_path(filepath, self.knowledge_dir)

        frontmatter, body, raw_wikilinks, has_frontmatter = self._parse_markdown(filepath)
        if frontmatter is None:
            return

        # Apply folder defaults then system defaults
        needs_rewrite = False
        folder_defaults = self._load_folder_defaults(filepath)
        for key, value in folder_defaults.items():
            if key not in frontmatter:
                frontmatter[key] = value
                needs_rewrite = True

        if 'title' not in frontmatter:
            frontmatter['title'] = display_name.replace('_', ' ')
            needs_rewrite = True
        if 'type' not in frontmatter:
            frontmatter['type'] = "Reference"
            needs_rewrite = True
        if 'scope' not in frontmatter:
            frontmatter['scope'] = "Public"
            needs_rewrite = True
        if 'created_at' not in frontmatter:
            mtime = os.path.getmtime(filepath)
            frontmatter['created_at'] = datetime.date.fromtimestamp(mtime).isoformat()
            needs_rewrite = True

        if not has_frontmatter or needs_rewrite:
            self._write_frontmatter(filepath, frontmatter, body)
            logger.info(f"Frontmatter written for '{node_id}'")

        node_type = frontmatter.get('type', 'Node')
        scope = frontmatter.get('scope', 'Public')
        if isinstance(scope, list):
            scope = scope[0]
        project = frontmatter.get('project', '')
        if isinstance(project, list):
            project = project[0] if project else ''
        project = str(project) if project else ''

        # ChromaDB sync (B3: re-embed only on body change)
        file_mtime = os.path.getmtime(filepath)
        body_hash = _hash_body(body)
        rel_path = os.path.relpath(filepath, self.knowledge_dir)
        existing = self.vector_store.get_node(node_id)
        existing_meta = existing.get('metadata', {}) if existing else {}
        body_changed = existing_meta.get('_body_hash') != body_hash

        frontmatter['_body_hash'] = body_hash
        frontmatter['_mtime'] = file_mtime
        frontmatter['_source_path'] = rel_path
        if body_changed:
            self.vector_store.upsert_node(node_id, body, frontmatter, display_name=display_name)
        else:
            self.vector_store.update_metadata(node_id, frontmatter, display_name=display_name)
            logger.debug(f"Skipping re-embed for '{node_id}' (body unchanged)")

        # KuzuDB: ensure node exists with current metadata
        title = frontmatter.get('title', display_name.replace('_', ' ')).replace('_', ' ')
        self.kuzu_mgr.add_node(node_id, initial_activation=0.5, node_type=node_type,
                               scope=scope, display_name=title, project=project)
        self.kuzu_mgr.update_node_metadata(node_id, node_type=node_type, scope=scope, project=project)

        def _ensure_stub(target_id: str):
            if not self.kuzu_mgr.get_node(target_id):
                self.kuzu_mgr.add_node(target_id, node_type="Node", scope=scope, project=project)

        # Resolve wikilinks and frontmatter relations to path-based IDs, then
        # build the desired set of outgoing edges.
        desired = {}  # (target_node_id, edge_type) -> weight
        for wl_display in raw_wikilinks:
            for tid in self._resolve_wikilink(wl_display, filepath):
                desired[(tid, "LINKED_TO")] = 0.8

        relations = frontmatter.get('relations', [])
        if isinstance(relations, list):
            for rel in relations:
                target = str(rel.get('target', '')).strip()
                rel_type = str(rel.get('type', 'RELATED_TO')).upper()
                if target:
                    for tid in self._resolve_wikilink(target, filepath):
                        desired[(tid, rel_type)] = 1.0

        # Reconcile: remove stale file-derived edges; keep ephemeral ones.
        for edge in self.kuzu_mgr.get_outgoing_edges(node_id):
            etype = edge['type']
            if etype in EPHEMERAL_EDGE_TYPES:
                continue
            if (edge['target'], etype) not in desired:
                self.kuzu_mgr.delete_edge(node_id, edge['target'], etype)

        for (target_id, rel_type), weight in desired.items():
            _ensure_stub(target_id)
            self.kuzu_mgr.add_edge(node_id, target_id, rel_type, weight=weight)

        # Activation boost for real body edits only (not cold boot, not system rewrites)
        if not is_startup_sync and body_changed:
            if self.am:
                self.am.record_interaction(node_id, "file_edit")
            else:
                node_data = self.kuzu_mgr.get_node(node_id)
                current = (node_data.get('activation_level') or 0.0) if node_data else 0.0
                self.kuzu_mgr.update_activation(node_id, min(current + 0.6, 1.0))

        logger.info(f"Sync {'(startup) ' if is_startup_sync else ''}complete for '{node_id}'. "
                    f"Links: {len(raw_wikilinks)}, type={node_type}, scope={scope}")

        # Enqueue for LLM enrichment if body is new/changed
        if (not is_startup_sync
                and self.llm is not None
                and len(body) > 150
                and node_type not in ('Observation',)):
            if frontmatter.get('enriched_hash') != body_hash:
                self._enrich_queue.put((filepath, node_id, display_name,
                                        body, list({w for wl in raw_wikilinks
                                                     for w in self._resolve_wikilink(wl, filepath)})))


def start_watcher(knowledge_dir: str = "./knowledge", once: bool = False):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    knowledge_path = os.path.join(base_dir, knowledge_dir.strip('./'))

    if not os.path.exists(knowledge_path):
        os.makedirs(knowledge_path, exist_ok=True)

    config_path = os.path.join(base_dir, "config", "settings.yaml")
    with open(config_path) as f:
        watcher_config = yaml.safe_load(f)
    embedding_config = watcher_config.get('llm', {}).get('embeddings')

    kuzu_mgr = KuzuManager(db_path=os.path.join(base_dir, "data", "kuzu_main"))
    vector_store = VectorStore(db_path=os.path.join(base_dir, "data", "chroma_db"), embedding_config=embedding_config)

    event_handler = WikiSyncHandler(kuzu_mgr, vector_store, knowledge_path)

    # Pass 1: build basename index so wikilink resolution is complete for all files
    logger.info(f"Building basename index for {knowledge_path}...")
    event_handler._build_basename_index()

    # Pass 2: cold boot sync
    logger.info(f"Cold boot sync in {knowledge_path}...")
    count = 0
    for root, dirs, files in os.walk(knowledge_path):
        for filename in files:
            if _is_indexable_md(filename):
                event_handler._sync_file(os.path.join(root, filename), is_startup_sync=True)
                count += 1
    logger.info(f"Cold boot complete. Synced {count} files.")

    if once:
        kuzu_mgr.close()
        return

    observer = Observer()
    observer.schedule(event_handler, knowledge_path, recursive=True)
    observer.start()
    logger.info(f"File Watcher started on '{knowledge_path}'")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        kuzu_mgr.close()
    observer.join()


if __name__ == "__main__":
    run_once = "--once" in sys.argv
    start_watcher(once=run_once)
