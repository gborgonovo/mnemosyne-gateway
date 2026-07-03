"""Contract tests: REST and MCP must produce the SAME file for the same operation.

Mnemosyne's knowledge is written through two independent surfaces — REST
(`gateway/http_server.py`, used by clients like the Ganaghello app) and MCP
(`gateway/mcp_app.py`, used by Claude). They were written separately and drifted:
the status-reset bug (commit 88aba32) was exactly one surface merging frontmatter
and the other overwriting it, with nothing checking that the two agreed.

These tests run the same logical operation through both surfaces against separate
temp knowledge dirs, then assert the resulting markdown file (frontmatter + body)
is identical. A future change to one surface but not the other turns a test red.

Two tiers:
  - hard asserts: operations that are meant to be equivalent and already are —
    a divergence here corrupts data (the bug class we are guarding against).
  - @unittest.expectedFailure: known, partly-intentional divergences. They fail
    today (documenting the gap) without breaking the suite, and become the
    checklist the point-2 service-layer refactor must converge. If one starts
    passing (unexpected success), the surfaces were unified and the marker
    should be removed.

Harness: the REST side imports gateway.http_server with the heavy backend mocked
(as tests/test_api_upsert.py does); the MCP side builds a real MCP server with
MagicMock DBs (the write tools touch only the filesystem), as tests/test_mcp_tools.py
does. Neither needs KuzuDB/ChromaDB for a write.

Run: python3 -m unittest tests/test_rest_mcp_parity.py
"""
import os
import re
import sys
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml
# Bind the REAL create_mcp_server before any patching starts, so the MCP side
# uses the real one even while the REST import sees it mocked.
from gateway.mcp_app import create_mcp_server as _real_create_mcp_server


