#!/usr/bin/env python3
"""Re-seed the thermal activation of the knowledge graph from file dates.

A KuzuDB rebuild (e.g. after removing a bloated WAL) recreates every node with
the default flat activation (~0.5), wiping the "what's hot" signal the morning
briefing relies on — so the briefing turns generic. This utility bootstraps a
sensible gradient: each node is seeded as if it had last been touched at the
most recent date known for its file, then the model's own decay is applied so
recent nodes stay warm and old ones cool down.

It is NOT a chronological feed: it only re-initializes the activation. From the
seed onward the normal thermal model (decay + interactions) takes over. Run it
after a rebuild, or any time the activation has gone flat — it's idempotent
(recomputed from dates each run).

Date used per node: max(file mtime, frontmatter created_at, frontmatter
enriched_at). The frontmatter dates survive Syncthing/migration even when mtime
gets reset; mtime captures recent edits when it's trustworthy. Max takes the
strongest available signal.

IMPORTANT: run with the gateway STOPPED — KuzuDB allows a single writer and the
gateway holds the lock.

Usage:
  python3 scripts/seed_thermal_activation.py                 # dry run (preview)
  python3 scripts/seed_thermal_activation.py --apply         # write activations
"""
import argparse
import os
import sys
import time
import datetime
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml
from core.kuzu_manager import KuzuManager
from core.attention import AttentionModel
from core.utils import node_id_from_path
from workers.file_watcher import _is_indexable_md

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _to_ts(value):
    """Coerce a frontmatter date (date/datetime object or string) to epoch, or None."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.timestamp()
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day).timestamp()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(value.strip(), fmt).timestamp()
            except ValueError:
                continue
    return None


def _frontmatter(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        m = re.match(r"^---\n(.*?)\n---", raw, re.DOTALL)
        if m:
            return yaml.safe_load(m.group(1)) or {}
    except Exception:
        pass
    return {}


def _node_date(path, source):
    """Date (epoch) for a node, per the chosen source.

      frontmatter : max(created_at, enriched_at)  — stable across sync/migration,
                    and enriched_at tracks the last real BODY change (gated on
                    body hash), not system frontmatter rewrites. Default.
      mtime       : filesystem mtime — captures recent edits, but enrichment
                    rewrites and migrations can reset it, collapsing the signal.
      max         : max of all of the above.
    """
    candidates = []
    if source in ("mtime", "max"):
        try:
            candidates.append(os.path.getmtime(path))
        except OSError:
            pass
    if source in ("frontmatter", "max"):
        fm = _frontmatter(path)
        for key in ("created_at", "enriched_at"):
            ts = _to_ts(fm.get(key))
            if ts:
                candidates.append(ts)
    return max(candidates) if candidates else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--knowledge-dir", default=os.path.join(BASE_DIR, "knowledge"))
    ap.add_argument("--db-path", default=os.path.join(BASE_DIR, "data", "kuzu_main"))
    ap.add_argument("--settings", default=os.path.join(BASE_DIR, "config", "settings.yaml"))
    ap.add_argument("--apply", action="store_true", help="write activations (default: dry run)")
    ap.add_argument("--date-source", choices=("frontmatter", "mtime", "max"), default="frontmatter",
                    help="which dates to seed from (default: frontmatter — robust to sync/migration)")
    ap.add_argument("--top", type=int, default=15, help="how many warmest nodes to preview")
    args = ap.parse_args()

    config = {}
    if os.path.exists(args.settings):
        with open(args.settings) as f:
            config = yaml.safe_load(f) or {}
    attn_cfg = config.get("attention", {})

    # Build the per-node target date map from files
    now = time.time()
    file_dates = {}  # node_id -> ts
    for root, _dirs, files in os.walk(args.knowledge_dir):
        for f in files:
            if not _is_indexable_md(f):
                continue
            path = os.path.join(root, f)
            node_id, _ = node_id_from_path(path, args.knowledge_dir)
            ts = _node_date(path, args.date_source)
            if ts:
                file_dates[node_id] = max(file_dates.get(node_id, 0), ts)

    if not file_dates:
        print(f"No indexable markdown files under {args.knowledge_dir}", file=sys.stderr)
        sys.exit(1)

    # Open KuzuDB (gateway must be stopped — single writer lock)
    try:
        kuzu_mgr = KuzuManager(db_path=args.db_path)
    except Exception as e:
        print(f"Could not open KuzuDB ({e}).\nIs the gateway running? Stop it first "
              f"(sudo systemctl stop mnemosyne).", file=sys.stderr)
        sys.exit(1)

    am = AttentionModel(kuzu_mgr, config=attn_cfg)
    floor = am.recency_activation
    decay_rates = am.decay_rates

    # Which of these nodes actually exist in the graph
    existing = {n["name"] for n in kuzu_mgr.get_all_nodes()}
    targets = {nid: ts for nid, ts in file_dates.items() if nid in existing}
    missing = len(file_dates) - len(targets)

    def _preview_activation(node_type, ts):
        # Reference nodes now decay slowly too (no longer exempt).
        rate = decay_rates.get(node_type or "Node", decay_rates.get("Node", 0.0025))
        hours = max(0.0, (now - ts) / 3600)
        return max(floor * ((1 - rate) ** hours), 0.0)

    print(f"\nKnowledge dir : {args.knowledge_dir}")
    print(f"Files with a date: {len(file_dates)}   matched to graph nodes: {len(targets)}"
          f"   (no graph node: {missing})")
    print(f"Recency floor (seed): {floor}   date-source: {args.date_source}   "
          f"mode: {'APPLY' if args.apply else 'DRY RUN'}\n")

    if not args.apply:
        # Estimate node types for a faithful preview
        types = {n["name"]: n.get("node_type", "Node") for n in
                 (kuzu_mgr.get_node(nid) or {"name": nid} for nid in targets)}
        scored = sorted(
            ((nid, _preview_activation(types.get(nid, "Node"), ts), ts) for nid, ts in targets.items()),
            key=lambda x: x[1], reverse=True,
        )
        print(f"Warmest {min(args.top, len(scored))} nodes after re-seed (preview):")
        for nid, act, ts in scored[:args.top]:
            d = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            print(f"  {act:.3f}  {d}  {nid[:60]}")
        print(f"\nDry run. Re-run with --apply to write {len(targets)} activations.")
        return

    for nid, ts in targets.items():
        kuzu_mgr.seed_activation(nid, floor, ts)
    am.apply_decay()  # decays each node from its seeded reference_ts to now
    print(f"Seeded and decayed {len(targets)} nodes from file dates. "
          f"The thermal model takes over from here.")


if __name__ == "__main__":
    main()
