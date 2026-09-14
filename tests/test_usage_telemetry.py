"""Telemetry on who reads the graph, and whether resurfacing leads anywhere.

Why these tests exist: `interaction_count` conflates reads, file edits and
proximity propagation, and nothing recorded which client called or what the
Gardener had resurfaced. That made two questions unanswerable, "is Mnemosyne
ever read, and by whom" and "does resurfacing produce useful recalls", and both
were answered by guesswork for months. The counters below are the instrument;
these tests keep them honest.
"""
import os
import sys
import time
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.kuzu_manager import KuzuManager
from core.attention import AttentionModel
from core.authz import agent_label
from core import thermal_backup

POOL = 64 * 1024 * 1024


class AgentLabelTest(unittest.TestCase):
    def test_label_from_key_prefix(self):
        self.assertEqual(agent_label("mnm_sk_mcp_ABC123"), "mcp")
        self.assertEqual(agent_label("mnm_sk_alfred_XYZ"), "alfred")
        self.assertEqual(agent_label("mnm_sk_ganaghello_Q1"), "ganaghello")

    def test_unknown_for_malformed_keys(self):
        for key in ("garbage", "", None, "mnm_sk_"):
            self.assertEqual(agent_label(key), "unknown")


class UsageTelemetryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.km = KuzuManager(db_path=os.path.join(self.dir, "kz"), buffer_pool_size=POOL)
        self.am = AttentionModel(self.km, config={})
        for name in ("alpha", "beta", "gamma"):
            self.km.add_node(name, node_type="Node", scope="Public")

    def tearDown(self):
        del self.am
        del self.km
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_file_edit_is_an_interaction_but_not_a_read(self):
        """The distinction the old single counter could not make."""
        self.am.record_interaction("gamma", "file_edit", agent="watcher")
        row = self.km.conn.execute(
            "MATCH (n:Node {name:'gamma'}) RETURN n.interaction_count, n.query_count"
        ).get_next()
        self.assertEqual(row[0], 1, "a file edit is still an interaction")
        self.assertEqual(row[1], 0, "but it must not count as a read")

    def test_reads_are_attributed_to_the_calling_client(self):
        self.am.record_interaction("alpha", "mcp_query", agent="mcp")
        self.am.record_interaction("alpha", "mcp_query", agent="mcp")
        self.am.record_interaction("beta", "mcp_query", agent="alfred")
        self.am.record_interaction("gamma", "file_edit", agent="watcher")

        stats = self.km.usage_stats()
        self.assertEqual(stats["queries_total"], 3)
        self.assertEqual(stats["nodes_ever_queried"], 2, "gamma was edited, never read")
        self.assertEqual(stats["queries_by_agent"], {"mcp": 2, "alfred": 1})

    def test_missing_agent_does_not_erase_the_previous_one(self):
        self.am.record_interaction("alpha", "mcp_query", agent="mcp")
        self.am.record_interaction("alpha", "mcp_query")  # caller with no label
        row = self.km.conn.execute(
            "MATCH (n:Node {name:'alpha'}) RETURN n.last_accessed_agent"
        ).get_next()
        self.assertEqual(row[0], "mcp")

    def test_resurfacing_efficacy_counts_only_what_followed(self):
        self.km.mark_resurfaced(["alpha", "beta"])
        time.sleep(0.02)
        self.am.record_interaction("alpha", "mcp_query", agent="mcp")

        res = self.km.usage_stats()["resurfacing"]
        self.assertEqual(res["resurfaced"], 2)
        self.assertEqual(res["followed_by_interaction"], 1, "only alpha was picked back up")
        self.assertEqual(res["rate"], 0.5)

    def test_resurfacing_rate_is_none_when_nothing_was_resurfaced(self):
        """No resurfacing must read as 'not measured', never as a rate of zero."""
        self.assertIsNone(self.km.usage_stats()["resurfacing"]["rate"])

    def test_stale_resurfacing_falls_outside_the_window(self):
        self.km.mark_resurfaced(["alpha"], ts=time.time() - 40 * 86400)
        self.assertEqual(self.km.usage_stats(window_days=14)["resurfacing"]["resurfaced"], 0)

    def test_counters_survive_a_database_rebuild(self):
        """Without this, a rebuild would silently reset the measurement itself."""
        self.am.record_interaction("alpha", "mcp_query", agent="mcp")
        self.am.record_interaction("beta", "mcp_query", agent="alfred")
        self.km.mark_resurfaced(["alpha"])

        path = os.path.join(self.dir, "thermal.json")
        self.assertFalse(thermal_backup.export(self.km, path)["skipped"])

        self.km.conn.execute(
            "MATCH (n:Node) SET n.query_count = 0, n.last_accessed_agent = '', n.last_resurfaced_at = 0.0"
        )
        self.assertEqual(self.km.usage_stats()["queries_total"], 0)

        thermal_backup.restore(self.km, path)
        stats = self.km.usage_stats()
        self.assertEqual(stats["queries_total"], 2)
        self.assertEqual(stats["queries_by_agent"], {"mcp": 1, "alfred": 1})
        self.assertEqual(stats["resurfacing"]["resurfaced"], 1)


class SchemaMigrationTest(unittest.TestCase):
    def test_columns_are_added_to_a_pre_existing_database(self):
        """A database created before the telemetry must migrate, not crash."""
        directory = tempfile.mkdtemp()
        try:
            path = os.path.join(directory, "kz")
            km = KuzuManager(db_path=path, buffer_pool_size=POOL)
            for column in ("query_count", "last_accessed_agent", "last_resurfaced_at"):
                km.conn.execute(f"ALTER TABLE Node DROP {column}")
            km.add_node("delta", node_type="Node", scope="Public")
            del km

            km = KuzuManager(db_path=path, buffer_pool_size=POOL)  # reopen: migrates
            AttentionModel(km, config={}).record_interaction("delta", "mcp_query", agent="mcp")
            self.assertEqual(km.usage_stats()["queries_by_agent"], {"mcp": 1})
            del km
        finally:
            shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
