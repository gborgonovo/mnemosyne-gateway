"""End-to-end test for MCP auth middleware + ContextVar propagation.

The critical risk: FastMCP runs sync tool functions via anyio.to_thread, so we
must prove that scopes set by the ASGI middleware actually reach the tool body.
This test drives a real FastMCP streamable-HTTP app through httpx's ASGITransport
(no DBs, no network) and asserts the three tiers behave correctly.
"""
import json
import unittest

import anyio
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from core.mcp_auth import (
    MCPAuthMiddleware,
    resolve_scopes,
    scope_filter,
    require_privileged,
    assert_write,
    current_scopes,
)


def _build_mcp(api_keys):
    # Disable DNS-rebinding protection for the in-process test host (prod keeps it).
    sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp = FastMCP("auth-test", stateless_http=True, streamable_http_path="/",
                  transport_security=sec)

    @mcp.tool()
    def whoami() -> str:
        """Return the scopes visible inside the tool, plus tier decisions."""
        return json.dumps({
            "scopes": current_scopes.get(),
            "scope_filter": scope_filter(),
            "diagnostic_denied": require_privileged() is not None,
            "write_private_denied": assert_write("Private") is not None,
            "write_public_denied": assert_write("Public") is not None,
        })

    app = MCPAuthMiddleware(mcp.streamable_http_app(), api_keys=api_keys)
    return mcp, app


async def _call_whoami(mcp, app, header_key=None, query_key=None):
    """Drive the MCP stateless protocol and return (status, parsed_tool_json).

    Wraps the call in session_manager.run() exactly like the gateway lifespan,
    since the streamable-HTTP task group is created there. The key can be passed
    via the X-API-Key header or the ?k= query param (Claude web's path).
    """
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

            # Response is SSE: find the `data:` line carrying the JSON-RPC result
            payload = None
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    payload = json.loads(line[5:].strip())
                    break
            text = payload["result"]["content"][0]["text"]
            return 200, json.loads(text)


class TestMCPAuthHelpers(unittest.TestCase):
    def test_resolve_scopes(self):
        # No keys configured → unrestricted (dev mode)
        self.assertEqual(resolve_scopes({}, None), ["*"])
        # Keys configured, missing/invalid → None (401)
        keys = {"KPRIV": ["Private"], "KPUB": ["Public"]}
        self.assertIsNone(resolve_scopes(keys, None))
        self.assertIsNone(resolve_scopes(keys, "WRONG"))
        # Valid keys → their scopes
        self.assertEqual(resolve_scopes(keys, "KPRIV"), ["Private"])
        self.assertEqual(resolve_scopes(keys, "KPUB"), ["Public"])


class TestMCPAuthE2E(unittest.TestCase):
    API_KEYS = {"KPRIV": ["Private", "Internal", "Public"], "KPUB": ["Public"]}

    def setUp(self):
        self.mcp, self.app = _build_mcp(self.API_KEYS)

    def test_no_key_is_401(self):
        status, _ = anyio.run(_call_whoami, self.mcp, self.app, None)
        self.assertEqual(status, 401)

    def test_invalid_key_is_401(self):
        status, _ = anyio.run(_call_whoami, self.mcp, self.app, "NOPE")
        self.assertEqual(status, 401)

    def test_public_key_tiers(self):
        status, data = anyio.run(_call_whoami, self.mcp, self.app, "KPUB")
        self.assertEqual(status, 200)
        # ContextVar propagated all the way into the tool
        self.assertEqual(data["scopes"], ["Public"])
        # Read is filtered to Public
        self.assertEqual(data["scope_filter"], ["Public"])
        # Diagnostic denied for a Public-only key
        self.assertTrue(data["diagnostic_denied"])
        # Cannot write Private, can write Public
        self.assertTrue(data["write_private_denied"])
        self.assertFalse(data["write_public_denied"])

    def test_private_key_tiers(self):
        status, data = anyio.run(_call_whoami, self.mcp, self.app, "KPRIV")
        self.assertEqual(status, 200)
        self.assertEqual(set(data["scopes"]), {"Private", "Internal", "Public"})
        self.assertTrue(set(data["scope_filter"]) == {"Private", "Internal", "Public"})
        # Diagnostic allowed (has Private/Internal)
        self.assertFalse(data["diagnostic_denied"])
        # Can write both
        self.assertFalse(data["write_private_denied"])
        self.assertFalse(data["write_public_denied"])

    def test_query_param_key(self):
        # Claude web carries the key in the connector URL (?k=...), no header
        status, data = anyio.run(
            _call_whoami, self.mcp, self.app, None, "KPUB")
        self.assertEqual(status, 200)
        self.assertEqual(data["scopes"], ["Public"])

    def test_query_param_invalid_is_401(self):
        status, _ = anyio.run(
            _call_whoami, self.mcp, self.app, None, "NOPE")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
