#!/usr/bin/env python3
"""
Mnemosyne retrieval eval runner — Phase 4a/4b.

Reads eval_set.json, runs each query, measures recall@1/3/5 for
recall + temporal queries, precision_abstain for abstention, and
edge_precision for typed-relation queries (HTTP-only).

Usage:
  # Offline (semantic + abstention, no re-rank):
  python3 evals/run_eval.py

  # Full (all categories via gateway HTTP, includes thermal re-rank):
  python3 evals/run_eval.py --api http://localhost:4001 --key mnm_sk_...

Results saved to evals/results_YYYYMMDD_HHMMSS.json for diff across runs.
HTTP mode measures recall@1 via /search (which applies B1 thermal re-rank).
Offline mode measures recall@1/3/5 via direct ChromaDB (pure semantic, no re-rank).
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.vector_store import VectorStore
from core.utils import normalize_node_name


def _norm(name: str) -> str:
    return normalize_node_name(name or "")


def run_recall(vs: VectorStore, item: dict) -> dict:
    results = vs.semantic_search(item["query"], limit=5)
    expected = [_norm(e) for e in item["expected_top"]]
    normed = [_norm(r["name"]) for r in results]
    distances = [r["distance"] for r in results]
    return {
        "hit@1": normed[:1] != [] and any(normed[0] == e for e in expected),
        "hit@3": any(n == e for n in normed[:3] for e in expected),
        "hit@5": any(n == e for n in normed[:5] for e in expected),
        "top5": [(r["name"], round(r["distance"], 3)) for r in results],
        "min_distance": round(distances[0], 3) if distances else None,
    }


def run_abstention(vs: VectorStore, item: dict) -> dict:
    threshold = item.get("abstention_threshold", 0.55)
    results = vs.semantic_search(item["query"], limit=1)
    if not results:
        return {"pass": True, "top1": None, "min_distance": None, "threshold": threshold}
    dist = results[0]["distance"]
    return {
        "pass": dist > threshold,
        "top1": results[0]["name"],
        "min_distance": round(dist, 3),
        "threshold": threshold,
    }


def run_edge(api_url: str, api_key: str, item: dict) -> dict:
    try:
        import requests
    except ImportError:
        return {"skip": True, "reason": "requests not installed"}
    exp_rel = item.get("expected_relation")
    exp_tgt = _norm(item.get("expected_target", ""))
    try:
        resp = requests.get(
            f"{api_url}/search",
            params={"q": item["query"]},
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return {"skip": True, "reason": f"HTTP {resp.status_code}"}
        data = resp.json()
        related = data.get("related", [])
        matched = any(
            (exp_rel is None or r.get("rel") == exp_rel)
            and (not exp_tgt or _norm(r.get("name", "")) == exp_tgt)
            for r in related
        )
        return {
            "pass": matched,
            "source_node": data.get("name"),
            "related": [(r.get("name"), r.get("rel")) for r in related[:6]],
        }
    except Exception as exc:
        return {"skip": True, "reason": str(exc)}


def run_recall_http(api_url: str, api_key: str, item: dict) -> dict:
    """Run a recall/temporal query via HTTP /search (tests the full re-rank pipeline).

    /search returns only the top-1 result after thermal re-ranking, so only
    recall@1 is meaningful here; @3 and @5 are set equal to @1.
    """
    try:
        import requests
    except ImportError:
        return {"skip": True, "reason": "requests not installed"}
    expected = [_norm(e) for e in item["expected_top"]]
    try:
        resp = requests.get(
            f"{api_url}/search",
            params={"q": item["query"]},
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if resp.status_code == 404:
            return {"hit@1": False, "hit@3": False, "hit@5": False,
                    "top5": [], "min_distance": None, "via": "http"}
        if resp.status_code != 200:
            return {"skip": True, "reason": f"HTTP {resp.status_code}"}
        data = resp.json()
        name = _norm(data.get("name", ""))
        score = data.get("score")
        hit = any(name == e for e in expected)
        return {
            "hit@1": hit, "hit@3": hit, "hit@5": hit,
            "top5": [(data.get("name"), score)],
            "min_distance": None, "via": "http",
        }
    except Exception as exc:
        return {"skip": True, "reason": str(exc)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", metavar="URL", help="Gateway base URL for edge queries")
    ap.add_argument("--key", metavar="KEY", help="API key for gateway HTTP queries")
    ap.add_argument(
        "--eval-set",
        default=os.path.join(os.path.dirname(__file__), "eval_set.json"),
        help="Path to eval_set.json",
    )
    ap.add_argument(
        "--output-dir",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="Directory for results JSON",
    )
    args = ap.parse_args()

    with open(args.eval_set) as f:
        eval_set = json.load(f)

    vs = VectorStore()
    all_results = []
    mode = "http" if (args.api and args.key) else "offline"

    for item in eval_set["queries"]:
        cat = item["category"]
        if cat in ("recall", "temporal"):
            if mode == "http":
                result = run_recall_http(args.api, args.key, item)
            else:
                result = run_recall(vs, item)
        elif cat == "abstention":
            result = run_abstention(vs, item)
        elif cat == "edge":
            if args.api and args.key:
                result = run_edge(args.api, args.key, item)
            else:
                result = {"skip": True, "reason": "pass --api and --key to enable edge queries"}
        else:
            result = {"skip": True, "reason": f"unknown category {cat!r}"}

        result.update({"id": item["id"], "category": cat, "query": item["query"]})
        all_results.append(result)

    # Aggregate metrics per category
    metrics: dict = {}
    for cat in ("recall", "temporal", "abstention", "edge"):
        items = [r for r in all_results if r["category"] == cat]
        active = [r for r in items if not r.get("skip")]
        n = len(active)
        skipped = len(items) - n
        if cat in ("recall", "temporal"):
            metrics[cat] = {
                "n": n,
                "skipped": skipped,
                "recall@1": round(sum(r["hit@1"] for r in active) / n, 3) if n else 0,
                "recall@3": round(sum(r["hit@3"] for r in active) / n, 3) if n else 0,
                "recall@5": round(sum(r["hit@5"] for r in active) / n, 3) if n else 0,
            }
        elif cat == "abstention":
            metrics[cat] = {
                "n": n,
                "precision_abstain": round(sum(r["pass"] for r in active) / n, 3) if n else 0,
                "avg_min_dist": round(sum(r["min_distance"] or 0 for r in active) / n, 3) if n else 0,
            }
        elif cat == "edge":
            metrics[cat] = {
                "n": n,
                "skipped": skipped,
                "edge_precision": round(sum(r.get("pass", 0) for r in active) / n, 3) if n else 0,
            }

    # Print report
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_label = f"HTTP ({args.api})" if mode == "http" else "offline (direct ChromaDB, no re-rank)"
    print(f"\n=== Mnemosyne Retrieval Eval — {ts} [{mode_label}] ===\n")
    for cat, m in metrics.items():
        if m.get("n", 0) > 0 or m.get("skipped", 0) > 0:
            print(f"  [{cat.upper():<12}]  {m}")
    print()

    markers = {"recall": {True: "✓", "3": "~", "5": ".", False: "✗"},
               "temporal": {True: "✓", "3": "~", "5": ".", False: "✗"}}
    for r in all_results:
        cat = r["category"]
        qid = r["id"]
        if r.get("skip"):
            print(f"  SKIP  {qid:<5}  {r.get('reason', '')}")
            continue
        if cat in ("recall", "temporal"):
            if r["hit@1"]:
                m = "✓"
            elif r["hit@3"]:
                m = "~"
            elif r["hit@5"]:
                m = "."
            else:
                m = "✗"
            top1 = r["top5"][0][0] if r["top5"] else "-"
            print(f"  {m}  {qid:<5}  top1={top1[:35]:<35}  {r['query'][:45]}")
        elif cat == "abstention":
            m = "✓" if r["pass"] else "✗"
            print(f"  {m}  {qid:<5}  dist={r['min_distance']}  top1={str(r.get('top1',''))[:28]}")
        elif cat == "edge":
            m = "✓" if r.get("pass") else "✗"
            src = r.get("source_node", "-")
            print(f"  {m}  {qid:<5}  src={src[:30]}")

    print("""
Legend: ✓=hit@1  ~=hit@3  .=hit@5  ✗=miss
""")

    # Save results JSON
    out_path = os.path.join(
        args.output_dir, f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(out_path, "w") as f:
        json.dump(
            {"timestamp": ts, "metrics": metrics, "queries": all_results},
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"  Saved: {out_path}\n")


if __name__ == "__main__":
    main()
