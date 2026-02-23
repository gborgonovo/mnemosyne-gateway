import sys
import os
import yaml

sys.path.append(os.getcwd())

from core.graph_manager import GraphManager
from core.attention import AttentionModel
from core.chunking import HeuristicChunker

def run_test():
    # Load config
    config_path = os.path.join(os.getcwd(), 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )
    am = AttentionModel(gm, config=config.get('attention', {}))
    chunker = HeuristicChunker()

    # 1. Setup Graph: Add a known entity
    print("Setting up graph with entity 'B&B'...")
    gm.add_node("B&B", primary_label="Entity")
    # let's add an alias just in case
    gm.add_alias("B&B", "beb")

    # 2. Ingest Document
    print("\nIngesting document about 'B&B'...")
    text = "Il B&B di Giorgione è un B&B bellissimo. Questo B&B ha un tetto grande."
    chunks = chunker.chunk_text(text)
    
    gm.add_document("Test_Doc_B&B", chunks)
    print(f"Document ingested into {len(chunks)} chunks.")

    # 3. Verify relationships
    print("\nVerifying relationships from chunk...")
    chunk_name = "Test_Doc_B&B_chunk_0"
    neighbors = gm.get_neighbors(chunk_name)
    mentions_found = False
    for n in neighbors:
        if n['rel_type'] == 'MENTIONED_IN' and n['node']['name'] == 'B&B':
             mentions_found = True
             print("SUCCESS: Found MENTIONED_IN relationship to 'B&B'!")
    
    if not mentions_found:
        print("FAIL: No MENTIONED_IN relationship found.")

    # 4. Verify attention attenuation
    print("\nTesting Attention Attenuation...")
    # Reset activation
    gm.update_activation(chunk_name, 0.0)
    gm.update_activation("B&B", 0.0)
    
    # Stimulate B&B
    print("Stimulating 'B&B'...")
    am.propagate_activation("B&B", initial_boost=1.0)
    
    bb_node = gm.get_node("B&B")
    chunk_node = gm.get_node(chunk_name)
    
    print(f"'B&B' activation: {bb_node['activation_level']}")
    print(f"'{chunk_name}' activation: {chunk_node['activation_level']}")
    
    if chunk_node['activation_level'] < 0.2:
        print("SUCCESS: Chunk activation is severely attenuated! (Semantic Firewall working)")
    else:
        print("FAIL: Chunk activation is too high!")

if __name__ == "__main__":
    run_test()
