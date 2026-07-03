"""Direct unit tests for gateway.mcp_app's create_goal/create_task/write_markdown
merge semantics: status defaults ONLY on creation and is never silently reset on
a repeat call, and fields the caller doesn't pass (relations, status set via a
side channel) survive an update instead of being wiped.

Drives the real MCP tool functions (grabbed via FastMCP's tool manager, no ASGI
transport needed) against isolated KuzuDB/ChromaDB. current_grants defaults to
the unrestricted dev grant when nothing sets it, which matches calling a tool
function directly (MCPAuthMiddleware isn't in the loop here).

Run: python3 -m unittest tests/test_mcp_tools.py
"""
import os
import re
import sys
import shutil
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml
from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore
from core.attention import AttentionModel
from workers.gardener import Gardener
from gateway.mcp_app import create_mcp_server


def _read_frontmatter(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)", raw, re.DOTALL)
    assert m, f"no frontmatter in {path}"
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


class TestMcpToolsStatusMerge(unittest.TestCase):
    def setUp(self):
        self.kdir = tempfile.mkdtemp()
        self.dbroot = tempfile.mkdtemp()
        self.kuzu = KuzuManager(db_path=os.path.join(self.dbroot, "kuzu"))
        self.vec = VectorStore(db_path=os.path.join(self.dbroot, "chroma"),
                               embedding_config={"mode": "mock"})
        self.am = AttentionModel(self.kuzu, config={})
        self.gd = Gardener(self.am, config={}, vector_store=self.vec)
        mcp = create_mcp_server(self.kuzu, self.vec, self.am, self.gd, config={}, knowledge_dir=self.kdir)
        self.create_goal = mcp._tool_manager.get_tool("create_goal").fn
        self.create_task = mcp._tool_manager.get_tool("create_task").fn

    def tearDown(self):
        self.kuzu.close()
        shutil.rmtree(self.kdir, ignore_errors=True)
        shutil.rmtree(self.dbroot, ignore_errors=True)

    def _path(self, slug):
        return os.path.join(self.kdir, f"{slug}.md")

    def test_goal_status_default_once_not_reset_and_relations_survive(self):
        self.create_goal(name="goal-mcp", description="d", relations="area:LOCATED_IN")
        fm, _ = _read_frontmatter(self._path("goal-mcp"))
        self.assertEqual(fm["status"], "active")
        self.assertEqual(fm["relations"], [{"target": "area", "type": "LOCATED_IN", "source": "user"}])

        # Mark it done through a side channel (simulating update_task_status).
        fm["status"] = "done"
        with open(self._path("goal-mcp"), "w", encoding="utf-8") as f:
            f.write("---\n"); yaml.dump(fm, f); f.write("---\n\nbody")

        # Repeat create_goal WITHOUT passing relations/status: before the fix,
        # write_markdown wiped everything but created_at/enriched_at, losing
        # both the relations and the "done" status.
        self.create_goal(name="goal-mcp", description="d2")
        fm2, body2 = _read_frontmatter(self._path("goal-mcp"))
        self.assertEqual(fm2["status"], "done", "status must survive an update that doesn't touch it")
        self.assertEqual(fm2["relations"], [{"target": "area", "type": "LOCATED_IN", "source": "user"}],
                         "relations must survive a repeat call that doesn't pass them")
        self.assertIn("d2", body2)

        # Explicit status IS honored.
        self.create_goal(name="goal-mcp", status="archived")
        fm3, _ = _read_frontmatter(self._path("goal-mcp"))
        self.assertEqual(fm3["status"], "archived")

    def test_task_status_default_once_and_not_reset(self):
        self.create_task(name="task-mcp", goal_name="")
        fm, _ = _read_frontmatter(self._path("task-mcp"))
        self.assertEqual(fm["status"], "todo")

        self.create_task(name="task-mcp", goal_name="", status="in_progress")
        fm2, _ = _read_frontmatter(self._path("task-mcp"))
        self.assertEqual(fm2["status"], "in_progress")

        self.create_task(name="task-mcp", goal_name="", description="notes")
        fm3, _ = _read_frontmatter(self._path("task-mcp"))
        self.assertEqual(fm3["status"], "in_progress", "must not reset to todo on a repeat call")


if __name__ == "__main__":
    unittest.main()
