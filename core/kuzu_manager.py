import kuzu
import logging
import os
import time
from core.utils import normalize_node_name

logger = logging.getLogger(__name__)

class KuzuManager:
    """
    Manages the topological graph and thermal state (activation) of Mnemosyne.
    Schema: Nodes carry normalized name as PK, display name, activation heat,
    node type, scope, interaction timestamps, and interaction count.
    """
    def __init__(self, db_path="./data/kuzu_main"):
        self.db_path = os.path.abspath(db_path)
        parent_dir = os.path.dirname(self.db_path)
        os.makedirs(parent_dir, exist_ok=True)

        logger.info(f"Inizializzazione KuzuDatabase su: {self.db_path}")
        try:
            self.db = kuzu.Database(self.db_path)
            self.conn = kuzu.Connection(self.db)
            self._init_schema()
        except Exception as e:
            logger.error(f"Errore critico durante l'apertura di Kùzu: {e}")
            raise

    def _init_schema(self):
        try:
            self.conn.execute("""
                CREATE NODE TABLE Node(
                    name STRING,
                    display_name STRING,
                    activation DOUBLE,
                    node_type STRING,
                    scope STRING,
                    last_interaction DOUBLE,
                    last_decay_applied DOUBLE,
                    interaction_count INT64,
                    PRIMARY KEY (name)
                )
            """)
            logger.info("Created Node table with full schema")
        except RuntimeError:
            self._migrate_schema()

        try:
            self.conn.execute("CREATE REL TABLE RELATES(FROM Node TO Node, type STRING, weight DOUBLE)")
            logger.info("Created RELATES rel table")
        except RuntimeError:
            pass

    def _migrate_schema(self):
        """Add new columns to existing Node table for schema upgrades."""
        now = time.time()
        migrations = [
            ("node_type",          "STRING", f"'Node'"),
            ("scope",              "STRING", f"'Public'"),
            ("last_interaction",   "DOUBLE", str(now)),
            ("last_decay_applied", "DOUBLE", str(now)),
            ("interaction_count",  "INT64",  "0"),
        ]
        for col_name, col_type, default_val in migrations:
            try:
                self.conn.execute(f"ALTER TABLE Node ADD {col_name} {col_type}")
                self.conn.execute(
                    f"MATCH (n:Node) WHERE n.{col_name} IS NULL SET n.{col_name} = {default_val}"
                )
                logger.info(f"Schema migration: added column '{col_name}'")
            except RuntimeError:
                pass

    def close(self):
        pass

    # ─── Node CRUD ────────────────────────────────────────────────────────────

    def add_node(self, name: str, initial_activation: float = 0.5,
                 node_type: str = "Node", scope: str = "Public"):
        norm_name = normalize_node_name(name)
        now = time.time()
        query = """
        MERGE (a:Node {name: $name})
        ON CREATE SET
            a.display_name = $display,
            a.activation = $act,
            a.node_type = $node_type,
            a.scope = $scope,
            a.last_interaction = $now,
            a.last_decay_applied = $now,
            a.interaction_count = $zero
        """
        self.conn.execute(query, parameters={
            "name": norm_name, "display": name,
            "act": initial_activation, "node_type": node_type,
            "scope": scope, "now": now, "zero": 0,
        })

    def get_node(self, name: str) -> dict:
        norm_name = normalize_node_name(name)
        query = """
        MATCH (n:Node {name: $name})
        RETURN n.name, n.display_name, n.activation, n.node_type, n.scope,
               n.last_interaction, n.interaction_count
        """
        res = self.conn.execute(query, parameters={"name": norm_name})
        if res.has_next():
            row = res.get_next()
            return {
                "name": row[0],
                "display_name": row[1],
                "activation_level": row[2],
                "node_type": row[3],
                "scope": row[4],
                "last_interaction": row[5],
                "interaction_count": row[6],
            }
        return None

    def update_node_metadata(self, name: str, node_type: str = None, scope: str = None):
        norm_name = normalize_node_name(name)
        updates, params = [], {"name": norm_name}
        if node_type:
            updates.append("n.node_type = $node_type")
            params["node_type"] = node_type
        if scope:
            updates.append("n.scope = $scope")
            params["scope"] = scope
        if updates:
            self.conn.execute(
                f"MATCH (n:Node {{name: $name}}) SET {', '.join(updates)}",
                parameters=params,
            )

    def update_activation(self, name: str, level: float):
        query = "MATCH (n:Node {name: $name}) SET n.activation = $level"
        self.conn.execute(query, parameters={"name": name, "level": level})

    def update_interaction(self, name: str, boost: float, update_timestamp: bool = True):
        """Apply activation boost. If update_timestamp, record this as a direct interaction."""
        norm_name = normalize_node_name(name)
        node = self.get_node(norm_name)
        if not node:
            return
        new_activation = min((node.get("activation_level") or 0.0) + boost, 1.0)
        now = time.time()
        if update_timestamp:
            query = """
            MATCH (n:Node {name: $name})
            SET n.activation = $act,
                n.last_interaction = $now,
                n.interaction_count = COALESCE(n.interaction_count, 0) + 1
            """
            self.conn.execute(query, parameters={"name": norm_name, "act": new_activation, "now": now})
        else:
            self.conn.execute(
                "MATCH (n:Node {name: $name}) SET n.activation = $act",
                parameters={"name": norm_name, "act": new_activation},
            )

    def delete_node(self, name: str):
        norm_name = normalize_node_name(name)
        try:
            self.conn.execute("MATCH (n:Node {name: $name})-[r]-() DELETE r", parameters={"name": norm_name})
            self.conn.execute("MATCH (n:Node {name: $name}) DELETE n", parameters={"name": norm_name})
            return True
        except Exception as e:
            logger.error(f"Failed to delete {norm_name}: {e}")
            return False

    # ─── Edges ────────────────────────────────────────────────────────────────

    def add_edge(self, source_name: str, target_name: str, relation_type: str, weight: float = 1.0):
        self.add_node(source_name)
        self.add_node(target_name)
        query = """
        MATCH (a:Node {name: $source}), (b:Node {name: $target})
        MERGE (a)-[r:RELATES {type: $rel_type}]->(b)
        ON MATCH SET r.weight = $weight
        ON CREATE SET r.weight = $weight
        """
        self.conn.execute(query, parameters={
            "source": normalize_node_name(source_name),
            "target": normalize_node_name(target_name),
            "rel_type": relation_type,
            "weight": weight,
        })

    def get_neighbors(self, name: str):
        norm_name = normalize_node_name(name)
        query = """
        MATCH (n:Node {name: $name})-[r:RELATES]-(m:Node)
        RETURN m.name, r.type, r.weight
        """
        res = self.conn.execute(query, parameters={"name": norm_name})
        neighbors = []
        while res.has_next():
            row = res.get_next()
            neighbors.append({"node_name": row[0], "rel_type": row[1], "weight": row[2]})
        return neighbors

    # ─── Queries ──────────────────────────────────────────────────────────────

    def get_active_nodes(self, threshold: float = 0.5, scopes: list = None):
        query = """
        MATCH (n:Node)
        WHERE n.activation > $threshold
        RETURN n.name, n.activation, n.node_type, n.scope
        """
        res = self.conn.execute(query, parameters={"threshold": threshold})
        active = []
        while res.has_next():
            row = res.get_next()
            name, activation, node_type, scope = row[0], row[1], row[2], row[3]
            if scopes and "*" not in scopes and scope not in scopes:
                continue
            active.append({
                "name": name,
                "activation_level": activation,
                "node_type": node_type,
                "scope": scope,
            })
        return active

    def get_all_nodes(self):
        res = self.conn.execute("MATCH (n:Node) RETURN n.name, n.activation")
        nodes = []
        while res.has_next():
            row = res.get_next()
            nodes.append({"name": row[0], "activation_level": row[1]})
        return nodes

    def get_dormant_nodes(self, scopes: list = None, min_interactions: int = 5,
                          days_node: int = 27, days_goal_task: int = 30) -> list:
        """
        Returns nodes that were historically active but have gone quiet.
        - Node type: activation-based (< 0.2) after days_node of inactivity
        - Goal/Task: time-based (> days_goal_task since last interaction)
        """
        activation_threshold = 0.2

        query = """
        MATCH (n:Node)
        WHERE NOT n.name STARTS WITH 'Obs_'
        AND n.node_type IN ['Goal', 'Task', 'Node']
        AND COALESCE(n.interaction_count, 0) >= $min_interactions
        RETURN n.name, n.activation, n.node_type, n.scope, n.last_interaction, n.interaction_count
        """
        res = self.conn.execute(query, parameters={"min_interactions": min_interactions})

        now = time.time()
        dormant = []
        while res.has_next():
            row = res.get_next()
            name, activation, node_type, scope, last_interaction, count = (
                row[0], row[1], row[2], row[3], row[4] or 0, row[5] or 0
            )
            time_inactive = now - last_interaction
            days_inactive = time_inactive / 86400

            is_dormant = False
            if node_type == "Node" and activation < activation_threshold and days_inactive > days_node:
                is_dormant = True
            elif node_type in ("Goal", "Task") and days_inactive > days_goal_task:
                is_dormant = True

            if not is_dormant:
                continue
            if scopes and "*" not in scopes and scope not in scopes:
                continue

            dormant.append({
                "name": name,
                "activation": activation,
                "node_type": node_type,
                "scope": scope,
                "days_inactive": int(days_inactive),
                "interaction_count": count,
            })
        return dormant

    def get_graph_export(self, limit: int = 5000):
        res_nodes = self.conn.execute(
            "MATCH (n:Node) RETURN n.name, n.activation LIMIT $limit",
            parameters={"limit": limit},
        )
        nodes = []
        while res_nodes.has_next():
            row = res_nodes.get_next()
            nodes.append({"id": row[0], "name": row[0], "activation": row[1]})

        res_edges = self.conn.execute(
            "MATCH (a:Node)-[r:RELATES]->(b:Node) RETURN a.name, b.name, r.type LIMIT $limit",
            parameters={"limit": limit},
        )
        edges = []
        while res_edges.has_next():
            row = res_edges.get_next()
            edges.append({"source": row[0], "target": row[1], "type": row[2]})

        return {"nodes": nodes, "relationships": edges}

    # ─── Decay ────────────────────────────────────────────────────────────────

    def apply_decay_per_node(self, decay_rates: dict):
        """
        Apply type-specific decay proportional to real time elapsed since last decay.
        Retroactively handles downtime: uses last_decay_applied as the reference point.
        """
        query = """
        MATCH (n:Node)
        RETURN n.name, n.activation, n.node_type, n.last_decay_applied
        """
        res = self.conn.execute(query)
        rows = []
        while res.has_next():
            row = res.get_next()
            rows.append((row[0], row[1], row[2], row[3]))

        now = time.time()
        default_rate = decay_rates.get("Node", 0.0025)

        for name, activation, node_type, last_decay in rows:
            rate = decay_rates.get(node_type or "Node", default_rate)
            last_decay = last_decay or now
            hours_elapsed = (now - last_decay) / 3600
            factor = (1 - rate) ** hours_elapsed
            new_activation = max((activation or 0.0) * factor, 0.0)
            self.conn.execute(
                "MATCH (n:Node {name: $name}) SET n.activation = $act, n.last_decay_applied = $now",
                parameters={"name": name, "act": new_activation, "now": now},
            )

    def batch_decay(self, decay_factor: float = 0.95):
        """Legacy uniform decay. Prefer apply_decay_per_node for new code."""
        self.conn.execute(
            "MATCH (n:Node) SET n.activation = n.activation * $factor",
            parameters={"factor": decay_factor},
        )
