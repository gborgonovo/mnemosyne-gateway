# Il kernel

## Cosa è il kernel e perché esiste

Il kernel è il cerchio più interno di Mnemosyne. È lo strato che nessun utente vede direttamente, ma da cui dipende tutto il resto. La sua funzione è una sola: mantenere la memoria in uno stato coerente, vivo e interrogabile.

A differenza della versione originale basata su un database server-side pesante (Neo4j), il kernel v0.3 adotta un'architettura **Hybrid File-First**. In questo modello, la vera memoria risiede nei file Markdown che crei e modifichi. Il kernel funge da "sistema nervoso" che indicizza, scalda e connette questi file in tempo reale.

---

## Architettura a Doppio Strato

L'architettura separa rigorosamente la conoscenza persistente dal suo stato epistemico (calore dinamico), garantendo che i tuoi file markdown rimangano puliti e leggibili.

### Strato A: Lo Stato Statico (Markdown)
La directory `knowledge/` è l'unica sorgente della verità.
- **Formato**: File `.md` standard.
- **Frontmatter**: Ogni file contiene metadati YAML (`title`, `type`, `scope`, `tags`).
- **Relazioni**: I collegamenti tra concetti sono espressi tramite **Wikilinks** (`[[Nome Nodo]]`).

### Strato B: La RAM Cognitiva (KùzuDB + ChromaDB)
Poiché scansionare migliaia di file ad ogni domanda dell'AI sarebbe troppo lento, Mnemosyne mantiene due "ombre" digitali dei tuoi file:
1. **KùzuDB (Graph Database)**: Una replica embedded leggera che traccia la topologia (chi è collegato a chi), il **Activation Level** (il calore del nodo) e i metadati di interazione.
2. **ChromaDB (Vector Database)**: Un indice semantico che trasforma il contenuto dei file in vettori matematici per permettere ricerche basate sul significato, non solo sulle parole chiave.

#### Schema KùzuDB — Nodo
Ogni nodo nel grafo porta i seguenti campi:

| Campo | Tipo | Significato |
|---|---|---|
| `name` | STRING (PK) | Nome normalizzato (chiave) |
| `display_name` | STRING | Nome originale con maiuscole |
| `activation` | DOUBLE | Calore attuale [0.0, 1.0] |
| `node_type` | STRING | Tipo: Node, Goal, Task, Observation |
| `scope` | STRING | Privacy: Private, Internal, Public |
| `last_interaction` | DOUBLE | Timestamp Unix dell'ultima interazione diretta |
| `last_decay_applied` | DOUBLE | Timestamp dell'ultimo decay applicato (per retroattività) |
| `interaction_count` | INT64 | Contatore storico delle interazioni dirette |

---

## Il Ciclo di Vita Cognitivo (Event Loop)

### Il File Watcher: Il battito cardiaco
Il cuore del kernel è il `FileWatcher`. È un demone silenzioso che osserva la cartella `knowledge/`.
- Quando crei o modifichi un file, il Watcher lo parseggia istantaneamente.
- Estrae i wikilink e aggiorna il grafo in KùzuDB.
- Aggiorna l'indice semantico in ChromaDB.
- Registra una **interazione di tipo `file_edit`** sul nodo, applicando un boost di calore (+0.6).

Al **Cold Boot** (avvio del sistema), il Watcher sincronizza tutti i file esistenti senza applicare boost di calore — aggiorna solo i metadati (tipo, scope, link). Il calore viene conservato dallo stato precedente.

### Il Modello di Attenzione (AttentionModel)
Governa la "fisica" della memoria con tre segnali di interazione distinti:

| Segnale | Evento | Boost | Aggiorna timestamp |
|---|---|---|---|
| `file_edit` | File modificato su disco | +0.6 | Sì |
| `mcp_query` | Nodo recuperato via MCP o API | +0.2 | Sì |
| `proximity` | Vicino semantico di un nodo interagito | +0.05 × peso arco | No |

La **propagazione di prossimità** si applica ai vicini diretti del nodo interagito — non ricorsivamente. Il boost è attenuato dal peso dell'arco.

