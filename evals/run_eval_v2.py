#!/usr/bin/env python3
"""Esegue un eval set v2 e timbra il risultato con COME e' stato misurato.

Perche' non riusa run_eval.py: quello presuppone il formato v1, che e' morto
(nessuna delle sue 21 risposte attese esiste piu' nel vault), e soprattutto non
registrava con quale embedder girava. E' esattamente cosi' che il numero di
giugno, misurato col default inglese di ChromaDB invece che col modello di
produzione, e' potuto essere citato per tre mesi come se descrivesse la
produzione.

Qui l'embedder e il vault sono argomenti espliciti e finiscono nel file dei
risultati. Un risultato senza quel timbro non e' interpretabile.

Uso:
    python3 evals/run_eval_v2.py --db-path ./data/chroma_qwen_vault
    python3 evals/run_eval_v2.py --db-path ... --embedder mock     # confronto fra motori
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.vector_store import VectorStore  # noqa: E402

EMBEDDERS = {
    "qwen": {"mode": "ollama", "base_url": "http://localhost:11434",
             "model_name": "Qwen3-Embedding:0.6b", "timeout": 300},
    "mock": {"mode": "mock"},  # attenzione: non e' finto, e' il default di ChromaDB (all-MiniLM, inglese)
}


def norm(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-set", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                       "eval_set_v2.json"))
    ap.add_argument("--db-path", required=True, help="indice ChromaDB da interrogare")
    ap.add_argument("--embedder", default="qwen", choices=sorted(EMBEDDERS))
    ap.add_argument("--output-dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    with open(args.eval_set, encoding="utf-8") as f:
        es = json.load(f)
    vs = VectorStore(db_path=args.db_path, embedding_config=EMBEDDERS[args.embedder])

    soglia = (es.get("soglie_astensione") or {}).get("default")
    esiti, per_cat = [], {}

    for q in es["queries"]:
        if q.get("runnable") is False:
            esiti.append({"id": q["id"], "category": q["category"], "saltata": q.get("blocked_by")})
            continue
        cat = q["category"]
        res = vs.semantic_search(q["query"], limit=5)
        nomi = [norm(r["name"]) for r in res]
        dist = [round(r["distance"], 3) for r in res]

        if cat == "abstention":
            # Senza soglia calibrata non si misura: si raccolgono le distanze,
            # che sono il dato con cui la soglia si calibra.
            e = {"id": q["id"], "category": cat, "top1": res[0]["name"] if res else None,
                 "min_distance": dist[0] if dist else None,
                 "pass": (dist[0] > soglia) if (soglia is not None and dist) else None}
        else:
            attesi = [norm(x) for x in q.get("expected_top", [])]
            e = {"id": q["id"], "category": cat,
                 "hit@1": bool(nomi[:1]) and nomi[0] in attesi,
                 "hit@3": any(n in attesi for n in nomi[:3]),
                 "hit@5": any(n in attesi for n in nomi[:5]),
                 "top5": [(r["name"], d) for r, d in zip(res, dist)],
                 "expected": q.get("expected_top", [])}
        esiti.append(e)
        per_cat.setdefault(cat, []).append(e)

    print(f"eval set v{es['meta']['version']} | embedder: {args.embedder} | indice: {args.db_path}\n")
    metriche = {}
    for cat, rows in per_cat.items():
        if cat == "abstention":
            ds = [r["min_distance"] for r in rows if r["min_distance"] is not None]
            metriche[cat] = {"n": len(rows), "distanze": sorted(ds),
                             "min": min(ds) if ds else None, "max": max(ds) if ds else None}
            print(f"{cat:14} n={len(rows)}  distanze={sorted(ds)}")
            print(f"{'':14} soglia non calibrata: una soglia fra {min(ds):.3f} e {max(ds):.3f} "
                  f"decide quante di queste diventano astensioni" if ds else "")
        else:
            n = len(rows)
            m = {k: round(sum(r[k] for r in rows) / n, 3) for k in ("hit@1", "hit@3", "hit@5")}
            metriche[cat] = {"n": n, **m}
            print(f"{cat:14} n={n}  recall@1={m['hit@1']}  @3={m['hit@3']}  @5={m['hit@5']}")

    falliti = [r for r in esiti if r.get("hit@5") is False]
    if falliti:
        print(f"\nfuori dai primi 5 ({len(falliti)}):")
        for r in falliti:
            print(f"  [{r['id']}] atteso {r['expected']}")
            print(f"        ottenuto {[n for n, _ in r['top5'][:3]]}")

    payload = {
        "misurato_il": datetime.now().isoformat(timespec="seconds"),
        "come": {"eval_set": os.path.basename(args.eval_set), "versione_set": es["meta"]["version"],
                 "embedder": args.embedder, "indice": args.db_path,
                 "nota": "i numeri valgono solo per questa combinazione di set, embedder e indice"},
        "metriche": metriche, "esiti": esiti,
    }
    if not args.no_save:
        out = os.path.join(args.output_dir, f"results_v2_{args.embedder}_{datetime.now():%Y%m%d_%H%M%S}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, ensure_ascii=False)
        print(f"\nsalvato in {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
