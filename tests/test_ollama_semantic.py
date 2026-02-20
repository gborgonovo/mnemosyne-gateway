
import yaml
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph_manager import GraphManager
from core.llm import get_llm_provider
from core.perception import PerceptionModule
from core.attention import AttentionModel

def test_semantic_context():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    print(f"Testing LLM Mode: {config['llm']['mode']} with model {config['llm']['model_name']}")

    gm = GraphManager(config['graph']['uri'], config['graph']['user'], config['graph']['password'])
    am = AttentionModel(gm, config=config.get('attention', {}))
    llm = get_llm_provider(config)
    pm = PerceptionModule(gm, llm, am)

    # Test Input
    user_input = "Cosa puoi dirmi del Prototipo Mnemosyne?"
    print(f"\nUser Input: {user_input}")

    # 1. Perception (Extraction)
    entities = pm.process_input(user_input)
    print(f"Extracted Entities: {entities}")

    # 2. Build Semantic Context (Mirrored from app.py)
    semantic_context = ""
    if entities:
        semantic_context = "=== USER'S PROJECT CONTEXT (from Mnemosyne Memory) ===\n"
        semantic_context += "CRITICAL: Use THIS data, not generic definitions.\n\n"
        
        for entity_name in entities:
            node = gm.get_node(entity_name)
            if node:
                semantic_context += f"📍 Entity: '{entity_name}'\n"
                # Simpler context for test
                semantic_context += f"   Properties: {dict(node)}\n"
            
            neighbors = gm.get_neighbors(entity_name)
            if neighbors:
                semantic_context += f"   Connected to: "
                semantic_context += ", ".join([f"{n['node']['name']}" for n in neighbors[:5]]) 
                semantic_context += "\n"
            
            # Observations
            with gm.driver.session() as session:
                obs_query = "MATCH (n)-[:MENTIONED_IN]->(o:Observation) WHERE toLower(n.name) = toLower($name) RETURN o.content as content LIMIT 3"
                results = session.run(obs_query, name=entity_name)
                observations = [record['content'] for record in results]
                if observations:
                    semantic_context += f"   📝 User said: {observations}\n"
            semantic_context += "\n"

    print("\nGenerated Semantic Context:")
    print("-" * 20)
    print(semantic_context)
    print("-" * 20)

    # 3. Generate Response
    print("\nGenerating The Butler's Response via Ollama...")
    response = llm.generate_response(user_input, semantic_context=semantic_context)
    
    print("\nThe Butler's Response:")
    print("=" * 20)
    print(response)
    print("=" * 20)

if __name__ == "__main__":
    test_semantic_context()
