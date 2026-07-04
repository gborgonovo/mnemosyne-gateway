"""B3 (content-hash sync) and B2 opt.2 (basename collision detection).

Drives the real WikiSyncHandler against isolated KuzuDB/ChromaDB (no llm, so no
enrichment thread). Spies on VectorStore.upsert_node / update_metadata to prove
that re-embedding happens only when the body actually changes.

Run: python3 -m unittest tests/test_robustness.py
"""
import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml
from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore
from workers.file_watcher import WikiSyncHandler


class _Base(unittest.TestCase):
    def setUp(self):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.kdir = tempfile.mkdtemp()
        self.dbroot = tempfile.mkdtemp()
        with open(os.path.join(base, "config", "settings.yaml")) as f:
            cfg = yaml.safe_load(f)
        self.kuzu = KuzuManager(db_path=os.path.join(self.dbroot, "kuzu"))
        self.vec = VectorStore(db_path=os.path.join(self.dbroot, "chroma"),
                               embedding_config=cfg.get("llm", {}).get("embeddings"))
        self.handler = WikiSyncHandler(self.kuzu, self.vec, self.kdir)  # no llm

    def tearDown(self):
        self.kuzu.close()
        shutil.rmtree(self.kdir, ignore_errors=True)
        shutil.rmtree(self.dbroot, ignore_errors=True)

    def _write(self, slug, frontmatter, body, subdir=""):
        d = os.path.join(self.kdir, subdir) if subdir else self.kdir
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{slug}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n"); yaml.dump(frontmatter, f); f.write(f"---\n\n{body}")
        return path


class TestContentHashSync(_Base):
    def test_no_reembed_when_body_unchanged(self):
        path = self._write("note", {"type": "Node", "scope": "Private"}, "Hello world body")
        with mock.patch.object(self.vec, "upsert_node", wraps=self.vec.upsert_node) as up, \
             mock.patch.object(self.vec, "update_metadata", wraps=self.vec.update_metadata) as md:
            self.handler._sync_file(path, is_startup_sync=False)   # first time -> embed
            self.assertEqual(up.call_count, 1)
            self.handler._sync_file(path, is_startup_sync=False)   # body identical -> no embed
            self.assertEqual(up.call_count, 1, "unchanged body must not re-embed")
            self.assertGreaterEqual(md.call_count, 1, "unchanged body should refresh metadata only")

    def test_reembed_when_body_changes(self):
        path = self._write("note", {"type": "Node", "scope": "Private"}, "first body")
        with mock.patch.object(self.vec, "upsert_node", wraps=self.vec.upsert_node) as up:
            self.handler._sync_file(path, is_startup_sync=False)
            self._write("note", {"type": "Node", "scope": "Private"}, "a different body now")
            self.handler._sync_file(path, is_startup_sync=False)
            self.assertEqual(up.call_count, 2, "a real body change must re-embed")

    def test_frontmatter_only_change_does_not_reboost(self):
        path = self._write("note", {"type": "Node", "scope": "Private"}, "stable body text")
        self.handler._sync_file(path, is_startup_sync=False)
        act1 = self.kuzu.get_node("note")["activation_level"]
        # Change only the frontmatter (scope), keep the body identical.
        self._write("note", {"type": "Node", "scope": "Internal"}, "stable body text")
        self.handler._sync_file(path, is_startup_sync=False)
        act2 = self.kuzu.get_node("note")["activation_level"]
        self.assertEqual(act2, act1, "frontmatter-only edit must not reheat the node")
        # but the metadata change did propagate to the graph
        self.assertEqual(self.kuzu.get_node("note")["scope"], "Internal")

    def test_cold_boot_unchanged_does_not_reembed(self):
        path = self._write("note", {"type": "Node", "scope": "Private"}, "evergreen content")
        self.handler._sync_file(path, is_startup_sync=True)   # populate
        with mock.patch.object(self.vec, "upsert_node", wraps=self.vec.upsert_node) as up:
            self.handler._sync_file(path, is_startup_sync=True)  # second cold boot
            self.assertEqual(up.call_count, 0, "cold boot on unchanged knowledge must not embed")


