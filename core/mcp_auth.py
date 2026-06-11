"""Authentication and authorization for the MCP transport.

The MCP Streamable HTTP app is mounted as an ASGI sub-app under the gateway.
FastAPI's `Depends(verify_api_key)` does NOT propagate to mounted sub-apps, so
the MCP surface would otherwise be completely unauthenticated. This module adds:

  - MCPAuthMiddleware: an ASGI middleware that extracts and validates X-API-Key
    on every HTTP request before it reaches the MCP transport. With auth
    configured, a missing/invalid key is rejected with 401 (fail-closed).
  - A task-local ContextVar carrying the caller's allowed scopes, since MCP tool
    functions receive no request object. Tools read it via the helpers below.

Authorization tiers (enforced inside the tools):
  - read      : results filtered to the caller's scopes (scope_filter)
  - diagnostic: debug_filesystem / inspect_file_raw / gardening — require
                Internal or Private (require_privileged)
  - write     : create/update/delete — require the target node's scope
                (assert_write)
"""
import json
from contextvars import ContextVar
from typing import List, Optional

# Allowed scopes for the current request. "*" means unrestricted (dev mode with
# no api_keys.yaml configured). Empty list should never be observed inside a tool
# because the middleware rejects unauthenticated requests before they run.
current_scopes: ContextVar[List[str]] = ContextVar("current_scopes", default=["*"])

PRIVILEGED_SCOPES = ("Internal", "Private")


def resolve_scopes(api_keys: dict, api_key: Optional[str]) -> Optional[List[str]]:
    """Map an API key to its allowed scopes.

    Returns:
      - ["*"] if no api_keys are configured (dev: auth disabled)
      - the key's scope list if the key is valid
      - None if a key is required but missing or invalid (caller should 401)
    """
    if not api_keys:
        return ["*"]
    if not api_key:
        return None
    if api_key not in api_keys:
        return None
    cfg = api_keys[api_key]
    if isinstance(cfg, list):
        return cfg
    return cfg.get("scopes", ["Public"])


# ─── Tool-side helpers (read the ContextVar) ────────────────────────────────

def get_scopes() -> List[str]:
    return current_scopes.get()


def is_unrestricted() -> bool:
    return "*" in current_scopes.get()


def scope_filter() -> Optional[List[str]]:
    """Scope list to pass to read queries, or None for unrestricted access."""
    scopes = current_scopes.get()
    if "*" in scopes:
        return None
    return list(scopes)


def has_privileged() -> bool:
    """True if the caller may use diagnostic/maintenance tools."""
    scopes = current_scopes.get()
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


def can_write(scope: str) -> bool:
    scopes = current_scopes.get()
    if "*" in scopes:
        return True
    return scope in scopes


def assert_write(scope: str) -> Optional[str]:
    """Guard for write tools. Returns a JSON error string to return directly if
    the caller may not write the given scope, or None if access is granted."""
    if can_write(scope):
        return None
    return json.dumps({
        "status": "error",
        "message": f"⛔ Accesso negato: la chiave API non può scrivere nodi con scope '{scope}'.",
    })


# ─── ASGI middleware ────────────────────────────────────────────────────────

class MCPAuthMiddleware:
    """Validates X-API-Key on every HTTP request to the wrapped MCP app and
    publishes the resolved scopes into the `current_scopes` ContextVar.

    Non-HTTP scopes (lifespan, websocket) pass through untouched.
    """

    def __init__(self, app, api_keys: dict):
        self.app = app
        self.api_keys = api_keys

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        api_key = self._extract_api_key(scope)
        scopes = resolve_scopes(self.api_keys, api_key)

        if scopes is None:
            await self._send_401(send)
            return

        token = current_scopes.set(scopes)
        try:
            await self.app(scope, receive, send)
        finally:
            current_scopes.reset(token)

    @staticmethod
    def _extract_api_key(scope) -> Optional[str]:
        # ASGI header names are lowercased per spec; match defensively anyway.
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-api-key":
                return value.decode("latin-1") or None
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
