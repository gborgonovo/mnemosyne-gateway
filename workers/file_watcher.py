import os
import sys
import time
import yaml
import re
import logging
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

    def _parse_markdown(self, filepath: str):
        """Extracts frontmatter, body, and wikilinks."""
        frontmatter, body, wikilinks = {}, "", []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
            if yaml_match:
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

            return frontmatter, body, wikilinks
        except Exception as e:
            logger.error(f"Error parsing file {filepath}: {e}")
            return None, None, []

    def _sync_file(self, filepath: str, is_startup_sync: bool = False):
        raw_name = os.path.splitext(os.path.basename(filepath))[0]
        norm_name = normalize_node_name(raw_name)

        frontmatter, body, normalized_wikilinks = self._parse_markdown(filepath)
        if frontmatter is None:
            return

        if 'title' not in frontmatter:
            frontmatter['title'] = raw_name
        if 'type' not in frontmatter:
            frontmatter['type'] = "Node"

        node_type = frontmatter.get('type', 'Node')
        scope = frontmatter.get('scope', 'Public')
        if isinstance(scope, list):
            scope = scope[0]

        # Sync ChromaDB (semantic layer)
        self.vector_store.upsert_node(raw_name, body, frontmatter)

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