### Il Decadimento (Differential Decay)
Il decadimento non è globale né uniforme. Ogni nodo decade a una velocità dipendente dal suo tipo, proporzionalmente al tempo reale trascorso dall'ultima applicazione del decay. Questo garantisce la correttezza anche dopo un riavvio del sistema.

**Mezza vita per tipo** (senza interazioni):

| Tipo | Rate orario | Mezza vita |
|---|---|---|
| `Node` | 0.0025 | ~11 giorni |
| `Task` | 0.00045 | ~64 giorni |
| `Goal` | 0.00026 | ~112 giorni (~4 mesi) |
| `Observation` | 0.004 | ~7 giorni |

Il campo `last_decay_applied` permette di applicare retroattivamente il decay corretto anche per i periodi in cui il sistema era spento.

---

## Il Gateway FastAPI (Thin Client)

Il Gateway è il punto di ingresso unico per le interazioni. Nella v0.3 è diventato un layer estremamente sottile ("Thin Gateway"):
- Non gestisce più transazioni database complesse.
- Serve principalmente come bridge per l'interfaccia MCP e per le API REST minime.
- Coordina l'autenticazione tramite `X-API-Key` per gestire gli **Scopes** (Privacy).

### Knowledge Scopes
La divisione della conoscenza in livelli di privacy è gestita tramite il metadato `scope` nello YAML dei file:
- `Private`: Note personali.
- `Internal`: Progetti di team.
- `Public`: Conoscenza condivisa.

Il calore si propaga liberamente nel grafo indipendentemente dagli scope (le relazioni semantiche sono reali). Il filtro per scope si applica invece sui risultati esposti all'esterno: ricerca semantica, briefing, endpoint API.

---

## I Worker

### Gardener (Il Sonno)
Esegue tre operazioni ad ogni ciclo (default: ogni ora):
1. **Decay differenziale**: applica il decadimento per-nodo proporzionale al tempo reale trascorso, retroattivo per i periodi di downtime.
2. **Resurface dei dormienti**: applica un micro-boost (+0.05) ai nodi che erano storicamente attivi ma sono ora inattivi, facendoli emergere nel briefing senza competere con i nodi genuinamente caldi (tetto: 0.25).
3. **Creazione di archi semantici**: per ogni nodo caldo, interroga ChromaDB per trovare nodi semanticamente simili (soglia: 0.85 di similarità coseno) e crea archi `SEMANTICALLY_RELATED` in KùzuDB con peso proporzionale al punteggio. Questi archi vengono poi usati dalla propagazione di prossimità normale.

Un nodo è considerato **dormiente** se:
- `Node`: activation < 0.2 e inattivo da più di 27 giorni
- `Goal` / `Task`: inattivo da più di 30 giorni (indipendentemente dal calore residuo)
- In entrambi i casi: almeno 5 interazioni storiche (era attivo in passato)

### Briefing Worker
Analizza i picchi di calore in KùzuDB e individua connessioni dormienti. Il briefing è **scope-aware**: filtra i nodi in base agli scope consentiti dalla chiave API. Espone:
- `GET /briefing`: nodi caldi + sezione dormienti
- `GET /briefing/longitudinal`: analisi storica dei progetti dormienti, raggruppati per tipo

---

## Resilience (Hydration Protocol)

L'intero strato dei database embedded è sacrificabile. Se le cartelle `data/kuzu_main` o `data/chroma_db` vengono eliminate, al riavvio del kernel il `FileWatcher` eseguirà un **Cold Boot**: scansionerà l'intera directory `knowledge/` e ricostruirà l'intero Connectome in pochi secondi. La tua conoscenza è al sicuro nei file; gli indici sono solo strumenti di velocità.

---

## Strumenti diagnostici

```bash
# Visualizzare le curve di decay per i parametri attuali
python3 scripts/simulate_decay.py

# Health check del sistema
curl http://localhost:4001/status

# Statistiche grafo
curl http://localhost:4001/graph/stats

# Briefing (nodi caldi + dormienti)
curl http://localhost:4001/briefing

# Analisi longitudinale
curl http://localhost:4001/briefing/longitudinal
```

---

*Documento 3 di 7 — Il kernel*
*Progetto Mnemosyne — GiodaLab*
