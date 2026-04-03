# Le integrazioni

## Cosa sono i cerchi 2 e 3

Il kernel di Mnemosyne è silenzioso per design. Non sa nulla del mondo esterno finché qualcuno non gli porta informazioni, e non restituisce nulla finché qualcuno non lo interroga. I cerchi 2 e 3 sono i canali attraverso cui questo scambio avviene.

Il cerchio 2 sono i **sensi**: tutto ciò che porta conoscenza dentro il grafo. Il cerchio 3 è la **voce**: il modo in cui Mnemosyne restituisce contesto agli strumenti intelligenti che ne hanno bisogno.

Il principio che li governa entrambi è lo stesso: Mnemosyne non dovrebbe richiedere azioni esplicite da parte dell'utente. L'alimentazione ideale è automatica — gli strumenti parlano a Mnemosyne mentre l'utente li usa normalmente. L'output ideale è contestuale — il contesto giusto arriva allo strumento giusto nel momento giusto, senza che l'utente debba chiederlo.

---

## Cerchio 2 — L'alimentazione

### Il modello: strumenti come sensi

Ogni strumento connesso a Mnemosyne diventa un senso: percepisce una parte del mondo dell'utente e la traduce in nodi e relazioni nel grafo. Questo modello inverte il problema dell'adozione: non è l'utente che deve ricordarsi di usare Mnemosyne — sono gli strumenti che parlano a Mnemosyne mentre l'utente fa altro.

Il pattern di integrazione corretto è sempre lo stesso:

```
Utente usa lo strumento normalmente
        ↓
Lo strumento cattura l'evento rilevante
        ↓
POST /add o POST /process_input → Mnemosyne
        ↓
Il grafo si aggiorna in background
```

### Endpoint di ingresso

#### POST /process_input — testo grezzo

L'endpoint principale per l'alimentazione automatica. Riceve testo libero, crea un nodo `Observation`, e accoda l'arricchimento semantico per il LLMWorker. La risposta è immediata — l'elaborazione avviene in background.

```http
POST /process_input
X-API-Key: <chiave>
Content-Type: application/json

{
  "text": "Abbiamo deciso di usare travi in legno lamellare per il solaio del fienile.",
  "scope": "Private",
  "namespace": "progetto_ganaghello"
}
```

#### POST /add — osservazione strutturata

Simile a `/process_input` ma con controllo esplicito sullo scope. Utile quando lo strumento ha già una struttura chiara da trasmettere.

#### POST /ingest — documenti estesi

Per l'ingestione di file `.txt` o `.md`. Il sistema applica l'HeuristicChunker per dividere il testo in chunk semantici, li collega al nodo `Document` padre, e avvia la scansione in background tramite Graph-Matching (confronto fuzzy con i nodi già esistenti nel grafo).

```http
POST /ingest
X-API-Key: <chiave>
Content-Type: multipart/form-data

file: <file.md>
scope: Private
namespace: progetto_ganaghello
```

L'ingestione documentale usa il **Semantic Firewall**: i `DocumentChunk` sono collegati al nodo `Document` con peso basso, che a sua volta si collega alle entità esistenti nel grafo. Questo impedisce che i documenti di archivio inquinino il contesto attivo con calore semantico eccessivo.

### Integrazione con Open WebUI

Open WebUI supporta due livelli di integrazione con Mnemosyne, che operano in modo complementare.

#### Il Filter (memoria passiva)

Il Filter è una funzione che si attiva silenziosamente ad ogni messaggio. Opera in due momenti:

