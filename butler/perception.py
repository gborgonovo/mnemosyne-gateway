import logging
import hashlib
from datetime import datetime
from core.graph_manager import GraphManager

logger = logging.getLogger(__name__)

class PerceptionModule:
    """
    Handles input processing and entity integration.
    """

    def __init__(self, graph_manager: GraphManager, event_bus=None, attention_model=None):
        self.gm = graph_manager
        self.eb = event_bus
        self.am = attention_model

    def create_observation(self, user_text: str, scope: str = "Public") -> str:
        """Creates an Observation node and returns its name."""
        obs_id = hashlib.md5(f"{user_text}{datetime.now()}".encode()).hexdigest()[:8]
        obs_name = f"Obs_{obs_id}"
        self.gm.add_node(obs_name, primary_label="Observation", scope=scope, properties={
            "content": user_text,
            "timestamp": datetime.now().isoformat()
        })
        return obs_name

    def request_enrichment(self, text: str, obs_name: str, scope: str = "Public"):
        """
        Publishes a request for semantic enrichment to the EventBus.
        """
        if not self.eb:
            logger.warning("PerceptionModule: No EventBus configured, enrichment request skipped.")
            return

        active_nodes = self.gm.get_active_nodes(threshold=0.2, scopes=[scope])
        active_names = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]
        
        self.eb.publish("REQ_ENRICHMENT", {
            "text": text,
            "obs_name": obs_name,
            "context_nodes": active_names,
            "scope": [scope]
        })
        logger.info(f"PERCEPTION: Enrichment requested for {obs_name} in scope {scope}")

    def integrate_entities(self, entities: list[dict], obs_name: str, relationships: list[dict] = None, scope: str = "Public"):
        """
        Integrates external entities and explicit relationships into the graph.
        """
        relationships = relationships or []
        touched_node_names = []
        node_map = {} # Keep track of created nodes for robust relationship linking
        
        for ent in entities:
            name = ent.get('name')
            if not name: continue
            ent_type = ent.get('type', 'Topic')
            
            # Create/Merge the node
            node_data = self.gm.add_node(name, primary_label=ent_type, scope=scope)
            touched_node_names.append(node_data['name'])
            node_map[name.lower()] = node_data['name']

        # Link entities to Observation
        for name in touched_node_names:
            self.gm.add_edge(name, obs_name, "MENTIONED_IN", weight=0.1)

        # Stimulate nodes if AttentionModel is available
        if self.am and touched_node_names:
            self.am.stimulate(touched_node_names, boost_amount=0.4)

        # Map Explicit Semantic Relationships
        connected_nodes = set()
        for rel in relationships:
            source = rel.get('source')
            target = rel.get('target')
            edge_type = rel.get('type')
            
            if not source or not target or not edge_type:
                continue
                
            # Safely resolve actual node names (handling slight case variations from LLM)
            actual_source = node_map.get(source.lower())
            actual_target = node_map.get(target.lower())
            
            # If the LLM hallucinated a relation for a node it didn't list in 'entities', safely create it
            if not actual_source:
                node_data = self.gm.add_node(source, primary_label="Topic", scope=scope)
                actual_source = node_data['name']
                self.gm.add_edge(actual_source, obs_name, "MENTIONED_IN", weight=0.1)
                
            if not actual_target:
                node_data = self.gm.add_node(target, primary_label="Topic", scope=scope)
                actual_target = node_data['name']
                self.gm.add_edge(actual_target, obs_name, "MENTIONED_IN", weight=0.1)
                
            # Format edge type (ensure uppercase, no spaces)
            safe_edge_type = edge_type.strip().upper().replace(" ", "_")
            
            self.gm.add_edge(actual_source, actual_target, safe_edge_type)
            connected_nodes.add(actual_source)
            connected_nodes.add(actual_target)
            
        # Fallback Heuristic: If we extracted multiple entities but NO relationships were generated,
        # we can still connect them generically just to avoid completely orphaned islands.
        if len(relationships) == 0 and len(touched_node_names) > 1:
            for i in range(len(touched_node_names)):
                for j in range(i + 1, len(touched_node_names)):
                    self.gm.add_edge(
                        touched_node_names[i], 
                        touched_node_names[j], 
                        "LINKED_TO"
                    )
                    
        return touched_node_names
