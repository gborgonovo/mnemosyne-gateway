import os
import sys
import time
import yaml
import re
import logging
import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore
from core.utils import normalize_node_name

logging.basicConfig(level=logging.INFO, format='%(asctime)s - FileWatcher - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WikiSyncHandler(FileSystemEventHandler):
    def __init__(self, kuzu_mgr: KuzuManager, vector_store: VectorStore,
                 knowledge_dir: str, am=None):
        super().__init__()
        self.kuzu_mgr = kuzu_mgr
        self.vector_store = vector_store
        self.knowledge_dir = knowledge_dir
        self.am = am

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"File modified: {event.src_path}")
            self._sync_file(event.src_path, is_startup_sync=False)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"File created: {event.src_path}")
            self._sync_file(event.src_path, is_startup_sync=False)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"File deleted: {event.src_path}")
            name = os.path.splitext(os.path.basename(event.src_path))[0]
            norm_name = normalize_node_name(name)
            self.kuzu_mgr.delete_node(norm_name)
            self.vector_store.delete_node(norm_name)
            logger.info(f"Node '{norm_name}' removed from DBs.")

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith('.md'):
            logger.info(f"File moved: {event.src_path} -> {event.dest_path}")
            src_name = os.path.splitext(os.path.basename(event.src_path))[0]
            dst_name = os.path.splitext(os.path.basename(event.dest_path))[0]
            if src_name != dst_name:
                # Different filename: remove old node, new one will be created by sync
                self.kuzu_mgr.delete_node(normalize_node_name(src_name))
                self.vector_store.delete_node(src_name)
            # Sync destination — picks up new folder defaults (project, scope)
            self._sync_file(event.dest_path, is_startup_sync=False)

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
        """Extracts frontmatter, body, and wikilinks. Returns has_frontmatter flag."""
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

            for wl in re.findall(r'\[\[(.*?)\]\]', body):
                target = wl.split('|')[0].strip()
                if target:
                    wikilinks.append(normalize_node_name(target))

            return frontmatter, body, wikilinks, has_frontmatter
        except Exception as e:
            logger.error(f"Error parsing file {filepath}: {e}")
            return None, None, [], False

    def _write_frontmatter(self, filepath: str, frontmatter: dict, body: str):
        """Write frontmatter + body back to file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
            f.write("---\n\n")
            f.write(body)

    def _sync_file(self, filepath: str, is_startup_sync: bool = False):
        raw_name = os.path.splitext(os.path.basename(filepath))[0]
        norm_name = normalize_node_name(raw_name)

        frontmatter, body, normalized_wikilinks, has_frontmatter = self._parse_markdown(filepath)
        if frontmatter is None:
            return

        # Apply folder defaults (_defaults.yaml) for keys not set in the file
        needs_rewrite = False
        folder_defaults = self._load_folder_defaults(filepath)
        for key, value in folder_defaults.items():
            if key not in frontmatter:
                frontmatter[key] = value
                needs_rewrite = True

        # Apply system defaults for any still-missing required fields
        if 'title' not in frontmatter:
            frontmatter['title'] = raw_name
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
            logger.info(f"Frontmatter written for '{norm_name}'")

        node_type = frontmatter.get('type', 'Node')
        scope = frontmatter.get('scope', 'Public')
        if isinstance(scope, list):
            scope = scope[0]

        # Sync ChromaDB (semantic layer)
        # During cold boot, skip re-embedding files whose mtime hasn't changed.
        file_mtime = os.path.getmtime(filepath)
        skip_embed = False
        if is_startup_sync:
            existing = self.vector_store.get_node(raw_name)
            if existing:
                stored_mtime = existing.get('metadata', {}).get('_mtime', 0)
                skip_embed = abs(float(stored_mtime) - file_mtime) < 1.0

        if not skip_embed:
            frontmatter['_mtime'] = file_mtime
            self.vector_store.upsert_node(raw_name, body, frontmatter)
        else:
            logger.debug(f"Skipping re-embed for '{norm_name}' (mtime unchanged)")

        # Ensure node exists in KuzuDB with correct metadata
        self.kuzu_mgr.add_node(raw_name, initial_activation=0.5, node_type=node_type, scope=scope)
        self.kuzu_mgr.update_node_metadata(norm_name, node_type=node_type, scope=scope)

        # Rebuild edges from wikilinks
        for target_norm in set(normalized_wikilinks):
            self.kuzu_mgr.add_edge(raw_name, target_norm, "LINKED_TO", weight=0.8)

        # Apply file_edit boost only for real changes, not cold boot
        if not is_startup_sync:
            if self.am:
                self.am.record_interaction(norm_name, "file_edit")
            else:
                node_data = self.kuzu_mgr.get_node(norm_name)
                current = (node_data.get('activation_level') or 0.0) if node_data else 0.0
                self.kuzu_mgr.update_activation(norm_name, min(current + 0.6, 1.0))

        logger.info(f"Sync {'(startup) ' if is_startup_sync else ''}complete for '{norm_name}'. "
                    f"Links: {len(set(normalized_wikilinks))}, type={node_type}, scope={scope}")


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

    logger.info(f"Cold boot sync in {knowledge_path}...")
    count = 0
    for root, dirs, files in os.walk(knowledge_path):
        for filename in files:
            if filename.endswith('.md'):
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
