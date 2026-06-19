#!/usr/bin/env python3
"""Triage Syncthing .sync-conflict-* files in the knowledge base.

Syncthing creates "name.sync-conflict-DATE-TIME-DEVICE.md" copies when the same
file is edited on two devices before sync reconciles them. In Mnemosyne most of
these are noise: the gateway rewrites frontmatter (enriched_hash, relations),
so the conflict copy usually differs ONLY in the frontmatter, not in the body.

This script classifies each conflict file WITHOUT deleting anything by default:

  SAFE    original exists and body is identical → frontmatter-only noise, deletable
  REVIEW  original exists but body differs      → possible lost edit, look first
  ORPHAN  original missing                      → look first, never auto-deleted

Run read-only first; add --delete to remove only the SAFE ones.

Usage:
  python3 scripts/triage_sync_conflicts.py [--knowledge-dir DIR] [--delete] [--verbose]
"""
import argparse
import os
import re
import sys

SYNC_CONFLICT_MARKER = ".sync-conflict-"


def _split_body(text: str) -> str:
    """Return the body (content after YAML frontmatter), or the whole text."""
    m = re.match(r'^---\n.*?\n---\n?(.*)', text, re.DOTALL)
    return m.group(1) if m else text


def _read(path: str) -> str:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def _original_path(conflict_path: str) -> str:
    """Map a conflict copy back to its original filename.

    'note.sync-conflict-20260615-013600-ABCDEF.md' → 'note.md'
    Robust to whatever Syncthing puts between the marker and the extension.
    """
    d = os.path.dirname(conflict_path)
    name = os.path.basename(conflict_path)
    base = name[:name.find(SYNC_CONFLICT_MARKER)]
    ext = os.path.splitext(name)[1]
    return os.path.join(d, base + ext)


def find_conflicts(knowledge_dir: str):
    for root, _dirs, files in os.walk(knowledge_dir):
        for f in files:
            if SYNC_CONFLICT_MARKER in f:
                yield os.path.join(root, f)


def classify(conflict_path: str):
    original = _original_path(conflict_path)
    if not os.path.exists(original):
        return "ORPHAN", original
    try:
        same_body = _split_body(_read(conflict_path)).strip() == _split_body(_read(original)).strip()
    except Exception as e:
        return "REVIEW", f"{original} (read error: {e})"
    return ("SAFE" if same_body else "REVIEW"), original


def main():
    default_kb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "knowledge")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--knowledge-dir", default=os.path.normpath(default_kb))
    ap.add_argument("--delete", action="store_true", help="delete the SAFE conflict files")
    ap.add_argument("--verbose", action="store_true", help="list every file, not just counts")
    args = ap.parse_args()

    if not os.path.isdir(args.knowledge_dir):
        print(f"Knowledge dir not found: {args.knowledge_dir}", file=sys.stderr)
        sys.exit(1)

    buckets = {"SAFE": [], "REVIEW": [], "ORPHAN": []}
    for cp in find_conflicts(args.knowledge_dir):
        verdict, original = classify(cp)
        buckets[verdict].append((cp, original))

    total = sum(len(v) for v in buckets.values())
    print(f"\nScanned: {args.knowledge_dir}")
    print(f"Conflict files found: {total}")
    print(f"  SAFE   (frontmatter-only, deletable): {len(buckets['SAFE'])}")
    print(f"  REVIEW (body differs, look first):    {len(buckets['REVIEW'])}")
    print(f"  ORPHAN (no original, look first):     {len(buckets['ORPHAN'])}\n")

    if args.verbose:
        for verdict in ("REVIEW", "ORPHAN", "SAFE"):
            for cp, original in buckets[verdict]:
                print(f"  [{verdict}] {cp}")
        print()

    # REVIEW/ORPHAN always listed so they are never silently lost
    for verdict in ("REVIEW", "ORPHAN"):
        if buckets[verdict] and not args.verbose:
            print(f"-- {verdict} (inspect manually) --")
            for cp, _original in buckets[verdict]:
                print(f"  {cp}")
            print()

    if not args.delete:
        if buckets["SAFE"]:
            print(f"Dry run. Re-run with --delete to remove the {len(buckets['SAFE'])} SAFE files.")
        return

    deleted = 0
    for cp, _original in buckets["SAFE"]:
        try:
            os.remove(cp)
            deleted += 1
        except OSError as e:
            print(f"  failed to delete {cp}: {e}", file=sys.stderr)
    print(f"Deleted {deleted} SAFE conflict files. "
          f"REVIEW ({len(buckets['REVIEW'])}) and ORPHAN ({len(buckets['ORPHAN'])}) left untouched.")


if __name__ == "__main__":
    main()