class TestCollisionDetection(_Base):
    """Path-based node IDs already eliminate cross-folder basename collisions
    (a file in folder A and one in folder B with the same name get different
    IDs, e.g. 'a__x' vs 'b__x' — see CLAUDE.md). A genuine collision today only
    happens WITHIN the same folder, when two different filenames normalize to
    the same segment (case, space, hyphen/underscore variants)."""

    def test_basename_collision_is_flagged(self):
        # Same folder, case-only difference: both normalize to node_id 'a__x'.
        a = self._write("x", {"type": "Node", "scope": "Private"}, "from x", subdir="A")
        b = self._write("X", {"type": "Node", "scope": "Private"}, "from X", subdir="A")
        self.handler._sync_file(a, is_startup_sync=True)
        self.handler._sync_file(b, is_startup_sync=True)
        self.assertIn("a__x", self.handler.collisions)
        self.assertEqual(len(self.handler.collisions["a__x"]["paths"]), 2)

    def test_delete_keeps_node_when_survivor_exists(self):
        a = self._write("x", {"type": "Node", "scope": "Private"}, "from x", subdir="A")
        b = self._write("X", {"type": "Node", "scope": "Private"}, "from X", subdir="A")
        self.handler._sync_file(a, is_startup_sync=True)
        self.handler._sync_file(b, is_startup_sync=True)
        # Delete A/x.md; A/X.md still normalizes to the same node_id 'a__x'.
        os.remove(a)

        class _Evt:
            is_directory = False
            src_path = a
        self.handler.on_deleted(_Evt())
        self.assertIsNotNone(self.kuzu.get_node("a__x"), "node must survive: another file maps to it")
        # Collision resolved: only one backing file remains.
        self.assertNotIn("a__x", self.handler.collisions)

    def test_delete_removes_node_when_no_survivor(self):
        path = self._write("solo", {"type": "Node", "scope": "Private"}, "only one")
        self.handler._sync_file(path, is_startup_sync=True)
        os.remove(path)

        class _Evt:
            is_directory = False
            src_path = path
        self.handler.on_deleted(_Evt())
        self.assertIsNone(self.kuzu.get_node("solo"), "node must be deleted when no other file maps to it")


class TestGhostReconciliation(_Base):
    """reconcile_ghosts removes nodes whose .md file is gone (deleted while the
    gateway was down), which normal on_deleted events never caught."""

    def test_ghost_removed_from_both_dbs(self):
        a = self._write("alpha", {"type": "Node", "scope": "Private"}, "body a")
        self._write("beta", {"type": "Node", "scope": "Private"}, "body b")
        self.handler._sync_file(a, is_startup_sync=True)
        self.handler._sync_file(os.path.join(self.kdir, "beta.md"), is_startup_sync=True)
        # Delete alpha's file directly, with NO watcher event (the gateway-was-down case).
        os.remove(a)
        res = self.handler.reconcile_ghosts()
        self.assertEqual(res["removed"], 1)
        self.assertIsNone(self.kuzu.get_node("alpha"), "ghost gone from Kuzu")
        self.assertIsNone(self.vec.get_node("alpha"), "ghost gone from Chroma")
        self.assertIsNotNone(self.kuzu.get_node("beta"), "survivor untouched")
        self.assertIsNotNone(self.vec.get_node("beta"))

    def test_live_wikilink_stub_is_preserved(self):
        # 'source' links to [[Target]] which has no file → sync creates a stub.
        src = self._write("source", {"type": "Node", "scope": "Private"}, "see [[Target]]")
        self.handler._sync_file(src, is_startup_sync=True)
        self.assertIsNotNone(self.kuzu.get_node("target"), "stub created by the wikilink")
        res = self.handler.reconcile_ghosts()
        self.assertEqual(res["removed"], 0, "a stub referenced by a live file is not a ghost")
        self.assertIsNotNone(self.kuzu.get_node("target"), "live stub preserved")

    def test_empty_knowledge_dir_is_a_no_op(self):
        p = self._write("solo", {"type": "Node", "scope": "Private"}, "content")
        self.handler._sync_file(p, is_startup_sync=True)
        os.remove(p)  # now the knowledge dir has no .md at all
        res = self.handler.reconcile_ghosts()
        self.assertTrue(res["skipped"], "must refuse to delete everything when disk is empty")
        self.assertEqual(res["removed"], 0)
        self.assertIsNotNone(self.kuzu.get_node("solo"), "node kept: catastrophic guard held")

    def test_max_fraction_guard_skips_bulk_deletion(self):
        for name in ("n1", "n2", "n3", "n4"):
            p = self._write(name, {"type": "Node", "scope": "Private"}, f"body {name}")
            self.handler._sync_file(p, is_startup_sync=True)
        # Delete 3 of 4 files → 75% would be ghosts, above the default 0.5 guard.
        for name in ("n1", "n2", "n3"):
            os.remove(os.path.join(self.kdir, f"{name}.md"))
        res = self.handler.reconcile_ghosts(max_fraction=0.5)
        self.assertTrue(res["skipped"])
        self.assertEqual(res["removed"], 0)
        self.assertIsNotNone(self.kuzu.get_node("n1"), "bulk deletion refused")

    def test_chroma_only_ghost_removed(self):
        # A node embedded in Chroma but with no file and no Kuzu node is still a ghost.
        self.vec.upsert_node("orphan", "stale body", {"type": "Node", "scope": "Private"},
                             display_name="orphan")
        keep = self._write("keep", {"type": "Node", "scope": "Private"}, "real")
        self.handler._sync_file(keep, is_startup_sync=True)
        res = self.handler.reconcile_ghosts()
        self.assertEqual(res["removed"], 1)
        self.assertIsNone(self.vec.get_node("orphan"), "chroma-only ghost removed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
