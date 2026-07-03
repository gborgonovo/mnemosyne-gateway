"""Unit tests for core.authz: territory matching and key-file validation.

Run: python3 -m unittest tests/test_authz.py
"""
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.authz import (
    territory_allows,
    normalize_key_config,
    validate_api_keys,
    format_validation_error,
    filter_by_read,
)


class TestTerritoryAllows(unittest.TestCase):
    def test_wildcard_allows_everything(self):
        self.assertTrue(territory_allows(["*"], "ganaghello__spazi__stalla"))
        self.assertTrue(territory_allows(["*"], "anything"))

    def test_empty_grants_allow_nothing(self):
        # Read-only keys have write == []: no territory is writable.
        self.assertFalse(territory_allows([], "ganaghello__x"))
        self.assertFalse(territory_allows(None, "ganaghello__x"))

    def test_prefix_covers_subtree(self):
        self.assertTrue(territory_allows(["Ganaghello"], "ganaghello"))
        self.assertTrue(territory_allows(["Ganaghello"], "ganaghello__spazi__stalla__stalla"))

    def test_boundary_not_substring(self):
        # 'Gana' must NOT match 'Ganaghello' — matching is on the segment boundary.
        self.assertFalse(territory_allows(["Gana"], "ganaghello__spazi"))

    def test_sibling_folders_isolated(self):
        # A grant on Sistema/Alfred must not leak into Sistema/Claude_Code.
        self.assertTrue(territory_allows(["Sistema/Alfred"], "sistema__alfred__prompt"))
        self.assertFalse(territory_allows(["Sistema/Alfred"], "sistema__claude_code__mem"))

    def test_nested_grant(self):
        self.assertTrue(territory_allows(["Ganaghello/Spazi"], "ganaghello__spazi__stalla"))
        self.assertFalse(territory_allows(["Ganaghello/Spazi"], "ganaghello__visione__charme"))

    def test_multiple_grants_or(self):
        grants = ["Ganaghello", "Articoli"]
        self.assertTrue(territory_allows(grants, "articoli__pezzo"))
        self.assertTrue(territory_allows(grants, "ganaghello__x"))
        self.assertFalse(territory_allows(grants, "vangelo__nota"))

    def test_root_file(self):
        # A root-level node (single segment) is only in '*'.
        self.assertTrue(territory_allows(["*"], "alfred"))
        self.assertFalse(territory_allows(["Ganaghello"], "alfred"))


class TestNormalizeKeyConfig(unittest.TestCase):
    def test_mapping_explicit(self):
        cfg = {"scopes": ["Private"], "read": ["*"], "write": ["Ganaghello"]}
        self.assertEqual(
            normalize_key_config(cfg),
            {"scopes": ["Private"], "read": ["*"], "write": ["Ganaghello"]},
        )

    def test_missing_territory_strict_denies(self):
        # Production posture (lenient=False): absent read/write default to [].
        out = normalize_key_config({"scopes": ["Private"]}, lenient=False)
        self.assertEqual(out["read"], [])
        self.assertEqual(out["write"], [])

    def test_missing_territory_lenient_grants(self):
        # Dev posture (lenient=True): absent read/write default to "*".
        out = normalize_key_config({"scopes": ["Private"]}, lenient=True)
        self.assertEqual(out["read"], ["*"])
        self.assertEqual(out["write"], ["*"])

    def test_legacy_list_form(self):
        strict = normalize_key_config(["Private", "Public"], lenient=False)
        self.assertEqual(strict, {"scopes": ["Private", "Public"], "read": [], "write": []})
        lenient = normalize_key_config(["Private"], lenient=True)
        self.assertEqual(lenient["read"], ["*"])


class TestValidateApiKeys(unittest.TestCase):
    def test_wellformed_has_no_problems(self):
        keys = {"k1abcd": {"scopes": ["Private"], "read": ["*"], "write": ["*"]}}
        self.assertEqual(validate_api_keys(keys), [])

    def test_legacy_list_is_flagged(self):
        keys = {"k1abcd": ["Private", "Public"]}
        problems = validate_api_keys(keys)
        self.assertEqual(len(problems), 1)
        self.assertIn("abcd", problems[0])  # key is named (redacted) in the message
        self.assertIn("vecchio", problems[0])

    def test_missing_field_is_flagged(self):
        keys = {"k1abcd": {"scopes": ["Private"], "read": ["*"]}}  # no write
        problems = validate_api_keys(keys)
        self.assertTrue(any("write" in p for p in problems))

    def test_error_message_is_explicit(self):
        problems = validate_api_keys({"k1abcd": ["Private"]})
        msg = format_validation_error(problems)
        # The refuse-to-start message must name the file, the fix, and the key.
        self.assertIn("api_keys.yaml", msg)
        self.assertIn("read", msg)
        self.assertIn("write", msg)
        self.assertIn("abcd", msg)


class TestFilterByRead(unittest.TestCase):
    def test_unrestricted_is_passthrough(self):
        items = [{"node_id": "ganaghello__x"}, {"node_id": "vangelo__y"}]
        self.assertEqual(filter_by_read(items, None, "node_id"), items)
        self.assertEqual(filter_by_read(items, ["*"], "node_id"), items)

    def test_confined_drops_outside(self):
        items = [{"name": "ganaghello__x"}, {"name": "vangelo__y"}, {"name": "ganaghello__z"}]
        out = filter_by_read(items, ["Ganaghello"], "name")
        self.assertEqual([i["name"] for i in out], ["ganaghello__x", "ganaghello__z"])


if __name__ == "__main__":
    unittest.main()