**Pre-processing** (prima che l'LLM risponda): chiama `GET /search` con le parole chiave del messaggio corrente e inietta il contesto rilevante nel system prompt. L'LLM risponde già sapendo cosa è pertinente nella memoria dell'utente.

**Post-processing** (dopo che l'LLM ha risposto): chiama `POST /process_input` con il contenuto della conversazione. Mnemosyne impara dalla chat senza che l'utente faccia nulla.

Il Filter si configura tramite le Valves in Open WebUI:

| Parametro | Descrizione |
|---|---|
| `Mnemosyne URL` | Indirizzo del Gateway (es. `http://host.docker.internal:4002`) |
| `Namespace` | Namespace applicativo per isolare il contesto |
| `Enable Search` | Attiva l'iniezione di contesto nel system prompt |
| `Search Context Limit` | Limite in caratteri del contesto iniettato |
| `Enable Continuous Learning` | Attiva il salvataggio automatico delle conversazioni |
| `Incognito Command` | Comando per sospendere memoria e apprendimento (default: `/incognito`) |

#### Il Tool (ricerca attiva)

Mentre il Filter inietta contesto passivamente, il Tool permette all'LLM di interrogare Mnemosyne autonomamente quando rileva di aver bisogno di informazioni specifiche dal passato. L'LLM chiama `search_memory(query, namespace)` come strumento esplicito, prima di generare la risposta.

I due livelli sono complementari: il Filter fornisce il contesto ambientale, il Tool permette l'approfondimento mirato.

### Pattern di integrazione per strumenti esterni

Qualsiasi strumento può diventare un senso di Mnemosyne con una sola chiamata HTTP. Il pattern minimo:

```javascript
// Esempio: uno strumento di gestione progetti
async function onTaskCreated(task) {
  // 1. Salva nel proprio database
  await db.tasks.create(task);

  // 2. Notifica Mnemosyne
  await fetch(`${MNEMOSYNE_URL}/process_input`, {
    method: 'POST',
    headers: {
      'X-API-Key': MNEMOSYNE_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      text: `Nuovo task creato: "${task.title}". Progetto: ${task.project}. Scadenza: ${task.due_date}.`,
      scope: 'Private',
      namespace: task.namespace
    })
  });
}
```

#### Best practice per le integrazioni

- **Duplicare solo quando serve semantica**: un dato in un database SQL è ottimizzato per essere recuperato esattamente — filtri, aggregazioni, query precise. Lo stesso dato come nodo in Mnemosyne partecipa al modello di attenzione: si scalda, si connette ad altri concetti, influenza il briefing. Ha senso duplicarlo quando vuoi che Mnemosyne faccia qualcosa di semantico con quel dato — non solo conservarlo. Un task sincronizzato da un gestionale di progetto ha senso nel grafo perché diventa parte del contesto vivo. Un indirizzo email probabilmente no.
- **Usare il namespace**: ogni strumento dovrebbe avere il proprio namespace per evitare contaminazione tra contesti diversi.
- **Preferire testo naturale**: Mnemosyne estrae le entità dal testo — non serve inviare JSON strutturato. Un testo narrativo è più ricco di un elenco di campi.
- **Gestire i fallimenti silenziosamente**: se la chiamata a Mnemosyne fallisce, l'esperienza utente nello strumento non deve essere bloccata. Mnemosyne è un layer aggiuntivo, non una dipendenza critica.

### Operazioni per tipo di entità

Mnemosyne espone operazioni CRUD mediate dal Gateway — non accesso diretto a Neo4j. Ogni operazione passa per il Gateway, che gestisce le conseguenze sulla coerenza del grafo: propagazione delle eliminazioni, ricalcolo del calore, aggiornamento delle relazioni.

Le operazioni disponibili variano per tipo, perché ogni tipo ha una semantica diversa:

| Endpoint | Metodo | Descrizione | Note |
|---|---|---|---|
| `/graph/schema` | GET | Introspezione dello schema | Torna labels e property keys attive |
| `/graph/stats` | GET | Statistiche del grafo | Conteggio nodi e relazioni per namespace |
| `/graph/export` | GET | Export JSON del grafo | Snapshot locale filtrato |
| `/search/advanced` | POST | Ricerca strutturata | Filtri esatti su property e tipi |
| `/nodes/{n}/neighbors` | GET | Graph-walking | Restituisce i nodi adiacenti |
| `Topic` | ✓ | ✓ | ✓ | ✓ | Eliminazione gestisce le relazioni collegate |
| `Topic` | ✓ | ✓ | ✓ | ✓ | Eliminazione gestisce le relazioni collegate |
| `Project` | ✓ | ✓ | ✓ | ✓ | Eliminazione può propagarsi ai Task collegati |
| `Goal` | ✓ | ✓ | ✓ (status, priority, deadline) | ✓ | Aggiornamento status triggera il modello di attenzione |
| `Task` | ✓ | ✓ | ✓ (status, due_date) | ✓ | Eliminazione gestisce il collegamento al Goal padre |
| `Observation` | ✓ | ✓ | — | ✓ | Non aggiornabile — è un frammento episodico immutabile |
| `Document` | ✓ (via /ingest) | ✓ | — | ✓ | Eliminazione rimuove anche i DocumentChunk e il file fisico |
| `DocumentChunk` | — | ✓ | — | — | Gestito automaticamente dall'ingestione |

L'aggiornamento di `Observation` e `Document` non è previsto per design: sono frammenti di memoria storica. Modificarli retroattivamente altererebbe il significato del passato.

**Pattern corretto per la modifica:**

- **Observation**: elimina il nodo e crea una nuova Observation con il contenuto corretto. Il grafo registra la nuova versione come fatto presente — semanticamente più onesto che correggere il passato.
- **Document**: usa il Deep Delete (elimina file fisico + nodo `Document` + tutti i `DocumentChunk` collegati), poi reingerisci il file aggiornato via `/ingest`. Il grafo riparte da zero su quel documento, senza residui del vecchio contenuto.

In entrambi i casi, se il contenuto precedente aveva già generato relazioni nel grafo — entità estratte, nodi collegati — queste sopravvivono all'eliminazione. Solo il frammento episodico viene rimosso, non la conoscenza che ne era derivata.

Questo è un comportamento intenzionale, non un effetto collaterale. La conoscenza estratta ha una vita propria: una volta che Mnemosyne ha appreso che "solaio" e "legno lamellare" sono concetti correlati nel contesto di un progetto, questa connessione rimane valida anche se l'Observation che l'aveva generata viene eliminata. Chi elimina una fonte si aspetta spesso di eliminare tutto ciò che ne derivava — ma in Mnemosyne non funziona così. Se si vuole rimuovere anche la conoscenza derivata, è necessario eliminare esplicitamente i nodi Topic o le relazioni interessate.

### Alimentazione manuale

Per chi preferisce un controllo esplicito, Mnemosyne supporta anche l'alimentazione manuale tramite la Dashboard Streamlit (tab Documents) o via CLI:

```bash
# Ingestione di un file dalla riga di comando
python3 gateway/legacy_cli.py add "Testo dell'osservazione"

# Ingestione di un documento
curl -X POST http://localhost:4002/ingest \
  -H "X-API-Key: <chiave>" \
  -F "file=@documento.md" \
  -F "scope=Private"
```

### Strumenti CLI per Agenti (OpenClaw & Scripts)

Per facilitare l'integrazione con agenti basati su terminale (come OpenClaw) o per l'uso manuale, Mnemosyne include una suite di script bash in `integrations/openclaw/` che fungono da client per le nuove API di introspezione:

- **`types.sh`**: Elenca tutti i tipi di nodi (labels) presenti.
- **`schema.sh`**: Mostra la struttura dettagliata di tipi e proprietà.
- **`stats.sh`**: Dashboard rapida su nodi e relazioni.
- **`related.sh <nome>`**: Esplora i vicini di un nodo specifico (Graph Walking).
- **`search-advanced.sh '<json>'`**: Esegue query precise (es. tutti i Task in stato 'todo').
- **`export.sh`**: Scarica uno snapshot locale in `export.json`.

Questi strumenti permettono agli agenti di "capire" la struttura della memoria prima di interrogarla, risolvendo il problema della cecità strutturale tipica dei database vettoriali puri.

---

## Cerchio 3 — L'output via MCP

### MCP come protocollo standard

Il Model Context Protocol (MCP) è il protocollo attraverso cui Mnemosyne restituisce contesto agli LLM. È la scelta architettuale chiave del cerchio 3: invece di costruire un'integrazione custom per ogni strumento, Mnemosyne espone un server MCP standard che qualsiasi client compatibile può interrogare.

Questo significa che Claude, Open WebUI, qualsiasi agente basato su LangChain o Vercel AI SDK — tutti possono attingere alla stessa memoria senza integrazioni dedicate.

### Configurazione del server MCP

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "/path/to/.venv/bin/python3",
      "args": ["/path/to/gateway/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/mnemosyne-gateway"
      }
    }
  }
}
```

### Strumenti esposti via MCP

| Strumento | Descrizione |
|---|---|
| `search_memory(query, scopes, namespace)` | Ricerca semantica ibrida nel grafo |
| `add_observation(text, scope, namespace)` | Aggiunge una nuova osservazione |
| `get_briefing(scopes, namespace)` | Temi caldi e suggerimenti proattivi |
| `create_goal(title, deadline, priority)` | Crea un obiettivo strategico |
| `create_task(title, due_date, goal)` | Crea un task operativo |
| `update_task_status(task, status)` | Aggiorna lo stato di un task |
| `forget_node(name, scope)` | Elimina fisicamente un nodo dal grafo |
| `update_node(name, properties)` | Aggiorna le proprietà di un nodo |
| `share_node(name, to_scope)` | Promuove un nodo a uno scope più ampio |

### La ricerca semantica ibrida

Quando un LLM interroga Mnemosyne via `/search` o tramite MCP, il sistema applica una strategia di ricerca a tre livelli:

1. **Exact match**: ricerca per nome esatto del nodo. Veloce e deterministica.
2. **Vector search**: ricerca per similarità vettoriale, se gli embedding sono abilitati. Trova concetti semanticamente vicini anche con parole diverse.
3. **Full-text (Lucene)**: fallback su indice full-text Neo4j. Analizza titoli e descrizioni per trovare il miglior match concettuale.

Il sistema scala automaticamente al livello successivo solo se il precedente non produce risultati soddisfacenti.

### Knowledge Scopes nell'output

Ogni chiamata di output rispetta la gerarchia degli scope. Un LLM autenticato con una chiave `Public` non può accedere a nodi `Private`, anche se sono semanticamente rilevanti. Questo garantisce che la privacy dell'utente sia preservata indipendentemente da quale strumento interroga la memoria.

La combinazione scope + namespace garantisce un doppio livello di isolamento: per riservatezza e per dominio applicativo.

---

*Documento 4 di 6 — Le integrazioni*
*Progetto Mnemosyne — GiodaLab*
