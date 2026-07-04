"""Round-trip tests for the thermal-state backup (core/thermal_backup.py).

The thermal state (activation, last_interaction, interaction_count,
last_decay_applied) lives only in KuzuDB and is lost on a rebuild. These drive a
real isolated KuzuManager: set some state, export to JSON, wipe it, restore, and
assert the exact values come back — interaction_count included, which the
date-based seed_thermal_activation.py never recovers.

Run: python3 -m unittest tests/test_thermal_backup.py
"""
import os
import sys
import json
import shutil
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.kuzu_manager import KuzuManager
from core import thermal_backup


class TestThermalBackup(unittest.TestCase):
    def setUp(self):
        self.dbroot = tempfile.mkdtemp()
        self.kuzu = KuzuManager(db_path=os.path.join(self.dbroot, "kuzu"))
        self.snap = os.path.join(self.dbroot, "thermal_state.json")

    def tearDown(self):
        self.kuzu.close()
        shutil.rmtree(self.dbroot, ignore_errors=True)

    def _thermal(self, name):
        n = self.kuzu.get_node(name)
        return None if n is None else (
            round(n["activation_level"], 6), n["interaction_count"])

    def test_export_restore_round_trip(self):
        # Two nodes with distinct, non-default thermal state.
        self.kuzu.add_node("caldo", initial_activation=0.9)
        self.kuzu.update_interaction("caldo", boost=0.0)  # bumps interaction_count to 1
        self.kuzu.update_interaction("caldo", boost=0.0)  # -> 2
        self.kuzu.add_node("freddo", initial_activation=0.1)
        before = {"caldo": self._thermal("caldo"), "freddo": self._thermal("freddo")}
        self.assertEqual(before["caldo"][1], 2, "precondition: interaction_count tracked")

        res = thermal_backup.export(self.kuzu, self.snap)
        self.assertEqual(res["nodes"], 2)
        self.assertTrue(os.path.exists(self.snap))

        # Simulate a rebuild: flatten the nodes to defaults.
        self.kuzu.update_activation("caldo", 0.5)
        self.kuzu.update_activation("freddo", 0.5)
        self.kuzu.restore_thermal("caldo", 0.5, 0.0, 0, 0.0)   # zero the counter
        self.assertEqual(self._thermal("caldo"), (0.5, 0))

        rres = thermal_backup.restore(self.kuzu, self.snap)
        self.assertEqual(rres["restored"], 2)
        self.assertEqual(rres["skipped"], 0)
        self.assertEqual(self._thermal("caldo"), before["caldo"],
                         "activation AND interaction_count restored exactly")
        self.assertEqual(self._thermal("freddo"), before["freddo"])

    def test_restore_skips_nodes_absent_from_graph(self):
        self.kuzu.add_node("still_here", initial_activation=0.7)
        # Snapshot contains a node the rebuilt graph no longer has.
        payload = {"version": 1, "snapshot_at": "2026-07-04T00:00:00", "nodes": {
            "still_here": {"activation": 0.7, "last_interaction": 100.0,
                           "interaction_count": 3, "last_decay_applied": 100.0},
            "vanished": {"activation": 0.9, "last_interaction": 100.0,
                         "interaction_count": 9, "last_decay_applied": 100.0},
        }}
        with open(self.snap, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        res = thermal_backup.restore(self.kuzu, self.snap)
        self.assertEqual(res["restored"], 1)
        self.assertEqual(res["skipped"], 1, "absent node skipped, no error")
        self.assertIsNone(self.kuzu.get_node("vanished"))

    def test_export_shape_and_empty_graph(self):
        # Empty graph → valid, empty snapshot (no crash).
        res = thermal_backup.export(self.kuzu, self.snap)
        self.assertEqual(res["nodes"], 0)
        with open(self.snap) as f:
            payload = json.load(f)
        self.assertEqual(payload["nodes"], {})
        self.assertIn("snapshot_at", payload)

        self.kuzu.add_node("x", initial_activation=0.42)
        thermal_backup.export(self.kuzu, self.snap)
        with open(self.snap) as f:
            payload = json.load(f)
        self.assertIn("x", payload["nodes"])
        self.assertEqual(set(payload["nodes"]["x"].keys()),
                         {"activation", "last_interaction", "interaction_count", "last_decay_applied"})


if __name__ == "__main__":
    unittest.main()
