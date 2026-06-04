# Mnemosyne — Indice della documentazione (v04)

## Documento 1 — Perché Mnemosyne ✓
*Visione e filosofia*
- L'origine: il problema della memoria frammentata
- Lo scopo della vita e il ruolo della memoria nelle emozioni
- Il mito di Mnemosyne: Lete e il dualismo oblio/ricordo
- Perché non è un tool, ma un'estensione del sé
- La visione a lungo termine: la memoria come eredità

## Documento 2 — I quattro cerchi ✓
*Il modello concettuale*
- Cerchio 1 — Stabilità: il kernel (File-First)
- Cerchio 2 — Alimentazione: i sensi in ingresso
- Cerchio 3 — Output: il contesto restituito agli LLM via MCP
- Cerchio 4 — Il Butler: il sistema nervoso autonomo (ora include Alfred)
- Il principio "invisibile finché non serve"

## Documento 3 — Il kernel
*Tecnico — Cerchio 1*
- L'Architettura Hybrid File-First: Markdown come Sorgente di Verità
- Il Connectome Liquido: KùzuDB (Topologia) e ChromaDB (Semantica)
- Il File Watcher: ciclo di vita completo (sync, auto-frontmatter, folder defaults, on_moved)
- LLM Enrichment in-process: thread daemon che scrive `relations:` nel frontmatter
- Relazioni tipizzate (`relations:`): fonte di verità persistente per archi strutturati
- Il Gateway FastAPI: gateway sottile e performante
- I Workers: Gardener (Sonno) e Briefing (Proattività)
- Nodi evergreen: il tipo Reference

## Documento 4 — Le integrazioni
*Tecnico — Cerchi 2 e 3*
- Il modello di alimentazione: strumenti come sensi
- Obsidian come interfaccia utente primaria: curatela umana
- MCP come protocollo di output standard per Agenti
- Gestione progetti: `list_projects`, `create_project`, `update_project`
- Parametri `folder` e `relations` nei tool di creazione
- Folder defaults (_defaults.yaml): ereditarietà per namespace
- Knowledge Scopes: privacy e visibilità tramite metadati YAML (ora nel grafo)

## Documento 5 — Il Butler e Alfred
*Architettura — Cerchio 4*
- L'evoluzione del Maggiordomo: dal backend all'intelligenza distribuita
- L'Initiative Engine: proattività su picchi termici
- Alfred: il sistema di plugin per azioni autonome nel mondo
- Manifest YAML, adapters SMTP/ntfy, plugin_runner

## Documento 6 — I tre orizzonti
*Strategia — Roadmap*
- Orizzonte vicino: memoria affidabile su file locali (v0.4.x — stato attuale)
- Orizzonte medio: connessione tra i mattoncini, emerge il filo
- Orizzonte lontano: archivio emotivo, la memoria come eredità

## Documento 7 — Approccio Ibrido File-First
*Approfondimento*
- Manifesto dell'architettura: perché abbiamo abbandonato Neo4j
- Il compromesso tra Trasparenza Umana (Markdown) e Performance AI (Embedded DBs)
- Folder defaults e tassonomia per namespace

## Documento 9 — Backlog
*Gap tecnici e feature request aperte*
- Embedding config non collegata (vector_store.py ignora settings.yaml)
- Redesign del decay model (attenzione relativa, non tempo assoluto)
- Fase 8 longitudinale non implementata (differential decay, dormant projects)
- Scope parziale nel grafo KuzuDB
- Cartelle non mappate come namespace di progetto (on_moved mancante)
- Associazione documenti originali ai nodi (campo source_doc, analogia Zotero)
- Eval harness per il retrieval (recall@k, temporalità, edge tipizzati, abstention)
