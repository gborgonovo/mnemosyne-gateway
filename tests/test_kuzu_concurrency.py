"""B5: stress test for the KuzuManager reentrant lock.

A single kuzu.Connection is shared across the FastAPI threadpool, the watchdog
thread, the enrichment thread and the gardener. This test hammers it from many
threads with mixed reads/writes (including the nested add_edge -> add_node and
update_interaction -> get_node paths that rely on the lock being reentrant) and
asserts no exception escapes and the final graph is consistent.

Run: python3 -m unittest tests/test_kuzu_concurrency.py
"""
import os
import sys
import shutil
import tempfile
import threading
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.kuzu_manager import KuzuManager


class TestKuzuConcurrency(unittest.TestCase):
    def setUp(self):
        self.dbroot = tempfile.mkdtemp()
        self.kuzu = KuzuManager(db_path=os.path.join(self.dbroot, "kuzu"))

    def tearDown(self):
        self.kuzu.close()
        shutil.rmtree(self.dbroot, ignore_errors=True)

    def test_concurrent_mixed_operations(self):
        n_threads = 12
        per_thread = 40
        errors = []

        def worker(tid):
            try:
                for i in range(per_thread):
                    node = f"node_{tid}_{i}"
                    self.kuzu.add_node(node, node_type="Node", scope="Private")
                    # add_edge internally calls add_node twice -> exercises RLock reentrancy
                    self.kuzu.add_edge(node, f"hub_{tid}", "RELATED_TO")
                    # update_interaction internally calls get_node -> reentrancy again
                    self.kuzu.update_interaction(node, boost=0.1)
                    self.kuzu.get_neighbors(node, scopes=["Private"])
                    self.kuzu.get_node(node)
            except Exception as e:  # noqa: BLE001 - capture to fail in main thread
                errors.append((tid, repr(e)))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"concurrent ops raised: {errors[:3]}")

        # Every node each thread created must exist with its edge to the hub.
        for tid in range(n_threads):
            for i in range(per_thread):
                node = f"node_{tid}_{i}"
                self.assertIsNotNone(self.kuzu.get_node(node), f"{node} missing")
            edges = self.kuzu.get_outgoing_edges(f"node_{tid}_0")
            self.assertIn("RELATED_TO", {e["type"] for e in edges})


if __name__ == "__main__":
    unittest.main(verbosity=2)
