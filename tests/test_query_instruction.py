"""Proves the query/document asymmetry fix: a query_instruction prefixes
search QUERIES only, never documents, and is off by default.

Why this exists: Qwen3-Embedding (the production model) is an instruction-tuned,
asymmetric embedder. Fed a query exactly like a document, it produces distances
that are all roughly equal, and recall degrades accordingly (measured
2026-09-14: recall@1 0.40 -> 0.60, temporal recall@1 0.00 -> 0.33 once queries
carry the instruction). The fix has to touch only semantic_search's query text,
never upsert_node's document text and never find_similar_nodes (which reuses a
stored embedding, no new text at all) — this is what these tests pin down.
"""
import os
import tempfile
import unittest

from core.vector_store import VectorStore


class RecordingEF:
    """Deterministic embedding function that records every text it was asked
    to embed, so tests can assert on exactly what reached the model.

    Implements the full ChromaDB EmbeddingFunction protocol (embed_documents
    AND embed_query, not just __call__) because modern ChromaDB routes a
    query() call through embed_query specifically — mirroring how the real
    OllamaEmbeddingFunctionWithTimeout in core/vector_store.py is built.
    """
    def __init__(self):
        self.seen = []

    def name(self):
        return "recording"

    def _embed(self, input):
        self.seen.extend(input)
        return [self._vec(t) for t in input]

    def __call__(self, input):
        return self._embed(input)

    def embed_documents(self, input):
        return self._embed(input)

    def embed_query(self, input):
        return self._embed(input)

    @staticmethod
    def _vec(text):
        # Distinct-but-deterministic: good enough to get back sane nearest
        # neighbours without hitting a real embedding backend.
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in h[:16]]


class TestQueryInstruction(unittest.TestCase):
    def _store(self, tmp, ef, instruction=""):
        return VectorStore(db_path=os.path.join(tmp, "chroma"), collection_name="qi_test",
                           embedding_function=ef,
                           embedding_config={"query_instruction": instruction})

    def test_default_is_off_and_unchanged(self):
        """No instruction configured: the query reaches the model verbatim,
        exactly as before this fix. Backward compatible by construction."""
        with tempfile.TemporaryDirectory() as tmp:
            ef = RecordingEF()
            vs = self._store(tmp, ef)  # instruction="" (the default)
            vs.upsert_node("alpha", "il gatto sale sul tetto", {"scope": "Public"}, "Alpha")
            ef.seen.clear()

            vs.semantic_search("dove sale il gatto")

            self.assertIn("dove sale il gatto", ef.seen)

    def test_instruction_prefixes_the_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            ef = RecordingEF()
            instruction = "Instruct: retrieve relevant documents\nQuery: "
            vs = self._store(tmp, ef, instruction=instruction)
            vs.upsert_node("alpha", "il gatto sale sul tetto", {"scope": "Public"}, "Alpha")
            ef.seen.clear()

            vs.semantic_search("dove sale il gatto")

            self.assertIn(instruction + "dove sale il gatto", ef.seen)
            self.assertNotIn("dove sale il gatto", ef.seen,
                             "the bare query must not also reach the model")

    def test_instruction_never_reaches_documents(self):
        """The bug being fixed was symmetry: same text path for queries and
        documents. Documents must stay exactly as written, prefix or not."""
        with tempfile.TemporaryDirectory() as tmp:
            ef = RecordingEF()
            instruction = "Instruct: retrieve relevant documents\nQuery: "
            vs = self._store(tmp, ef, instruction=instruction)

            vs.upsert_node("alpha", "il gatto sale sul tetto", {"scope": "Public"}, "Alpha")

            self.assertIn("il gatto sale sul tetto", ef.seen)
            self.assertTrue(all(instruction not in t for t in ef.seen),
                            "a document body was embedded with the query instruction attached")

    def test_find_similar_nodes_is_unaffected(self):
        """find_similar_nodes reuses a stored embedding (doc-to-doc comparison):
        it must never see the query_instruction, because nothing there is a
        search query in the asymmetric sense."""
        with tempfile.TemporaryDirectory() as tmp:
            ef = RecordingEF()
            instruction = "Instruct: retrieve relevant documents\nQuery: "
            vs = self._store(tmp, ef, instruction=instruction)
            vs.upsert_node("alpha", "il gatto sale sul tetto", {"scope": "Public"}, "Alpha")
            vs.upsert_node("beta", "il felino sale sul tetto", {"scope": "Public"}, "Beta")
            calls_before = len(ef.seen)

            vs.find_similar_nodes("alpha", similarity_threshold=0.0, limit=5)

            self.assertEqual(len(ef.seen), calls_before,
                             "find_similar_nodes must not call the embedder at all")

    def test_retrieval_actually_improves_with_the_instruction(self):
        """Not just plumbing: with a fake embedder whose vectors are sensitive
        to the exact string, matching the instruction on both sides of a
        precomputed offset should still retrieve correctly. This guards
        against a fix that prefixes the query but breaks the query path."""
        with tempfile.TemporaryDirectory() as tmp:
            ef = RecordingEF()
            vs = self._store(tmp, ef, instruction="Instruct: search\nQuery: ")
            vs.upsert_node("rogito", "imposte 3915 euro notaio 2591 euro", {"scope": "Public"}, "Rogito")
            vs.upsert_node("altro", "tegole tettoia nord da sistemare", {"scope": "Public"}, "Altro")

            results = vs.semantic_search("imposte 3915 euro notaio 2591 euro")

            self.assertEqual(results[0]["name"], "Rogito")


if __name__ == "__main__":
    unittest.main()
