"""Shared node persistence for both write surfaces (REST http_server, MCP mcp_app).

Single source of truth for locating, writing (upsert-with-merge), reading and
deleting knowledge markdown files, plus relation/scope parsing. Both surfaces are
thin adapters over these functions, so the two copies can no longer drift apart —
that drift between two hand-written copies is what produced the status-reset bug
(commit 88aba32).

Design:
- **Pure functions** taking `knowledge_dir` as the first argument, never captured.
  REST passes its module-global KNOWLEDGE_DIR (read fresh each call, so tests that
  mutate it keep working); MCP passes its closure knowledge_dir.
- **Framework-free**: invalid input raises ValueError; each surface translates it
  (REST → HTTP 400, MCP → JSON error). No FastAPI/HTTP concepts leak into core.
"""
import os
import re
import yaml
from datetime import datetime
from typing import Optional

from core.utils import (
    node_id_from_path, normalize_node_name, _normalize_segment,
    resolve_safe_folder, strip_leading_frontmatter, atomic_write, render_markdown,
)

# Syncthing conflict copies ("name.sync-conflict-...md") still end in .md but must
# never be resolved as a real node. Kept in sync with workers.file_watcher; inlined
# here to avoid a core→workers dependency.
_SYNC_CONFLICT_MARKER = ".sync-conflict-"


def _indexable(fname: str) -> bool:
    return fname.endswith(".md") and _SYNC_CONFLICT_MARKER not in fname


def _safe_filename(name: str) -> str:
    """Filename stem from a node name: keep word chars, spaces and hyphens."""
    return re.sub(r"[^\w\s-]", "", name).strip()


# ─── Lookup ─────────────────────────────────────────────────────────────────

def find_node_file(knowledge_dir: str, name: str) -> Optional[str]:
    """Locate a node's markdown file under knowledge_dir.

    Accepts a path-based node id ('a__b__c'), a relative subfolder path
    ('A/B/C'), or a bare basename. The '.md' extension is optional. The bare
    basename match is normalization-aware (case/space/hyphen/underscore), so a
    canonical id round-trips to the file that produced it.
    """
    if not name:
        return None
    cleaned = name.strip().replace("\\", "/")
    if cleaned.lower().endswith(".md"):
        cleaned = cleaned[:-3]
    base = os.path.abspath(knowledge_dir)

    # 1) Path-based id (contains __): match by computed node_id.
    if "__" in cleaned:
        target_id = normalize_node_name(cleaned)
        for root, _dirs, files in os.walk(knowledge_dir):
            for f in files:
                if not _indexable(f):
                    continue
                fp = os.path.join(root, f)
                nid, _ = node_id_from_path(fp, knowledge_dir)
                if nid == target_id:
                    return fp
        return None

    # 2) Relative subfolder path → resolve directly.
    if "/" in cleaned:
        candidate = os.path.abspath(os.path.join(base, cleaned + ".md"))
        if (candidate == base or candidate.startswith(base + os.sep)) and os.path.isfile(candidate):
            return candidate

    # 3) Bare basename: normalized comparison, consistent with node_id_from_path.
    target_norm = _normalize_segment(os.path.basename(cleaned))
    for root, _dirs, files in os.walk(knowledge_dir):
        for f in files:
            if not _indexable(f):
                continue
            if _normalize_segment(os.path.splitext(f)[0]) == target_norm:
                return os.path.join(root, f)
    return None


def read_markdown(knowledge_dir: str, name: str) -> Optional[str]:
    """Raw file content for a node, or None if not found."""
    path = find_node_file(knowledge_dir, name)
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def resolve_write_path(knowledge_dir: str, name: str, folder: str = "") -> str:
    """Absolute path for a NEW node, optionally under an existing subfolder.

    Raises ValueError (via resolve_safe_folder) on traversal or a missing folder.
    """
    target_dir = resolve_safe_folder(knowledge_dir, folder)
    return os.path.join(target_dir, f"{_safe_filename(name)}.md")


def target_node_id(knowledge_dir: str, name: str, folder: str = "") -> str:
    """Path-based node_id a write to (name, folder) will land on: the existing
    file if one matches, else the resolved new path. Used for territory authz
    before anything is written. Raises ValueError on an invalid folder."""
    existing = find_node_file(knowledge_dir, name)
    path = existing or resolve_write_path(knowledge_dir, name, folder)
    nid, _ = node_id_from_path(path, knowledge_dir)
    return nid


def territory_id(knowledge_dir: str, abs_path: str) -> str:
    """Path-based id (node_id shape) for a file or folder, for authz.territory_allows."""
    rel = os.path.relpath(os.path.abspath(abs_path), os.path.abspath(knowledge_dir))
    return "__".join(_normalize_segment(p) for p in rel.replace("\\", "/").split("/")
                     if p and p != ".")


