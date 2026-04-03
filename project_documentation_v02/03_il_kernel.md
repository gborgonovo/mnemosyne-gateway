# Il kernel

## Cosa è il kernel e perché esiste

Il kernel è il cerchio più interno di Mnemosyne. È lo strato che nessun utente vede direttamente, ma da cui dipende tutto il resto. La sua funzione è una sola: mantenere la memoria in uno stato coerente, vivo e interrogabile.

A differenza dei sistemi di archiviazione tradizionali, il kernel di Mnemosyne non è statico. Ogni informazione che entra viene collocata in un grafo di relazioni, riceve una temperatura semantica, e partecipa a un ciclo continuo di attivazione e decadimento. Il kernel è il motore di questo ciclo.

---

## Il Connectome (Neo4j)

Il Connectome è il grafo Neo4j dove vive la conoscenza. Non è un database di documenti né un archivio vettoriale — è una rete di concetti connessi, dove ogni nodo rappresenta un'entità (un progetto, una persona, un'idea, un task) e ogni arco rappresenta una relazione semantica tra due entità.

### Micro-tipi (labels)

Il sistema usa un insieme deliberatamente piccolo di tipi fondamentali:

- `Topic`: il tipo universale per concetti, persone, strumenti, luoghi e risorse. Copre la maggior parte dei nodi del grafo.
- `Project`: contenitore strutturale per task e topic correlati.
- `Goal`: obiettivi strategici, con `deadline` e `priority`.
- `Task`: azioni operative. Possono esistere indipendentemente dai Goal.
- `Observation`: frammenti di memoria episodica — il testo grezzo di una conversazione o di una nota.
- `Document` / `DocumentChunk`: per la gestione di testi estesi.

Questa scarsità è intenzionale. Meno tipi significa meno ambiguità per l'LLM in fase di estrazione, e un grafo più pulito nel tempo.

### Relazioni primitive

Tutte le relazioni sono pesate — il peso influenza la propagazione del calore semantico:

- `LINKED_TO` (0.3): associazione generica.
- `DEPENDS_ON` (0.9): dipendenza strutturale o prerequisito.
- `PART_OF` (0.8): gerarchia organizzativa.
- `MANAGES` (0.8): ownership e gestione.
- `CONTAINS` (–): relazione gerarchica documento → chunk.
- `MENTIONED_IN` (0.1): collegamento tra entità e Observation. Il peso basso è deliberato — è il *Semantic Firewall* che impedisce ai documenti di archivio di inquinare il contesto attivo.
- `RELATED_TO` (0.4): similarità semantica o concettuale.
- `REQUIRES` (0.9): dipendenza funzionale.
- `HAS_MEMBER` (0.7): appartenenza a un team o gruppo.

### Knowledge Scopes

Ogni nodo appartiene a uno scope di visibilità:

- `Private`: conoscenza personale, accessibile solo via client autorizzati.
- `Internal`: conoscenza di progetto o organizzativa.
- `Public`: conoscenza condivisibile con agenti esterni.

Gli scope sono filtri pervasivi: ogni query al grafo rispetta la gerarchia di visibilità della chiave API usata. Un nodo `Private` non è mai visibile a una chiave configurata solo per `Public`.

---

## Il modello di attenzione (AttentionModel)

Il modello di attenzione è il meccanismo che trasforma il Connectome da archivio statico a memoria dinamica. Ogni nodo ha una proprietà `activation_level` (0.0–1.0) — la sua "temperatura".

### Stimolazione

Quando un concetto viene menzionato — in una conversazione, in un documento ingestito, tramite un'azione esplicita — il nodo corrispondente riceve un boost di attivazione:

```
stimulate(node_names, boost_amount)
```

### Propagazione

Il calore si propaga ai nodi vicini lungo le relazioni, attenuato dal peso dell'arco:

```
propagate()
```

Se il nodo "Progetto Alpha" è caldo, il calore si trasferisce ai suoi Task e Topic collegati — ma con intensità decrescente in base al peso della relazione. La relazione `MENTIONED_IN` ha un'attenuazione aggiuntiva di ×0.1 (il Semantic Firewall): i documenti di archivio non contaminano il contesto attivo.

### Decadimento differenziale

Il decadimento riduce gradualmente l'attivazione di tutti i nodi:

```
A_t = A_(t-1) × (1 - K_decay)
```

Il decadimento non è uniforme:

- `Topic` generici: decadono alla velocità standard.
- `Goal` e `Task` attivi: decadono più lentamente — la visione strategica resiste all'operatività quotidiana.
- Nodi con `persistence: high`: non decadono — sono i pilastri dell'identità dell'utente.

---

## Il Gateway FastAPI

