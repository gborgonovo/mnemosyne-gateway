#!/usr/bin/env python3
"""Controlla che un eval set sia ancora valido contro il vault reale.

Perche' esiste: il set v1 e' rimasto in uso per tre mesi dopo essere diventato
inutilizzabile, e nessuno se n'e' accorto. Tutti i 21 nodi che si aspettava di
trovare erano scomparsi dal vault, quindi ogni sua esecuzione misurava zero su
qualcosa che non c'era piu'. I numeri che ne uscivano (recall@1 0,615) sono
finiti nell'audit come prova che il recupero fosse il collo di bottiglia.

Un eval che scade in silenzio e' peggio di nessun eval, perche' produce numeri
che sembrano misure. Questo script rende quella scadenza rumorosa: esce con
codice 1 se qualcosa non torna, quindi si puo' mettere in una suite o in un
timer e non va ricordato a mano.

Uso:
    python3 evals/validate_eval_set.py                       # set v2, vault di default
    python3 evals/validate_eval_set.py --eval-set <file> --vault <dir>
    python3 evals/validate_eval_set.py --quiet               # solo il verdetto
"""
import argparse
import json
import os
import sys
import unicodedata

DEFAULT_VAULT = os.path.expanduser("~/KnowledgeBase")
DEFAULT_SET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_set_v2.json")
DERIVA_MAX = 0.25  # oltre il 25% di scostamento nel conteggio nodi, il set va rivisto


def chiave(nome: str) -> str:
    """Normalizza un nome di nodo per il confronto: NFC, minuscolo, senza .md.

    NFC serve perche' i nomi accentati ('felicità' contro 'felicità') possono
    essere codificati in due modi diversi fra il file e il JSON, e un confronto
    ingenuo li dichiara assenti.
    """
    if nome.endswith(".md"):
        nome = nome[:-3]
    return unicodedata.normalize("NFC", nome).strip().lower()


