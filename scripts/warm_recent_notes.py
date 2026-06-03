#!/usr/bin/env python3
"""One-time: warm notes modified in the last N days up to the recency floor.

Retroactively gives recently-touched notes the same heat the live file_edit
path now assigns (recency_activation, default 0.75), so they appear in the
next briefing without having to re-edit each one by hand.

IMPORTANT: run with the gateway STOPPED — it holds the exclusive KuzuDB
writer lock, so this will fail with a lock error while it is up. Cold-boot
sync on startup preserves activation (MERGE ON MATCH), so the warmed values
survive the restart:

    ./scripts/stop.sh
    .venv/bin/python3 scripts/warm_recent_notes.py --days 7
    ./scripts/start.sh

Use --dry-run first to preview what would change.
"""
import os
import sys
import time
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from core.utils import normalize_node_name

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KNOWLEDGE = os.path.join(BASE, 'knowledge')


def load_recency_floor() -> float:
    import yaml
    path = os.path.join(BASE, 'config', 'settings.yaml')
    try:
        cfg = yaml.safe_load(open(path)) or {}
        return float(cfg.get('attention', {}).get('recency_activation', 0.75))
    except Exception:
        return 0.75


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--days', type=float, default=7,
                    help='warm notes whose file was modified in the last N days (default: 7)')
    ap.add_argument('--dry-run', action='store_true',
                    help='preview changes without writing')
    args = ap.parse_args()

    floor = load_recency_floor()
    cutoff = time.time() - args.days * 86400

    try:
        kuzu = KuzuManager(db_path=os.path.join(BASE, 'data', 'kuzu_main'))
    except Exception as e:
        print(f"❌ Could not open KuzuDB: {e}")
        print("   Is the gateway running? Stop it first: ./scripts/stop.sh")
        sys.exit(1)

    warmed, skipped, missing = 0, 0, 0
    for root, _dirs, files in os.walk(KNOWLEDGE):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            path = os.path.join(root, fname)
            if os.path.getmtime(path) < cutoff:
                continue
            raw_name = os.path.splitext(fname)[0]
            norm = normalize_node_name(raw_name)
            node = kuzu.get_node(norm)
            if not node:
                print(f"  ? not in graph (will be synced on next start): {raw_name}")
                missing += 1
                continue
            current = node.get('activation_level') or 0.0
            if current >= floor:
                skipped += 1
                continue
            if args.dry_run:
                print(f"  would warm {raw_name}: {current:.2f} -> {floor:.2f}")
            else:
                kuzu.update_interaction(norm, 0.0, update_timestamp=True, floor=floor)
                print(f"  warmed {raw_name}: {current:.2f} -> {floor:.2f}")
            warmed += 1

    prefix = '[dry-run] ' if args.dry_run else ''
    print(f"\n{prefix}Warmed {warmed}, already warm {skipped}, not in graph {missing} "
          f"(floor={floor}, window={args.days}d).")
    if missing and not args.dry_run:
        print("Note: files not in the graph get synced (and warmed via file_edit) on next gateway start.")


if __name__ == '__main__':
    main()
