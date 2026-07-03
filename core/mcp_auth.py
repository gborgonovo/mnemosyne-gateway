"""Authentication and authorization for the MCP transport.

The MCP Streamable HTTP app is mounted as an ASGI sub-app under the gateway.
FastAPI's `Depends(verify_api_key)` does NOT propagate to mounted sub-apps, so
the MCP surface would otherwise be completely unauthenticated. This module adds:

  - MCPAuthMiddleware: an ASGI middleware that extracts and validates X-API-Key
    on every HTTP request before it reaches the MCP transport. With auth
    configured, a missing/invalid key is rejected with 401 (fail-closed).
  - A task-local ContextVar carrying the caller's grants (scopes + read/write
    territories), since MCP tool functions receive no request object. Tools read
    it via the helpers below.

Authorization axes (enforced inside the tools), always in AND:
  - scope     : confidentiality tier the caller may touch (scope_filter for
                reads, can_write/assert_write for writes)
  - territory : folder namespace the caller may read (read_filter_grants) or
                write (assert_write). See core.authz.
  - privilege : diagnostic tools (debug_filesystem / inspect_file_raw /
                gardening) require Internal or Private (require_privileged)
"""
import json
from contextvars import ContextVar
from typing import List, Optional
from urllib.parse import parse_qs

from core.authz import territory_allows

# Grants for the current request: {scopes, read, write}. The default is the
# unrestricted dev grant ("*"), used only when no api_keys are configured; the
# middleware rejects unauthenticated requests before any tool runs otherwise.
_UNRESTRICTED = {"scopes": ["*"], "read": ["*"], "write": ["*"]}
current_grants: ContextVar[dict] = ContextVar("current_grants", default=_UNRESTRICTED)

PRIVILEGED_SCOPES = ("Internal", "Private")


def resolve_grants(grants_map: dict, api_key: Optional[str]) -> Optional[dict]:
    """Map an API key to its normalized grants {scopes, read, write}.

    Returns:
      - the unrestricted dev grant if no keys are configured (auth disabled)
      - the key's grants if the key is valid
      - None if a key is required but missing or invalid (caller should 401)

    grants_map is the pre-resolved {key: {scopes, read, write}} built once at
    startup (see gateway.http_server.API_GRANTS), so no normalization happens
    per request.
    """
    if not grants_map:
        return dict(_UNRESTRICTED)
    if not api_key:
        return None
    if api_key not in grants_map:
        return None
    return grants_map[api_key]


# ─── Tool-side helpers (read the ContextVar) ────────────────────────────────

def get_scopes() -> List[str]:
    return current_grants.get().get("scopes", [])


def is_unrestricted() -> bool:
    return "*" in get_scopes()


def scope_filter() -> Optional[List[str]]:
    """Scope list to pass to read queries, or None for unrestricted access."""
    scopes = get_scopes()
    if "*" in scopes:
        return None
    return list(scopes)


def read_filter_grants() -> Optional[List[str]]:
    """Read-territory grants to filter query results, or None when unrestricted."""
    read = current_grants.get().get("read", ["*"])
    if "*" in read:
        return None
    return list(read)


def has_privileged() -> bool:
    """True if the caller may use diagnostic/maintenance tools."""
    scopes = get_scopes()
    if "*" in scopes:
        return True
    return any(s in scopes for s in PRIVILEGED_SCOPES)


def require_privileged() -> Optional[str]:
    """Guard for diagnostic/maintenance tools. Returns an error string to return
    directly if the caller is not allowed, or None if access is granted."""
    if has_privileged():
        return None
    return ("⛔ Accesso negato: questo strumento richiede una chiave API "
            "con scope Internal o Private.")


def can_write(scope: str, node_id: str) -> bool:
    """True only if the caller may write BOTH this scope AND this territory."""
    grants = current_grants.get()
    scopes = grants.get("scopes", [])
    scope_ok = "*" in scopes or scope in scopes
    return scope_ok and territory_allows(grants.get("write", []), node_id)


def assert_write(scope: str, node_id: str) -> Optional[str]:
    """Guard for write tools. Returns a JSON error string to return directly if
    the caller may not write the given (scope, territory), or None if allowed."""
    grants = current_grants.get()
    scopes = grants.get("scopes", [])
    if not ("*" in scopes or scope in scopes):
        return json.dumps({
            "status": "error",
            "message": f"⛔ Accesso negato: la chiave API non può scrivere nodi con scope '{scope}'.",
        })
    if not territory_allows(grants.get("write", []), node_id):
        return json.dumps({
            "status": "error",
            "message": (f"⛔ Accesso negato: la chiave API non può scrivere nel "
                        f"territorio di '{node_id}'."),
        })
    return None


# ─── ASGI middleware ────────────────────────────────────────────────────────

class MCPAuthMiddleware:
    """Validates X-API-Key on every HTTP request to the wrapped MCP app and
    publishes the resolved grants into the `current_grants` ContextVar.

    Non-HTTP scopes (lifespan, websocket) pass through untouched.
    """

    def __init__(self, app, grants_map: dict):
        self.app = app
        self.grants_map = grants_map

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        api_key = self._extract_api_key(scope)
        grants = resolve_grants(self.grants_map, api_key)

        if grants is None:
            await self._send_401(send)
            return

        token = current_grants.set(grants)
        try:
            await self.app(scope, receive, send)
        finally:
            current_grants.reset(token)

    @staticmethod
    def _extract_api_key(scope) -> Optional[str]:
        """Extract the API key from the X-API-Key header, falling back to the
        ?k= query parameter.

        Claude Code can send a custom header; Claude web connectors cannot, so
        the key is carried in the connector URL's query string instead. The
        header takes precedence when both are present.
        """
        # ASGI header names are lowercased per spec; match defensively anyway.
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-api-key":
                decoded = value.decode("latin-1")
                if decoded:
                    return decoded

        query_string = scope.get("query_string", b"")
        if query_string:
            params = parse_qs(query_string.decode("latin-1"))
            values = params.get("k")
            if values and values[0]:
                return values[0]
        return None

    @staticmethod
    async def _send_401(send):
        body = json.dumps({"detail": "X-API-Key header missing or invalid"}).encode()
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({"type": "http.response.body", "body": body})
