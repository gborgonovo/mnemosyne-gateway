import sys
import os
import yaml
import asyncio
from typing import List

# Setup path
sys.path.append(os.getcwd())

from core.graph_manager import GraphManager
from butler.perception import PerceptionModule
from butler.llm import get_llm_provider

# Mocking the state for testing
class MockState:
    gm = None
    pm = None
    config = {}

async def test_context_generation(user_content: str):
    config_path = 'config/settings.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    gm = GraphManager(config['graph']['uri'], config['graph']['user'], config['graph']['password'])
    llm = get_llm_provider(config)
    pm = PerceptionModule(gm, llm)
    
    print(f"User Query: {user_content}")
    entities = pm.process_input(user_content)
    print(f"Extracted Entities: {entities}")
    
    context_fragments = []
    for entity in entities:
        if entity.startswith("Obs_"):
            continue
            
        node = gm.get_node(entity)
        if node and "Observation" in node.get('labels', []):
            continue

        if node:
            clean_labels = [l for l in node.get('labels', []) if l not in ["Node", "Entity", "Topic"]]
            label_str = f" [{', '.join(clean_labels)}]" if clean_labels else ""
            frag = f"--- INFO ABOUT: {entity}{label_str} ---\n"
            
            neighbors = gm.get_neighbors(entity)
            semantic_neighbors = [
                n['node']['name'] for n in neighbors 
                if "Observation" not in n['node'].get('labels', [])
                and not n['node']['name'].startswith("Obs_")
            ]
            if semantic_neighbors:
                frag += f"Related to: {', '.join(semantic_neighbors[:5])}\n"
            
            with gm.driver.session() as session:
                obs_query = """
                MATCH (n)-[:MENTIONED_IN]->(o:Observation)
                WHERE toLower(n.name) = toLower($name)
                RETURN o.content as content
                ORDER BY o.timestamp DESC LIMIT 3
                """
                results = session.run(obs_query, name=entity)
                observations = [record['content'] for record in results]
                
                valid_memory = [o for o in observations if o.strip().lower() != user_content.strip().lower()]

                if (not valid_memory or len(valid_memory) < 2) and semantic_neighbors:
                    for neighbor in semantic_neighbors[:3]:
                        neigh_results = session.run(obs_query, name=neighbor)
                        observations.extend([rec['content'] for rec in neigh_results])
                        
                valid_memory = [o for o in observations if o.strip().lower() != user_content.strip().lower()]
                
                if valid_memory:
                    frag += f"--- Relevant Personal Memories ---\n"
                    unique_obs = list(dict.fromkeys(valid_memory))
                    for o in unique_obs[:5]:
                        clean_obs = " ".join(o.split())
                        if "Obs_" in clean_obs: continue 
                        if len(clean_obs) > 600: clean_obs = clean_obs[:600] + "..."
                        frag += f"- \"{clean_obs}\"\n"

            context_fragments.append(frag)
    
    if context_fragments:
        raw_context = "\n".join(context_fragments)
        cleaned_context = "\n".join([line for line in raw_context.split("\n") if "Obs_" not in line])
        print("\n=== FINAL CONTEXT INJECTED ===\n")
        print(cleaned_context)
        print("\n==============================\n")
    else:
        print("\nNO CONTEXT GENERATED\n")

    gm.close()

if __name__ == "__main__":
    asyncio.run(test_context_generation("Cosa sai del progetto B&B?"))
