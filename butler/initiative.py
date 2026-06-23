import logging

from core.utils import readable_name

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
            if name.startswith("obs_"):
                continue
            neighbors = self.kuzu_mgr.get_neighbors(name, scopes=scopes)
            for neighbor in neighbors:
                n_name = neighbor['node_name']
                if n_name.startswith("obs_"):
                    continue
                n_node = self.kuzu_mgr.get_node(n_name)
                if not n_node:
                    continue
                n_val = n_node.get('activation_level', 0.0)
                if n_val < self.explanation_threshold:
                    rel_type = neighbor['rel_type']
                    suggestions.append(
                        f"- Hot topic '{name}' is linked to '{n_name}' via [{rel_type}], currently inactive."
                    )

        if not suggestions:
            return ""
        return "Proactive Insights (dormant but relevant ideas):\n" + "\n".join(suggestions[:3])

    def generate_initiatives(self, scopes: list = None) -> list:
        initiatives = []
        active_nodes = self.kuzu_mgr.get_active_nodes(threshold=self.threshold, scopes=scopes)
        seen_targets = set()

        for node in active_nodes:
            name = node['name']
            if name.startswith("obs_"):
                continue
            neighbors = self.kuzu_mgr.get_neighbors(name, scopes=scopes)
            for neighbor in neighbors:
                n_name = neighbor['node_name']
                if n_name in seen_targets or n_name.startswith("obs_"):
                    continue
                n_node = self.kuzu_mgr.get_node(n_name)
                if not n_node:
                    continue
                if n_node.get('activation_level', 0.0) < self.explanation_threshold:
                    src = readable_name(node)
                    tgt = readable_name(n_node)
                    # Readable, Italian fields: Alfred verbalizes these into the
                    # briefing. No node_id slugs, no pre-baked English sentences.
                    initiatives.append({
                        "source": src,
                        "target": tgt,
                        "message": (
                            f"{src} è in primo piano in questo periodo, mentre un tema "
                            f"collegato, {tgt}, è rimasto in disparte: potrebbe valere la "
                            f"pena ricollegarli."
                        ),
                        "reason": f"{src} è attivo, {tgt} è inattivo.",
                    })
                    seen_targets.add(n_name)
                    if len(initiatives) >= 3:
                        return initiatives

        return initiatives
