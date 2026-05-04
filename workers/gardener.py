import logging

logger = logging.getLogger(__name__)

class Gardener:
    """
    Background worker for graph hygiene. Each cycle:
    1. Applies per-node decay (retroactive for downtime)
    2. Resurfaces dormant nodes with a small boost
    3. Discovers semantic relationships between hot nodes and creates graph edges
    """

    def __init__(self, am, config: dict = None, vector_store=None):
        self.am = am
        self.config = config or {}
        self.vector_store = vector_store
        self.interval = self.config.get("gardener", {}).get("interval_seconds", 3600)
        self.similarity_threshold = self.config.get("gardener", {}).get("similarity_threshold", 0.85)

    def run_once(self):
        logger.info("Gardener cycle starting...")
        try:
            self.am.apply_decay()
        except Exception as e:
            logger.error(f"Error during decay: {e}")
        try:
            self.am.resurface_dormant()
        except Exception as e:
            logger.error(f"Error during dormant resurfacing: {e}")
        try:
            self.build_semantic_edges()
        except Exception as e:
            logger.error(f"Error during semantic edge building: {e}")
        logger.info("Gardener cycle complete.")

    def build_semantic_edges(self):
        """
        For each hot node, query ChromaDB for semantically similar nodes above
        similarity_threshold, then create or update SEMANTICALLY_RELATED edges
        in KuzuDB with weight = similarity score.
        Only runs when a vector_store is available.
        """
        if not self.vector_store:
            return

        hot_threshold = self.config.get("attention", {}).get("activation_threshold", 0.5)
        hot_nodes = self.am.kuzu_mgr.get_active_nodes(threshold=hot_threshold)
        edges_created = 0

        for node in hot_nodes:
            name = node['name']
            if name.startswith('obs_'):
                continue

            similar = self.vector_store.find_similar_nodes(
                name,
                similarity_threshold=self.similarity_threshold,
                limit=5,
            )
            for sim in similar:
                self.am.kuzu_mgr.add_edge(name, sim['name'], 'SEMANTICALLY_RELATED', weight=sim['similarity'])
                edges_created += 1

        if edges_created:
            logger.info(f"Semantic edges: created/updated {edges_created} SEMANTICALLY_RELATED edges.")
