import logging
from core.graph_manager import GraphManager

logger = logging.getLogger(__name__)

class AttentionModel:
    """
    Implements the physics of the Attention Mechanism.
    Handles Decay and Propagation logic.
    """

    def __init__(self, graph_manager: GraphManager, config: dict, event_bus=None):
        self.gm = graph_manager
        self.eb = event_bus
        self.decay_rate = config.get("decay_rate", 0.05)
        self.dampening = config.get("propagation_dampening", {"forward": 1.0, "backward": 0.5})
        self.activation_threshold = config.get("activation_threshold", 0.1)
        self.peak_threshold = config.get("peak_threshold", 0.7)
        self.intentionality_config = config.get("intentionality", {})

    def propagate_activation(self, source_node_name: str, initial_boost: float = 0.0):
        """
        Boosts a node and propagates energy to neighbors.
        """
        # 1. Boost the source
        current_node = self.gm.get_node(source_node_name)
        if not current_node:
            logger.warning(f"Cannot propagate from unknown node: {source_node_name}")
            return
        
        current_val = current_node.get('activation_level', 0.0)
        new_val = min(current_val + initial_boost, 1.0) # Cap at 1.0
        self.gm.update_activation(source_node_name, new_val)

        # 2. Propagate to neighbors
        neighbors = self.gm.get_neighbors(source_node_name)
        
        for neighbor in neighbors:
            n_node = neighbor['node']
            n_name = n_node['name']
            weight = neighbor['weight'] if neighbor['weight'] else 0.5
            direction = neighbor['direction'] # 'out' or 'in'

            # Determine Propagation Factor based on direction
            if direction == 'out':
                factor = self.dampening.get('forward', 1.0)
            else:
                factor = self.dampening.get('backward', 0.5)

            # Apply attenuation for explicit chunk linking
            if neighbor.get('rel_type') == 'MENTIONED_IN' and direction == 'in':
                factor *= 0.1 # Severe penalty to prevent document chunks from flaring up unconditionally

            # Formula: Transfer = SourceActivation * RelWeight * DirectionFactor
            # We don't want cascading infinite loops in this MVP, so we only do 1-hop propagation 
            # or simply boost neighbors based on the Source's *boost*, not total level (to be safer).
            # Let's use Source's current level for a "continuous flow" model.
            
            transfer_amount = new_val * weight * factor * 0.5 # 0.5 is a global dampener to prevent explosion
            
            n_current_val = n_node.get('activation_level', 0.0)
            n_new_val = min(n_current_val + transfer_amount, 1.0)
            
            if n_new_val > n_current_val: # Only update if it increases
                self.gm.update_activation(n_name, n_new_val)
                logger.debug(f"Propagated {transfer_amount:.2f} from {source_node_name} to {n_name} ({direction})")
                
                # Peak Detection
                if n_new_val >= self.peak_threshold and self.eb:
                    self.eb.publish("NODE_ENERGIZED", {"name": n_name, "level": n_new_val})

    def apply_decay(self):
        """
        Reduces activation of all nodes in the graph unless marked as persistent.
        Implements differential decay for Intentionality (Goals/Tasks).
        Should be called periodically (e.g., hourly).
        """
        all_nodes = self.gm.get_all_nodes()
        count = 0
        for node in all_nodes:
            name = node['name']
            current_val = node['activation']
            props = node.get('props', {})
            labels = node.get('labels', [])
            
            # Skip decay for persistent nodes (Pedanteria)
            if props.get('persistence') == 'high':
                continue

            if current_val > 0.01: # Optimization: ignore dead nodes
                
                # Differential Decay Logic
                effective_decay_rate = self.decay_rate
                
                diff_decay_enabled = self.intentionality_config.get("enabled", True) and self.intentionality_config.get("differential_decay", True)
                
                if diff_decay_enabled:
                    if "Goal" in labels:
                        # Goals decay 50% slower than normal topics
                        effective_decay_rate *= 0.5
                    elif "Task" in labels:
                        status = props.get('status', 'todo')
                        if status == 'in_progress':
                            # Active tasks decay very slowly (20% of normal rate)
                            effective_decay_rate *= 0.2
                        elif status == 'done':
                            # Completed tasks decay 5x faster to clear the mind
                            effective_decay_rate *= 5.0
                    elif "Observation" in labels:
                        # Raw observations decay 2x faster than normal topics
                        effective_decay_rate *= 2.0
                        
                    # Cap the decay rate to 1.0 to avoid weird math
                    effective_decay_rate = min(effective_decay_rate, 1.0)
                
                # Exponential Decay: new_val = current_val * (1 - decay_rate)
                new_val = max(current_val * (1 - effective_decay_rate), 0.0)
                if abs(new_val - current_val) > 0.001:
                    self.gm.update_activation(name, new_val)
                    count += 1
        logger.info(f"Differential decay applied to {count} nodes.")

    def stimulate(self, node_names: list[str], boost_amount: float = 0.3):
        """
        External stimulation (e.g. from User Input).
        """
        for name in node_names:
            self.propagate_activation(name, initial_boost=boost_amount)
