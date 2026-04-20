import logging
import time
import os
import sys

logger = logging.getLogger(__name__)

class Gardener:
    """
    Background worker for Graph Hygiene and Thermal Sleep mechanism.
    Periodically triggers mathematical decay in KuzuDB for network heat reduction.
    """

    def __init__(self, am, config: dict = None):
        self.am = am
        self.config = config or {}
        self.interval = self.config.get("gardener", {}).get("interval_seconds", 3600)
        
    def run_once(self):
        """
        Executes one cycle of gardening (Sleep Phase).
        """
        logger.info("Gardener waking up...")
        
        # Apply strict topological decay via KuzuDB batch query
        try:
            self.apply_temporal_decay()
        except Exception as e:
            logger.error(f"Error during decay: {e}")
            
        logger.info("Gardener finished cycle. Going back to sleep.")

    def apply_temporal_decay(self):
        if self.am:
            logger.info("Gardener triggered 'Sleep' decay phase...")
            self.am.apply_decay()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Gardener script ready to be executed via Gateway main loop.")
