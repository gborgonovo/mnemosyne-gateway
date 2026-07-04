#!/usr/bin/env python3
"""Restore the thermal state (activation / interaction counters) into KuzuDB from
a backup snapshot.

The thermal state is the only authoritative state not in the markdown files (see
core/thermal_backup.py). After a KuzuDB rebuild the nodes come back at the flat
default and interaction_count=0, so the longitudinal briefing goes blind. This
reads knowledge/_system/thermal_state.json (written by the gateway, preserved in
the daily git backup) and writes the exact stored values back — interaction_count
included, unlike scripts/seed_thermal_activation.py which only guesses activation
from file dates.

Typical recovery after a rebuild:
  1. delete data/kuzu_main, restart the gateway (re-sync + re-embed from files)
  2. stop the gateway
  3. python3 scripts/restore_thermal_state.py --apply
  4. restart the gateway

IMPORTANT: run with the gateway STOPPED — KuzuDB allows a single writer and the
gateway holds the lock.

Usage:
  python3 scripts/restore_thermal_state.py                 # dry run (preview)
  python3 scripts/restore_thermal_state.py --apply         # write into KuzuDB
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.kuzu_manager import KuzuManager
from core import thermal_backup

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db-path", default=os.path.join(BASE_DIR, "data", "kuzu_main"))
    ap.add_argument("--snapshot",
                    default=os.path.join(BASE_DIR, "knowledge", "_system", "thermal_state.json"))
    ap.add_argument("--apply", action="store_true", help="write into KuzuDB (default: dry run)")
    args = ap.parse_args()

    if not os.path.exists(args.snapshot):
        print(f"No snapshot at {args.snapshot}", file=sys.stderr)
        sys.exit(1)
    with open(args.snapshot, "r", encoding="utf-8") as f:
        payload = json.load(f)
    snap_nodes = payload.get("nodes", {})

    try:
        kuzu_mgr = KuzuManager(db_path=args.db_path)
    except Exception as e:
        print(f"Could not open KuzuDB ({e}).\nIs the gateway running? Stop it first "
              f"(sudo systemctl stop mnemosyne).", file=sys.stderr)
        sys.exit(1)

    existing = {n["name"] for n in kuzu_mgr.get_all_nodes()}
    present = [nid for nid in snap_nodes if nid in existing]
    absent = len(snap_nodes) - len(present)

    print(f"\nSnapshot     : {args.snapshot}")
    print(f"  taken at   : {payload.get('snapshot_at', '?')}")
    print(f"  nodes      : {len(snap_nodes)}")
    print(f"KuzuDB       : {args.db_path}  ({len(existing)} nodes)")
    print(f"  to restore : {len(present)}   (in snapshot but absent from graph: {absent})")
    print(f"  mode       : {'APPLY' if args.apply else 'DRY RUN'}\n")

    if not args.apply:
        print(f"Dry run. Re-run with --apply to restore {len(present)} nodes.")
        kuzu_mgr.close()
        return

    res = thermal_backup.restore(kuzu_mgr, args.snapshot)
    kuzu_mgr.close()
    print(f"Restored {res['restored']} nodes ({res['skipped']} skipped). "
          f"The thermal model takes over from here.")


if __name__ == "__main__":
    main()