def node_scope(knowledge_dir: str, name: str) -> str:
    """Scope from an existing node's frontmatter. Falls back to 'Private' (most
    restrictive) when the file or scope can't be read, so an unknown-scope node is
    never writable by a low-privilege key."""
    path = find_node_file(knowledge_dir, name)
    if not path or not os.path.exists(path):
        return "Private"
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        m = re.match(r"^---\n(.*?)\n---", raw, re.DOTALL)
        if m:
            fm = yaml.safe_load(m.group(1)) or {}
            return fm.get("scope", "Private")
    except Exception:
        pass
    return "Private"


# ─── Parsing ────────────────────────────────────────────────────────────────

def parse_relations(relations_str: str, source: Optional[str] = None) -> list:
    """Parse 'Target:TYPE,Other:PART_OF' into [{target, type[, source]}, ...].

    `source` (e.g. 'user') is tagged on each relation so the LLM enrichment worker
    treats them as authoritative and never overwrites them.
    """
    result = []
    for item in relations_str.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            target, rel_type = item.rsplit(":", 1)
            rel = {"target": target.strip(), "type": rel_type.strip().upper()}
        else:
            rel = {"target": item, "type": "RELATED_TO"}
        if source:
            rel["source"] = source
        result.append(rel)
    return result


def resolve_scope(scope: Optional[str], scopes: str) -> str:
    """Unify the scope vs scopes inconsistency: prefer the explicit singular
    `scope`; else the first of the legacy comma-separated `scopes`; else Private
    (never silently Public)."""
    if scope:
        return scope.strip()
    if scopes:
        first = [s.strip() for s in scopes.split(",") if s.strip()]
        if first:
            return first[0]
    return "Private"


# ─── Write / delete ───────────────────────────────────────────────────────────

def upsert(knowledge_dir: str, name: str, body: str, frontmatter_updates: dict,
           folder: str = "", defaults: Optional[dict] = None) -> tuple:
    """Find-or-create a node markdown file, merging frontmatter (upsert by name).

    On UPDATE: starts from the file's existing frontmatter and applies
    `frontmatter_updates` on top, so fields the caller didn't pass (relations
    from enrichment, a status set elsewhere, created_at/enriched_at) survive.
    On CREATE: applies `defaults` via setdefault first, then stamps `created_at`,
    then applies `frontmatter_updates` — an explicit value always wins, and a type
    default never resets an existing node's field on a later call.

    Returns (canonical_name, action) where action is 'created' or 'updated' and
    canonical_name is the path-based slug actually written (store & reuse it).
    Raises ValueError on an invalid folder for a new node.
    """
    body = strip_leading_frontmatter(body)
    existing_path = find_node_file(knowledge_dir, name)
    action = "updated" if existing_path else "created"

    frontmatter: dict = {}
    if existing_path:
        with open(existing_path, "r", encoding="utf-8") as f:
            m = re.match(r"^---\n(.*?)\n---\n", f.read(), re.DOTALL)
        frontmatter = (yaml.safe_load(m.group(1)) if m else None) or {}
    else:
        for k, v in (defaults or {}).items():
            frontmatter.setdefault(k, v)
        frontmatter.setdefault("created_at", datetime.now().strftime("%Y-%m-%d"))

    frontmatter.update(frontmatter_updates)

    path = existing_path or resolve_write_path(knowledge_dir, name, folder)
    atomic_write(path, render_markdown(frontmatter, body))
    canonical, _ = node_id_from_path(path, knowledge_dir)
    return canonical, action


def delete_node_file(knowledge_dir: str, name: str) -> bool:
    """Remove a node's markdown file. Returns True if a file was deleted."""
    path = find_node_file(knowledge_dir, name)
    if path and os.path.exists(path):
        os.remove(path)
        return True
    return False


def update_node(knowledge_dir: str, name: str, content: Optional[str] = None,
                frontmatter_updates: Optional[dict] = None) -> tuple:
    """Merge frontmatter (and optionally replace the body) of an EXISTING node.

    Reuses the existing body when `content` is None/empty; merges
    `frontmatter_updates` onto the current frontmatter (via upsert). Raises
    FileNotFoundError if the node doesn't exist. Returns (canonical, 'updated').
    """
    path = find_node_file(knowledge_dir, name)
    if not path or not os.path.exists(path):
        raise FileNotFoundError(name)
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)", raw, re.DOTALL)
    existing_body = m.group(2) if m else raw
    body = content if content else existing_body
    return upsert(knowledge_dir, name, body, frontmatter_updates or {})


