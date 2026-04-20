import logging

logger = logging.getLogger(__name__)

class AttentionModel:
    """
    Implements the physics of the Attention Mechanism.
    Handles Decay and Propagation logic strictly on KuzuDB.
    """

    def __init__(self, kuzu_manager, config: dict, event_bus=None):
        self.kuzu_mgr = kuzu_manager
        self.eb = event_bus
        self.decay_rate = config.get("decay_rate", 0.05)
        self.dampening = config.get("propagation_dampening", {"forward": 1.0, "backward": 0.5})
        self.peak_threshold = config.get("peak_threshold", 0.7)

    def apply_decay(self):
        """
        Reduces activation of all nodes in KuzuDB through a global batch operation.
        """
        logger.info(f"Applying global temporal decay (factor = {1 - self.decay_rate:.2f})...")
        self.kuzu_mgr.batch_decay(1 - self.decay_rate)
        
    def propagate_activation(self, source_node_name: str, initial_boost: float = 0.0):
        """
        Boosts a node and propagates energy to neighbors based on topology.
        """
        node = self.kuzu_mgr.get_node(source_node_name)
        if not node:
            return
            
        current_val = node.get('activation_level', 0.0)
        new_val = min(current_val + initial_boost, 1.0)
        self.kuzu_mgr.update_activation(source_node_name, new_val)

        neighbors = self.kuzu_mgr.get_neighbors(source_node_name)
        
        for neighbor in neighbors:
            n_name = neighbor['node_name']
            weight = neighbor['weight'] if neighbor['weight'] else 0.5
            
            # Simple global Dampening applied
            transfer_amount = new_val * weight * self.dampening.get('forward', 0.5) * 0.5
            
            n_node = self.kuzu_mgr.get_node(n_name)
            if not n_node: continue
            
            n_current_val = n_node.get('activation_level', 0.0)
            n_new_val = min(n_current_val + transfer_amount, 1.0)
            
            if n_new_val > n_current_val:
                self.kuzu_mgr.update_activation(n_name, n_new_val)
                logger.debug(f"Propagated {transfer_amount:.2f} to {n_name}")
                
                if n_new_val >= self.peak_threshold and self.eb:
                    self.eb.publish("NODE_ENERGIZED", {"name": n_name, "level": n_new_val})

    def stimulate(self, node_names: list[str], boost_amount: float = 0.3):
        for name in node_names:
            self.propagate_activation(name, initial_boost=boost_amount)
