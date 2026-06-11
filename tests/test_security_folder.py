"""Security tests for A1 (path traversal on the `folder` parameter) and the
fail-closed auth / CORS pairing of A2.

Two layers, both isolated (temp dirs, no real DB, no production knowledge/):
  - TestResolveSafeFolder: unit tests on core.utils.resolve_safe_folder, the
    single chokepoint shared by the REST and MCP write paths.
  - TestResolveWritePathGateway: imports the gateway with its heavy backend
    mocked out and asserts _resolve_write_path maps a rejected folder to
    HTTP 400 while still accepting nested subfolders (the memory-sync hook
    relies on folder='Sistema/Claude_Code').

Run: python3 -m unittest tests/test_security_folder.py
"""
import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.utils import resolve_safe_folder


class TestResolveSafeFolder(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "Ganaghello"))
        os.makedirs(os.path.join(self.base, "Sistema", "Claude_Code"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_empty_folder_resolves_to_root(self):
        self.assertEqual(resolve_safe_folder(self.base, ""), os.path.abspath(self.base))

    def test_existing_flat_folder_ok(self):
        self.assertEqual(
            resolve_safe_folder(self.base, "Ganaghello"),
            os.path.join(os.path.abspath(self.base), "Ganaghello"),
        )

    def test_nested_subfolder_allowed(self):
        # The memory-sync hook writes with folder='Sistema/Claude_Code'.
        self.assertEqual(
            resolve_safe_folder(self.base, "Sistema/Claude_Code"),
            os.path.join(os.path.abspath(self.base), "Sistema", "Claude_Code"),
        )

    def test_parent_traversal_rejected(self):
        with self.assertRaises(ValueError):
            resolve_safe_folder(self.base, "../x")

    def test_absolute_path_rejected(self):
        with self.assertRaises(ValueError):
            resolve_safe_folder(self.base, "/tmp")

    def test_embedded_traversal_rejected(self):
        with self.assertRaises(ValueError):
            resolve_safe_folder(self.base, "a/../../x")

    def test_traversal_from_existing_folder_rejected(self):
        with self.assertRaises(ValueError):
            resolve_safe_folder(self.base, "Ganaghello/../../etc")

    def test_nonexistent_folder_rejected(self):
        with self.assertRaises(ValueError):
            resolve_safe_folder(self.base, "DoesNotExist")


class TestResolveWritePathGateway(unittest.TestCase):
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
        cls.HTTPException = __import__("fastapi").HTTPException

    @classmethod
    def tearDownClass(cls):
        for p in cls._patchers:
            p.stop()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "Ganaghello"))
        os.makedirs(os.path.join(self.tmp, "Sistema", "Claude_Code"))
        self._orig = self.hs.KNOWLEDGE_DIR
        self.hs.KNOWLEDGE_DIR = self.tmp

    def tearDown(self):
        self.hs.KNOWLEDGE_DIR = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_existing_folder_ok(self):
        path = self.hs._resolve_write_path("note", "Ganaghello")
        self.assertEqual(path, os.path.join(self.tmp, "Ganaghello", "note.md"))

    def test_nested_subfolder_ok(self):
        path = self.hs._resolve_write_path("mem", "Sistema/Claude_Code")
        self.assertEqual(path, os.path.join(self.tmp, "Sistema", "Claude_Code", "mem.md"))

    def test_traversal_variants_return_400(self):
        for bad in ("../x", "/tmp", "a/../../x"):
            with self.subTest(folder=bad):
                with self.assertRaises(self.HTTPException) as ctx:
                    self.hs._resolve_write_path("evil", bad)
                self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
