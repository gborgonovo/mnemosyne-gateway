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

    def _get_filter_clause(self, scopes: list[str], namespaces: list[str] = None, var_name: str = "n") -> str:
        """
        Generates a Cypher WHERE clause fragment for scope and namespace filtering.
        `namespaces` format expected: ["progettoA:rw", "progettoB:r", ":r"]
        """
        # 1. Scope Filter Logic
        scope_condition = ""
        if scopes and "*" not in scopes:
            all_allowed = set()
            for s in scopes:
                all_allowed.update(self.scope_hierarchy.get(s, [s]))
            known_scopes = list(self.scope_hierarchy.keys())
            
            allowed_cond = " OR ".join([f"{var_name}:{s}" for s in all_allowed])
            fallback_cond = " AND ".join([f"NOT {var_name}:{s}" for s in known_scopes])
            scope_condition = f"(({allowed_cond}) OR ({fallback_cond}))"
            
        # 2. Namespace Filter Logic
        namespace_condition = ""
        if namespaces and "*" not in namespaces:
            allowed_namespaces = []
            can_read_globals = False
            
            for ns in namespaces:
                if ns == ":r" or ns == ":rw":
                    can_read_globals = True
                else:
                    parts = ns.split(":")
                    if parts[0]: allowed_namespaces.append(parts[0])
            
            ns_conds = []
            if allowed_namespaces:
                # Need to use ANY to check if any of the target namespaces exists in the node's namespace array
                # BUT since Neo4j params are better, we will format it directly here for the specific elements 
                ns_array_str = "[" + ",".join([f"'{ns}'" for ns in allowed_namespaces]) + "]"
                ns_conds.append(f"ANY(ns IN {var_name}.namespaces WHERE ns IN {ns_array_str})")
            
            if can_read_globals:
                ns_conds.append(f"({var_name}.namespaces IS NULL OR size({var_name}.namespaces) = 0)")
                
            if ns_conds:
                namespace_condition = f"({' OR '.join(ns_conds)})"

        # Combine conditions
        clauses = []
        if scope_condition: clauses.append(scope_condition)
        if namespace_condition: clauses.append(namespace_condition)
        
        return " AND ".join(clauses) if clauses else ""

    def _extract_primary_type(self, labels: list[str]) -> str:
        """
        Determines the primary type of a node from its labels,
        excluding 'Node' and scope labels.
        """
        if not labels:
            return "Node"
        exclusion_list = ["Node"] + list(self.scope_hierarchy.keys())
        type_labels = [l for l in labels if l not in exclusion_list]
        return type_labels[0] if type_labels else labels[0]

    def add_node(self, name: str, primary_label: str = "Topic", tags: list = None, properties: dict = None, scope: str = "Public", namespace: str = None):
        """
        Creates or updates a node.
        primary_label: Entity, Topic, Resource, Goal, Task, Document, DocumentChunk, or Node.
        tags: List of secondary labels.
        scope: Public, Internal, Private.
        namespace: Logical isolation identifier (optional).
        """
        if primary_label not in ["Entity", "Topic", "Resource", "Node", "Observation", "Goal", "Task", "Document", "DocumentChunk"]:
            logger.warning(f"Unknown primary label '{primary_label}', falling back to 'Node'.")
            primary_label = "Node"

        tags = tags or []
        properties = properties or {}
        
        properties['name'] = name
        properties['last_seen'] = datetime.now().isoformat()
        if 'activation_level' not in properties:
             properties['activation_level'] = 1.0

        if namespace:
             # Ensure the array contains the namespace
             # The MERGE SET will overwrite, but we merge logic handling if it already had other namespaces or just override
             properties['namespaces'] = [namespace]

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
            "IS_A": 1.0, "MENTIONED_IN": 0.1, "MAYBE_SAME_AS": 0.0,
            "PART_OF": 0.8, "MANAGES": 0.8, "HAS_MEMBER": 0.7,
            "REQUIRES": 0.9, "RELATED_TO": 0.4
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

    def get_node(self, name: str, scopes: list[str] = None, namespaces: list[str] = None):
        """
        Retrieves a node by name, respecting scope filtering.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
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

    def create_fulltext_index(self):
        """
        Ensures a full-text search index is available for semantic fallback.
        """
        # Note: se l'indice esiste già con la vecchia configurazione, va rimosso dal database
        # affinché IF NOT EXISTS crei quello nuovo.
        query = (
            "CREATE FULLTEXT INDEX mnemosyne_text_idx IF NOT EXISTS "
            "FOR (n:Node) ON EACH [n.name, n.title, n.description, n.summary, n.ai_context, n.content]"
        )
        try:
            with self.driver.session() as session:
                session.run(query)
                logger.info("Full-text index 'mnemosyne_text_idx' checked/created (includes n.content).")
        except Exception as e:
            logger.warning(f"Could not create full-text index: {e}")

    def create_vector_index(self):
        """
        Ensures a vector search index is available for semantic search.
        Requires determining the vector dimension from an existing node.
        """
        query_check = "SHOW INDEXES YIELD name, type WHERE name = 'mnemosyne_vector_idx' RETURN name"
        query_dim = "MATCH (n:Node) WHERE n.embedding IS NOT NULL RETURN size(n.embedding) as dim LIMIT 1"
        try:
            with self.driver.session() as session:
                res = session.run(query_check)
                if res.single() is None:
                    # Index does not exist, find dimension
                    dim_res = session.run(query_dim)
                    dim_record = dim_res.single()
                    if dim_record:
                        dim = dim_record['dim']
                        query_create = (
                            "CREATE VECTOR INDEX mnemosyne_vector_idx IF NOT EXISTS "
                            "FOR (n:Node) ON (n.embedding) "
                            "OPTIONS {indexConfig: { "
                            f" `vector.dimensions`: {dim}, "
                            " `vector.similarity_function`: 'cosine' "
                            "}}"
                        )
                        session.run(query_create)
                        logger.info(f"Vector index 'mnemosyne_vector_idx' created with dimension {dim}.")
                    else:
                        logger.warning("No embeddings found in graph, postponed vector index creation.")
                else:
                    logger.info("Vector index 'mnemosyne_vector_idx' checked.")
        except Exception as e:
            logger.warning(f"Could not check/create vector index: {e}")

    def search_nodes_fulltext(self, search_text: str, scopes: list[str] = None, namespaces: list[str] = None, limit: int = 5):
        """
        Searches nodes using the Neo4j full-text index 'mnemosyne_text_idx'.
        Applies basic fuzzy matching by appending '~' to search terms.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces, var_name="node")
        
        # very basic sanitization: remove lucene special characters
        safe_text = ''.join(c for c in search_text if c.isalnum() or c.isspace())
        if not safe_text.strip():
            return []
            
        # create lucene query: "word1~ word2~"
        tokens = safe_text.split()
        lucene_query = " OR ".join([f"{t}~" for t in tokens if len(t) > 2])
        if not lucene_query:
            lucene_query = safe_text
            
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        query = (
            "CALL db.index.fulltext.queryNodes('mnemosyne_text_idx', $lucene_query) YIELD node, score "
            f"{where_clause} "
            "RETURN node, score "
            "ORDER BY score DESC LIMIT toInteger($limit)"
        )
        
        with self.driver.session() as session:
            try:
                result = session.run(query, lucene_query=lucene_query, limit=limit)
                return [dict(record) for record in result]
            except Exception as e:
                logger.error(f"Full-text search failed: {e}")
                return []

    def search_nodes_vector(self, query_embedding: list[float], scopes: list[str] = None, namespaces: list[str] = None, limit: int = 5):
        """
        Searches nodes using the Neo4j vector index 'mnemosyne_vector_idx'.
        Requires that the vector index is already created.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces, var_name="node")
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        # We query the vector index and return the top match
        query = (
            "CALL db.index.vector.queryNodes('mnemosyne_vector_idx', $limit, $embedding) YIELD node, score "
            f"{where_clause} "
            "RETURN node, score "
            "ORDER BY score DESC"
        )
        
        with self.driver.session() as session:
            try:
                result = session.run(query, embedding=query_embedding, limit=limit)
                return [dict(record) for record in result]
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                return []

    def get_highly_similar_node_pairs(self, threshold: float = 0.85, limit: int = 100, scopes: list[str] = None, namespaces: list[str] = None):
        """
        Uses Neo4j cosine similarity function to find pairs of nodes that are semantically very close.
        Avoids O(N^2) Python comparisons.
        """
        scope_clause_1 = self._get_filter_clause(scopes, namespaces=namespaces, var_name="n1")
        scope_clause_2 = self._get_filter_clause(scopes, namespaces=namespaces, var_name="n2")
        
        where_conds = [
            "id(n1) < id(n2)",
            "n1.embedding IS NOT NULL",
            "n2.embedding IS NOT NULL",
            "NOT 'Observation' IN labels(n1)",
            "NOT 'Observation' IN labels(n2)"
        ]
        if scope_clause_1: where_conds.append(scope_clause_1)
        if scope_clause_2: where_conds.append(scope_clause_2)
            
        where_clause = "WHERE " + " AND ".join(where_conds)
        
        query = f"""
        MATCH (n1:Node)
        WHERE n1.embedding IS NOT NULL
        AND NOT 'Observation' IN labels(n1)
        {scope_clause_1 if scope_clause_1 else ""}
        
        // Use the vector index to find top candidates for each node
        CALL db.index.vector.queryNodes('mnemosyne_vector_idx', 10, n1.embedding) 
        YIELD node as n2, score
        
        WHERE id(n1) < id(n2) 
        AND score >= $threshold
        AND NOT 'Observation' IN labels(n2)
        {f'AND {scope_clause_2}' if scope_clause_2 else ""}
        
        // Ensure they aren't already linked 
        AND NOT (n1)-[]-(n2)
        
        // Compartimentalization: Ensure they share the exact same namespaces or are both global
        AND coalesce(n1.namespaces, []) = coalesce(n2.namespaces, [])
        
        RETURN n1.name as source, n2.name as target, score
        ORDER BY score DESC LIMIT $limit
        """
        
        with self.driver.session() as session:
            try:
                result = session.run(query, threshold=threshold, limit=limit)
                return [dict(record) for record in result]
            except Exception as e:
                logger.error(f"Failed to find similar node pairs: {e}")
                return []

    def semantic_search(self, query: str, llm_provider=None, enable_embeddings: bool = False, scopes: list[str] = None, namespaces: list[str] = None, limit: int = 1):
        """
        Performs semantic search using vector index, falling back to full-text,
        and finally to exact/fuzzy name match.
        Returns a tuple: (best_match_node, search_type, score) or (None, None, None)
        """
        # 1. EXACT NAME MATCH (Highest priority, most reliable)
        node = self.get_node(query, scopes=scopes, namespaces=namespaces)
        if node:
            return node, "exact", 1.0

        # 2. VECTOR SEARCH (Semantic)
        if enable_embeddings and llm_provider:
            try:
                query_embedding = llm_provider.embed(query)
                if query_embedding:
                    vector_results = self.search_nodes_vector(query_embedding, scopes=scopes, namespaces=namespaces, limit=limit)
                    if vector_results:
                        return vector_results[0]['node'], "vector", vector_results[0]['score']
            except Exception as e:
                logger.warning(f"Vector embedding failed, falling back to full-text: {e}")
                
        # 3. SEMANTIC FALLBACK (Full-Text)
        results = self.search_nodes_fulltext(query, scopes=scopes, namespaces=namespaces, limit=limit)
        if results:
            return results[0]['node'], "full-text", results[0]['score']
            
        return None, None, None

    def get_all_nodes(self, label: str = None, scopes: list[str] = None, namespaces: list[str] = None):
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        
        conditions = []
        if label:
            conditions.append(f"n:{label}")
        if scope_clause:
            conditions.append(scope_clause)
            
        where_clause = ""
        if conditions:
             where_clause = "WHERE " + " AND ".join(conditions)
             
        query = f"MATCH (n) {where_clause} RETURN n.name as name, labels(n) as labels, n.activation_level as activation, properties(n) as props"
        with self.driver.session() as session:
            return [dict(record) for record in session.run(query)]

    def delete_node(self, name: str, scopes: list[str] = None, namespaces: list[str] = None) -> bool:
        """
        Deletes a node and all its relationships, respecting scope filtering.
        Returns True if a node was actually deleted.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
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

    def update_node_properties(self, name: str, properties: dict, scopes: list[str] = None, namespaces: list[str] = None) -> dict:
        """
        Updates properties of a node, respecting scope filtering.
        Returns the updated properties dictionary or None if not found.
        """
        if not properties:
            return None
            
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
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

    def get_active_nodes(self, threshold: float = 0.5, scopes: list[str] = None, namespaces: list[str] = None):
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
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

    def get_neighbors(self, name: str, scopes: list[str] = None, namespaces: list[str] = None):
        """Returns list of (neighbor_node, relationship_type, weight, direction, rel_props)"""
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces, var_name="m")
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

    def trace_dependencies(self, start_node_name: str, max_depth: int = 3, scopes: list[str] = None, namespaces: list[str] = None):
        """
        Traces downstream dependencies, filtered by scope.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces, var_name="m")
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

    def merge_nodes(self, keep: int | str, discard: int | str):
        where_k = "id(k) = $keep" if isinstance(keep, int) else "k.name = $keep"
        where_d = "id(d) = $discard" if isinstance(discard, int) else "d.name = $discard"
        
        query = f"""
        MATCH (k), (d)
        WHERE {where_k} AND {where_d}
        
        // Remove direct relationships between them
        OPTIONAL MATCH (k)-[rel]-(d)
        DELETE rel

        WITH k, d
        // Move OUT relationships
        CALL {{
            WITH k, d
            MATCH (d)-[r]->(out)
            WHERE out <> k
            CALL apoc.create.relationship(k, type(r), properties(r), out) YIELD rel AS newOutRel
            DELETE r
            RETURN count(r) AS moved_out
        }}

        WITH k, d
        // Move IN relationships
        CALL {{
            WITH k, d
            MATCH (in)-[r]->(d)
            WHERE in <> k
            CALL apoc.create.relationship(in, type(r), properties(r), k) YIELD rel AS newInRel
            DELETE r
            RETURN count(r) AS moved_in
        }}

        WITH k, d
        // Tombstone 'd'
        CALL apoc.create.removeLabels(d, labels(d)) YIELD node AS rmd
        CALL apoc.create.addLabels(rmd, ['Archived', 'Tombstone']) YIELD node AS finalD
        SET finalD.merged_into = id(k)
        
        RETURN k
        """
        with self.driver.session() as session:
            try:
                res = session.run(query, keep=keep, discard=discard)
                record = res.single()
                return dict(record[0]) if record else None
            except Exception as e:
                logger.error(f"Failed to safe-merge nodes: {e}")
                return None
            
    def get_stats(self, scopes: list[str] = None, namespaces: list[str] = None) -> dict:
        """Returns basic statistics about the graph, filtered by scope."""
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
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

    def get_schema(self, scopes: list[str] = None, namespaces: list[str] = None) -> dict:
        """
        Returns all unique labels and property keys present in the specified namespace.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        
        query_labels = f"""
        MATCH (n) {where_clause}
        UNWIND labels(n) as label
        RETURN label, count(n) as count
        ORDER BY count DESC
        """
        query_props = f"""
        MATCH (n) {where_clause}
        UNWIND keys(n) as prop
        RETURN prop, count(n) as count
        ORDER BY count DESC
        """
        schema = {"labels": [], "properties": []}
        with self.driver.session() as session:
            for record in session.run(query_labels):
                schema["labels"].append({"label": record["label"], "count": record["count"]})
            for record in session.run(query_props):
                schema["properties"].append({"property": record["prop"], "count": record["count"]})
        return schema
        
    def advanced_search(self, filters: dict, scopes: list[str] = None, namespaces: list[str] = None, limit: int = 50) -> list[dict]:
        """
        Generates a safe structural query based on filters dict.
        filters: {"type": "Task", "status": "todo", "name": "something"}
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        
        conds = []
        if scope_clause:
            conds.append(scope_clause)
            
        params = {"limit": limit}
        
        node_label = "Node"
        if "type" in filters and filters["type"]:
            node_label = filters["type"]
            
        for k, v in filters.items():
            if k == "type": continue
            # Prevent cypher injection in property keys
            safe_k = ''.join(c for c in k if c.isalnum() or c == '_')
            if not safe_k: continue
            
            conds.append(f"n.{safe_k} = ${safe_k}")
            params[safe_k] = v
            
        where_clause = "WHERE " + " AND ".join(conds) if conds else ""
        
        query = f"""
        MATCH (n:{node_label})
        {where_clause}
        RETURN n.name as name, labels(n) as labels, properties(n) as props
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            results = session.run(query, **params)
            return [dict(record) for record in results]

    def export_graph(self, scopes: list[str] = None, namespaces: list[str] = None, limit: int = 5000) -> dict:
        """
        Exports a snapshot of nodes and relationships within the requested scope/namespace limit.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces, var_name="n")
        where_clause = f"WHERE {scope_clause}" if scope_clause else ""
        scope_clause_m = self._get_filter_clause(scopes, namespaces=namespaces, var_name="m")
        if scope_clause_m: scope_clause_m = "WHERE " + scope_clause_m
        else: scope_clause_m = ""
        
        query = f"""
        MATCH (n)
        {where_clause}
        OPTIONAL MATCH (n)-[r]->(m)
        {scope_clause_m}
        WITH n, r, m LIMIT $limit
        RETURN collect(DISTINCT n) as nodes, collect(DISTINCT r) as rels
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            record = result.single()
            
            nodes = []
            rels = []
            if record:
                for n in record.get("nodes", []):
                    # Neo4j 4/5 API parsing
                    element_id = n.element_id if hasattr(n, 'element_id') else n.id
                    nodes.append({"id": element_id, "name": dict(n).get("name"), "labels": list(n.labels), "properties": dict(n)})
                for r in record.get("rels", []):
                    if r is not None:
                        source_id = r.start_node.element_id if hasattr(r.start_node, 'element_id') else r.start_node.id
                        target_id = r.end_node.element_id if hasattr(r.end_node, 'element_id') else r.end_node.id
                        rels.append({
                            "type": r.type, 
                            "source": source_id, 
                            "target": target_id, 
                            "properties": dict(r)
                        })
                        
            return {"nodes": nodes, "relationships": rels}

    def get_all_aliases(self, scopes: list[str] = None, namespaces: list[str] = None) -> dict[str, str]:
        """
        Returns a dictionary mapping lowercased aliases/names to their canonical node names.
        Used for selective fuzzy matching against existing Entities/Topics.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        where_clause = f"({scope_clause}) AND ('Entity' IN labels(n) OR 'Topic' IN labels(n))" if scope_clause else "('Entity' IN labels(n) OR 'Topic' IN labels(n))"
        query = f"""
        MATCH (n) WHERE {where_clause}
        RETURN n.name as canonical_name, coalesce(n.aliases, []) as aliases
        """
        alias_map = {}
        with self.driver.session() as session:
            for record in session.run(query):
                canonical = record["canonical_name"]
                alias_map[canonical.lower()] = canonical
                for alias in record["aliases"]:
                    alias_map[alias.lower()] = canonical
        return alias_map

    def _fuzzy_link_chunk(self, chunk_name: str, text: str, alias_map: dict[str, str]):
        """
        Searches the text for known aliases and creates MENTIONED_IN relationships
        only for highly relevant matches (explicit chunk linking with attenuation).
        """
        import re
        text_lower = text.lower()
        
        # We look for explicit mentions of aliases.
        for alias, canonical_name in alias_map.items():
            if alias in text_lower:
                # Count explicit boundaries
                count = len(re.findall(r'\b' + re.escape(alias) + r'\b', text_lower))
                
                # Threshold for relevance: short words need more mentions.
                threshold = 3 if len(alias) <= 4 else 1
                
                if count >= threshold:
                    # Create attenuated relationship (backward weight will be handled by attention model)
                    self.add_edge(chunk_name, canonical_name, "MENTIONED_IN", weight=0.1)

    def add_document(self, title: str, chunks: list[str], scope: str = "Public", file_path: str = None):
        """
        Ingests a document as a 'Document' node and links its 'DocumentChunk' children.
        Performs selective fuzzy matching contextually.
        """
        props = {"file_path": file_path} if file_path else {}
        doc_node = self.add_node(title, primary_label="Document", properties=props, scope=scope)
        alias_map = self.get_all_aliases(scopes=[scope])  # Namespace skipped for document extraction context
        
        prev_chunk_name = None
        for i, text in enumerate(chunks):
            chunk_name = f"{title}_chunk_{i}"
            props = {"text": text, "index": i}
            
            # 1. Create Chunk node
            self.add_node(chunk_name, primary_label="DocumentChunk", properties=props, scope=scope)
            
            # 2. Link to Document
            self.add_edge(doc_node["name"], chunk_name, "CONTAINS")
            
            # 3. Link sequence
            if prev_chunk_name:
                self.add_edge(prev_chunk_name, chunk_name, "NEXT_CHUNK")
            prev_chunk_name = chunk_name
            
            # 4. Selective Fuzzy Matching
            self._fuzzy_link_chunk(chunk_name, text, alias_map)

    def get_dormant_projects(self, threshold_days: int = 30, limit: int = 5, scopes: list[str] = None, namespaces: list[str] = None) -> list[dict]:
        """
        Finds 'Goal', 'Project', or heavy 'Topic' nodes that haven't been seen recently
        but had significant connections in the past.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        where_scope = f"AND {scope_clause}" if scope_clause else ""
        
        query = f"""
        MATCH (n)
        WHERE (n:Goal OR n:Project OR n:Topic)
        {where_scope}
        AND n.last_seen IS NOT NULL
        // Convert ISO string to Neo4j datetime for comparison
        AND datetime(n.last_seen) < datetime() - duration({{days: $threshold_days}})
        AND NOT coalesce(n.status, '') IN ['done', 'completed', 'discarded']
        OPTIONAL MATCH (n)-[r]-()
        WITH n, count(r) as rel_count
        WHERE rel_count > 2 // Must have been somewhat significant
        RETURN n.name as name, labels(n) as labels, n.last_seen as last_seen, rel_count
        ORDER BY rel_count DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            results = session.run(query, threshold_days=threshold_days, limit=limit)
            return [dict(record) for record in results]
            
    def get_temporal_trends(self, days_ago: int = 7, limit: int = 5, scopes: list[str] = None, namespaces: list[str] = None) -> list[dict]:
        """
        Finds nodes that were highly active or created within the last N days.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        where_scope = f"AND {scope_clause}" if scope_clause else ""
        
        query = f"""
        MATCH (n)
        WHERE (n:Goal OR n:Project OR n:Topic OR n:Entity)
        {where_scope}
        AND n.last_seen IS NOT NULL
        AND datetime(n.last_seen) >= datetime() - duration({{days: $days_ago}})
        RETURN n.name as name, labels(n) as labels, n.last_seen as last_seen, n.activation_level as activation
        ORDER BY n.activation_level DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            results = session.run(query, days_ago=days_ago, limit=limit)
            return [dict(record) for record in results]

    def delete_document(self, title: str, scope: str = "Public") -> bool:
        """
        Deep deletes a document node and all its associated DocumentChunk nodes.
        """
        query = f"""
        MATCH (d:Document {{name: $title}})-[:CONTAINS]->(c:DocumentChunk)
        WHERE d:{scope}
        DETACH DELETE d, c
        """
        # Also handle documents with no chunks yet or where chunks were already deleted
        cleanup_query = f"""
        MATCH (d:Document {{name: $title}})
        WHERE d:{scope}
        DETACH DELETE d
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, title=title)
                summary = result.consume()
                nodes_deleted = summary.counters.nodes_deleted
                
                # Second pass for the document node itself if first query didn't match chunks
                result2 = session.run(cleanup_query, title=title)
                summary2 = result2.consume()
                nodes_deleted += summary2.counters.nodes_deleted
                
                return nodes_deleted > 0
        except Exception as e:
            logger.error(f"GRAPH DELETE FAILED for '{title}': {e}")
            raise e

    def get_nodes_missing_embeddings(self, limit: int = 10, scopes: list[str] = None, namespaces: list[str] = None) -> list[dict]:
        """
        Retrieves nodes that are eligible for vector search but don't have an embedding yet.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        where_scope = f"AND {scope_clause}" if scope_clause else ""
        
        # We target :Node and :Observation (which are the main entity types)
        query = f"""
        MATCH (n:Node)
        WHERE n.embedding IS NULL
        {where_scope}
        RETURN n.name as name, labels(n) as labels, 
               coalesce(n.name, '') + ' ' + coalesce(n.title, '') + ' ' + coalesce(n.description, '') + ' ' + coalesce(n.summary, '') + ' ' + coalesce(n.ai_context, '') + ' ' + coalesce(n.content, '') as text
        LIMIT $limit
        """
        with self.driver.session() as session:
            results = session.run(query, limit=limit)
            return [dict(record) for record in results]

    def update_node_embedding(self, name: str, embedding: list[float]) -> bool:
        """
        Saves the embedding vector to a specific node.
        """
        query = """
        MATCH (n:Node {name: $name})
        SET n.embedding = $embedding
        RETURN n
        """
        with self.driver.session() as session:
            result = session.run(query, name=name, embedding=embedding)
            return result.single() is not None

    def get_orphan_tasks(self, scopes: list[str] = None, namespaces: list[str] = None) -> list[dict]:
        """
        Finds Task nodes that have NO relationships attached to them AND
        are not explicitly marked to be kept as orphans.
        """
        scope_clause = self._get_filter_clause(scopes, namespaces=namespaces)
        where_scope = f"AND {scope_clause}" if scope_clause else ""
        
        query = f"""
        MATCH (n:Task)
        WHERE NOT (n)-[]-()
        AND coalesce(n.allow_orphan, false) = false
        {where_scope}
        RETURN n.name as name, labels(n) as labels, properties(n) as props
        """
        with self.driver.session() as session:
            results = session.run(query)
            return [dict(record) for record in results]

