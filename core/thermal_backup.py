"""Backup and restore of the thermal state (activation / interaction counters).

This is the ONE piece of authoritative state that is not derivable from the
markdown files: activation, last_interaction, interaction_count and the decay
clock live only in KuzuDB. The daily git backup covers `knowledge/` (the files),
so without this the thermal state is lost on any DB rebuild — and the longitudinal
features (dormant/hub detection, gated on interaction_count) go blind for weeks.

We snapshot it to a small JSON sidecar (written by the gateway, atomically, and
placed under knowledge/ so the git backup includes it) rather than into the node
frontmatter (which would churn every file hourly as activation decays) or as a
binary DB dump (unnecessary: re-embedding on rebuild is cheap with local Ollama).

`restore` writes the fields back verbatim; the next decay cycle carries them
forward from their stored last_decay_applied, so recovery is exact, not the
date-based approximation of scripts/seed_thermal_activation.py.
"""
import json
import logging
from datetime import datetime

from core.utils import atomic_write

logger = logging.getLogger(__name__)

_FIELDS = ("activation", "last_interaction", "interaction_count", "last_decay_applied")


def export(kuzu_mgr, path: str) -> dict:
    """Write a JSON snapshot of every node's thermal state to `path` (atomically).

    Best-effort: never raises to the caller (gardener/shutdown). Returns a summary
    {"nodes": n, "skipped": bool}.
    """
    try:
        rows = kuzu_mgr.get_thermal_state()
        payload = {
            "version": 1,
            "snapshot_at": datetime.now().isoformat(timespec="seconds"),
            "nodes": {r["name"]: {k: r[k] for k in _FIELDS} for r in rows},
        }
        atomic_write(path, json.dumps(payload, indent=1))
        logger.info(f"Thermal state exported: {len(rows)} nodes -> {path}")
        return {"nodes": len(rows), "skipped": False}
    except Exception as e:
        logger.error(f"Thermal state export failed: {e}")
        return {"nodes": 0, "skipped": True}


def restore(kuzu_mgr, path: str) -> dict:
    """Restore thermal fields into KuzuDB from a JSON snapshot.

    Applies each snapshot entry to the node of the same id if it still exists in
    the (rebuilt) graph; snapshot entries for nodes no longer present are skipped.
    Returns {"restored": n, "skipped": n}.
    """
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    nodes = payload.get("nodes", {})

    existing = {n["name"] for n in kuzu_mgr.get_all_nodes()}
    restored = skipped = 0
    for node_id, fields in nodes.items():
        if node_id not in existing:
            skipped += 1
            continue
        kuzu_mgr.restore_thermal(
            node_id,
            activation=fields.get("activation", 0.0),
            last_interaction=fields.get("last_interaction", 0.0),
            interaction_count=fields.get("interaction_count", 0),
            last_decay_applied=fields.get("last_decay_applied", 0.0),
        )
        restored += 1
    logger.info(f"Thermal state restored: {restored} nodes, {skipped} skipped (absent).")
    return {"restored": restored, "skipped": skipped}
