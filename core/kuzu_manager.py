import kuzu
import logging
import os
import threading
import time
from functools import wraps
from core.utils import normalize_node_name

logger = logging.getLogger(__name__)


def _synchronized(method):
    """Serialize a KuzuManager method behind the instance's reentrant lock.

    A single kuzu.Connection is shared by the FastAPI threadpool, the watchdog
    thread, the enrichment thread and the gardener; KuzuDB does not guarantee a
    single Connection is thread-safe, and multi-statement methods (e.g.
    delete_node) must run atomically. The lock is an RLock so methods that call
    other locked methods (add_edge -> add_node, update_interaction -> get_node)
    do not deadlock.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class KuzuManager:
    """
    Manages the topological graph and thermal state (activation) of Mnemosyne.
    Schema: Nodes carry normalized name as PK, display name, activation heat,
    node type, scope, interaction timestamps, and interaction count.
    """
    # With buffer_pool_size=0 (KuzuDB default) Kuzu reserves ~80% of system RAM
    # as buffer pool — on an 8 GB host that is ~6.4 GB resident for a few MB of
    # actual graph, which caused the OOM incident. We cap it instead.
    #
    # NB: the cap is a CEILING, not a fixed allocation, but it must be large
    # enough for KuzuDB to open and checkpoint the DB at startup: 512 MB proved
    # too low ("Buffer manager exception: buffer pool is full" on open). 2 GB
    # opens with margin, stays well under the default ~6.4 GB, and at steady
    # state only the small working set is actually resident. Override via
    # settings.yaml -> database.kuzu_buffer_pool_mb if needed.
    DEFAULT_BUFFER_POOL_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB

    def __init__(self, db_path="./data/kuzu_main", buffer_pool_size: int = None):
        self._lock = threading.RLock()
        self.db_path = os.path.abspath(db_path)
        parent_dir = os.path.dirname(self.db_path)
        os.makedirs(parent_dir, exist_ok=True)

        self._buffer_pool_size = buffer_pool_size or self.DEFAULT_BUFFER_POOL_BYTES

        logger.info(
            f"Initializing KuzuDatabase at: {self.db_path} "
            f"(buffer_pool_size={self._buffer_pool_size // (1024*1024)} MB)"
        )
        try:
            self.db = kuzu.Database(self.db_path, buffer_pool_size=self._buffer_pool_size)
            self.conn = kuzu.Connection(self.db)
            self._init_schema()
        except Exception as e:
            logger.error(f"Critical error opening KuzuDB: {e}")
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
                    project STRING,
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
            ("project",            "STRING", f"''"),
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

    @_synchronized
    def checkpoint(self):
        """Force a WAL checkpoint: flush the write-ahead log into the main DB
        file and truncate it.

        Without this the WAL grows unbounded (every write appends to it) and is
        only ever consolidated on a clean database close. If the process is
        OOM-killed or restarted uncleanly, a large WAL is left behind; replaying
        it at the next startup holds too many dirty pages and saturates the
        buffer pool ("buffer pool is full"), which turns every graph query into
        a 500. Checkpointing periodically (gardener) and on shutdown keeps the
        WAL small so a replay is always cheap. Best-effort: a failure here must
        never crash the caller.
        """
        try:
            self.conn.execute("CHECKPOINT")
            logger.info("KuzuDB checkpoint complete (WAL flushed).")
        except Exception as e:
            logger.warning(f"KuzuDB checkpoint skipped: {e}")

    def close(self):
        """Clean shutdown: checkpoint the WAL, then release the connection and
        database so KuzuDB leaves a consolidated state (small/empty WAL) behind.
        Wired into the gateway lifespan shutdown so `systemctl stop|restart`
        (SIGTERM) never leaves a bloated WAL for the next boot to choke on.
        """
        with self._lock:
            try:
                self.conn.execute("CHECKPOINT")
            except Exception as e:
                logger.warning(f"KuzuDB checkpoint on close skipped: {e}")
            for obj_name in ("conn", "db"):
                obj = getattr(self, obj_name, None)
                if obj is not None:
                    try:
                        obj.close()
                    except Exception as e:
                        logger.warning(f"KuzuDB {obj_name}.close() failed: {e}")
                    setattr(self, obj_name, None)
            logger.info("KuzuDB closed cleanly.")

    # ─── Node CRUD ────────────────────────────────────────────────────────────

    @_synchronized
    def add_node(self, name: str, initial_activation: float = 0.5,
                 node_type: str = "Node", scope: str = "Public",
                 display_name: str = None, project: str = ""):
        norm_name = normalize_node_name(name)
        display = display_name or name
        now = time.time()
        query = """
        MERGE (a:Node {name: $name})
        ON CREATE SET
            a.display_name = $display,
            a.activation = $act,
            a.node_type = $node_type,
            a.scope = $scope,
            a.project = $project,
            a.last_interaction = $now,
            a.last_decay_applied = $now,
            a.interaction_count = $zero
        ON MATCH SET
            a.display_name = $display
        """
        self.conn.execute(query, parameters={
            "name": norm_name, "display": display,
            "act": initial_activation, "node_type": node_type,
            "scope": scope, "project": project, "now": now, "zero": 0,
        })

    @_synchronized
    def get_node(self, name: str) -> dict:
        norm_name = normalize_node_name(name)
        query = """
        MATCH (n:Node {name: $name})
        RETURN n.name, n.display_name, n.activation, n.node_type, n.scope,
               n.last_interaction, n.interaction_count, n.project
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
                "project": row[7],
            }
        return None

    @_synchronized
    def update_node_metadata(self, name: str, node_type: str = None, scope: str = None, project: str = None):
        norm_name = normalize_node_name(name)
        updates, params = [], {"name": norm_name}
        if node_type:
            updates.append("n.node_type = $node_type")
            params["node_type"] = node_type
        if scope:
            updates.append("n.scope = $scope")
            params["scope"] = scope
        if project:
            updates.append("n.project = $project")
            params["project"] = project
        if updates:
            self.conn.execute(
                f"MATCH (n:Node {{name: $name}}) SET {', '.join(updates)}",
                parameters=params,
            )

    @_synchronized
    def update_activation(self, name: str, level: float):
        query = "MATCH (n:Node {name: $name}) SET n.activation = $level"
        self.conn.execute(query, parameters={"name": name, "level": level})

    @_synchronized
    def seed_activation(self, name: str, level: float, reference_ts: float):
        """Set a node's activation and pin its decay clock to reference_ts.

        Used by the thermal re-seed utility after a graph rebuild: setting both
        last_interaction and last_decay_applied to reference_ts makes a
        subsequent apply_decay_per_node() compute decay from that timestamp,
        so the node lands at the activation it would have if it had been touched
        at reference_ts and decayed naturally since. No-op if the node is absent.
        """
        self.conn.execute(
            "MATCH (n:Node {name: $name}) "
            "SET n.activation = $level, n.last_interaction = $ts, n.last_decay_applied = $ts",
            parameters={"name": normalize_node_name(name), "level": level, "ts": reference_ts},
        )

    @_synchronized
    def get_thermal_state(self) -> list:
        """Snapshot of every node's thermal state, for backup (see core.thermal_backup).

        Returns [{name, activation, last_interaction, interaction_count,
        last_decay_applied}, ...]. This is the ONLY authoritative state that is not
        derivable from the markdown files, hence the only thing that needs backing up.
        """
        res = self.conn.execute(
            "MATCH (n:Node) RETURN n.name, n.activation, n.last_interaction, "
            "n.interaction_count, n.last_decay_applied"
        )
        rows = []
        while res.has_next():
            r = res.get_next()
            rows.append({
                "name": r[0],
                "activation": r[1],
                "last_interaction": r[2],
                "interaction_count": r[3],
                "last_decay_applied": r[4],
            })
        return rows

    @_synchronized
    def restore_thermal(self, name: str, activation: float, last_interaction: float,
                        interaction_count: int, last_decay_applied: float):
        """Write a node's thermal fields back verbatim from a backup snapshot.

        Complements seed_activation (which reconstructs from a single reference
        timestamp): this restores the exact stored values, interaction_count
        included, so the longitudinal features (dormant/hub detection, gated on
        interaction_count >= N) work immediately after a rebuild. No-op if absent.
        """
        self.conn.execute(
            "MATCH (n:Node {name: $name}) SET n.activation = $act, "
            "n.last_interaction = $li, n.interaction_count = $ic, n.last_decay_applied = $lda",
            parameters={
                "name": normalize_node_name(name), "act": activation,
                "li": last_interaction, "ic": interaction_count, "lda": last_decay_applied,
            },
        )

    @_synchronized
    def update_interaction(self, name: str, boost: float, update_timestamp: bool = True, floor: float = 0.0):
        """Apply activation boost. If update_timestamp, record this as a direct interaction.

        floor: lift the resulting activation to at least this value (used for the
        recency floor on file edits); never lowers an already-hotter node.
        """
        norm_name = normalize_node_name(name)
        node = self.get_node(norm_name)
        if not node:
            return
        new_activation = min((node.get("activation_level") or 0.0) + boost, 1.0)
        if floor:
            new_activation = max(new_activation, floor)
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

    @_synchronized
    def delete_node(self, name: str):
        norm_name = normalize_node_name(name)
        try:
            self.conn.execute("MATCH (n:Node {name: $name})-[r:RELATES]->() DELETE r", parameters={"name": norm_name})
            self.conn.execute("MATCH ()-[r:RELATES]->(n:Node {name: $name}) DELETE r", parameters={"name": norm_name})
            self.conn.execute("MATCH (n:Node {name: $name}) DELETE n", parameters={"name": norm_name})
            return True
        except Exception as e:
            logger.error(f"Failed to delete {norm_name}: {e}")
            return False

    # ─── Edges ────────────────────────────────────────────────────────────────

    @_synchronized
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

    @_synchronized
    def get_outgoing_edges(self, name: str) -> list:
        """Return this node's outgoing RELATES edges as [{target, type}, ...].

        Directed (source → target), unlike get_neighbors. Used by the file
        watcher to reconcile file-derived edges against the current frontmatter.
        """
        norm_name = normalize_node_name(name)
        query = """
        MATCH (n:Node {name: $name})-[r:RELATES]->(m:Node)
        RETURN m.name, r.type
        """
        res = self.conn.execute(query, parameters={"name": norm_name})
        edges = []
        while res.has_next():
            row = res.get_next()
            edges.append({"target": row[0], "type": row[1]})
        return edges

    @_synchronized
    def delete_edge(self, source_name: str, target_name: str, relation_type: str):
        """Remove a single directed RELATES edge of a specific type."""
        self.conn.execute(
            """
            MATCH (a:Node {name: $source})-[r:RELATES {type: $rel_type}]->(b:Node {name: $target})
            DELETE r
            """,
            parameters={
                "source": normalize_node_name(source_name),
                "target": normalize_node_name(target_name),
                "rel_type": relation_type,
            },
        )

    @_synchronized
    def get_neighbors(self, name: str, scopes: list = None):
        norm_name = normalize_node_name(name)
        query = """
        MATCH (n:Node {name: $name})-[r:RELATES]-(m:Node)
        RETURN m.name, r.type, r.weight, m.scope
        """
        res = self.conn.execute(query, parameters={"name": norm_name})
        neighbors = []
        while res.has_next():
            row = res.get_next()
            neighbor_scope = row[3]
            if scopes and "*" not in scopes and neighbor_scope not in scopes:
                continue
            neighbors.append({"node_name": row[0], "rel_type": row[1], "weight": row[2]})
        return neighbors

    # ─── Queries ──────────────────────────────────────────────────────────────

    @_synchronized
    def get_active_nodes(self, threshold: float = 0.5, scopes: list = None, project: str = None):
        query = """
        MATCH (n:Node)
        WHERE n.activation > $threshold
        RETURN n.name, n.display_name, n.activation, n.node_type, n.scope, n.project
        """
        res = self.conn.execute(query, parameters={"threshold": threshold})
        active = []
        while res.has_next():
            row = res.get_next()
            name, display_name, activation, node_type, scope, node_project = row[0], row[1], row[2], row[3], row[4], row[5]
            if scopes and "*" not in scopes and scope not in scopes:
                continue
            if project and (node_project or "") != project:
                continue
            active.append({
                "name": name,
                "display_name": display_name,
                "activation_level": activation,
                "node_type": node_type,
                "scope": scope,
                "project": node_project,
            })
        return active

    @_synchronized
    def get_all_nodes(self):
        res = self.conn.execute("MATCH (n:Node) RETURN n.name, n.activation")
        nodes = []
        while res.has_next():
            row = res.get_next()
            nodes.append({"name": row[0], "activation_level": row[1]})
        return nodes

    @_synchronized
    def get_dormant_nodes(self, scopes: list = None, min_interactions: int = 5,
                          days_node: int = 27, days_goal_task: int = 30,
                          days_journal: int = 45, project: str = None) -> list:
        """
        Returns nodes that were historically active but have gone quiet.
        - Node type: activation-based (< 0.2) after days_node of inactivity
        - Goal/Task: time-based (> days_goal_task since last interaction)
        - Journal: time-based (> days_journal since last interaction)
        """
        activation_threshold = 0.2

        query = """
        MATCH (n:Node)
        WHERE NOT n.name STARTS WITH 'obs_'
        AND n.node_type IN ['Goal', 'Task', 'Node', 'Journal']
        AND COALESCE(n.interaction_count, 0) >= $min_interactions
        RETURN n.name, n.display_name, n.activation, n.node_type, n.scope, n.last_interaction, n.interaction_count, n.project
        """
        res = self.conn.execute(query, parameters={"min_interactions": min_interactions})

        now = time.time()
        dormant = []
        while res.has_next():
            row = res.get_next()
            name, display_name, activation, node_type, scope, last_interaction, count, node_project = (
                row[0], row[1], row[2], row[3], row[4], row[5] or 0, row[6] or 0, row[7]
            )
            time_inactive = now - last_interaction
            days_inactive = time_inactive / 86400

            is_dormant = False
            if node_type == "Node" and activation < activation_threshold and days_inactive > days_node:
                is_dormant = True
            elif node_type in ("Goal", "Task") and days_inactive > days_goal_task:
                is_dormant = True
            elif node_type == "Journal" and days_inactive > days_journal:
                is_dormant = True

            if not is_dormant:
                continue
            if scopes and "*" not in scopes and scope not in scopes:
                continue
            if project and (node_project or "") != project:
                continue

            dormant.append({
                "name": name,
                "display_name": display_name,
                "activation": activation,
                "node_type": node_type,
                "scope": scope,
                "project": node_project,
                "days_inactive": int(days_inactive),
                "interaction_count": count,
            })
        return dormant

    @_synchronized
    def get_dormant_by_connectivity(self, min_edges: int = 2, activation_ceiling: float = 0.3,
                                     days_inactive: int = 14, scopes: list = None) -> list:
        """
        Returns nodes that are structurally important (many connections) but have gone quiet.
        These are candidates for longitudinal resurface: forgotten hubs.
        """
        query = """
        MATCH (n:Node)-[r:RELATES]-(m:Node)
        WHERE NOT n.name CONTAINS '__obs_'
        AND NOT n.name STARTS WITH 'obs_'
        AND n.activation < $ceiling
        RETURN n.name, n.display_name, n.activation, n.node_type, n.scope, n.last_interaction,
               n.interaction_count, count(r) AS edge_count
        ORDER BY edge_count DESC
        """
        res = self.conn.execute(query, parameters={"ceiling": activation_ceiling})

        now = time.time()
        cutoff = now - days_inactive * 86400
        results = []
        while res.has_next():
            row = res.get_next()
            name, display_name, activation, node_type, scope, last_interaction, interaction_count, edge_count = (
                row[0], row[1], row[2], row[3], row[4], row[5] or 0, row[6] or 0, row[7]
            )
            if edge_count < min_edges:
                continue
            if last_interaction > cutoff:
                continue
            if scopes and "*" not in scopes and scope not in scopes:
                continue
            results.append({
                "name": name,
                "display_name": display_name,
                "activation": activation,
                "node_type": node_type,
                "scope": scope,
                "edge_count": edge_count,
                "days_inactive": int((now - last_interaction) / 86400),
                "interaction_count": interaction_count,
            })
        return results

    @_synchronized
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

    @_synchronized
    def apply_decay_per_node(self, decay_rates: dict):
        """
        Apply type-specific decay proportional to real time elapsed since last decay.
        Retroactively handles downtime: uses last_decay_applied as the reference point.
        """
        query = """
        MATCH (n:Node)
        RETURN n.name, n.activation, n.node_type, n.last_decay_applied, n.last_interaction
        """
        res = self.conn.execute(query)
        rows = []
        while res.has_next():
            row = res.get_next()
            rows.append((row[0], row[1], row[2], row[3], row[4]))

        now = time.time()
        default_rate = decay_rates.get("Node", 0.0025)

        for name, activation, node_type, last_decay, last_interaction in rows:
            # Reference nodes used to be exempt from decay (evergreen). They now
            # decay slowly (see decay_rates["Reference"]) so they can cool down
            # if unused instead of permanently dominating the hot set.
            rate = decay_rates.get(node_type or "Node", default_rate)
            # Use the most recent of last_decay_applied and last_interaction so that
            # a fresh interaction resets the decay clock (no decay accumulates during active use).
            reference = max(last_decay or now, last_interaction or 0)
            hours_elapsed = (now - reference) / 3600
            factor = (1 - rate) ** hours_elapsed
            new_activation = max((activation or 0.0) * factor, 0.0)
            self.conn.execute(
                "MATCH (n:Node {name: $name}) SET n.activation = $act, n.last_decay_applied = $now",
                parameters={"name": name, "act": new_activation, "now": now},
            )

    @_synchronized
    def find_by_basename(self, basename: str) -> list:
        """Find all nodes whose path-based ID ends with __<basename> or equals <basename>.

        Used by API endpoints that accept a bare display name and need to resolve
        it to the actual path-based node ID(s). Returns a list of node dicts;
        the caller decides how to handle multiple matches (ambiguity).
        """
        from core.utils import _normalize_segment
        norm_base = _normalize_segment(basename)
        suffix = "__" + norm_base
        query = """
        MATCH (n:Node)
        WHERE n.name = $exact OR n.name ENDS WITH $suffix
        RETURN n.name, n.display_name, n.activation, n.node_type, n.scope, n.project
        """
        res = self.conn.execute(query, parameters={"exact": norm_base, "suffix": suffix})
        results = []
        while res.has_next():
            row = res.get_next()
            results.append({
                "name": row[0],
                "display_name": row[1],
                "activation_level": row[2],
                "node_type": row[3],
                "scope": row[4],
                "project": row[5],
            })
        return results

    @_synchronized
    def batch_decay(self, decay_factor: float = 0.95):
        """Legacy uniform decay. Prefer apply_decay_per_node for new code."""
        self.conn.execute(
            "MATCH (n:Node) SET n.activation = n.activation * $factor",
            parameters={"factor": decay_factor},
        )

    @_synchronized
    def get_stats(self) -> dict:
        """Return lightweight graph statistics for the /status telemetry endpoint."""
        node_res = self.conn.execute("MATCH (n:Node) RETURN count(n)")
        node_count = node_res.get_next()[0] if node_res.has_next() else 0

        edge_res = self.conn.execute("MATCH ()-[r:RELATES]->() RETURN count(r)")
        edge_count = edge_res.get_next()[0] if edge_res.has_next() else 0

        type_res = self.conn.execute(
            "MATCH (n:Node) RETURN n.node_type, count(n) ORDER BY count(n) DESC"
        )
        by_type = {}
        while type_res.has_next():
            row = type_res.get_next()
            by_type[row[0] or "unknown"] = row[1]

        return {"nodes": node_count, "edges": edge_count, "by_type": by_type}
