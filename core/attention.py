import logging

logger = logging.getLogger(__name__)

class AttentionModel:
    """
    Activation physics for Mnemosyne.
    Handles usage-based decay (per type, retroactive), interaction boosts
    (file edit > MCP query > proximity), and dormant node resurfacing.
    """

    def __init__(self, kuzu_manager, config: dict, event_bus=None):
        self.kuzu_mgr = kuzu_manager
        self.eb = event_bus

        self.decay_rates = config.get("decay_rates", {
            "Node":        0.0025,
            "Goal":        0.00026,
            "Task":        0.00045,
            "Observation": 0.004,
        })
        self.boost_weights = config.get("boost_weights", {
            "file_edit": 0.6,
            "mcp_query": 0.2,
            "proximity": 0.05,
        })
        self.dampening = config.get("propagation_dampening", {"forward": 1.0, "backward": 0.5})
        self.peak_threshold = config.get("peak_threshold", 0.7)

        dormant_cfg = config.get("dormant", {})
        self.dormant_resurface_boost = dormant_cfg.get("resurface_boost", 0.05)
        self.dormant_ceiling = dormant_cfg.get("ceiling", 0.25)
        self.dormant_days_node = dormant_cfg.get("days_node", 27)
        self.dormant_days_goal_task = dormant_cfg.get("days_goal_task", 30)
        self.dormant_min_interactions = dormant_cfg.get("min_interactions", 5)

    # ─── Decay ────────────────────────────────────────────────────────────────

    def apply_decay(self):
        """
        Apply type-specific decay proportional to real elapsed time.
        Retroactively correct for any downtime using last_decay_applied timestamp.
        """
        logger.info("Applying per-node temporal decay...")
        self.kuzu_mgr.apply_decay_per_node(self.decay_rates)

    # ─── Interaction recording ─────────────────────────────────────────────────

    def record_interaction(self, node_name: str, interaction_type: str = "mcp_query"):
        """
        Record a direct interaction with a node and propagate proximity boost to neighbors.
        interaction_type: 'file_edit' | 'mcp_query' | 'proximity'
        """
        boost = self.boost_weights.get(interaction_type, self.boost_weights["mcp_query"])
        update_ts = interaction_type != "proximity"

        self.kuzu_mgr.update_interaction(node_name, boost, update_timestamp=update_ts)
        logger.debug(f"Interaction '{interaction_type}' on '{node_name}' (boost={boost:.2f})")

        node = self.kuzu_mgr.get_node(node_name)
        if node and node.get("activation_level", 0) >= self.peak_threshold and self.eb:
            self.eb.publish("NODE_ENERGIZED", {"name": node_name, "level": node["activation_level"]})

        if interaction_type != "proximity":
            self._propagate_proximity(node_name)

    def _propagate_proximity(self, source_node_name: str):
        """Apply a small proximity boost to direct neighbors of an interacted node."""
        neighbors = self.kuzu_mgr.get_neighbors(source_node_name)
        base_boost = self.boost_weights.get("proximity", 0.05)
        for neighbor in neighbors:
            n_name = neighbor["node_name"]
            weight = neighbor["weight"] if neighbor["weight"] else 0.5
            adjusted = base_boost * weight
            if adjusted > 0.005:
                self.kuzu_mgr.update_interaction(n_name, adjusted, update_timestamp=False)
                logger.debug(f"Proximity boost {adjusted:.3f} → '{n_name}'")

    def stimulate(self, node_names: list, boost_amount: float = None,
                  interaction_type: str = "mcp_query"):
        """
        Convenience wrapper to record interactions on a list of nodes.
        boost_amount is ignored — weights come from config.
        """
        for name in node_names:
            self.record_interaction(name, interaction_type=interaction_type)

    # ─── Dormant resurfacing ───────────────────────────────────────────────────

    def resurface_dormant(self, scopes: list = None):
        """
        Apply a small boost to dormant nodes so they surface in the briefing.
        Capped at dormant_ceiling to avoid competing with genuinely active nodes.
        """
        dormant_nodes = self.kuzu_mgr.get_dormant_nodes(
            scopes=scopes,
            min_interactions=self.dormant_min_interactions,
            days_node=self.dormant_days_node,
            days_goal_task=self.dormant_days_goal_task,
        )
        for node in dormant_nodes:
            current = node["activation"]
            if current < self.dormant_ceiling:
                boost = min(self.dormant_resurface_boost, self.dormant_ceiling - current)
                self.kuzu_mgr.update_interaction(node["name"], boost, update_timestamp=False)
                logger.debug(f"Resurfaced dormant node '{node['name']}' (+{boost:.3f})")

        if dormant_nodes:
            logger.info(f"Resurfaced {len(dormant_nodes)} dormant nodes.")
