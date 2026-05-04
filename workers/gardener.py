import logging

logger = logging.getLogger(__name__)

class Gardener:
    """
    Background worker for graph hygiene.
    Each cycle: applies per-node decay (retroactive), then resurfaces dormant nodes.
    """

    def __init__(self, am, config: dict = None):
        self.am = am
        self.config = config or {}
        self.interval = self.config.get("gardener", {}).get("interval_seconds", 3600)

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
        logger.info("Gardener cycle complete.")
