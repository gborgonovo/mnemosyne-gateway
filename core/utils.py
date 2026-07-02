import os
import re
import tempfile
import yaml


def atomic_write(path: str, content: str, encoding: str = "utf-8") -> None:
    """Write text to `path` atomically.

    Writes to a temp file in the *same* directory, flushes + fsyncs it, then
    os.replace()s it over the target. os.replace is atomic on a single
    filesystem, so a crash mid-write can never leave a half-written or truncated
    file for the watcher to index or Syncthing to propagate — readers always see
    either the old file or the complete new one, never a torn state.

    The temp name is dotted and ends in '.part' (not '.md') so the file watcher,
    which only indexes '.md' files, ignores it during the brief window before the
    rename; the rename itself surfaces to watchdog as the final '.md' path.
    """
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".mnemo-tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def render_markdown(frontmatter: dict, body: str) -> str:
    """Serialize a frontmatter mapping + body into a markdown document string.

    Single chokepoint for the '---\\n<yaml>---\\n\\n<body>' layout, so every
    writer produces byte-identical framing and can hand the result to
    atomic_write().
    """
    fm = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
    return f"---\n{fm}---\n\n{body}"


def readable_name(node: dict) -> str:
    """Human-readable name for a node dict ({name, display_name}).

    Prefers display_name; otherwise derives a label from the last segment of the
    path-based node_id (underscores -> spaces) instead of exposing the raw slug.
    Shared by the briefing and the InitiativeEngine so neither leaks node_ids.
    """
    nid = node.get("name", "") or ""
    dn = node.get("display_name")
    if dn and dn != nid:
        return dn
    last = nid.split("__")[-1] if nid else nid
    return last.replace("_", " ").strip() or nid


def resolve_safe_folder(knowledge_dir: str, folder: str) -> str:
    """Resolve and validate a client-supplied subfolder under knowledge_dir.

    Returns the absolute target directory. Nested subfolders separated by '/'
    are allowed (e.g. 'Sistema/Claude_Code', used by the memory-sync hook), but
    absolute paths and any '..' traversal component are rejected, and the result
    is guaranteed to stay inside knowledge_dir. An empty folder resolves to the
    knowledge root. Raises ValueError on a rejected or non-existent folder.
    """
    base = os.path.abspath(knowledge_dir)
    if not folder:
        return base
    cleaned = folder.strip().replace("\\", "/")
    if cleaned.startswith("/") or os.path.isabs(cleaned):
        raise ValueError(f"Invalid folder '{folder}': absolute paths are not allowed.")
    parts = [p for p in cleaned.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"Invalid folder '{folder}': parent-directory references are not allowed.")
    target = os.path.abspath(os.path.join(base, *parts))
    if target != base and not target.startswith(base + os.sep):
        raise ValueError(f"Invalid folder '{folder}': path escapes the knowledge directory.")
    if not os.path.isdir(target):
        raise ValueError(f"Folder '{folder}' does not exist.")
    return target


def strip_leading_frontmatter(body: str) -> str:
    """Remove any frontmatter block(s) accidentally embedded at the start of a body.

    Guards against a caller passing raw file content (frontmatter included) as
    the new body, which would otherwise nest a second frontmatter block on the
    next write. Loops so repeated nesting is collapsed in one pass. Only strips
    a leading block that parses as a non-empty YAML mapping, so a stray '---'
    horizontal rule at the top of real content is left untouched.
    """
    if not body:
        return body
    changed = False
    while True:
        candidate = body.lstrip()
        m = re.match(r'^---\n(.*?)\n---\n?(.*)', candidate, re.DOTALL)
        if not m:
            break
        try:
            parsed = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            break
        if not isinstance(parsed, dict) or not parsed:
            break
        body = m.group(2)
        changed = True
    return body.lstrip("\n") if changed else body


def _normalize_segment(name: str) -> str:
    """Normalize a single path segment (no __ separators) to a DB-safe string."""
    normalized = name.lower().strip()
    normalized = re.sub(r'[\s\-]+', '_', normalized)
    normalized = re.sub(r'[^\w]', '', normalized)
    normalized = re.sub(r'_{2,}', '_', normalized)
    return normalized.strip('_')


def normalize_node_name(name: str) -> str:
    """Standardize a node name or path-based node ID for use as a primary key.

    Path-based IDs use '__' (double underscore) as a segment separator
    (e.g. 'ganaghello__spazi__stalla'). The separator is preserved so that
    IDs round-trip correctly through this function. Single-segment names
    (no '__') are normalized as before: lowercase, spaces/dashes to underscores,
    non-alphanumeric removed.
    """
    if not name:
        return "unnamed"
    name = name.strip()
    if "__" in name:
        parts = name.split("__")
        normed = [_normalize_segment(p) for p in parts if p]
        return "__".join(normed) if normed else "unnamed"
    return _normalize_segment(name)


def node_id_from_path(filepath: str, knowledge_dir: str) -> tuple:
    """Derive the path-based node ID and display name from a markdown file path.

    Returns (node_id, display_name) where:
      node_id      = path segments joined with '__', each segment normalized
                     e.g. 'ganaghello__spazi__stalla__stalla'
      display_name = the filename without extension (original casing)
                     e.g. 'Stalla'

    Files at the knowledge root have no folder prefix; the node_id is just
    the normalized filename: 'knowledge/alfred.md' -> ('alfred', 'alfred').
    """
    knowledge_abs = os.path.abspath(knowledge_dir)
    file_abs = os.path.abspath(filepath)
    rel = os.path.relpath(file_abs, knowledge_abs)       # e.g. 'Ganaghello/Spazi/Stalla/Stalla.md'
    rel_no_ext = os.path.splitext(rel)[0]                # e.g. 'Ganaghello/Spazi/Stalla/Stalla'
    parts = rel_no_ext.replace("\\", "/").split("/")     # e.g. ['Ganaghello', 'Spazi', 'Stalla', 'Stalla']
    display_name = parts[-1]                             # e.g. 'Stalla'
    normed_parts = [_normalize_segment(p) for p in parts if p and p != "."]
    node_id = "__".join(normed_parts)                   # e.g. 'ganaghello__spazi__stalla__stalla'
    return node_id, display_name