def _parse(path):
    """(frontmatter dict, body str) from a markdown file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)", raw, re.DOTALL)
    assert m, f"no frontmatter in {path}"
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


def _single_md(directory):
    """Path of the one .md file under directory (for random-id Observations)."""
    found = [f for f in os.listdir(directory) if f.endswith(".md")]
    assert len(found) == 1, f"expected exactly one .md in {directory}, found {found}"
    return os.path.join(directory, found[0])


class TestRestMcpParity(unittest.TestCase):
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
        # Separate knowledge dirs so the two surfaces never see each other's files.
        self.rest_dir = tempfile.mkdtemp()
        self.mcp_dir = tempfile.mkdtemp()
        self._orig_kdir = self.hs.KNOWLEDGE_DIR
        self.hs.KNOWLEDGE_DIR = self.rest_dir
        self.auth = {"scopes": ["*"], "read": ["*"], "write": ["*"]}
        mcp = _real_create_mcp_server(mock.MagicMock(), mock.MagicMock(),
                                      mock.MagicMock(), mock.MagicMock(),
                                      config={}, knowledge_dir=self.mcp_dir)
        self._mcp = {name: mcp._tool_manager.get_tool(name).fn
                     for name in ("add_observation", "create_node", "create_goal",
                                  "create_task", "forget_knowledge_node")}

    def tearDown(self):
        self.hs.KNOWLEDGE_DIR = self._orig_kdir
        shutil.rmtree(self.rest_dir, ignore_errors=True)
        shutil.rmtree(self.mcp_dir, ignore_errors=True)

    # ── helpers ────────────────────────────────────────────────────────────
    def _rest(self, path):
        return os.path.join(self.rest_dir, path)

    def _mcp_path(self, path):
        return os.path.join(self.mcp_dir, path)

    def _set_status_on_disk(self, path, status):
        fm, body = _parse(path)
        fm["status"] = status
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n"); yaml.dump(fm, f); f.write(f"---\n\n{body}")

    # ── Tier 1: hard parity (a divergence here corrupts data) ────────────────
    def test_goal_create_parity(self):
        self.hs.create_goal_api(
            self.hs.Goal(name="obiettivo-uno", description="d", deadline="2027-01-01",
                         scopes="Private", relations="area:LOCATED_IN"),
            api_auth=self.auth)
        self._mcp["create_goal"](name="obiettivo-uno", description="d",
                                 deadline="2027-01-01", scopes="Private",
                                 relations="area:LOCATED_IN")
        rfm, rbody = _parse(self._rest("obiettivo-uno.md"))
        mfm, mbody = _parse(self._mcp_path("obiettivo-uno.md"))
        self.assertEqual(rfm, mfm)
        self.assertEqual(rbody, mbody)
        # sanity: the values we care about really are there
        self.assertEqual(rfm["type"], "Goal")
        self.assertEqual(rfm["status"], "active")
        self.assertEqual(rfm["scope"], "Private")

    def test_goal_status_not_reset_on_update_parity(self):
        # create on both, mark done out-of-band on both, then re-upsert WITHOUT
        # status: both surfaces must preserve "done" (the 88aba32 bug class).
        for fn in (lambda: self.hs.create_goal_api(
                        self.hs.Goal(name="g", description="d", scopes="Private"),
                        api_auth=self.auth),
                   lambda: self._mcp["create_goal"](name="g", description="d",
                                                    scopes="Private")):
            fn()
        self._set_status_on_disk(self._rest("g.md"), "done")
        self._set_status_on_disk(self._mcp_path("g.md"), "done")
        self.hs.create_goal_api(
            self.hs.Goal(name="g", description="d", deadline="2027-06-01", scopes="Private"),
            api_auth=self.auth)
        self._mcp["create_goal"](name="g", description="d", deadline="2027-06-01",
                                 scopes="Private")
        rfm, rbody = _parse(self._rest("g.md"))
        mfm, mbody = _parse(self._mcp_path("g.md"))
        self.assertEqual(rfm["status"], "done")
        self.assertEqual(rfm, mfm)
        self.assertEqual(rbody, mbody)

    def test_task_create_parity(self):
        self.hs.create_task_api(
            self.hs.Task(name="task-uno", goal_name="obiettivo-uno", description="body",
                         scopes="Private", relations="x:PART_OF"),
            api_auth=self.auth)
        self._mcp["create_task"](name="task-uno", goal_name="obiettivo-uno",
                                 description="body", scopes="Private",
                                 relations="x:PART_OF")
        rfm, rbody = _parse(self._rest("task-uno.md"))
        mfm, mbody = _parse(self._mcp_path("task-uno.md"))
        self.assertEqual(rfm, mfm)
        self.assertEqual(rbody, mbody)
        self.assertEqual(rfm["status"], "todo")
        self.assertIn({"target": "obiettivo-uno", "type": "CONTRIBUTES_TO", "source": "user"},
                      rfm["relations"])

    def test_task_status_not_reset_on_update_parity(self):
        self.hs.create_task_api(self.hs.Task(name="t", description="d", scopes="Private"),
                                api_auth=self.auth)
        self._mcp["create_task"](name="t", goal_name="", description="d", scopes="Private")
        self._set_status_on_disk(self._rest("t.md"), "in_progress")
        self._set_status_on_disk(self._mcp_path("t.md"), "in_progress")
        self.hs.create_task_api(self.hs.Task(name="t", description="d2", scopes="Private"),
                                api_auth=self.auth)
        self._mcp["create_task"](name="t", goal_name="", description="d2", scopes="Private")
        rfm, _ = _parse(self._rest("t.md"))
        mfm, _ = _parse(self._mcp_path("t.md"))
        self.assertEqual(rfm["status"], "in_progress")
        self.assertEqual(rfm, mfm)

    def test_observation_type_scope_body_parity(self):
        # created_at diverges (see the xfail below); type, scope and body must match.
        self.hs.add_observation_api(self.hs.Observation(content="ciao mondo", scope="Public"),
                                    api_auth=self.auth)
        self._mcp["add_observation"](content="ciao mondo", scope="Public")
        rfm, rbody = _parse(_single_md(self.rest_dir))
        mfm, mbody = _parse(_single_md(self.mcp_dir))
        self.assertEqual(rfm["type"], mfm["type"], "Observation")
        self.assertEqual(rfm["scope"], mfm["scope"])
        self.assertEqual(rbody, mbody)

    def test_delete_parity(self):
        self.hs.create_goal_api(self.hs.Goal(name="del-me", scopes="Private"), api_auth=self.auth)
        self._mcp["create_goal"](name="del-me", scopes="Private")
        self.assertTrue(os.path.exists(self._rest("del-me.md")))
        self.assertTrue(os.path.exists(self._mcp_path("del-me.md")))
        self.hs.delete_node_api("del-me", api_auth=self.auth)
        self._mcp["forget_knowledge_node"]("del-me")
        self.assertFalse(os.path.exists(self._rest("del-me.md")))
        self.assertFalse(os.path.exists(self._mcp_path("del-me.md")))

    def test_upsert_idempotent_no_duplicate_parity(self):
        for _ in range(2):
            self.hs.create_goal_api(self.hs.Goal(name="once", scopes="Private"), api_auth=self.auth)
            self._mcp["create_goal"](name="once", scopes="Private")
        self.assertEqual([f for f in os.listdir(self.rest_dir) if f.endswith(".md")], ["once.md"])
        self.assertEqual([f for f in os.listdir(self.mcp_dir) if f.endswith(".md")], ["once.md"])

    # ── Tier 2: known, partly-intentional divergences (converge in point 2) ──
    # Each asserts the IDEAL (equality). It fails today, documenting the gap;
    # unify the surfaces in the service-layer refactor and it flips to a pass
    # (unexpected success), signalling that the marker can be removed.

    @unittest.expectedFailure
    def test_observation_created_at_parity_TODO_point2(self):
        # MCP write_markdown stamps created_at on every new file; REST
        # write_markdown (used by /observations) does not. REST goals/tasks/nodes
        # DO get created_at (via _upsert_node_file) — only observations diverge.
        self.hs.add_observation_api(self.hs.Observation(content="x", scope="Public"),
                                    api_auth=self.auth)
        self._mcp["add_observation"](content="x", scope="Public")
        rfm, _ = _parse(_single_md(self.rest_dir))
        mfm, _ = _parse(_single_md(self.mcp_dir))
        self.assertEqual("created_at" in rfm, "created_at" in mfm)

    @unittest.expectedFailure
    def test_node_body_parity_TODO_point2(self):
        # POST /nodes uses the raw content as body; MCP create_node wraps it in
        # a "# name" heading (+ optional wikilinks). Different body shape.
        self.hs.upsert_node(
            self.hs.NodeUpsert(name="nodo", content="corpo", node_type="Node", scope="Private"),
            api_auth=self.auth)
        self._mcp["create_node"](name="nodo", content="corpo", node_type="Node", scope="Private")
        _, rbody = _parse(self._rest("nodo.md"))
        _, mbody = _parse(self._mcp_path("nodo.md"))
        self.assertEqual(rbody, mbody)

    @unittest.expectedFailure
    def test_node_default_scope_parity_TODO_point2(self):
        # Default scope differs: NodeUpsert defaults to Private, create_node to Public.
        self.hs.upsert_node(self.hs.NodeUpsert(name="nodo2", content="c"), api_auth=self.auth)
        self._mcp["create_node"](name="nodo2", content="c")
        rfm, _ = _parse(self._rest("nodo2.md"))
        mfm, _ = _parse(self._mcp_path("nodo2.md"))
        self.assertEqual(rfm["scope"], mfm["scope"])


if __name__ == "__main__":
    unittest.main()
