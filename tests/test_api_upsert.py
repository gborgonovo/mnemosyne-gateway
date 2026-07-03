"""Phase-1 API evolution tests (relations on /tasks,/goals, upsert, canonical
name, goal_name->CONTRIBUTES_TO, stub scope inheritance).

Two layers:
  - TestUpsertEndpoints: imports the gateway with its heavy backend mocked out,
    then calls the route functions directly against a temp KNOWLEDGE_DIR. This
    exercises the real frontmatter/upsert/relations logic with no DB lock.
  - TestStubScopeInheritance: drives the real WikiSyncHandler against isolated
    KuzuDB/ChromaDB to assert that an edge to a not-yet-existing target spawns a
    stub inheriting the source node's scope (C1), not a Public default.

Run: python3 -m unittest tests/test_api_upsert.py
"""
import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml


def _read_frontmatter(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    import re
    m = re.match(r"^---\n(.*?)\n---\n(.*)", raw, re.DOTALL)
    assert m, f"no frontmatter in {path}"
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


class TestUpsertEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mock every heavy dependency the gateway builds at import time so the
        # module loads instantly and never touches the real DBs / file watcher.
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
        self.auth = {"scopes": ["*"], "read": ["*"], "write": ["*"]}

    def tearDown(self):
        self.hs.KNOWLEDGE_DIR = self._orig_kdir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _path(self, slug):
        return os.path.join(self.tmp, f"{slug}.md")

    # R1 + R4 ---------------------------------------------------------------
    def test_goal_relations_and_canonical_name(self):
        resp = self.hs.create_goal_api(
            self.hs.Goal(name="goal-001", description="d", deadline="2027-06-01",
                         scopes="Private", relations="area-001:LOCATED_IN"),
            api_auth=self.auth,
        )
        self.assertEqual(resp["name"], "goal-001")
        self.assertEqual(resp["type"], "Goal")
        self.assertEqual(resp["scope"], "Private")
        self.assertEqual(resp["action"], "created")
        fm, _ = _read_frontmatter(self._path("goal-001"))
        self.assertEqual(fm["relations"], [{"target": "area-001", "type": "LOCATED_IN", "source": "user"}])
        self.assertEqual(fm["scope"], "Private")

    # R1 + R2 ---------------------------------------------------------------
    def test_task_relations_and_goal_name_becomes_contributes_to(self):
        resp = self.hs.create_task_api(
            self.hs.Task(name="task-001", goal_name="goal-001", description="body",
                         scopes="Private",
                         relations="task-padre-001:PART_OF,area-001:LOCATED_IN"),
            api_auth=self.auth,
        )
        self.assertEqual(resp["name"], "task-001")
        fm, body = _read_frontmatter(self._path("task-001"))
        rels = fm["relations"]
        self.assertIn({"target": "task-padre-001", "type": "PART_OF", "source": "user"}, rels)
        self.assertIn({"target": "area-001", "type": "LOCATED_IN", "source": "user"}, rels)
        self.assertIn({"target": "goal-001", "type": "CONTRIBUTES_TO", "source": "user"}, rels)
        # R2: no implicit [[goal_name]] wikilink / LINKED_TO noise in the body
        self.assertNotIn("[[goal-001]]", body)
        self.assertNotIn("Linked Goal", body)

    # R3 -------------------------------------------------------------------
    def test_upsert_is_idempotent_and_preserves_created_at(self):
        self.hs.create_task_api(self.hs.Task(name="task-x", description="v1", scopes="Private"), api_auth=self.auth)
        fm1, _ = _read_frontmatter(self._path("task-x"))
        created = fm1["created_at"]
        # Second write, different content
        resp = self.hs.create_task_api(self.hs.Task(name="task-x", description="v2 updated", scopes="Private"), api_auth=self.auth)
        self.assertEqual(resp["action"], "updated")
        # exactly one file, created_at preserved, body refreshed
        md_files = [f for f in os.listdir(self.tmp) if f.endswith(".md")]
        self.assertEqual(md_files, ["task-x.md"])
        fm2, body2 = _read_frontmatter(self._path("task-x"))
        self.assertEqual(fm2["created_at"], created)
        self.assertIn("v2 updated", body2)

    # R6 -------------------------------------------------------------------
    def test_singular_scope_takes_precedence(self):
        # Explicit singular `scope` overrides the legacy `scopes` plural.
        resp = self.hs.create_task_api(
            self.hs.Task(name="task-scope", scope="Internal", scopes="Private,Public"),
            api_auth=self.auth,
        )
        self.assertEqual(resp["scope"], "Internal")
        fm, _ = _read_frontmatter(self._path("task-scope"))
        self.assertEqual(fm["scope"], "Internal")

    def test_default_scope_is_private_not_public(self):
        resp = self.hs.create_goal_api(self.hs.Goal(name="goal-def"), api_auth=self.auth)
        self.assertEqual(resp["scope"], "Private")

    def test_upsert_preserves_enriched_at(self):
        # Create a Journal node, stamp enriched_at, then re-upsert and assert it survives.
        resp = self.hs.upsert_node(self.hs.NodeUpsert(name="note-1", content="hello", node_type="Journal", scope="Private"), api_auth=self.auth)
        self.assertEqual(resp["type"], "Journal")
        fm, _ = _read_frontmatter(self._path("note-1"))
        fm["enriched_at"] = "2026-06-10 12:00:00"
        with open(self._path("note-1"), "w", encoding="utf-8") as f:
            f.write("---\n"); yaml.dump(fm, f, allow_unicode=True); f.write("---\n\nhello")
        self.hs.upsert_node(self.hs.NodeUpsert(name="note-1", content="changed", node_type="Journal", scope="Private"), api_auth=self.auth)
        fm2, _ = _read_frontmatter(self._path("note-1"))
        self.assertEqual(str(fm2.get("enriched_at")), "2026-06-10 12:00:00")


class TestStubScopeInheritance(unittest.TestCase):
    """C1: an edge target that has no file yet must inherit the source scope."""

    def setUp(self):
        from core.kuzu_manager import KuzuManager
        from core.vector_store import VectorStore
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # Unique temp dirs per test so a lingering Chroma/Kuzu handle from the
        # previous test can't leave a readonly/locked DB behind.
        self.kdir = tempfile.mkdtemp()
        self.dbroot = tempfile.mkdtemp()
        self.kpath = os.path.join(self.dbroot, "kuzu")
        self.vpath = os.path.join(self.dbroot, "chroma")
        with open(os.path.join(base, "config", "settings.yaml")) as f:
            cfg = yaml.safe_load(f)
        self.kuzu = KuzuManager(db_path=self.kpath)
        self.vec = VectorStore(db_path=self.vpath, embedding_config=cfg.get("llm", {}).get("embeddings"))
        from workers.file_watcher import WikiSyncHandler
        self.handler = WikiSyncHandler(self.kuzu, self.vec, self.kdir)  # no llm -> no enrichment thread

    def tearDown(self):
        self.kuzu.close()
        shutil.rmtree(self.kdir, ignore_errors=True)
        shutil.rmtree(self.dbroot, ignore_errors=True)

    def _write(self, slug, frontmatter, body="body"):
        path = os.path.join(self.kdir, f"{slug}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n")
            yaml.dump(frontmatter, f)
            f.write(f"---\n\n{body}")
        return path

    def _edge_types(self, source, target):
        return {e["type"] for e in self.kuzu.get_outgoing_edges(source) if e["target"] == target}

    def test_relation_stub_inherits_private_scope(self):
        path = self._write("task-child", {"type": "Task", "scope": "Private",
                                           "relations": [{"target": "area-001", "type": "LOCATED_IN"}]})
        self.handler._sync_file(path, is_startup_sync=True)
        stub = self.kuzu.get_node("area-001")
        self.assertIsNotNone(stub, "stub target node should have been created")
        self.assertEqual(stub["scope"], "Private", "stub must inherit source scope, not default Public")

    def test_removed_relation_edge_is_reconciled(self):
        # First sync: edge task -> area exists.
        path = self._write("task-r", {"type": "Task", "scope": "Private",
                                       "relations": [{"target": "area-001", "type": "LOCATED_IN"}]})
        self.handler._sync_file(path, is_startup_sync=True)
        self.assertEqual(self._edge_types("task-r", "area_001"), {"LOCATED_IN"})
        # Re-sync with the relation removed: edge must disappear.
        self._write("task-r", {"type": "Task", "scope": "Private"})
        self.handler._sync_file(path, is_startup_sync=True)
        self.assertEqual(self._edge_types("task-r", "area_001"), set(),
                         "stale file-derived edge should be removed on reconcile")

    def test_changed_relation_type_is_reconciled(self):
        path = self._write("task-c", {"type": "Task", "scope": "Private",
                                       "relations": [{"target": "goal-1", "type": "RELATED_TO"}]})
        self.handler._sync_file(path, is_startup_sync=True)
        self.assertEqual(self._edge_types("task-c", "goal_1"), {"RELATED_TO"})
        self._write("task-c", {"type": "Task", "scope": "Private",
                               "relations": [{"target": "goal-1", "type": "CONTRIBUTES_TO"}]})
        self.handler._sync_file(path, is_startup_sync=True)
        self.assertEqual(self._edge_types("task-c", "goal_1"), {"CONTRIBUTES_TO"},
                         "edge type change must drop the old type, not accumulate")

    def test_semantically_related_edge_is_preserved(self):
        path = self._write("task-s", {"type": "Task", "scope": "Private",
                                       "relations": [{"target": "area-001", "type": "LOCATED_IN"}]})
        self.handler._sync_file(path, is_startup_sync=True)
        # Gardener-style ephemeral edge added out of band.
        self.kuzu.add_edge("task-s", "neighbor-1", "SEMANTICALLY_RELATED", weight=0.7)
        # A plain re-sync must not wipe the ephemeral edge.
        self.handler._sync_file(path, is_startup_sync=True)
        self.assertEqual(self._edge_types("task-s", "neighbor_1"), {"SEMANTICALLY_RELATED"},
                         "Gardener edges must survive file-sync reconciliation")
        self.assertEqual(self._edge_types("task-s", "area_001"), {"LOCATED_IN"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
