import logging
import random
from core.graph_manager import GraphManager

logger = logging.getLogger(__name__)

class InitiativeEngine:
    """
    Decides when and how to proactively interact with the user.
    Based on node activation levels and graph topology.
    """

    def __init__(self, graph_manager: GraphManager, config: dict = None):
        self.gm = graph_manager
        config = config or {}
        init_config = config.get("initiative", {})
        self.threshold = init_config.get("initiative_threshold", 0.7)
        self.explanation_threshold = init_config.get("explanation_threshold", 0.5)
        self.retrieval_config = config.get("retrieval", {})
        self.blacklist = {"interessante", "utile", "importante", "bene", "ciao", "ok"}

    def get_proactive_context(self, scopes: list[str] = None) -> str:
        """
        Returns a string summary of active nodes and their 'forgotten' neighbors
        to be used by the LLM for proactive responses.
        Filters out suggestions with negative feedback.
        """
        active_nodes = self.gm.get_active_nodes(threshold=self.threshold, scopes=scopes)
        suggestions = []
        
        for node in active_nodes:
            # Skip if source is an Observation
            if "Observation" in node.get('labels', []):
                continue
                
            name = node['name']
            neighbors = self.gm.get_neighbors(name, scopes=scopes)
            for neighbor in neighbors:
                n_node = neighbor['node']
                n_name = n_node['name']
                # Skip if active, Observation, or blacklisted
                if "Observation" in n_node.get('labels', []) or n_name.lower() in self.blacklist:
                    continue
                
                # Check feedback score
                rel_props = neighbor.get('rel_props', {})
                feedback = rel_props.get('feedback_score', 0)
                
                # Rule: If feedback is negative (< 0), The Butler should NOT mention it.
                if feedback < 0:
                    continue

                n_val = n_node.get('activation_level', 0.0)
                if n_val < self.explanation_threshold:
                    rel_type = neighbor['rel_type']
                    suggestion_str = f"- {name} is related to {n_name} via {rel_type}"
                    if feedback > 0:
                        suggestion_str += " (User found this relevant previously)"
                    suggestions.append(suggestion_str)
        
        if not suggestions:
            return ""
            
        limit = self.retrieval_config.get("initiative_limit", 3)
        return "Relevant but currently neglected topics in the user's mind:\n" + "\n".join(suggestions[:limit])

    def generate_initiatives(self, scopes: list[str] = None) -> list[dict]:
        """
        Scans active nodes and generates proactive suggestions for the sidebar.
        """
        initiatives = []
        active_nodes = self.gm.get_active_nodes(threshold=self.threshold, scopes=scopes)
        seen_targets = set()
        
        for node in active_nodes:
            # CRITICAL: Skip technical observation nodes as initiative sources
            if "Observation" in node.get('labels', []):
                continue
                
            name = node['name']
            neighbors = self.gm.get_neighbors(name, scopes=scopes)
            for neighbor in neighbors:
                n_node = neighbor['node']
                n_name = n_node['name']
                
                # Skip if already suggested, Observation, or blacklisted
                if n_name in seen_targets or "Observation" in n_node.get('labels', []) or n_name.lower() in self.blacklist:
                    continue
                    
                n_val = n_node.get('activation_level', 0.0)
                if n_val < self.explanation_threshold:
                    # Check feedback score
                    rel_props = neighbor.get('rel_props', {})
                    feedback = rel_props.get('feedback_score', 0)
                    
                    if feedback < 0:
                        continue
                        
                    phrases = [
                        f"Dato che stiamo parlando di **{name}**, mi viene in mente **{n_name}**.",
                        f"A proposito di **{name}**, non dimentichiamo **{n_name}**.",
                        f"Mentre riflettiamo su **{name}**, potremmo considerare anche **{n_name}**.",
                        f"Il tema di **{name}** mi riporta alla mente **{n_name}**.",
                        f"Curioso come **{name}** sia collegato a **{n_name}**, non trova?"
                    ]
                    message = random.choice(phrases)
                    initiatives.append({
                        "source": name,
                        "target": n_name,
                        "message": message,
                        "reason": f"Node '{name}' is active, but '{n_name}' is dormant."
                    })
                    seen_targets.add(n_name)
                    
                    if len(initiatives) >= self.retrieval_config.get("initiative_limit", 3): # Limit sidebar noise
                        return initiatives
        
        # New: Strategic Planning - Goal Decomposition
        for node in active_nodes:
            if "Goal" in node.get('labels', []):
                name = node['name']
                neighbors = self.gm.get_neighbors(name)
                # Check if there are any Tasks linked to this Goal
                tasks = [n for n in neighbors if "Task" in n['node'].get('labels', [])]
                
                if not tasks:
                    initiatives.append({
                        "source": name,
                        "target": "Deconstruction",
                        "message": f"Il tuo obiettivo **{name}** sembra complesso. Vuoi che proviamo a scomporlo in passi azionabili?",
                        "reason": f"Goal '{name}' is active but has no linked Tasks."
                    })
                    if len(initiatives) >= self.retrieval_config.get("initiative_limit", 3):
                        return initiatives

        return initiatives
