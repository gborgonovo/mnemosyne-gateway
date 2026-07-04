"""Regression tests for core.utils.atomic_write permissions.

The bug: mkstemp() creates the temp 0600 and os.replace() carries that mode onto
the destination, so every rewrite flipped an existing 0644 knowledge file to 0600
(root:root in prod). A Syncthing running as another user then couldn't read/hash
the file and the change silently stopped propagating (271 files stuck in
Ganaghello/, prod↔dev divergence found 2026-07-04). The file must always stay
readable by group/other.

Run: python3 -m unittest tests/test_atomic_write.py
"""
import os
import sys
import stat
import shutil
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.utils import atomic_write


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class TestAtomicWritePerms(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_new_file_is_group_and_other_readable(self):
        p = os.path.join(self.dir, "new.md")
        atomic_write(p, "hello")
        m = _mode(p)
        self.assertTrue(m & 0o044, f"new file must be group/other readable, got {oct(m)}")
        self.assertNotEqual(m, 0o600, "must never leave a mkstemp 0600 file behind")
        with open(p) as f: self.assertEqual(f.read(), "hello")

    def test_rewrite_does_not_downgrade_to_0600(self):
        # The exact regression: an existing 0644 file rewritten must stay readable.
        p = os.path.join(self.dir, "node.md")
        atomic_write(p, "v1")
        os.chmod(p, 0o644)
        atomic_write(p, "v2 changed")
        m = _mode(p)
        self.assertTrue(m & 0o044, f"rewrite must stay group/other readable, got {oct(m)}")
        with open(p) as f: self.assertEqual(f.read(), "v2 changed")

    def test_recovers_a_file_left_at_0600(self):
        # If a file is somehow already 0600, a rewrite must heal it, not perpetuate it.
        p = os.path.join(self.dir, "locked.md")
        atomic_write(p, "x")
        os.chmod(p, 0o600)
        atomic_write(p, "y")
        self.assertTrue(_mode(p) & 0o004, "other-read must be granted so Syncthing can hash it")

    def test_preserves_extra_bits_of_existing_mode(self):
        # A group-writable file (0664) keeps its group-write bit across a rewrite.
        p = os.path.join(self.dir, "shared.md")
        atomic_write(p, "a")
        os.chmod(p, 0o664)
        atomic_write(p, "b")
        self.assertEqual(_mode(p), 0o664, "existing extra bits preserved, read guaranteed")


if __name__ == "__main__":
    unittest.main()
