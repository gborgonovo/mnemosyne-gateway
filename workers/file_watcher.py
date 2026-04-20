import os
import sys
import time
import yaml
import re
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Ensure local imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore
from core.utils import normalize_node_name

logging.basicConfig(level=logging.INFO, format='%(asctime)s - FileWatcher - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WikiSyncHandler(FileSystemEventHandler):
    def __init__(self, kuzu_mgr: KuzuManager, vector_store: VectorStore, knowledge_dir: str):
        super().__init__()
        self.kuzu_mgr = kuzu_mgr
        self.vector_store = vector_store
        self.knowledge_dir = knowledge_dir

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"File modified: {event.src_path}")
            self._sync_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"File created: {event.src_path}")
            self._sync_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"File deleted: {event.src_path}")
            name = os.path.splitext(os.path.basename(event.src_path))[0]
            norm_name = normalize_node_name(name)
            self.kuzu_mgr.delete_node(norm_name)
            self.vector_store.delete_node(norm_name)
            logger.info(f"Node '{norm_name}' (from {name}) removed from DBs.")

    def _parse_markdown(self, filepath: str):
        """Extracts frontmatter, body, and wikilinks."""
        frontmatter = {}
        body = ""
        wikilinks = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 1. Parse Frontmatter
            yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
            if yaml_match:
                try:
                    frontmatter = yaml.safe_load(yaml_match.group(1)) or {}
                except yaml.YAMLError as e:
                    logger.error(f"Invalid YAML in {filepath}: {e}")
                body = yaml_match.group(2).strip()
            else:
                body = content.strip()

            # 2. Extract Wikilinks [[Node Name]]
            # Pattern matches [[Name]] but ignores potential [[Name|Alias]] for now
            wikilinks_raw = re.findall(r'\[\[(.*?)\]\]', body)
            for wl in wikilinks_raw:
                target = wl.split('|')[0].strip()
                if target:
                    # Normalize target to ensure [[Aia]] and [[aia]] are the same
                    wikilinks.append(normalize_node_name(target))
                    
            return frontmatter, body, wikilinks
        except Exception as e:
             logger.error(f"Error parsing file {filepath}: {e}")
             return None, None, []

    def _sync_file(self, filepath: str):
        raw_name = os.path.splitext(os.path.basename(filepath))[0]
        norm_name = normalize_node_name(raw_name)
        
        frontmatter, body, normalized_wikilinks = self._parse_markdown(filepath)
        
        if frontmatter is None:
            return # Error occurred
        # Provide defaults
        if 'title' not in frontmatter:
            frontmatter['title'] = raw_name
        if 'type' not in frontmatter:
            frontmatter['type'] = "Node"

        # 1. Sync ChromaDB (Semantic) - Internal normalization applies but we keep raw_name for display_name
        self.vector_store.upsert_node(raw_name, body, frontmatter)
        
        # 2. Sync KuzuDB (Topological Heatmap)
        node_data = self.kuzu_mgr.get_node(norm_name)
        new_activation = 1.0 # default high heat for newly edited files
        if node_data:
             new_activation = min(node_data['activation_level'] + 0.3, 1.0)
             
        self.kuzu_mgr.add_node(raw_name, initial_activation=new_activation)
        self.kuzu_mgr.update_activation(norm_name, new_activation)
        
        # 3. Rebuild Edges
        for target_norm in set(normalized_wikilinks):
            self.kuzu_mgr.add_edge(raw_name, target_norm, "LINKED_TO", weight=0.8)
            
        logger.info(f"Sync complete for '{norm_name}' (Original: {raw_name}). Found {len(set(normalized_wikilinks))} links.")

def start_watcher(knowledge_dir: str = "./knowledge", once: bool = False):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    knowledge_path = os.path.join(base_dir, knowledge_dir.strip('./'))
    
    if not os.path.exists(knowledge_path):
        os.makedirs(knowledge_path, exist_ok=True)

    kuzu_mgr = KuzuManager(db_path=os.path.join(base_dir, "data", "kuzu_db"))
    vector_store = VectorStore(db_path=os.path.join(base_dir, "data", "chroma_db"))
    
    event_handler = WikiSyncHandler(kuzu_mgr, vector_store, knowledge_path)
    
    # 1. Cold Boot - Recursive Sync all existing files on startup
    logger.info(f"Performing recursive cold boot synchronization in {knowledge_path}...")
    count = 0
    for root, dirs, files in os.walk(knowledge_path):
        for filename in files:
            if filename.endswith('.md'):
                filepath = os.path.join(root, filename)
                event_handler._sync_file(filepath)
                count += 1
    logger.info(f"Cold boot complete. Synced {count} files.")

    if once:
        kuzu_mgr.close()
        return

    # 2. Start Watcher
    observer = Observer()
    observer.schedule(event_handler, knowledge_path, recursive=True)
    observer.start()
    logger.info(f"File Watcher started. Monitoring '{knowledge_path}'...")
    
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
