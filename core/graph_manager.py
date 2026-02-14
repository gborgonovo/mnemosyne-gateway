import logging
from neo4j import GraphDatabase
from datetime import datetime

logger = logging.getLogger(__name__)

class GraphManager:
    """
    Manages interactions with the Neo4j Graph Database.
    Implements the Hybrid Schema (Micro-Types + Tags) and Primitive Relationships.
    """

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.verify_connection()

    def verify_connection(self):
        try:
            self.driver.verify_connectivity()
            logger.info("Connected to Neo4j successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        self.driver.close()

    def add_node(self, name: str, primary_label: str = "Topic", tags: list = None, properties: dict = None):
        """
        Creates or updates a node.
        primary_label: Entity, Topic, Resource, Goal, Task, or Node.
        tags: List of secondary labels (e.g., Project, Urgent).
        """
        if primary_label not in ["Entity", "Topic", "Resource", "Node", "Observation", "Goal", "Task"]:
            logger.warning(f"Unknown primary label '{primary_label}', falling back to 'Node'.")
            primary_label = "Node"

        tags = tags or []
        properties = properties or {}
        
        # Standard properties
        properties['name'] = name
        properties['last_seen'] = datetime.now().isoformat()
        if 'activation_level' not in properties:
             properties['activation_level'] = 1.0 # New nodes are hot

        # Construct Cypher query
        # STRATEGY: 
        # 1. MERGE on generic property 'name' WITHOUT checking specific label 'Node' first, 
        #    to catch nodes that might have been created without 'Node' label.
        # 2. Then set the Labels.
        
        labels_cypher = f":{primary_label}"
        for tag in tags:
            labels_cypher += f":{tag}"
        
        query = (
            f"MERGE (n {{name: $name}}) "
            f"SET n:Node{labels_cypher}, n += $props "
            f"RETURN n"
        )
        
        if primary_label == "Observation":
             # Observations are unique by ID/hash, so we don't merge on name "Obs_..." if we want purity,
             # but actually they have unique names so it's fine.
             pass

        with self.driver.session() as session:
            result = session.run(query, name=name, props=properties)
            return result.single()[0]

    def add_edge(self, source_name: str, target_name: str, relation_type: str, weight: float = None):
        """
        Creates a relationship between two nodes identified by name.
        relation_type: LINKED_TO, DEPENDS_ON, EVOKES, IS_A
        """
        valid_relations = {
            "LINKED_TO": 0.3,
            "DEPENDS_ON": 0.9,
            "EVOKES": 0.6,
            "IS_A": 1.0,
            "MENTIONED_IN": 0.1,
            "MAYBE_SAME_AS": 0.0
        }

        if relation_type not in valid_relations:
            logger.warning(f"Unknown relationship type: {relation_type}. Defaulting to LINKED_TO")
            relation_type = "LINKED_TO"

        if weight is None:
            weight = valid_relations[relation_type]

        query = (
            "MATCH (a {name: $source}), (b {name: $target}) "
            f"MERGE (a)-[r:{relation_type}]->(b) "
            "SET r.weight = $weight, r.last_active = $timestamp "
            "RETURN type(r)"
        )

        with self.driver.session() as session:
            session.run(query, source=source_name, target=target_name, 
                        weight=weight, timestamp=datetime.now().isoformat())

    def get_node(self, name: str):
        """
        Retrieves a node by name or by its aliases.
        """
        # Try direct name match first
        query = "MATCH (n {name: $name}) RETURN n"
        with self.driver.session() as session:
            result = session.run(query, name=name)
            record = result.single()
            if record:
                return record[0]
            
            # Fallback: Case-insensitive search
            query_fallback = "MATCH (n) WHERE toLower(n.name) = toLower($name) RETURN n"
            result = session.run(query_fallback, name=name)
            record = result.single()
            if record:
                return record[0]
            
            # If not found, check aliases
            alias_query = "MATCH (n) WHERE $name IN n.aliases RETURN n"
            result = session.run(alias_query, name=name)
            record = result.single()
            return record[0] if record else None

    def get_all_nodes(self):
        query = "MATCH (n) RETURN n.name as name, labels(n) as labels, n.activation_level as activation, properties(n) as props"
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query)]

    def get_active_nodes(self, threshold: float = 0.5):
        query = """
        MATCH (n) 
        WHERE n.activation_level > $threshold 
        RETURN n.name as name, n.activation_level as activation, labels(n) as labels
        """
        with self.driver.session() as session:
            # Normalize output to list of dicts
            return [dict(record) for record in session.run(query, threshold=threshold)]

    def update_activation(self, name: str, level: float):
        query = "MATCH (n {name: $name}) SET n.activation_level = $level"
        with self.driver.session() as session:
            session.run(query, name=name, level=level)

    def add_alias(self, node_name: str, alias: str):
        """
        Adds a synonym to the aliases list of a node.
        """
        query = """
        MATCH (n {name: $name})
        SET n.aliases = coalesce(n.aliases, []) + $alias
        """
        with self.driver.session() as session:
            session.run(query, name=node_name, alias=alias)
            logger.info(f"Added alias '{alias}' to node '{node_name}'")

    def get_neighbors(self, name: str):
        """Returns list of (neighbor_node, relationship_type, weight, direction, rel_props)"""
        query = """
        MATCH (n {name: $name})-[r]-(m) 
        RETURN m as node, labels(m) as labels, type(r) as rel_type, r.weight as weight, 
               properties(r) as rel_props, startNode(r) = n as is_outgoing
        """
        neighbors = []
        with self.driver.session() as session:
            results = session.run(query, name=name)
            for record in results:
                # direction: 'out' if n -> m, 'in' if m -> n
                direction = 'out' if record['is_outgoing'] else 'in'
                
                # Convert Node object to dict and merge labels
                node_dict = dict(record['node'])
                node_dict['labels'] = record['labels']
                
                neighbors.append({
                    'node': node_dict,
                    'rel_type': record['rel_type'],
                    'weight': record['weight'],
                    'rel_props': record['rel_props'],
                    'direction': direction
                })
        return neighbors
    def trace_dependencies(self, start_node_name: str, max_depth: int = 3):
        """
        Traces downstream dependencies (outgoing directional links).
        Useful for Impact Analysis.
        Returns a list of impact chains.
        """
        query = """
        MATCH (n {name: $name})
        MATCH path = (n)-[:DEPENDS_ON|IS_A|HA_VINCOLO*1..3]->(m)
        RETURN [x in nodes(path) | x.name] as chain, [r in relationships(path) | type(r)] as types
        """
        # Note: We limit depth to 3 to prevent complexity explosion in MVP
        with self.driver.session() as session:
            results = session.run(query, name=start_node_name)
            return [dict(record) for record in results]

    def merge_nodes(self, keep_id: int, discard_id: int):
        """
        Merges node with discard_id into node with keep_id.
        Moves all relationships and labels.
        """
        with self.driver.session() as session:
            # Using APOC to merge nodes is much safer and cleaner
            session.run("""
                MATCH (k), (d)
                WHERE id(k) = $keep_id AND id(d) = $discard_id
                CALL apoc.refactor.mergeNodes([k, d], {properties:"combine", mergeRels:true})
                YIELD node
                RETURN node
            """, keep_id=keep_id, discard_id=discard_id)
            
    def get_stats(self) -> dict:
        """Returns basic statistics about the graph."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n)
                OPTIONAL MATCH ()-[r]->()
                RETURN count(DISTINCT n) as nodes, count(DISTINCT r) as relationships
            """)
            record = result.single()
            if record:
                return {"nodes": record["nodes"], "relationships": record["relationships"]}
            return {"nodes": 0, "relationships": 0}
