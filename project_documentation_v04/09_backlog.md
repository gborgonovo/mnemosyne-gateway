# Backlog — Idee e sviluppi futuri

Questo documento raccoglie le idee, i gap tecnici e le feature request aperte per Mnemosyne. È la fonte di verità per capire cosa c'è da fare e perché.

---

## Gap tecnici

### 1. Embedding config non collegata

**Stato:** aperto

`config/settings.yaml` ha una sezione `embeddings` con `mode`, `model_name`, `base_url`, `api_key`, ma `core/vector_store.py` la ignora: ChromaDB usa sempre `all-MiniLM-L6-v2` in locale.

**Fix:** istanziare l'embedding function corretta in base al `mode` e passarla a `get_or_create_collection(embedding_function=...)`. ChromaDB ha adapter built-in per OpenAI e endpoint compatibili (Ollama).

**Perché è importante:** permette di usare embedding remoti (OpenAI, Ollama) evitando di scaricare e girare modelli localmente. Fondamentale per chi usa Mnemosyne su macchine leggere.

---

### 2. Redesign del decay model

**Stato:** aperto — non implementare prima di discutere il design

Il decay attuale è uniforme: ×0.95 ogni ora su tutti i nodi indistintamente. Non cattura l'idea di "progetto caldo vs. progetto dimenticato".

**Modello corretto:** decay proporzionale al tempo dall'ultima interazione con quel nodo specifico. Il timestamp da usare è il filesystem `mtime` (già disponibile, file-first), sincronizzato in KuzuDB dalla file watcher come campo derivato. Formula target: `activation = f(frequenza_recente_interazioni)`, non `activation_iniziale × 0.95^ore`.

**File da toccare:** `workers/gardener.py`, `core/attention.py`.

---

### 3. Fase 8 longitudinale non implementata

**Stato:** aperto — da fare insieme al redesign del decay (#2)

La documentazione descrive meccanismi non presenti nel codice:

- **Differential decay**: Goals/Tasks dovrebbero decadere più lentamente dei topic standard. Attualmente `batch_decay` applica lo stesso fattore a tutti.
- **`get_dormant_projects()`**: rileva nodi ad alta connettività storica ma bassa attività recente. Non esiste in `initiative.py`.
- **Activation boost sui dormanti**: Longitudinal Scanner che applica piccoli boost ai progetti dormienti per farli risalire.
- **`interaction_count` e `last_accessed_agent`**: campi previsti nello schema KuzuDB, non presenti.

Parzialmente coperto: `initiative.py` segnala vicini freddi di nodi caldi ("stai pensando a X, ti ricordi di Y?"), ma non è vera analisi longitudinale.

---

### 4. Scope parziale nel grafo KuzuDB

**Stato:** aperto

La compartimentazione per scope (`Private`/`Internal`/`Public`) funziona in ChromaDB e nelle API, ma non in KuzuDB: `get_active_nodes()`, `get_neighbors()`, briefing, initiative e decay si applicano a tutto il grafo indistintamente.

**Conseguenza:** un nodo `Private` non appare nelle ricerche semantiche per chiavi con scope inferiore, ma la sua activation si propaga comunque ai vicini nel grafo e appare nel briefing interno.

**Fix:** aggiungere campo `scope` allo schema KuzuDB e propagare il filtro a tutte le query del grafo.

---

### 5. Cartelle non mappate come namespace di progetto

**Stato:** aperto

Le sottocartelle di `knowledge/` non si riflettono nel grafo. Un file in `lavoro/progetto.md` diventa il nodo `progetto` come se fosse in root.

**Design concordato:**
- Folder = namespace semantico (progetto), non scope. Scope rimane ortogonale.
- `_defaults.yaml` nella cartella specifica `project` e `scope` predefiniti (già implementato).
- Manca: propagazione automatica del campo `project` nel frontmatter in base alla cartella padre.
- Manca: handler `on_moved` in `WikiSyncHandler` — spostare un file lascia il vecchio nodo stale nel grafo, il nuovo non viene indicizzato con i defaults della cartella di destinazione.

**File da toccare:** `workers/file_watcher.py`, schema KuzuDB.

---

## Feature request

### 6. Associazione documenti originali ai nodi

**Stato:** aperto

Possibilità di collegare documenti originali (PDF, MD, DOCX, ecc.) a un nodo Mnemosyne, in modo da risalire alla fonte quando serve il dettaglio completo.

**Analogia:** Zotero — ogni elemento ha una scheda con i metadati e un PDF allegato. L'idea è replicare questa struttura nel grafo cognitivo: un nodo descrive il concetto, con un puntatore al documento originale.

**Idea di implementazione:**
- Campo frontmatter `source_doc` con percorso o URL del documento originale.
- Endpoint REST/MCP per aprire o scaricare il documento associato.
- Estensione futura: chunking del documento per indicizzazione semantica in ChromaDB (oltre al semplice puntatore).

---

### 7. Eval harness per il retrieval

**Stato:** backlog — da fare prima di confrontarsi con benchmark pubblici (LongMemEval)

Costruire un set custom di 30-50 coppie (query, nodo/risposta attesa) sul knowledge reale, per misurare:

- **recall@k**: `query_knowledge` recupera la risposta corretta tra i primi k risultati?
- **Ragionamento temporale**: il sistema restituisce la versione aggiornata di un fatto, o quella vecchia?
- **Valore degli edge tipizzati**: le relazioni `PART_OF`/`MANAGES` migliorano il retrieval rispetto al solo vettore semantico?
- **Abstention**: su domande senza risposta nel grafo, evita di allucinare?

**Forma suggerita:** `tests/test_retrieval_eval.py`.

**Perché prima di LongMemEval:** LongMemEval richiederebbe un adapter per il modello file-first; l'eval custom ha miglior rapporto valore/sforzo e dà segnali azionabili su cosa migliorare.

---

*Documento 9 — Backlog*
*Aggiornato: 2026-06-04*
