"""End-to-end test for MCP auth middleware + ContextVar propagation.

The critical risk: FastMCP runs sync tool functions via anyio.to_thread, so we
must prove that the grants set by the ASGI middleware actually reach the tool
body. This test drives a real FastMCP streamable-HTTP app through httpx's
ASGITransport (no DBs, no network) and asserts scope + territory tiers behave.
"""
import json
import unittest

import anyio
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from core.mcp_auth import (
    MCPAuthMiddleware,
    resolve_grants,
    get_scopes,
    scope_filter,
    read_filter_grants,
    require_privileged,
    assert_write,
    current_grants,
)

# Normalized grants map (the shape gateway.http_server.API_GRANTS holds).
GRANTS = {
    "KFULL": {"scopes": ["Private", "Internal", "Public"], "read": ["*"], "write": ["*"]},
    "KPUB":  {"scopes": ["Public"], "read": ["*"], "write": ["*"]},
    "KGANA": {"scopes": ["Private", "Public"], "read": ["Ganaghello"], "write": ["Ganaghello"]},
    "KRO":   {"scopes": ["Private", "Internal", "Public"], "read": ["*"], "write": []},
}


def _build_mcp(grants_map):
    sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp = FastMCP("auth-test", stateless_http=True, streamable_http_path="/",
                  transport_security=sec)

    @mcp.tool()
    def whoami() -> str:
        """Report scope + territory decisions visible inside the tool."""
        return json.dumps({
            "scopes": get_scopes(),
            "scope_filter": scope_filter(),
            "read_filter": read_filter_grants(),
            "diagnostic_denied": require_privileged() is not None,
            # write checks now take (scope, node_id): territory matters
            "w_priv_gana":  assert_write("Private", "ganaghello__conti") is not None,
            "w_priv_other": assert_write("Private", "vangelo__nota") is not None,
            "w_pub_gana":   assert_write("Public", "ganaghello__pagina") is not None,
        })

    app = MCPAuthMiddleware(mcp.streamable_http_app(), grants_map=grants_map)
    return mcp, app


async def _call_whoami(mcp, app, header_key=None, query_key=None):
    transport = httpx.ASGITransport(app=app)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if header_key is not None:
        headers["X-API-Key"] = header_key
    url = "/" if query_key is None else f"/?k={query_key}"

    async with mcp.session_manager.run():
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            body = {
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "whoami", "arguments": {}},
            }
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                return resp.status_code, None
            payload = None
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    payload = json.loads(line[5:].strip())
                    break
            text = payload["result"]["content"][0]["text"]
            return 200, json.loads(text)


class TestResolveGrants(unittest.TestCase):
    def test_no_keys_is_dev_unrestricted(self):
        g = resolve_grants({}, None)
        self.assertEqual(g["scopes"], ["*"])
        self.assertEqual(g["read"], ["*"])
        self.assertEqual(g["write"], ["*"])

    def test_missing_or_invalid_key_is_none(self):
        self.assertIsNone(resolve_grants(GRANTS, None))
        self.assertIsNone(resolve_grants(GRANTS, "WRONG"))

    def test_valid_key_returns_grants(self):
        self.assertEqual(resolve_grants(GRANTS, "KGANA")["read"], ["Ganaghello"])


class TestMCPAuthE2E(unittest.TestCase):
    def setUp(self):
        self.mcp, self.app = _build_mcp(GRANTS)

    def test_no_key_is_401(self):
        status, _ = anyio.run(_call_whoami, self.mcp, self.app, None)
        self.assertEqual(status, 401)

    def test_invalid_key_is_401(self):
        status, _ = anyio.run(_call_whoami, self.mcp, self.app, "NOPE")
        self.assertEqual(status, 401)

    def test_full_key(self):
        status, data = anyio.run(_call_whoami, self.mcp, self.app, "KFULL")
        self.assertEqual(status, 200)
        self.assertEqual(set(data["scopes"]), {"Private", "Internal", "Public"})
        self.assertIsNone(data["read_filter"])          # reads everything
        self.assertFalse(data["diagnostic_denied"])
        self.assertFalse(data["w_priv_gana"])           # writes anywhere
        self.assertFalse(data["w_priv_other"])
        self.assertFalse(data["w_pub_gana"])

    def test_public_key_scope_tier(self):
        status, data = anyio.run(_call_whoami, self.mcp, self.app, "KPUB")
        self.assertEqual(status, 200)
        self.assertEqual(data["scope_filter"], ["Public"])
        self.assertTrue(data["diagnostic_denied"])      # Public-only: no diagnostics
        self.assertTrue(data["w_priv_gana"])            # scope denies Private
        self.assertFalse(data["w_pub_gana"])            # Public write ok (territory *)

    def test_confined_key_territory(self):
        status, data = anyio.run(_call_whoami, self.mcp, self.app, "KGANA")
        self.assertEqual(status, 200)
        self.assertEqual(data["read_filter"], ["Ganaghello"])   # reads only its tree
        self.assertFalse(data["w_priv_gana"])           # Private + inside territory: ok
        self.assertTrue(data["w_priv_other"])           # right scope, wrong territory: denied
        self.assertFalse(data["w_pub_gana"])            # Public + inside territory: ok

    def test_readonly_key_cannot_write(self):
        status, data = anyio.run(_call_whoami, self.mcp, self.app, "KRO")
        self.assertEqual(status, 200)
        self.assertIsNone(data["read_filter"])          # reads everything
        # write == [] : no territory writable, even holding every scope
        self.assertTrue(data["w_priv_gana"])
        self.assertTrue(data["w_priv_other"])
        self.assertTrue(data["w_pub_gana"])

    def test_query_param_key(self):
        status, data = anyio.run(_call_whoami, self.mcp, self.app, None, "KGANA")
        self.assertEqual(status, 200)
        self.assertEqual(data["read_filter"], ["Ganaghello"])

    def test_query_param_invalid_is_401(self):
        status, _ = anyio.run(_call_whoami, self.mcp, self.app, None, "NOPE")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
