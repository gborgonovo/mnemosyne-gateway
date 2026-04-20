import sys
import os
import time
import yaml
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

print("🔍 Starting Mnemosyne File-First Diagnostic...")
config = load_config()

# 1. KùzuDB Benchmark
print("\n--- Testing KùzuDB (Topology/Heat) ---")
try:
    start = time.time()
    kuzu_mgr = KuzuManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'kuzu_db'))
    active_nodes = kuzu_mgr.get_active_nodes(0.0)
    end = time.time()
    node_count = len(active_nodes)
    print(f"✅ KùzuDB: OK (Time: {end - start:.2f}s)")
    print(f"   Stats: {node_count} nodes mapped in thermal index.")
except Exception as e:
    print(f"❌ KùzuDB Error: {e}")

# 2. ChromaDB Benchmark
print("\n--- Testing ChromaDB (Semantic Vector) ---")
try:
    start = time.time()
    vector_store = VectorStore(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db'))
    nodes = vector_store.list_nodes()
    
    end = time.time()
    print(f"✅ ChromaDB: OK (Time: {end - start:.2f}s)")
    print(f"   Stats: {len(nodes)} documents embedded in vector space.")
except Exception as e:
    print(f"❌ ChromaDB Error: {e}")

# 3. File System Check
print("\n--- Testing File System ---")
knowledge_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge')
try:
    if not os.path.exists(knowledge_dir):
        print(f"⚠️ Directory {knowledge_dir} non trovata.")
    else:
        file_count = 0
        for root, dirs, files in os.walk(knowledge_dir):
            for f in files:
                if f.endswith('.md'):
                    file_count += 1
        print(f"✅ File System: {file_count} file markdown presenti.")
except Exception as e:
    print(f"❌ File System Error: {e}")

print("\nDiagnostic Complete.")
