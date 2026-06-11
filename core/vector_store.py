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
            import requests
            url = config.get("base_url", "http://localhost:11434")
            model = config.get("model_name", "nomic-embed-text")
            timeout = config.get("timeout", 300)

            class OllamaEmbeddingFunctionWithTimeout:
                def __init__(self, url, model_name, timeout):
                    self.url = url.rstrip("/")
                    self.model_name = model_name
                    self.timeout = timeout

                def name(self):
                    return "ollama"

                def _embed(self, texts):
                    embeddings = []
                    for text in texts:
                        response = requests.post(
                            f"{self.url}/api/embeddings",
                            json={"model": self.model_name, "prompt": text},
                            timeout=self.timeout
                        )
                        response.raise_for_status()
                        embeddings.append(response.json()["embedding"])
                    return embeddings

                def __call__(self, input):
                    return self._embed(input)

                def embed_documents(self, input):
                    return self._embed(input)

                def embed_query(self, input):
                    return self._embed(input)

            return OllamaEmbeddingFunctionWithTimeout(url=url, model_name=model, timeout=timeout)

        return None  # mock/default: ChromaDB uses all-MiniLM-L6-v2 locally

    @staticmethod
    def _sanitize_metadata(node_id: str, metadata: dict, display_name: str = None) -> dict:
        """Coerce metadata to Chroma-safe scalar types and stamp original_name.

        original_name is the human-readable display name (file basename without
        extension), used in search results. node_id is the internal path-based key.
        """
        safe_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                safe_metadata[k] = v
            elif isinstance(v, list):
                safe_metadata[k] = ",".join(str(i) for i in v)
        safe_metadata['original_name'] = display_name if display_name is not None else node_id
        return safe_metadata

    def upsert_node(self, node_id: str, body: str, metadata: dict, display_name: str = None):
        """Upsert a document into the vector space.

        node_id is the path-based primary key (e.g. 'ganaghello__spazi__stalla__stalla').
        display_name is the human-readable basename (e.g. 'Stalla'); stored as
        original_name in metadata and returned by semantic_search as 'name'.
        Re-embeds only when body changed (callers are expected to guard with a body hash).
        """
        norm_id = normalize_node_name(node_id)
        safe_metadata = self._sanitize_metadata(node_id, metadata, display_name)

        embed_text = body[:4000] if body.strip() else "_EMPTY_"
        self.collection.upsert(
            ids=[norm_id],
            documents=[embed_text],
            metadatas=[safe_metadata]
        )
        logger.debug(f"Upserted {norm_id} (display: {display_name or node_id}) in ChromaDB")

    def update_metadata(self, node_id: str, metadata: dict, display_name: str = None):
        """Update an existing node's metadata WITHOUT re-embedding the document.

        Used when only the frontmatter changed (scope, project, enriched_hash,
        ...) but the body is unchanged: avoids a needless embedding call and the
        re-embed echo-loop. No-op if the node isn't in the collection yet.
        """
        norm_id = normalize_node_name(node_id)
        if not self.get_node(norm_id):
            return
        self.collection.update(
            ids=[norm_id],
            metadatas=[self._sanitize_metadata(node_id, metadata, display_name)],
        )

    def semantic_search(self, query: str, scopes: list = None, limit: int = 5):
        """Retrieve top K nodes semantically similar to query.

        Each result dict contains:
          name     - human-readable display name (original_name from metadata)
          node_id  - internal path-based ID (ChromaDB document ID)
          document - embedded text
          metadata - full metadata dict
          distance - cosine distance (lower = more similar)
        """
        where_filter = None
        if scopes and "*" not in scopes:
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
                    "node_id": doc_id,
                    "document": results["documents"][0][i],
                    "metadata": meta,
                    "distance": results["distances"][0][i]
                })
        return parsed_results

    def get_node(self, name: str):
        """Retrieve a specific node by its normalized path-based ID."""
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
        """Returns nodes semantically similar to node_name above the given threshold.

        Similarity = 1 - cosine_distance. Excludes the node itself and obs_ nodes.
        Returns node_id (path-based ID) as 'name' for Gardener edge creation.
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
        """Returns all nodes in the collection."""
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
