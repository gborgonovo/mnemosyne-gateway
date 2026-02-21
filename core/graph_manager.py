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
        self.scope_hierarchy = {
            "Private": ["Private", "Internal", "Public", "Global"],
            "Internal": ["Internal", "Public", "Global"],
            "Public": ["Public", "Global"],
            "Global": ["Global"]
        }

    def verify_connection(self):
        try:
            self.driver.verify_connectivity()
            logger.info("Connected to Neo4j successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        self.driver.close()

    def _get_scope_filter(self, scopes: list[str], var_name: str = "n") -> str:
        """
        Generates a Cypher WHERE clause fragment for scope filtering.
        """
        if not scopes:
            return "" # No filtering if no scopes provided (internal use)
        
        # Expand scopes based on hierarchy
        all_allowed = set()
        for s in scopes:
            all_allowed.update(self.scope_hierarchy.get(s, [s]))
        
        condition = " OR ".join([f"{var_name}:{s}" for s in all_allowed])
        return f"({condition})"

    def add_node(self, name: str, primary_label: str = "Topic", tags: list = None, properties: dict = None, scope: str = "Public"):
        """
        Creates or updates a node.
        primary_label: Entity, Topic, Resource, Goal, Task, or Node.
        tags: List of secondary labels.
        scope: Public, Internal, Private.
        """
        if primary_label not in ["Entity", "Topic", "Resource", "Node", "Observation", "Goal", "Task"]:
            logger.warning(f"Unknown primary label '{primary_label}', falling back to 'Node'.")
            primary_label = "Node"

        tags = tags or []
        properties = properties or {}
        
        properties['name'] = name
        properties['last_seen'] = datetime.now().isoformat()
        if 'activation_level' not in properties:
             properties['activation_level'] = 1.0

        # Construct Labels
        labels_cypher = f":{primary_label}:{scope}"
        for tag in tags:
            labels_cypher += f":{tag}"
        
        query = (
            f"MERGE (n {{name: $name}}) "
            f"SET n:Node{labels_cypher}, n += $props "
            f"RETURN n"
        )
        
        with self.driver.session() as session:
            result = session.run(query, name=name, props=properties)
            return result.single()[0]

    def add_edge(self, source_name: str, target_name: str, relation_type: str, weight: float = None):
        """
        Creates a relationship between two nodes identified by name.
        """
        valid_relations = {
            "LINKED_TO": 0.3, "DEPENDS_ON": 0.9, "EVOKES": 0.6,
            "IS_A": 1.0, "MENTIONED_IN": 0.1, "MAYBE_SAME_AS": 0.0
        }

        if relation_type not in valid_relations:
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

    def get_node(self, name: str, scopes: list[str] = None):
        """
        Retrieves a node by name, respecting scope filtering.
        """
        scope_clause = self._get_scope_filter(scopes)
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""

        # 1. Try exact match
        query = f"MATCH (n {{name: $name}}) {where_clause} RETURN n"
        with self.driver.session() as session:
            result = session.run(query, name=name)
            record = result.single()
            if record:
                return record[0]
            
            # 2. Case-insensitive fallback
            fallback_where = f"WHERE toLower(n.name) = toLower($name) " + (f"AND {scope_clause}" if scope_clause else "")
            query_fallback = f"MATCH (n) {fallback_where} RETURN n"
            result = session.run(query_fallback, name=name)
            record = result.single()
            if record:
                return record[0]
            
            # 3. Alias check
            alias_where = f"WHERE $name IN n.aliases " + (f"AND {scope_clause}" if scope_clause else "")
            alias_query = f"MATCH (n) {alias_where} RETURN n"
            result = session.run(alias_query, name=name)
            record = result.single()
            return record[0] if record else None

    def get_all_nodes(self, scopes: list[str] = None):
        scope_clause = self._get_scope_filter(scopes)
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        query = f"MATCH (n) {where_clause} RETURN n.name as name, labels(n) as labels, n.activation_level as activation, properties(n) as props"
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query)]

    def delete_node(self, name: str, scopes: list[str] = None) -> bool:
        """
        Deletes a node and all its relationships, respecting scope filtering.
        Returns True if a node was actually deleted.
        """
        scope_clause = self._get_scope_filter(scopes)
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        query = f"""
        MATCH (n {{name: $name}}) 
        {where_clause}
        WITH n LIMIT 1
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
        with self.driver.session() as session:
            result = session.run(query, name=name)
            record = result.single()
            return record["deleted_count"] > 0 if record else False

    def update_node_properties(self, name: str, properties: dict, scopes: list[str] = None) -> dict:
        """
        Updates properties of a node, respecting scope filtering.
        Returns the updated properties dictionary or None if not found.
        """
        if not properties:
            return None
            
        scope_clause = self._get_scope_filter(scopes)
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        # Don't allow changing core identifier via property update
        if 'name' in properties:
            del properties['name']
            
        query = f"""
        MATCH (n {{name: $name}})
        {where_clause}
        WITH n LIMIT 1
        SET n += $props
        RETURN properties(n) as updated_props
        """
        with self.driver.session() as session:
            result = session.run(query, name=name, props=properties)
            record = result.single()
            return dict(record["updated_props"]) if record else None

    def get_active_nodes(self, threshold: float = 0.5, scopes: list[str] = None):
        scope_clause = self._get_scope_filter(scopes)
        where_condition = f"n.activation_level > $threshold"
        if scope_clause:
            where_condition += f" AND {scope_clause}"
        
        query = f"""
        MATCH (n) 
        WHERE {where_condition}
        RETURN n.name as name, n.activation_level as activation, labels(n) as labels
        """
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query, threshold=threshold)]

    def update_activation(self, name: str, level: float):
        query = "MATCH (n {name: $name}) SET n.activation_level = $level"
        with self.driver.session() as session:
            session.run(query, name=name, level=level)

    def add_alias(self, node_name: str, alias: str):
        query = """
        MATCH (n {name: $name})
        SET n.aliases = coalesce(n.aliases, []) + $alias
        """
        with self.driver.session() as session:
            session.run(query, name=node_name, alias=alias)

    def get_neighbors(self, name: str, scopes: list[str] = None):
        """Returns list of (neighbor_node, relationship_type, weight, direction, rel_props)"""
        scope_clause = self._get_scope_filter(scopes, var_name="m")
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        query = f"""
        MATCH (n {{name: $name}})-[r]-(m) 
        {where_clause}
        RETURN m as node, labels(m) as labels, type(r) as rel_type, r.weight as weight, 
               properties(r) as rel_props, startNode(r) = n as is_outgoing
        """
        neighbors = []
        with self.driver.session() as session:
            results = session.run(query, name=name)
            for record in results:
                direction = 'out' if record['is_outgoing'] else 'in'
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

    def trace_dependencies(self, start_node_name: str, max_depth: int = 3, scopes: list[str] = None):
        """
        Traces downstream dependencies, filtered by scope.
        """
        scope_clause = self._get_scope_filter(scopes, var_name="m")
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        query = f"""
        MATCH (n {{name: $name}})
        MATCH path = (n)-[:DEPENDS_ON|IS_A|HA_VINCOLO*1..{max_depth}]->(m)
        {where_clause}
        RETURN [x in nodes(path) | x.name] as chain, [r in relationships(path) | type(r)] as types
        """
        with self.driver.session() as session:
            results = session.run(query, name=start_node_name)
            return [dict(record) for record in results]

    def merge_nodes(self, keep_id: int, discard_id: int):
        with self.driver.session() as session:
            session.run("""
                MATCH (k), (d)
                WHERE id(k) = $keep_id AND id(d) = $discard_id
                CALL apoc.refactor.mergeNodes([k, d], {properties:"combine", mergeRels:true})
                YIELD node
                RETURN node
            """, keep_id=keep_id, discard_id=discard_id)
            
    def get_stats(self, scopes: list[str] = None) -> dict:
        """Returns basic statistics about the graph, filtered by scope."""
        scope_clause = self._get_scope_filter(scopes)
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        query = f"""
            MATCH (n)
            {where_clause}
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN count(DISTINCT n) as nodes, count(DISTINCT r) as relationships
        """
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            if record:
                return {"nodes": record["nodes"], "relationships": record["relationships"]}
            return {"nodes": 0, "relationships": 0}
