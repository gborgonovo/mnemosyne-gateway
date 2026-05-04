import logging
import random

logger = logging.getLogger(__name__)

class InitiativeEngine:
    """
    Decides when and how to proactively surface forgotten connections.
    Finds hot nodes whose neighbors have gone cold, filtered by scope.
    """

    def __init__(self, kuzu_manager, config: dict = None):
        self.kuzu_mgr = kuzu_manager
        config = config or {}
        init_config = config.get("initiative", {})
        self.threshold = init_config.get("initiative_threshold", 0.5)
        self.explanation_threshold = init_config.get("explanation_threshold", 0.4)

    def get_proactive_context(self, scopes: list = None) -> str:
        active_nodes = self.kuzu_mgr.get_active_nodes(threshold=self.threshold, scopes=scopes)
        suggestions = []

        for node in active_nodes:
            name = node['name']
            if name.startswith("Obs_"):
                continue
            neighbors = self.kuzu_mgr.get_neighbors(name)
            for neighbor in neighbors:
                n_name = neighbor['node_name']
                if n_name.startswith("Obs_"):
                    continue
                n_node = self.kuzu_mgr.get_node(n_name)
                if not n_node:
                    continue
                n_val = n_node.get('activation_level', 0.0)
                if n_val < self.explanation_threshold:
                    rel_type = neighbor['rel_type']
                    suggestions.append(
                        f"- L'argomento caldo '{name}' è collegato a '{n_name}' via [{rel_type}], attualmente inattivo."
                    )

        if not suggestions:
            return ""
        return "Insight Proattivi (idee dormienti ma rilevanti):\n" + "\n".join(suggestions[:3])

    def generate_initiatives(self, scopes: list = None) -> list:
        initiatives = []
        active_nodes = self.kuzu_mgr.get_active_nodes(threshold=self.threshold, scopes=scopes)
        seen_targets = set()

        for node in active_nodes:
            name = node['name']
            if name.startswith("Obs_"):
                continue
            neighbors = self.kuzu_mgr.get_neighbors(name)
            for neighbor in neighbors:
                n_name = neighbor['node_name']
                if n_name in seen_targets or n_name.startswith("Obs_"):
                    continue
                n_node = self.kuzu_mgr.get_node(n_name)
                if not n_node:
                    continue
                if n_node.get('activation_level', 0.0) < self.explanation_threshold:
                    phrases = [
                        f"Dato che stiamo considerando **{name}**, mi viene in mente **{n_name}**.",
                        f"Mentre riflettiamo su **{name}**, potremmo considerare i collegamenti con **{n_name}**.",
                        f"Curioso come **{name}** richiami alla memoria **{n_name}**, non trova?",
                    ]
                    initiatives.append({
                        "source": name,
                        "target": n_name,
                        "message": random.choice(phrases),
                        "reason": f"'{name}' è caldo ma '{n_name}' è inattivo.",
                    })
                    seen_targets.add(n_name)
                    if len(initiatives) >= 3:
                        return initiatives

        return initiatives
