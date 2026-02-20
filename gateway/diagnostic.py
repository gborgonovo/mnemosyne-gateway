import sys
import os
import time
import yaml

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph_manager import GraphManager
from butler.llm import get_llm_provider

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

print("🔍 Starting Mnemosyne Latency Diagnostic...")
config = load_config()

# 1. Neo4j Benchmark
print("\n--- Testing Neo4j ---")
try:
    start = time.time()
    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )
    gm.verify_connection()
    stats = gm.get_stats()
    end = time.time()
    print(f"✅ Neo4j: OK (Time: {end - start:.2f}s)")
    print(f"   Stats: {stats}")
except Exception as e:
    print(f"❌ Neo4j Error: {e}")

# 2. LLM Benchmark
print("\n--- Testing LLM ---")
try:
    start = time.time()
    llm = get_llm_provider(config)
    print(f"   Mode: {config['llm']['mode']}")
    print(f"   Model: {config['llm']['model_name']}")
    response = llm.generate("test")
    end = time.time()
    print(f"✅ LLM: OK (Time: {end - start:.2f}s)")
    print(f"   Response Preview: {response[:100]}...")
except Exception as e:
    print(f"❌ LLM Error: {e}")
    import traceback
    traceback.print_exc()

print("\nDiagnostic Complete.")