Il Gateway è il punto di ingresso unico per tutte le interazioni con il sistema. Espone un'API REST, coordina i Worker, e gestisce l'autenticazione e il routing degli scope.

### Autenticazione

In modalità produzione, ogni richiesta deve includere l'header `X-API-Key`. Le chiavi sono mappate agli scope in `config/api_keys.yaml`. In assenza del file, il Gateway opera in *Open Mode* — utile per sviluppo locale.

### Namespace applicativo

Gli scope (`Private`, `Internal`, `Public`) controllano la visibilità per livello di riservatezza, ma non per dominio applicativo. Un'applicazione per la gestione di un progetto di ristrutturazione non dovrebbe accedere ai nodi di un'applicazione CRM, anche se entrambe operano nello scope `Private`.

Per questo, ogni chiave API può essere associata a un **namespace** — un identificatore che isola logicamente i nodi di una specifica applicazione o contesto. Il Gateway filtra sempre per `(scope, namespace)` combinati. 

Dalla v0.2.x, il namespace non è solo un filtro di visibilità, ma una **barriera algoritmica**: il Gardener e i motori di ricerca vettoriale non confrontano mai nodi appartenenti a namespace diversi. Questo garantisce che entità omonime (es. "Casa" nel Progetto A e "Casa" nel Progetto B) non vengano mai fuse o confuse tra loro.

```yaml
# config/api_keys.yaml
"app_key_ristrutturazione":
  scopes:
    - Private
  namespace: "progetto_ganaghello"

"app_key_crm":
  scopes:
    - Private
    - Internal
  namespace: "giodalab_crm"
```

I nodi possono essere promossi a namespace condivisi tramite l'endpoint `/share`, permettendo la condivisione esplicita di conoscenza tra applicazioni quando necessario.

### Endpoint principali

| Endpoint | Metodo | Descrizione |
|---|---|---|
| `/status` | GET | Health check per Neo4j e EventBus |
| `/process_input` | POST | Invia testo grezzo — crea Observation e accoda l'arricchimento |
| `/add` | POST | Aggiunge un'osservazione in uno scope specifico |
| `/ingest` | POST | Ingestione massiva di file (txt/md) via background task |
| `/search` | GET | Ricerca semantica ibrida (Exact → Vector → Full-text) |
| `/briefing` | GET | Temi caldi e suggerimenti proattivi |
| `/briefing/longitudinal` | GET | Analisi storica: trend e progetti dormienti |
| `/nodes` | GET/PUT/DELETE | CRUD diretto sui nodi del grafo |
| `/share` | POST | Promuove un nodo da uno scope a un altro |
| `/stats` | GET | Statistiche in tempo reale sul grafo |
| `/rpc` | POST | Segnalazione interna tra Worker |
| `/register` | POST | Handshake per plugin e Worker esterni |

### Event Bus

Il Gateway include un Event Bus interno che pubblica eventi quando avvengono cambiamenti significativi nel grafo — ad esempio `NODE_ENERGIZED` quando un nodo supera una soglia di attivazione. I Worker si iscrivono a questi eventi e reagiscono in modo asincrono.

---

## I Worker

I Worker sono processi indipendenti che estendono le capacità del kernel senza appesantirlo. Comunicano con il Gateway via HTTP (protocollo Mnemosyne-RPC).

### LLMWorker

Consuma la Knowledge Queue — una coda persistente su disco in `data/queue/` — per estrarre entità, topic e relazioni semantiche dalle Observation via LLM, e reintegrarli nel grafo tramite il Gateway.

Il flusso è deliberatamente asincrono: il Gateway risponde immediatamente all'utente, e l'arricchimento semantico avviene in background senza bloccare la conversazione.

Il Worker supporta quattro modalità LLM configurabili in `settings.yaml`:

| Modalità | Descrizione |
|---|---|
| `mock` | Risposte predefinite, ideale per test |
| `ollama` | Inferenza locale via Ollama |
| `openai` | API OpenAI |
| `remote` | Qualsiasi endpoint OpenAI-compatibile |

### BriefingWorker

Si iscrive all'evento `NODE_ENERGIZED` e genera suggerimenti proattivi quando un concetto supera la soglia di attivazione configurata. I suggerimenti sono recuperabili via `GET /briefing`.

### Gardener

Opera come daemon in background — avviato automaticamente dal Gateway — eseguendo cicli periodici di manutenzione del grafo:

