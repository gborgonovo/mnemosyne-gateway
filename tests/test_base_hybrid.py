import sys
import os
import shutil
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore

class TestHybridArchitecture(unittest.TestCase):

    def setUp(self):
        self.kuzu_path = "./data/test_kuzu"
        self.chroma_path = "./data/test_chroma"
        # Always start from a clean state
        if os.path.exists(self.kuzu_path):
            os.remove(self.kuzu_path)
        if os.path.exists(self.chroma_path):
            shutil.rmtree(self.chroma_path)
        self.kuzu = KuzuManager(db_path=self.kuzu_path)
        self.chroma = VectorStore(db_path=self.chroma_path, collection_name="test_col")

    def tearDown(self):
        self.kuzu.close()
        if os.path.exists(self.kuzu_path):
            os.remove(self.kuzu_path)
        if os.path.exists(self.chroma_path):
            shutil.rmtree(self.chroma_path)

    def test_kuzu_thermal_propagation(self):
        self.kuzu.add_node("RootNode", initial_activation=1.0)
        self.kuzu.add_node("ChildNode", initial_activation=0.0)
        self.kuzu.add_edge("RootNode", "ChildNode", "LINKS_TO", weight=1.0)
        
        root = self.kuzu.get_node("RootNode")
        self.assertEqual(root["activation_level"], 1.0)
        
        neighbors = self.kuzu.get_neighbors("RootNode")
        self.assertEqual(len(neighbors), 1)

    def test_chroma_semantic(self):
        metadata = {"type": "Test", "author": "Bot"}
        self.chroma.upsert_node("Doc1", "This is a document about artificial intelligence.", metadata)
        
        results = self.chroma.semantic_search("intelligence", limit=1)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Doc1")

if __name__ == '__main__':
    unittest.main()
