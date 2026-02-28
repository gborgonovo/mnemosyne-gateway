import os
import sys
import logging
import yaml
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph_manager import GraphManager
from butler.llm import get_llm_provider

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    if not os.path.exists(config_path):
        # Try template if settings.yaml is missing (though it shouldn't be for backfill)
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml.template')
        
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    
    # Check if embeddings are enabled
    llm_config = config.get('llm', {})
    embedding_config = llm_config.get('embeddings', {})
    
    if not embedding_config.get('enabled', False):
        print("\n" + "="*50)
        print("⚠️  WARNING: Embeddings are DISABLED in settings.yaml (llm.embeddings.enabled).")
        print("="*50)
        confirm = input("Do you want to proceed with backfilling anyway? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return

    # Initialize components
    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )
    # Use the specifically configured embedding provider
    llm = get_llm_provider(embedding_config, root_config=config)
    
    print("\n🧠 Mnemosyne Embedding Backfill Utility")
    print("---------------------------------------")
    print(f"LLM Mode: {embedding_config.get('mode')}")
    print(f"Embedding Model: {embedding_config.get('model_name')}")
    print("---------------------------------------\n")
    
    total_processed = 0
    batch_size = 50
    
    while True:
        # We fetch nodes missing embeddings
        nodes = gm.get_nodes_missing_embeddings(limit=batch_size)
        if not nodes:
            break
            
        print(f"Batch Processing {len(nodes)} nodes...")
        for node in tqdm(nodes, desc="Generating Vectors"):
            text_to_embed = node.get('text', '').strip()
            if not text_to_embed:
                text_to_embed = node.get('name', 'Unknown')
                
            try:
                embedding = llm.embed(text_to_embed)
                if embedding:
                    gm.update_node_embedding(node['name'], embedding)
                    total_processed += 1
                else:
                    logger.warning(f"Failed to generate embedding for '{node['name']}'")
            except Exception as e:
                logger.error(f"Error embedding node '{node['name']}': {e}")
                
    print(f"\n✅ SUCCESS: Total nodes updated: {total_processed}")
    gm.close()

if __name__ == "__main__":
    main()
