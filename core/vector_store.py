import chromadb
from chromadb.config import Settings
import logging
import os
import uuid
from core.utils import normalize_node_name

logger = logging.getLogger(__name__)

class VectorStore:
    """
    Manages semantic search, metadata filtering and document embeddings via ChromaDB.
    This acts as the persistence layer for Mnemosyne's frontmatter and document bodies.
    """
    def __init__(self, db_path="./data/chroma_db", collection_name="mnemosyne_wiki", embedding_config: dict = None):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.db_path)
        ef = self._build_embedding_function(embedding_config or {})
        collection_kwargs = {"name": collection_name, "metadata": {"hnsw:space": "cosine"}}
        if ef:
            collection_kwargs["embedding_function"] = ef
        self.collection = self.client.get_or_create_collection(**collection_kwargs)
        mode = (embedding_config or {}).get("mode", "default")
        logger.info(f"Initialized ChromaDB at {self.db_path} (embedding mode: {mode})")

    def _build_embedding_function(self, config: dict):
        mode = config.get("mode", "mock")

        if mode == "openai":
            from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
            api_key_raw = config.get("api_key", "")
            if api_key_raw and (api_key_raw.startswith("sk-") or len(api_key_raw) > 30):
                api_key = api_key_raw
            else:
                api_key = os.getenv(api_key_raw) if api_key_raw else os.getenv("OPENAI_API_KEY")
            model = config.get("model_name", "text-embedding-3-small")
            kwargs = {"api_key": api_key, "model_name": model}
            if config.get("base_url"):
                kwargs["api_base"] = config["base_url"]
            return OpenAIEmbeddingFunction(**kwargs)

        if mode == "ollama":
            from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
            url = config.get("base_url", "http://localhost:11434")
            model = config.get("model_name", "nomic-embed-text")
            return OllamaEmbeddingFunction(url=url, model_name=model)

        return None  # mock/default: ChromaDB uses all-MiniLM-L6-v2 locally

    def upsert_node(self, name: str, body: str, metadata: dict):
        """
        Upserts a full markdown document and its metadata into the vector space.
        Uses normalized 'name' as the canonical ID.
        """
        norm_name = normalize_node_name(name)
        # Chroma metadata must be scalar types (str, int, float, bool)
        safe_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                safe_metadata[k] = v
            elif isinstance(v, list):
                safe_metadata[k] = ",".join(str(i) for i in v)
                
        # We store the original name in metadata while using normalized for PK
        safe_metadata['original_name'] = name

        self.collection.upsert(
            ids=[norm_name],
            documents=[body] if body.strip() else ["_EMPTY_"],
            metadatas=[safe_metadata]
        )
        logger.debug(f"Upserted {norm_name} (orig: {name}) in ChromaDB")

    def semantic_search(self, query: str, scopes: list = None, limit: int = 5):
        """
        Retrieves top K nodes semantically similar to query.
        Also parses scope filtering.
        """
        where_filter = None
        if scopes and "*" not in scopes:
            # We assume scopes are mapped under "scope" metadata or we can filter by "type"
            # For this MVP we just create an IN filter if multiple, or simple EQUALS
            if len(scopes) == 1:
                where_filter = {"scope": scopes[0]}
            else:
                where_filter = {"scope": {"$in": scopes}}

        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_filter
        )
        
        parsed_results = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                parsed_results.append({
                    "name": meta.get("original_name", doc_id),
                    "document": results["documents"][0][i],
                    "metadata": meta,
                    "distance": results["distances"][0][i]
                })
        return parsed_results

    def get_node(self, name: str):
        """
        Retrieve a specific node by its normalized name (ID).
        """
        norm_name = normalize_node_name(name)
        results = self.collection.get(
            ids=[norm_name],
            include=["metadatas", "documents"]
        )
        if results and results.get("ids") and len(results["ids"]) > 0:
            return {
                "name": results["ids"][0],
                "document": results["documents"][0],
                "metadata": results["metadatas"][0]
            }
        return None

    def delete_node(self, name: str):
        norm_name = normalize_node_name(name)
        try:
            self.collection.delete(ids=[norm_name])
            return True
        except ValueError:
            return False

    def find_similar_nodes(self, node_name: str, similarity_threshold: float = 0.85, limit: int = 5):
        """
        Returns nodes semantically similar to node_name above the given threshold.
        Similarity = 1 - cosine_distance. Excludes the node itself and Obs_ nodes.
        """
        node_data = self.get_node(node_name)
        if not node_data:
            return []
        document = node_data.get('document', '')
        if not document or document == '_EMPTY_':
            return []

        results = self.collection.query(
            query_texts=[document],
            n_results=limit + 1,
        )

        norm_name = normalize_node_name(node_name)
        similar = []
        if results and results.get('ids') and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                if doc_id == norm_name or doc_id.startswith('obs_'):
                    continue
                similarity = 1.0 - results['distances'][0][i]
                if similarity >= similarity_threshold:
                    similar.append({'name': doc_id, 'similarity': round(similarity, 4)})
        return similar

    def list_nodes(self):
        """
        Returns all nodes in the collection.
        """
        results = self.collection.get(
            include=["metadatas"]
        )
        nodes = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"]):
                 nodes.append({
                     "name": doc_id,
                     "metadata": results["metadatas"][i]
                 })
        return nodes
