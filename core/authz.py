"""Per-key authorization: scopes (confidentiality) + namespaces (territory).

Two orthogonal axes gate every access, always in AND:

  - scope     : how confidential a node is (Public/Internal/Private). Attached to
                the node. A key declares which scopes it may touch.
  - namespace : which part of the folder tree a key may operate in. Declared per
                key as `read` and `write` lists of folder prefixes. A node's
                territory is derived from its path-based node_id.

Node IDs are path segments joined by '__' (see core.utils.node_id_from_path),
e.g. 'ganaghello__spazi__stalla__stalla'. A territory grant like
'Sistema/Claude_Code' is normalized to segments ['sistema', 'claude_code'] and
matched as a *prefix* of the node's segments, on the segment boundary (so 'Gana'
never matches 'Ganaghello'). '*' matches everything; an empty list matches
nothing (read-only when `write` is empty).

Fail-closed by design: a key that omits `read`/`write` grants nothing. The
gateway validates the key file at startup (validate_api_keys) and refuses to
start on a malformed key rather than applying a permissive default.
"""
from typing import List, Optional, Tuple

from core.utils import _normalize_segment


def _territory_segments(grant: str) -> List[str]:
    """Normalize a folder-prefix grant to node_id-style segments."""
    return [_normalize_segment(p) for p in grant.replace("\\", "/").split("/") if p]


def territory_allows(grants: List[str], node_id: str) -> bool:
    """True if node_id falls inside at least one of the folder-prefix grants.

    '*' allows everything; an empty/None grants list allows nothing. Matching is
    on the segment boundary: grant segments must be a prefix of the node_id
    segments, so 'Ganaghello' covers its whole subtree but 'Gana' matches nothing.
    """
    if not grants:
        return False
    if "*" in grants:
        return True
    node_segs = [s for s in node_id.split("__") if s]
    for g in grants:
        g_segs = _territory_segments(g)
        if g_segs and g_segs == node_segs[:len(g_segs)]:
            return True
    return False


def normalize_key_config(cfg, lenient: bool = False) -> dict:
    """Coerce a single api_keys.yaml entry into {scopes, read, write}.

    Accepts the legacy plain-list form (scopes only) and the mapping form.

    `lenient` selects the default for an absent territory field:
      - False (production, auth_required=true): missing read/write default to []
        (fail-closed) — a key that declares no territory can do nothing. Under
        auth_required the gateway won't even reach here with such a key, because
        validate_api_keys refuses startup first; [] is the safe baseline.
      - True (local dev, auth_required=false): missing read/write default to
        ["*"], so an old-format key keeps full access, consistent with the
        "no api_keys.yaml = open dev mode" posture.
    """
    default = ["*"] if lenient else []
    if isinstance(cfg, list):
        return {"scopes": list(cfg), "read": list(default), "write": list(default)}
    if isinstance(cfg, dict):
        return {
            "scopes": list(cfg.get("scopes", [])),
            "read": list(cfg.get("read", default)),
            "write": list(cfg.get("write", default)),
        }
    return {"scopes": [], "read": list(default), "write": list(default)}


def _redact(key: str) -> str:
    """Show only the last 4 chars of an API key, for safe log/error output."""
    return f"…{key[-4:]}" if key and len(key) >= 4 else "…"


def validate_api_keys(api_keys: dict) -> List[str]:
    """Return a list of human-readable problems with the key file, empty if OK.

    A key is well-formed when it is a mapping that declares `scopes`, `read` and
    `write` explicitly. The legacy plain-list form and any mapping missing
    `read`/`write` are reported so the operator can fix them instead of the
    gateway silently granting or silently denying access.
    """
    problems = []
    for key, cfg in api_keys.items():
        tag = _redact(key)
        if isinstance(cfg, list):
            problems.append(
                f"chiave '{tag}': formato vecchio (lista di scope). "
                f"Converti a un blocco con 'scopes', 'read' e 'write' espliciti."
            )
            continue
        if not isinstance(cfg, dict):
            problems.append(f"chiave '{tag}': valore non valido (atteso un blocco YAML).")
            continue
        for field in ("scopes", "read", "write"):
            if field not in cfg:
                problems.append(f"chiave '{tag}': manca il campo '{field}'.")
            elif not isinstance(cfg[field], list):
                problems.append(f"chiave '{tag}': il campo '{field}' deve essere una lista.")
    return problems


def format_validation_error(problems: List[str]) -> str:
    """Build the explicit, actionable refuse-to-start message.

    Names each offending key and what to fix, so an operator never faces a
    silent exit whose cause is invisible.
    """
    lines = [
        "=" * 64,
        "MNEMOSYNE: AVVIO RIFIUTATO — configurazione chiavi API non valida",
        "=" * 64,
        "auth_required è true, quindi ogni chiave in config/api_keys.yaml deve",
        "dichiarare esplicitamente 'scopes', 'read' e 'write' (namespace ACL).",
        "Nessun default implicito viene applicato: fail-closed, per non concedere",
        "accessi non voluti.",
        "",
        "Problemi trovati:",
    ]
    lines += [f"  - {p}" for p in problems]
    lines += [
        "",
        "Esempio di blocco valido:",
        '  "mnm_sk_esempio_…":',
        "    scopes: [Private, Internal, Public]",
        '    read:  ["*"]',
        '    write: ["*"]',
        "",
        "Correggi config/api_keys.yaml e riavvia.",
        "=" * 64,
    ]
    return "\n".join(lines)


def filter_by_read(items: list, read_grants: Optional[List[str]], id_key: str) -> list:
    """Drop items whose node id is outside the caller's read territory.

    read_grants None (or containing '*') means unrestricted: returned as-is
    (fast path, no per-item work). id_key names the dict field holding the
    path-based node id ('node_id' for search results, 'name' for graph nodes).
    """
    if not read_grants or "*" in read_grants:
        return items
    return [it for it in items if territory_allows(read_grants, str(it.get(id_key, "")))]
