import logging
import hashlib
from datetime import datetime
from core.graph_manager import GraphManager
from core.llm import LLMProvider

logger = logging.getLogger(__name__)

class PerceptionModule:
    """
    Handles input processing and entity integration.
    """

    def __init__(self, graph_manager: GraphManager, llm: LLMProvider, attention_model=None):
        self.gm = graph_manager
        self.llm = llm
        self.am = attention_model

    def process_input(self, user_text: str) -> list[str]:
        logger.info(f"PERCEPTION: Processing input text: {user_text}")
        
        # 1. Create Observation Node (Context) - ALWAYS DO THIS FIRST
        # Even if extraction fails, we want the text in our history.
        obs_id = hashlib.md5(f"{user_text}{datetime.now()}".encode()).hexdigest()[:8]
        obs_name = f"Obs_{obs_id}"
        self.gm.add_node(obs_name, primary_label="Observation", properties={
            "content": user_text,
            "timestamp": datetime.now().isoformat()
        })
        
        touched_node_names = []

        # 2. Extract entities using LLM (with context for semantic resolution)
        try:
            active_nodes = self.gm.get_active_nodes(threshold=0.2)
            active_names = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]

            
            entities = self.llm.extract_entities(user_text, context_nodes=active_names)
            
            # 3. Ingest into Graph
            for ent in entities:
                name = ent.get('name')
                if not name: continue
                
                ent_type = ent.get('type', 'Topic')
                
                # Create/Merge the node
                node_data = self.gm.add_node(name, primary_label=ent_type)
                touched_node_names.append(node_data['name'])

            # 4. Link entities to Observation
            for name in touched_node_names:
                self.gm.add_edge(name, obs_name, "MENTIONED_IN", weight=0.1)

            # 5. Stimulate nodes if AttentionModel is available
            if self.am and touched_node_names:
                self.am.stimulate(touched_node_names, boost_amount=0.4)

            # 6. Heuristic: Connect consecutive entities
            if len(touched_node_names) > 1:
                for i in range(len(touched_node_names)):
                    for j in range(i + 1, len(touched_node_names)):
                        self.gm.add_edge(
                            touched_node_names[i], 
                            touched_node_names[j], 
                            "LINKED_TO"
                        )
        except Exception as e:
            logger.error(f"PERCEPTION: LLM extraction failed: {e}")
            # We don't raise here, we just return empty so the chat continues
        
        return touched_node_names
