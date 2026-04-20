import kuzu
import logging
import os
import shutil
from core.utils import normalize_node_name

logger = logging.getLogger(__name__)

class KuzuManager:
    """
    Manages the topological graph and thermal state (activation) of Mnemosyne.
    Schema: Nodes have normalized names as PK, and original display names.
    """
    def __init__(self, db_path="./data/kuzu_db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self):
        try:
            # name: normalized pk, display_name: original casing
            self.conn.execute("CREATE NODE TABLE Node(name STRING, display_name STRING, activation DOUBLE, PRIMARY KEY (name))")
            logger.info("Created Kuzu NODE TABLE 'Node' with case-insensitive normalization")
        except RuntimeError:
            pass # Table already exists

        try:
            self.conn.execute("CREATE REL TABLE RELATES(FROM Node TO Node, type STRING, weight DOUBLE)")
            logger.info("Created Kuzu REL TABLE 'RELATES'")
        except RuntimeError:
            pass # Table already exists

    def close(self):
        # Kuzu automatically writes to disk, no explicit close of connection needed
        pass

    def add_node(self, name: str, initial_activation: float = 1.0):
        norm_name = normalize_node_name(name)
        # Try to keep the first display name encountered that isn't empty
        query = "MERGE (a:Node {name: $name}) ON CREATE SET a.activation = $act, a.display_name = $display"
        self.conn.execute(query, parameters={"name": norm_name, "act": initial_activation, "display": name})
        
    def get_node(self, name: str) -> dict:
        norm_name = normalize_node_name(name)
        query = "MATCH (n:Node {name: $name}) RETURN n.name as name, n.display_name as display, n.activation as activation"
        res = self.conn.execute(query, parameters={"name": norm_name})
        if res.has_next():
            row = res.get_next()
            return {"name": row[0], "display_name": row[1], "activation_level": row[2]}
        return None

    def add_edge(self, source_name: str, target_name: str, relation_type: str, weight: float = 1.0):
        # Ensure nodes exist
        self.add_node(source_name)
        self.add_node(target_name)
        
        # Merge relationship
        query = """
        MATCH (a:Node {name: $source}), (b:Node {name: $target})
        MERGE (a)-[r:RELATES {type: $rel_type}]->(b)
        ON MATCH SET r.weight = $weight
        ON CREATE SET r.weight = $weight
        """
        self.conn.execute(query, parameters={
            "source": source_name, 
            "target": target_name, 
            "rel_type": relation_type, 
            "weight": weight
        })

    def update_activation(self, name: str, level: float):
        query = "MATCH (n:Node {name: $name}) SET n.activation = $level"
        self.conn.execute(query, parameters={"name": name, "level": level})

    def get_active_nodes(self, threshold: float = 0.5):
        query = "MATCH (n:Node) WHERE n.activation > $threshold RETURN n.name as name, n.activation as activation"
        res = self.conn.execute(query, parameters={"threshold": threshold})
        active = []
        while res.has_next():
            row = res.get_next()
            active.append({"name": row[0], "activation_level": row[1]})
        return active

    def get_neighbors(self, name: str):
        query = """
        MATCH (n:Node {name: $name})-[r:RELATES]-(m:Node)
        RETURN m.name as node_name, r.type as rel_type, r.weight as weight
        """
        res = self.conn.execute(query, parameters={"name": name})
        neighbors = []
        while res.has_next():
            row = res.get_next()
            neighbors.append({
                "node_name": row[0],
                "rel_type": row[1],
                "weight": row[2]
            })
        return neighbors

    def get_graph_export(self, limit: int = 5000):
        res_nodes = self.conn.execute("MATCH (n:Node) RETURN n.name, n.activation LIMIT $limit", parameters={"limit": limit})
        nodes = []
        while res_nodes.has_next():
            row = res_nodes.get_next()
            nodes.append({"id": row[0], "name": row[0], "activation": row[1]})
            
        res_edges = self.conn.execute("MATCH (a:Node)-[r:RELATES]->(b:Node) RETURN a.name, b.name, r.type LIMIT $limit", parameters={"limit": limit})
        edges = []
        while res_edges.has_next():
            row = res_edges.get_next()
            edges.append({"source": row[0], "target": row[1], "type": row[2]})
            
        return {"nodes": nodes, "relationships": edges}

    def delete_node(self, name: str):
        norm_name = normalize_node_name(name)
        query1 = "MATCH (n:Node {name: $name})-[r]-() DELETE r"
        query2 = "MATCH (n:Node {name: $name}) DELETE n"
        try:
            self.conn.execute(query1, parameters={"name": norm_name})
            self.conn.execute(query2, parameters={"name": norm_name})
            return True
        except Exception as e:
            logger.error(f"Failed to delete {norm_name}: {e}")
            return False

    def batch_decay(self, decay_factor: float = 0.95):
        query = "MATCH (n:Node) SET n.activation = n.activation * $factor"
        self.conn.execute(query, parameters={"factor": decay_factor})

    def get_all_nodes(self):
        query = "MATCH (n:Node) RETURN n.name, n.activation"
        res = self.conn.execute(query)
        nodes = []
        while res.has_next():
             row = res.get_next()
             nodes.append({"name": row[0], "activation_level": row[1]})
        return nodes