- **Deduplicazione Intelligente (Safe Merge)**: individua nodi con nomi simili nello stesso namespace. Se l'LLM conferma la similarità con punteggio elevato (>= 9/10), il Gardener esegue un *Safe Merge* automatico (vedi sotto).
- **Monitoraggio scadenze**: i Task con `due_date` scaduta o imminente ricevono un boost di attivazione massiccio.
- **Rilevamento progetti dormienti**: Goal e Project con alta attivazione storica ma inattivi da più di 30 giorni vengono riportati all'attenzione.
- **Gestione Task orfani**: Task senza relazioni vengono segnalati per contestualizzazione, a meno che non siano marcati con `allow_orphan: true`.
- **Decadimento temporale**: applica il ciclo di decadimento su tutti i nodi.

### Il Safe Merge (Tombstoning)

A differenza dei sistemi distruttivi, il processo di merge di Mnemosyne è conservativo. Quando due nodi vengono fusi:
1.  Il nodo "Sorgente" (duplicato) trasferisce tutte le sue relazioni (IN/OUT) al nodo "Destinazione" (principale).
2.  Le proprietà non in conflitto vengono migrate.
3.  Il nodo Sorgente non viene eliminato fisicamente, ma riceve le label speciali `:Archived:Tombstone` e perde tutte le altre label.
4.  Viene aggiunta la proprietà `merged_into` con l'ID del nodo Destinazione per permettere il tracciamento storico o il ripristino manuale in caso di errore dell'LLM.

Questo approccio permette al Gardener di operare in autonomia senza il timore di perdite di dati irreversibili.

### Risoluzione delle ambiguità semantiche (MAYBE_SAME_AS)

Quando il Gardener rileva due nodi potenzialmente identici — ad esempio "B&B" e "Bed and Breakfast" — crea una relazione `MAYBE_SAME_AS` tra di loro. Questa relazione non viene risolta automaticamente: richiede una decisione dell'utente.

Il flusso di risoluzione avviene in due modalità complementari:

**Durante una conversazione**: se uno dei nodi coinvolti è attivo nel contesto corrente, il Butler segnala l'ambiguità nel momento opportuno — non interrompendo, ma agganciandosi al flusso naturale. *"Ho notato che esiste anche un nodo 'Bed and Breakfast' — è lo stesso concetto?"*

**Durante la pulizia periodica**: il BriefingWorker include le ambiguità irrisolte nel briefing longitudinale, ordinate per calore dei nodi coinvolti. Chi è più caldo sale in cima. Chi è freddo da settimane può aspettare.

La risoluzione ha tre esiti possibili:

- **Merge**: i due nodi diventano uno. Tutte le relazioni e le attivazioni vengono consolidate sul nodo principale.
- **Separazione esplicita**: i nodi sono distinti per design. La relazione `MAYBE_SAME_AS` viene sostituita da una relazione semantica appropriata (es. `RELATED_TO`).
- **Rinvio**: l'utente non decide ora. La relazione rimane irrisolta e verrà riproposta in un momento successivo.

Il Gardener può essere eseguito anche manualmente per debug o forzare un ciclo di pulizia:

```bash
python3 workers/gardener.py
```

---

## Il Plugin Contract (Mnemosyne-RPC)

Il kernel è estensibile tramite Worker esterni che comunicano via HTTP seguendo il protocollo Mnemosyne-RPC.

### Ciclo di vita di un Worker esterno

**1. Registrazione**
```http
POST /register
{
  "worker_id": "my_worker",
  "capabilities": ["entity_extraction"],
  "endpoint": "http://localhost:5001/process"
}
```

**2. Ricezione eventi**
Il Gateway invia webhook all'endpoint registrato quando si verificano eventi rilevanti.

**3. Arricchimento**
Il Worker elabora i dati e restituisce il risultato:
```http
POST /enrich
{
  "source_observation": "id_123",
  "extracted_entities": [{"name": "Neo4j", "type": "Topic"}],
  "confidence": 0.95
}
```

### Best practice per i Worker

- Includere sempre `X-API-Key` se il Gateway ha autenticazione attiva.
- Garantire l'idempotenza: elaborare due volte lo stesso evento non deve creare duplicati.
- Rispettare gli scope ricevuti nel payload dell'evento.
- Gestire i timeout con grazia — il Gateway ritenterà in caso di mancata risposta.

---

## Gestione del sistema

### Avvio e stop

```bash
./scripts/start.sh   # Avvia Gateway, LLMWorker, BriefingWorker
./scripts/stop.sh    # Arresta tutti i processi
./scripts/restart.sh # Riavvio pulito con health check automatico
```

### Monitoring

```bash
./scripts/monitor.sh # Pannello di controllo: stato processi, connettività, statistiche grafo
```

### Backup e restore

```bash
./scripts/backup.sh              # Export JSON timestampato del Connectome
./scripts/restore.sh             # Restore interattivo (default: ultimo backup)
./scripts/restore.sh <file_path> # Restore da file specifico
```

---

*Documento 3 di 6 — Il kernel*
*Progetto Mnemosyne — GiodaLab*