def nodi_del_vault(vault: str) -> dict:
    """{chiave: percorso relativo} per ogni .md del vault, esclusi .git e i file di sistema."""
    trovati = {}
    for radice, _, nomi in os.walk(vault):
        if os.sep + ".git" in radice:
            continue
        for n in nomi:
            if n.endswith(".md") and not n.startswith("_"):
                trovati[chiave(n)] = os.path.relpath(os.path.join(radice, n), vault)
    return trovati


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-set", default=DEFAULT_SET)
    ap.add_argument("--vault", default=DEFAULT_VAULT)
    ap.add_argument("--quiet", action="store_true", help="stampa solo il verdetto finale")
    args = ap.parse_args()

    if not os.path.isdir(args.vault):
        print(f"ERRORE: vault non trovato: {args.vault}")
        return 2
    with open(args.eval_set, encoding="utf-8") as f:
        es = json.load(f)

    presenti = nodi_del_vault(args.vault)
    queries = es.get("queries", [])
    meta = es.get("meta", {})
    problemi = []

    def dì(*a):
        if not args.quiet:
            print(*a)

    dì(f"eval set: {os.path.basename(args.eval_set)} (versione {meta.get('version', '?')},"
       f" scritto il {meta.get('scritto_il', '?')})")
    dì(f"vault:    {args.vault}, {len(presenti)} nodi\n")

    # 1. Deriva del corpus. Non e' un errore, e' un avviso: un vault che e'
    #    cambiato molto puo' aver reso obsolete le domande anche se i nodi
    #    attesi esistono ancora.
    attesi_allora = (meta.get("scritto_contro") or {}).get("nodi")
    if attesi_allora:
        deriva = abs(len(presenti) - attesi_allora) / attesi_allora
        stato = "ok" if deriva <= DERIVA_MAX else f"ATTENZIONE: {deriva:.0%} di scostamento"
        dì(f"deriva del corpus: scritto contro {attesi_allora} nodi, oggi {len(presenti)} -> {stato}")
        if deriva > DERIVA_MAX:
            problemi.append(f"il vault e' cambiato del {deriva:.0%} dalla stesura: rivedere le domande")

    # 2. Il controllo che nel v1 mancava: le risposte attese esistono ancora?
    mancanti, verificate = [], 0
    for q in queries:
        if q.get("category") == "abstention":
            continue  # per costruzione non si aspettano nodi
        for atteso in q.get("expected_top", []):
            k = chiave(atteso)
            if k in presenti:
                verificate += 1
            else:
                mancanti.append((q["id"], atteso))

    dì(f"\nrisposte attese presenti nel vault: {verificate}")
    if mancanti:
        dì(f"risposte attese ASSENTI: {len(mancanti)}")
        for qid, atteso in mancanti:
            dì(f"   [{qid}] {atteso}")
        problemi.append(f"{len(mancanti)} risposte attese non esistono piu' nel vault")

    # 3. Copertura e stato di avanzamento, per sapere cosa resta da confermare.
    per_categoria, per_stato, non_eseguibili = {}, {}, []
    for q in queries:
        c = q.get("category", "?")
        per_categoria[c] = per_categoria.get(c, 0) + 1
        s = q.get("stato", "?")
        per_stato[s] = per_stato.get(s, 0) + 1
        if q.get("runnable") is False:
            non_eseguibili.append((q["id"], q.get("blocked_by", "?")))

    dì("\ndomande per categoria:")
    for c, n in sorted(per_categoria.items(), key=lambda t: -t[1]):
        dì(f"   {n:3}  {c}")
    dì("domande per stato:")
    for s, n in sorted(per_stato.items(), key=lambda t: -t[1]):
        dì(f"   {n:3}  {s}")

    if non_eseguibili:
        dì(f"\nnon ancora eseguibili ({len(non_eseguibili)}), in attesa di cio' che misurano:")
        for qid, motivo in non_eseguibili:
            dì(f"   [{qid}] {motivo}")

    # 4. Soglie di astensione: se non sono calibrate, la categoria non va misurata.
    #    Nel v1 erano tarate su un altro embedder e hanno prodotto un numero
    #    (0,4) che non voleva dire nulla.
    soglie = es.get("soglie_astensione") or {}
    calibrazione = next((v for k, v in soglie.items() if k.startswith("calibrazione_")), None)
    if per_categoria.get("abstention") and soglie.get("default") is None:
        if calibrazione:
            # Una soglia nulla DOPO una calibrazione non e' un lavoro in sospeso:
            # e' il risultato. Distinguere le due cose evita di rimettere in coda
            # un lavoro gia' fatto che ha dato esito negativo.
            dì(f"\nsoglia di astensione: nessuna, per misura e non per dimenticanza")
            dì(f"   esito: {calibrazione.get('esito', '?')}")
            dì(f"   {calibrazione.get('misura', '')}")
        else:
            dì("\nsoglie di astensione non calibrate: la categoria va saltata, non misurata a caso")
            problemi.append("soglie di astensione da calibrare sull'embedder in uso")

    da_confermare = per_stato.get("da_confermare", 0)
    if da_confermare:
        n = da_confermare
        dì(f"\n{n} domand{'a' if n == 1 else 'e'} {'e' if n == 1 else 'sono'} ancora da confermare: "
           f"finche' lo {'e' if n == 1 else 'sono'}, i numeri che produc{'e' if n == 1 else 'ono'} "
           f"sono indicativi e non un cancello.")

    print()
    if problemi:
        n = len(problemi)
        print(f"VERDETTO: {n} cos{'a' if n == 1 else 'e'} da sistemare prima di fidarsi dei numeri")
        for p in problemi:
            print(f"  - {p}")
        return 1
    print("VERDETTO: il set e' allineato al vault")
    return 0


if __name__ == "__main__":
    sys.exit(main())
