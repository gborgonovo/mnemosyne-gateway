import chromadb
from chromadb.config import Settings
import logging
import os
import uuid
from core.utils import normalize_node_name
from core.chunking import HeuristicChunker

logger = logging.getLogger(__name__)

# Bodies larger than this are split into chunks before embedding.
# Below this threshold, behaviour is identical to the previous single-doc path.
CHUNK_THRESHOLD = 4000
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200


class VectorStore:
    """
    Manages semantic search, metadata filtering and document embeddings via ChromaDB.
    This acts as the persistence layer for Mnemosyne's frontmatter and document bodies.

    Large nodes (body > CHUNK_THRESHOLD chars) are stored as multiple ChromaDB
    documents with IDs ``{node_id}__c0``, ``__c1``, etc.  All public methods
    accept and return canonical node_ids (path-based, no chunk suffix).
    """
    def __init__(self, db_path="./data/chroma_db", collection_name="mnemosyne_wiki", embedding_config: dict = None,
                 embedding_function=None):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.db_path)
        # embedding_function lets tests inject a deterministic/counting EF;
        # production builds it from the config.
        ef = embedding_function or self._build_embedding_function(embedding_config or {})
        collection_kwargs = {"name": collection_name, "metadata": {"hnsw:space": "cosine"}}
        if ef:
            collection_kwargs["embedding_function"] = ef
        self.collection = self.client.get_or_create_collection(**collection_kwargs)
        mode = (embedding_config or {}).get("mode", "default")
        logger.info(f"Initialized ChromaDB at {self.db_path} (embedding mode: {mode})")

        self._chunker = HeuristicChunker(max_chars_per_chunk=CHUNK_SIZE, overlap_chars=CHUNK_OVERLAP)

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

    def _get_chunks(self, norm_id: str):
        """Return (ids, metadatas, documents) for all chunks of norm_id, or empty lists."""
        try:
            r = self.collection.get(where={"_parent_id": norm_id}, include=["metadatas", "documents"])
            if r and r.get("ids"):
                return r["ids"], r["metadatas"], r["documents"]
        except Exception:
            pass
        return [], [], []

    def upsert_node(self, node_id: str, body: str, metadata: dict, display_name: str = None):
        """Upsert a document into the vector space.

        node_id is the path-based primary key (e.g. 'ganaghello__spazi__stalla__stalla').
        display_name is the human-readable basename (e.g. 'Stalla'); stored as
        original_name in metadata and returned by semantic_search as 'name'.
        Re-embeds only when body changed (callers are expected to guard with a body hash).

        Bodies > CHUNK_THRESHOLD chars are split into chunks stored as
        '{norm_id}__c0', '__c1', etc., each embedded independently.
        """
        norm_id = normalize_node_name(node_id)
        safe_metadata = self._sanitize_metadata(node_id, metadata, display_name)
        embed_text = body.strip() if body.strip() else "_EMPTY_"

        if len(embed_text) > CHUNK_THRESHOLD:
            chunks = self._chunker.chunk_text(embed_text)
            if not chunks:
                chunks = [embed_text[:CHUNK_THRESHOLD]]

            # Remove old single-doc entry (transition: was small, now large)
            try:
                self.collection.delete(ids=[norm_id])
            except Exception:
                pass

            # Remove old chunk entries (body changed, chunk count may differ)
            old_ids, _, _ = self._get_chunks(norm_id)
            if old_ids:
                self.collection.delete(ids=old_ids)

            chunk_count = len(chunks)
            chunk_ids = [f"{norm_id}__c{i}" for i in range(chunk_count)]
            chunk_metas = []
            for i in range(chunk_count):
                cm = dict(safe_metadata)
                cm["_parent_id"] = norm_id
                cm["_chunk_index"] = i
                cm["_chunk_count"] = chunk_count
                chunk_metas.append(cm)

            self.collection.upsert(ids=chunk_ids, documents=chunks, metadatas=chunk_metas)
            logger.debug(f"Upserted {norm_id} ({chunk_count} chunks) in ChromaDB")
        else:
            # Remove old chunk entries (transition: was large, now small)
            old_ids, _, _ = self._get_chunks(norm_id)
            if old_ids:
                self.collection.delete(ids=old_ids)

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
        safe_meta = self._sanitize_metadata(node_id, metadata, display_name)

        # Try single-doc node first
        direct = self.collection.get(ids=[norm_id])
        if direct and direct.get("ids"):
            self.collection.update(ids=[norm_id], metadatas=[safe_meta])
            return

        # Chunked node: update all chunks, preserving chunk-specific fields
        chunk_ids, chunk_metas_existing, _ = self._get_chunks(norm_id)
        if not chunk_ids:
            return
        updated_metas = []
        for i, existing in enumerate(chunk_metas_existing):
            cm = dict(safe_meta)
            cm["_parent_id"] = norm_id
            cm["_chunk_index"] = existing.get("_chunk_index", i)
            cm["_chunk_count"] = existing.get("_chunk_count", len(chunk_ids))
            updated_metas.append(cm)
        self.collection.update(ids=chunk_ids, metadatas=updated_metas)

    def semantic_search(self, query: str, scopes: list = None, limit: int = 5):
        """Retrieve top K nodes semantically similar to query.

        Each result dict contains:
          name     - human-readable display name (original_name from metadata)
          node_id  - internal path-based ID (canonical, not chunk-suffixed)
          document - embedded text of the best-matching chunk
          metadata - full metadata dict
          distance - cosine distance (lower = more similar)

        When a large node is split into chunks, only the best-scoring chunk is
        returned, deduplicated by parent node_id.
        """
        where_filter = None
        if scopes and "*" not in scopes:
            if len(scopes) == 1:
                where_filter = {"scope": scopes[0]}
            else:
                where_filter = {"scope": {"$in": scopes}}

        # Fetch extra candidates to account for chunk deduplication
        total_docs = self.collection.count()
        if total_docs == 0:
            return []
        fetch_limit = min(limit * 4, 50, total_docs)

        results = self.collection.query(
            query_texts=[query],
            n_results=fetch_limit,
            where=where_filter
        )

        parsed_results = []
        seen_parents = set()

        if results and results.get("ids") and len(results["ids"]) > 0:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                # Resolve parent: chunks carry _parent_id; single-docs use their own id
                parent_id = meta.get("_parent_id", doc_id)

                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)

                parsed_results.append({
                    "name": meta.get("original_name", parent_id),
                    "node_id": parent_id,
                    "document": results["documents"][0][i],
                    "metadata": meta,
                    "distance": results["distances"][0][i]
                })

                if len(parsed_results) >= limit:
                    break

        return parsed_results

    def get_node(self, name: str):
        """Retrieve a specific node by its normalized path-based ID.

        For chunked nodes the direct lookup finds nothing; falls back to
        returning chunk 0 as a metadata/document proxy.
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

        # Fallback: chunked node — return chunk 0 as proxy
        chunk_ids, chunk_metas, chunk_docs = self._get_chunks(norm_name)
        if chunk_ids:
            # Find chunk 0
            for i, meta in enumerate(chunk_metas):
                if meta.get("_chunk_index", -1) == 0:
                    return {"name": norm_name, "document": chunk_docs[i], "metadata": meta}
            # Fallback to first returned chunk
            return {"name": norm_name, "document": chunk_docs[0], "metadata": chunk_metas[0]}

        return None

    def delete_node(self, name: str):
        norm_name = normalize_node_name(name)
        deleted = False

        try:
            self.collection.delete(ids=[norm_name])
            deleted = True
        except ValueError:
            pass

        # Also delete chunk entries
        chunk_ids, _, _ = self._get_chunks(norm_name)
        if chunk_ids:
            self.collection.delete(ids=chunk_ids)
            deleted = True

        return deleted

    def _get_stored_embedding(self, norm_name: str):
        """Return the embedding vector already stored for a node, or None.

        Single-doc nodes store it under norm_name; chunked nodes under chunk 0.
        Avoids re-embedding the document: the vector was computed at upsert time.
        """
        direct = self.collection.get(ids=[norm_name], include=["embeddings"])
        if direct and direct.get("ids"):
            embs = direct.get("embeddings")
            if embs is not None and len(embs) > 0:
                return embs[0]
            return None

        # Chunked node: use chunk 0's vector. NB: ChromaDB returns embeddings as
        # numpy arrays, so never use them in a boolean/`or` context.
        r = self.collection.get(where={"_parent_id": norm_name},
                                include=["embeddings", "metadatas"])
        if not (r and r.get("ids")):
            return None
        embs = r.get("embeddings")
        if embs is None or len(embs) == 0:
            return None
        metas = r.get("metadatas") or []
        for i, m in enumerate(metas):
            if m.get("_chunk_index", -1) == 0 and i < len(embs):
                return embs[i]
        return embs[0]

    def find_similar_nodes(self, node_name: str, similarity_threshold: float = 0.85, limit: int = 5):
        """Returns nodes semantically similar to node_name above the given threshold.

        Similarity = 1 - cosine_distance. Excludes the node itself, obs_ nodes,
        and deduplicates across chunks of the same parent node.
        Returns node_id (path-based ID, no chunk suffix) as 'name' for Gardener edge creation.

        Reuses the node's stored embedding (query_embeddings) instead of
        re-embedding its text: the Gardener calls this for every hot node each
        cycle, and re-embedding via the (possibly remote/CPU-bound) embedding
        backend was the source of mass embedding bursts.
        """
        norm_name = normalize_node_name(node_name)

        vector = self._get_stored_embedding(norm_name)
        if vector is None:
            return []

        total_docs = self.collection.count()
        if total_docs <= 1:
            return []
        fetch_n = min((limit + 1) * 4, total_docs)

        results = self.collection.query(
            query_embeddings=[vector],
            n_results=fetch_n,
        )

        seen_parents = {norm_name}
        similar = []

        if results and results.get('ids') and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                meta = results['metadatas'][0][i] if results.get('metadatas') else {}
                parent_id = meta.get("_parent_id", doc_id)

                if parent_id in seen_parents or parent_id.startswith('obs_'):
                    continue

                similarity = 1.0 - results['distances'][0][i]
                if similarity >= similarity_threshold:
                    seen_parents.add(parent_id)
                    similar.append({'name': parent_id, 'similarity': round(similarity, 4)})
                    if len(similar) >= limit:
                        break

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
