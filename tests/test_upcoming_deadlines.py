"""Deadline reminders: core.node_service.get_upcoming_deadlines and its wiring
into gateway.http_server._compute_briefing / GET /briefing.

Deliberately independent of the thermal/activation model: a `deadline` is
urgency, not interest, so it must surface whether or not the node was touched
(see config/settings.yaml `deadlines:` and plugins/morning_briefing.yaml).
`deadline`/`remind_from` are frontmatter-only fields (not indexed in KuzuDB or
ChromaDB), so the scan reads markdown files directly — no DB needed for the
unit tests below.

Run: python3 -m unittest tests/test_upcoming_deadlines.py
"""
import os
import sys
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.node_service import get_upcoming_deadlines


def _write(path, frontmatter_lines, body="body"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        for line in frontmatter_lines:
            f.write(line + "\n")
        f.write("---\n\n")
        f.write(body)


class TestUpcomingDeadlines(unittest.TestCase):
    """Direct tests of the file-scan function, no gateway involved."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.today = date(2026, 8, 6)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _scan(self, **kwargs):
        return get_upcoming_deadlines(self.tmp, today=self.today, **kwargs)

    def test_within_default_lead_window(self):
        _write(os.path.join(self.tmp, "colloquio.md"),
               ["type: Goal", "status: active", "scope: Private",
                'deadline: "2026-08-20"'])
        results = self._scan(lead_days_by_type={"Goal": 14}, default_lead_days=7)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "colloquio")
        self.assertEqual(results[0]["days_remaining"], 14)

    def test_outside_lead_window_not_yet_surfaced(self):
        _write(os.path.join(self.tmp, "corso.md"),
               ["type: Goal", "status: active", "scope: Private",
                'deadline: "2026-09-10"'])
        results = self._scan(lead_days_by_type={"Goal": 14}, default_lead_days=7)
        self.assertEqual(results, [])

    def test_explicit_remind_from_overrides_default(self):
        _write(os.path.join(self.tmp, "corso.md"),
               ["type: Goal", "status: active", "scope: Private",
                'deadline: "2026-09-10"', 'remind_from: "2026-08-01"'])
        results = self._scan(lead_days_by_type={"Goal": 14}, default_lead_days=7)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["days_remaining"], 35)

    def test_default_lead_days_used_for_unlisted_type(self):
        _write(os.path.join(self.tmp, "node.md"),
               ["type: Node", "status: active", "scope: Private",
                'deadline: "2026-08-11"'])
        results = self._scan(lead_days_by_type={"Goal": 14}, default_lead_days=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["days_remaining"], 5)

    def test_overdue_and_open_stays_visible_with_negative_days(self):
        _write(os.path.join(self.tmp, "task.md"),
               ["type: Task", "status: todo", "scope: Private",
                'deadline: "2026-07-01"'])
        results = self._scan()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["days_remaining"], -36)

    def test_done_status_excluded_even_if_overdue(self):
        _write(os.path.join(self.tmp, "task.md"),
               ["type: Task", "status: done", "scope: Private",
                'deadline: "2026-07-01"'])
        self.assertEqual(self._scan(), [])

    def test_archived_status_excluded(self):
        _write(os.path.join(self.tmp, "goal.md"),
               ["type: Goal", "status: archived", "scope: Private",
                'deadline: "2026-07-01"'])
        self.assertEqual(self._scan(), [])

    def test_no_deadline_excluded(self):
        _write(os.path.join(self.tmp, "node.md"), ["type: Node", "scope: Private"])
        self.assertEqual(self._scan(), [])

    def test_sorted_soonest_or_most_overdue_first(self):
        _write(os.path.join(self.tmp, "a.md"),
               ["type: Task", "status: todo", "scope: Private", 'deadline: "2026-08-10"'])
        _write(os.path.join(self.tmp, "b.md"),
               ["type: Task", "status: todo", "scope: Private", 'deadline: "2026-08-08"'])
        results = self._scan()
        self.assertEqual([r["name"] for r in results], ["b", "a"])

    def test_scope_and_preview_carried_through(self):
        _write(os.path.join(self.tmp, "task.md"),
               ["type: Task", "status: todo", "scope: Internal",
                'deadline: "2026-08-06"'],
               body="# task\n\nPreparare le slide.")
        results = self._scan()
        self.assertEqual(results[0]["scope"], "Internal")
        self.assertIn("Preparare le slide.", results[0]["preview"])


class TestUpcomingDeadlinesBriefingWiring(unittest.TestCase):
    """_compute_briefing surfaces upcoming_deadlines alongside hot/dormant,
    scoped and filtered the same way as the rest of the briefing."""

    @classmethod
    def setUpClass(cls):
        cls._patchers = [
            mock.patch("core.kuzu_manager.KuzuManager"),
            mock.patch("core.vector_store.VectorStore"),
            mock.patch("core.attention.AttentionModel"),
            mock.patch("workers.gardener.Gardener"),
            mock.patch("workers.file_watcher.WikiSyncHandler"),
            mock.patch("watchdog.observers.Observer"),
            mock.patch("gateway.mcp_app.create_mcp_server"),
            mock.patch("butler.llm.get_llm_provider"),
        ]
        for p in cls._patchers:
            p.start()
        import gateway.http_server as hs
        cls.hs = hs

    @classmethod
    def tearDownClass(cls):
        for p in cls._patchers:
            p.stop()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig_kdir = self.hs.KNOWLEDGE_DIR
        self.hs.KNOWLEDGE_DIR = self.tmp
        # Empty hot/dormant sets: isolates this test to the deadlines wiring.
        self.hs.kuzu_mgr.get_active_nodes.return_value = []
        self.hs.kuzu_mgr.get_dormant_nodes.return_value = []

    def tearDown(self):
        self.hs.KNOWLEDGE_DIR = self._orig_kdir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_upcoming_deadline_surfaces_in_briefing(self):
        # Real config's Goal lead time is 14 days (config/settings.yaml
        # deadlines.lead_days_by_type), so 5 days out is well inside the window.
        deadline = (date.today() + timedelta(days=5)).isoformat()
        _write(os.path.join(self.tmp, "colloquio.md"),
               ["type: Goal", "status: active", "scope: Private",
                f'deadline: "{deadline}"'])
        briefing = self.hs._compute_briefing(None)
        self.assertEqual(len(briefing["upcoming_deadlines"]), 1)
        item = briefing["upcoming_deadlines"][0]
        self.assertEqual(item["name"], "colloquio")
        self.assertEqual(item["type"], "Goal")
        self.assertEqual(item["deadline"], deadline)
        self.assertEqual(item["days_remaining"], 5)

    def test_deadline_outside_caller_scope_is_dropped(self):
        deadline = date.today().isoformat()
        _write(os.path.join(self.tmp, "privato.md"),
               ["type: Task", "status: todo", "scope: Private",
                f'deadline: "{deadline}"'])
        briefing = self.hs._compute_briefing(["Public"])
        self.assertEqual(briefing["upcoming_deadlines"], [])


if __name__ == "__main__":
    unittest.main()