# ─── Project folders ──────────────────────────────────────────────────────────

def normalize_folder_name(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", name).lower()


def folder_tree(knowledge_dir: str, base_dir: Optional[str] = None, prefix: str = "") -> str:
    """Indented tree of project folders under base_dir (default: knowledge root),
    annotating each with scope/description from its _defaults.yaml."""
    base_dir = base_dir or knowledge_dir
    try:
        entries = sorted(os.listdir(base_dir))
    except (PermissionError, FileNotFoundError):
        return ""
    dirs = [e for e in entries if os.path.isdir(os.path.join(base_dir, e))
            and not e.startswith("_") and not e.startswith(".")]
    lines = []
    for d in dirs:
        dir_path = os.path.join(base_dir, d)
        meta = ""
        defaults_path = os.path.join(dir_path, "_defaults.yaml")
        if os.path.exists(defaults_path):
            try:
                with open(defaults_path) as f:
                    defaults = yaml.safe_load(f) or {}
                parts = []
                if "scope" in defaults:
                    parts.append(f"scope={defaults['scope']}")
                if "description" in defaults:
                    parts.append(f"'{defaults['description']}'")
                if parts:
                    meta = f" [{', '.join(parts)}]"
            except Exception:
                pass
        lines.append(f"{prefix}{d}/{meta}")
        subtree = folder_tree(knowledge_dir, dir_path, prefix + "  ")
        if subtree:
            lines.append(subtree)
    return "\n".join(lines)


def project_folder_path(knowledge_dir: str, name: str, parent: str = "") -> str:
    """Absolute path a new project folder (name, under parent) would occupy.
    Raises ValueError on a bad/absent parent. Used for territory authz before
    creating anything."""
    base_path = resolve_safe_folder(knowledge_dir, parent)
    safe_name = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")
    return os.path.join(base_path, safe_name)


def project_defaults(knowledge_dir: str, folder: str) -> dict:
    """Current _defaults.yaml of an existing project folder (or {}). Raises
    ValueError on a bad/absent folder. Read before authz on update."""
    folder_path = resolve_safe_folder(knowledge_dir, folder)
    defaults_path = os.path.join(folder_path, "_defaults.yaml")
    if os.path.exists(defaults_path):
        with open(defaults_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def create_project(knowledge_dir: str, name: str, description: str = "",
                   scope: str = "Private", parent: str = "") -> dict:
    """Create a project folder with _defaults.yaml (+ an index .md if description).

    Raises ValueError on a bad parent or if a folder with the same name already
    exists at that level. Returns {result_path, warnings} (warnings = similar
    folder names, for the caller to surface).
    """
    base_path = resolve_safe_folder(knowledge_dir, parent)
    safe_name = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")

    existing_dirs = [d for d in os.listdir(base_path)
                     if os.path.isdir(os.path.join(base_path, d)) and not d.startswith("_")]
    for existing in existing_dirs:
        if existing.lower() == safe_name.lower():
            raise ValueError(f"Folder '{existing}' already exists at this level.")
    warnings = [e for e in existing_dirs
                if normalize_folder_name(e) == normalize_folder_name(safe_name)]

    folder_path = os.path.join(base_path, safe_name)
    os.makedirs(folder_path, exist_ok=True)

    defaults = {"project": name, "scope": scope}
    if description:
        defaults["description"] = description
    atomic_write(os.path.join(folder_path, "_defaults.yaml"),
                 yaml.dump(defaults, allow_unicode=True, default_flow_style=False))

    if description:
        index_fm = {"type": "Node", "scope": scope,
                    "created_at": datetime.now().strftime("%Y-%m-%d")}
        atomic_write(os.path.join(folder_path, f"{safe_name}.md"),
                     render_markdown(index_fm, f"# {name}\n\n{description}"))

    result_path = os.path.join(parent, safe_name) if parent else safe_name
    return {"result_path": result_path, "warnings": warnings}


def update_project(knowledge_dir: str, folder: str, description: str = "",
                   scope: str = "") -> dict:
    """Update a project folder's _defaults.yaml in place (description and/or scope).
    Raises ValueError on a bad/absent folder. Returns the updated defaults."""
    folder_path = resolve_safe_folder(knowledge_dir, folder)
    defaults_path = os.path.join(folder_path, "_defaults.yaml")
    defaults = {}
    if os.path.exists(defaults_path):
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
    if description:
        defaults["description"] = description
    if scope:
        defaults["scope"] = scope
    atomic_write(defaults_path, yaml.dump(defaults, allow_unicode=True, default_flow_style=False))
    return defaults
