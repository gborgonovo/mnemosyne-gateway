"""Proves find_similar_nodes reuses stored embeddings instead of re-embedding.

The Gardener calls find_similar_nodes for every hot node each cycle. Previously
this used query_texts=[document], which re-embeds the text via the embedding
backend (ollama, CPU-bound) — the root cause of the embedding bursts that
saturated the production VPS. This test injects a counting embedding function
and asserts that find_similar_nodes generates zero new embeddings.
"""
import os
import hashlib
import tempfile
import unittest

from core.vector_store import VectorStore, CHUNK_THRESHOLD


class CountingEF:
    """Deterministic embedding function that counts how many texts it embeds."""
    def __init__(self):
        self.calls = 0

    def name(self):
        return "counting"

    def __call__(self, input):
        self.calls += len(input)
        return [self._vec(t) for t in input]

    @staticmethod
    def _vec(text):
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in h[:16]]  # 16-dim deterministic vector


class TestFindSimilarReuse(unittest.TestCase):
    def _store(self, tmp, ef):
        return VectorStore(db_path=os.path.join(tmp, "chroma"),
                           collection_name="reuse_test",
                           embedding_function=ef)

    def test_no_reembed_single_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            ef = CountingEF()
            vs = self._store(tmp, ef)
            vs.upsert_node("alpha", "il gatto sale sul tetto", {"scope": "Public"}, "Alpha")
            vs.upsert_node("beta", "il felino sale sul tetto", {"scope": "Public"}, "Beta")

            before = ef.calls
            res = vs.find_similar_nodes("alpha", similarity_threshold=0.0, limit=5)

            # The whole point: zero new embeddings generated
            self.assertEqual(ef.calls, before,
                             "find_similar_nodes must not generate new embeddings")
            # And it still works: finds the other node, never itself
            names = [r["name"] for r in res]
            self.assertIn("beta", names)
            self.assertNotIn("alpha", names)

    def test_no_reembed_chunked(self):
        with tempfile.TemporaryDirectory() as tmp:
            ef = CountingEF()
            vs = self._store(tmp, ef)
            big = "paragrafo di prova. " * 1000  # > CHUNK_THRESHOLD → chunked
            self.assertGreater(len(big), CHUNK_THRESHOLD)
            vs.upsert_node("big__node", big, {"scope": "Public"}, "Big")
            vs.upsert_node("alpha", "qualcosa di diverso", {"scope": "Public"}, "Alpha")

            before = ef.calls
            vs.find_similar_nodes("big__node", similarity_threshold=0.0, limit=5)

            self.assertEqual(ef.calls, before,
                             "find_similar_nodes must not re-embed a chunked node")

    def test_missing_vector_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            ef = CountingEF()
            vs = self._store(tmp, ef)
            vs.upsert_node("alpha", "testo", {"scope": "Public"}, "Alpha")
            # Unknown node: no stored vector, no embedding, empty result
            before = ef.calls
            res = vs.find_similar_nodes("does_not_exist")
            self.assertEqual(res, [])
            self.assertEqual(ef.calls, before)


if __name__ == "__main__":
    unittest.main()
