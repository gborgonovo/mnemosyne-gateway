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

    def integrate_entities(self, entities: list[dict], obs_name: str, scope: str = "Public", relationships: list[dict] = None):
        """
        Integrates external entities into the graph.
        """
        touched_node_names = []
        node_map = {}
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

        if relationships:
            for rel in relationships:
                source_req = rel.get('source')
                target_req = rel.get('target')
                edge_type = rel.get('type')

                if not source_req or not target_req or not edge_type:
                    continue

                source_key = source_req.lower()
                target_key = target_req.lower()

                # Anti-hallucination: create on the fly if not extracted in entities list
                if source_key not in node_map:
                    node_data = self.gm.add_node(source_req, primary_label="Topic", scope=scope)
                    touched_node_names.append(node_data['name'])
                    node_map[source_key] = node_data['name']

                if target_key not in node_map:
                    node_data = self.gm.add_node(target_req, primary_label="Topic", scope=scope)
                    touched_node_names.append(node_data['name'])
                    node_map[target_key] = node_data['name']

                actual_source = node_map[source_key]
                actual_target = node_map[target_key]
                self.gm.add_edge(actual_source, actual_target, edge_type)
        else:
            # Heuristic: Connect consecutive entities only if explicit relationships were not provided
            if len(touched_node_names) > 1:
                for i in range(len(touched_node_names)):
                    for j in range(i + 1, len(touched_node_names)):
                        self.gm.add_edge(
                            touched_node_names[i], 
                            touched_node_names[j], 
                            "LINKED_TO"
                        )
        return touched_node_names
