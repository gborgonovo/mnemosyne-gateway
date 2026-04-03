# Mnemosyne - Technical Specifications

**Version:** 1.3
**Date:** 2026-03-06
**Status:** Implemented (Ontology Upgrade v2 Complete)

---

## 1. Project Vision

Mnemosyne is not a chatbot; it is a **Cognitive Partner**. It acts as an extension of the user's mind, maintaining long-term context, evolving relationships between concepts, and offering proactive cognitive support.
Unlike traditional AI assistants that react to prompts, Mnemosyne maintains a persistent state of "attention" on the user's projects and life goals, intervening when it detects relevant connections or neglected areas.

## 2. System Architecture (Gateway-First)

Mnemosyne è ora un **Cognitive Middleware Headless**. Espone le sue capacità cognitive tramite un **HTTP Bridge (FastAPI)** e un server **MCP**, permettendo l'integrazione con agenti locali (OpenClaw), interfacce web (Open WebUI) e client CLI.

- **Core**: Python 3.10+ (LLM-Free Micro-Kernel)
- **Graph Engine**: Neo4j (via Docker)
- **API Engine**: FastAPI / Uvicorn (Distributed Gateway)
- **Communication Protocol**: Mnemosyne-RPC (Event-driven over REST)
- **Interface**: FastMCP (stdio transport) & HTTP REST
- **Storage Pools**: Knowledge Scopes (Neo4j) & Physical Archive (Filesystem)

### 2.2 Functional Blocks

1. **The Connectome (Core)**: The semantic graph storage (LLM-Free).
2. **Mnemosyne Gateway**: Distributed FastAPI server and Event Bus hub.
3. **MCP Interface**: Server FastMCP for direct tool integration and proactive planning.
4. **Attention Engine**: Mathematical model for activation & decay (with Differential Decay).
5. **Knowledge Scopes**: Hierarchical visibility filtering (Private/Public) and selective deletion.
6. **Distributed Workers**:
    - **LLMWorker**: Asynchronous entity extraction and enrichment.
    - **Gardener**: Background worker for hygiene, **TimeWatcher** logic, and **Longitudinal Analysis**.
7. **The Butler Persona**: Relational layer for user interaction.

### 2.3 Network / Ports

Mnemosyne utilizza le seguenti porte per la comunicazione tra i moduli e l'accesso esterno:

- **4001**: **Mnemosyne Gateway** (API HTTP). Porta principale per l'integrazione client.
- **8501**: **Mnemosyne Dashboard** (Streamlit). Interfaccia grafica di monitoraggio.
- **7687**: **Neo4j Bolt**. Comunicazione binaria con il database.
- **7474**: **Neo4j HTTP**. Interfaccia web di Neo4j Browser.
- **11434**: **Ollama API**. Comunicazione con il motore LLM (se in modalità `ollama`).

---

## 3. Core Modules Specification

### 3.1 The Connectome (Graph Schema)

Il Connectome implementa la visione del **"Grafo Liquido"**: la conoscenza non è una gerarchia statica, ma una rete di nodi che cambiano importanza (attivazione) in base all'uso. Invece di una ontologia rigida, utilizziamo un set minimo di "Micro-Types" per fornire una grammatica di base al sistema.

#### Filosofia: Emergenza vs. Struttura

- **Emergenza**: Il sistema permette a nuove connessioni di formarsi liberamente tramite le `Observation` e il feedback dell'utente.
- **Struttura (Micro-Types)**: I tipi fondamentali aiutano The Butler a capire *come* usare le informazioni:
  - `Topic`: Nodo universale per concetti, persone, strumenti, luoghi e risorse digitali (unifica i precedenti `Entity` e `Resource`).
  - `Project`: Nodi-contenitore per la strutturazione di attività e temi correlati. [NEW]
  - `Goal`: Obiettivi strategici ad alto livello (es. "Lanciare Mnemosyne"). Possiedono `deadline` e `priority`.
  - `Task`: Azioni concrete. Possiedono `status` (todo, done) e `due_date`. Possono essere indipendenti dai Goal.
  - `Observation`: La memoria episodica. Ogni frase acquisita è collegata al tempo.
  - `Document`: Contenitore logico per testi estesi acquisiti via ingestion.

*Note: Qualsiasi altro descrittore (es. "Progetto", "Urgente", "Sogno") viene applicato come etichetta secondaria o proprietà, permettendo al grafo di evolvere organicamente senza rompere la logica di base.*

#### Relationship Primitives

To allow heuristic emergence, relationships are mapped to fundamental vectors:

1. `LINKED_TO` (Weight: **0.3**, Bidirectional): Generic semantic association.
2. `DEPENDS_ON` (Weight: **0.9**, Directional): Structural blockage or requirement.
3. `REQUIRES` (Weight: **0.9**, Directional): Used for (Goal)->(Task) decomposition.
4. `EVOKES` (Weight: **0.6**, Bidirectional): Emotional or mnemonic trigger.
5. `IS_A` (Weight: **1.0**, Directional): Taxonomic classification.
6. `MENTIONED_IN` (Weight: **0.1**, Directional): Link between an Entity/Topic and an Observation or DocumentChunk.
7. `MAYBE_SAME_AS` (Weight: **0.0**, Bidirectional): Suggested merge by the Gardener.
8. `CONTAINS` (Weight: **Structural**, Directional): Links a `Document` to its `DocumentChunk` nodes.
9. `NEXT_CHUNK` (Weight: **Structural**, Directional): Maintains the sequential flow between chunks.
10. `PART_OF` (Weight: **0.8**, Directional): Organizational hierarchy (e.g., Team -> Lab). [NEW]
11. `MANAGES` (Weight: **0.8**, Directional): Ownership and management (e.g., Lab -> Project). [NEW]
12. `HAS_MEMBER` (Weight: **0.7**, Directional): Personnel membership (e.g., Team -> Person). [NEW]
13. `RELATED_TO` (Weight: **0.4**, Bidirectional): Conceptual or semantic similarity. [NEW]
14. `FEEDBACK` (Property): Each relationship can store a `feedback_score` (negative scores hide initiatives).

### 3.2 The Attention Engine (Proactive Planning)

This module gives the graph "life" by simulating heat (activation) flow.

#### Differential Decay Model

Per supportare il **Proactive Planning**, il decadimento temporale non è uniforme:

- **Standard**: $A_{t} = A_{t-1} \times (1 - K_{decay})$
- **Goals**: Decadimento dimezzato ($0.5 \times K_{decay}$) per mantenere la visione a lungo termine.
- **Active Tasks**: Decadimento drasticamente ridotto ($0.2 \times K_{decay}$) per i task `in_progress`.
- **Done Tasks**: Decadimento accelerato ($5 \times K_{decay}$) per "pulire" lo spazio cognitivo dopo il completamento.

#### Modificatore "Pedanteria" (Persistence)

I nodi marcati con `persistence: high` hanno un coefficiente $K_{decay} \approx 0$ e un moltiplicatore di priorità nell'Initiative Engine, garantendo che rimangano "caldi" fino alla rimozione del tag.

#### Propagation Model

**Bidirectional with Back-Propagation Attenuation**.

- **Forward (A $\to$ B)**: Full strength transfer. If A is active, B becomes relevant.
- **Backward (B $\to$ A)**: Attenuated transfer (e.g., 50%). If B is discussed, A is "remembered" faintly.
- **Semantic Firewall (B $\to$ Chunk)**: Severe attenuation ($0.1 \times factor$) for `MENTIONED_IN` relationships when moving backward from an Entity to a `DocumentChunk`, preventing document noise from overwhelming the active context.

### 3.3 The Gardener (Hygiene & TimeWatcher)

A background process responsible for "Graph Hygiene" and temporal awareness.

- **Temporal Awareness (TimeWatcher)**: Scans the Connectome for `Goal.deadline` and `Task.due_date`.
  - **Approaching**: If a deadline is within 24-48h, the TimeWatcher injects a Heat Boost (+0.5).
  - **Overdue**: If a deadline is passed, it injects a Massive Boost (+0.8), triggering proactive warnings from The Butler.
- **Vector Index Maintenance**: The Gardener periodically ensures that the Neo4j Vector Index is up-to-date for nodes with embeddings.
- **Deduplication**: Combines string heuristics with LLM Semantic Comparison to find non-obvious duplicates.
- **Automated Sanitization**: Merges nodes with exact same names to prevent graph fragmentation.
- **Orphan Task Detection**: Identifies `Task` nodes without any relationships. If not marked as `allow_orphan`, it flags them for user contextualization via the Briefing system. [NEW]
- **Longitudinal Scanner**: A periodic routine that identifies "Dormant Projects" (nodes with high historical connectivity but low recent activity) and applies subtle heat boosts to surface them proactively.
- **Worker Status**: Active as a background daemon thread in the Gateway. [NEW]

### 3.4 Knowledge Scopes (Visibility & Deletion)

Mnemosyne implementa un modello di visibilità gerarchico direttamente a livello di query database.

- **Private**: Visibile solo all'istanza/utente proprietario.
- **Internal**: Visibile internamente al sistema.
- **Public**: Esponibile ad agenti esterni.

**Explicit Control**: Oltre alla dimenticanza passiva (decay), il sistema supporta l'eliminazione fisica (`delete_node`) e l'aggiornamento delle proprietà, permettendo la rettifica dei ricordi.

**Ereditarietà**: Uno scope superiore (es. `Private`) ha accesso a tutta la conoscenza degli scope inferiori (`Internal`, `Public`), ma non viceversa.

### 3.5 Mnemosyne REST API (Universal Node CRUD)

Il Gateway espone un set di API REST universali per permettere l'utilizzo di Mnemosyne come un **Headless Graph CMS**. Queste API operano direttamente sulle proprietà dei nodi, bypassando la logica probabilistica degli LLM per operazioni deterministiche.

- **`GET /nodes`**: Elenca i nodi nel grafo. Supporta il filtro `?type=Label` per recuperare solo nodi con una specifica etichetta primaria (es. `Lab`, `Entity`).
- **`GET /nodes/{name}`**: Recupera i dettagli e le proprietà di un singolo nodo tramite il suo identificativo unico (slug).
- **`PUT /nodes/{name}`**: Operazione di **Upsert**. Crea il nodo se non esiste o ne aggiorna le proprietà se già presente. Accetta un payload JSON con `type`, `properties` e `tags`.
- **`DELETE /nodes/{name}`**: Rimuove fisicamente il nodo dal grafo.
- **`PATCH /nodes/{name}/allow_orphan`**: Marca un Task come intenzionalmente isolato, disattivando gli avvisi di igiene del Gardener. [NEW]

Tutti gli endpoint rispettano i **Knowledge Scopes** e richiedono l'autenticazione tramite `X-API-Key` se configurata.

### 3.6 Hybrid Semantic Search (Resilient Fallback)

Il Core implementa una strategia di ricerca a 3 livelli gestita dal `GraphManager`. L'obiettivo è massimizzare la rilevanza riducendo la dipendenza da modelli computazionalmente costosi.

1. **Livello 1 (Match Esatto & Alias)**: Ricerca deterministica per nome del nodo o dei suoi alias. È il metodo più veloce e accurato per concetti già noti.
2. **Livello 2 (Vector Search)**: Se `enable_embeddings` è attivo, il sistema genera un vettore per la query e interroga l'indice vettoriale di Neo4j. Utilizza la *Cosine Similarity* per trovare concetti correlati anche senza match di parole chiave.
3. **Livello 3 (Full-Text Fallback - Lucene)**: Se la ricerca vettoriale è disattivata, fallisce o non restituisce risultati sufficienti, il sistema interroga l'indice Full-Text (`mnemosyne_text_idx`). Questo permette ricerche fuzzy e parziali su `name`, `description`, `content` (Observation) e `ai_context`. [UPDATED]

**Orchestration Logic**: La logica di fallback è isolata nel metodo `gm.semantic_search()`, permettendo al Gateway di rimanere agnostico rispetto al backend di ricerca utilizzato.

### 3.7 Mnemosyne-RPC Protocol (Plugin System)

### 3.5 Asynchronous Learning Pipeline

To ensure a non-blocking user experience and handle potential local LLM latencies (cold starts), the learning process is decoupled from the main request cycle.

- **Immediate Action**: The system creates the `Observation` node and returns a success response to the client instantly.
- **Persistent Queue**: A job is created in a persistent disk-based queue (`data/queue/`) containing the raw text and metadata.
- **Background Worker**: A dedicated `LearningWorker` thread monitors the queue and performs the heavy LLM extraction and graph integration tasks.
- **Resilience**: If the LLM provider is unavailable or slow, jobs are retried automatically without data loss.

### 3.6 Massive Ingestion Pipeline (Zero-LLM)

Designed to handle large scale text data without overwhelming GPU resources.

- **Heuristic Chunker**: Splits text based on structural cues (paragraphs, punctuation) and character limits, ensuring semantic boundaries are respected without using an LLM.
- **Physical Archiving**: Original files are saved to `data/storage/documents/` during ingestion, creating a "source witness" for the graph knowledge.
- **Selective Fuzzy Matcher**: Scans chunks for known entities/topics and creates explicit `MENTIONED_IN` links only for high-relevance matches.
- **Background Processing**: Ingestion is handled via FastAPI `BackgroundTasks`, keeping the Gateway responsive.
- **Deep Deletion**: The system synchronizes the removal of `Document` nodes from the graph with the physical removal of the file from disk, ensuring zero memory pollution.

### 3.7 Gateway Security & Data Governance

To support distributed use cases (e.g., Server2 accessing Mnemosyne on Server1), the Gateway implements a granular security layer.

- **API Key Authentication**: Optional but mandatory for remote access. Enabled by creating a `config/api_keys.yaml` file.
- **Scope-Level Governance**: Each API Key is mapped to a list of authorized Knowledge Scopes.
- **Intersection Logic**: The system automatically intersects the scopes requested by the client with the scopes authorized for their specific API Key. If a key is limited to `Public` and the client requests `Private`, the request is rejected with a `403 Forbidden`.
- **Zero-Config Default**: If no `api_keys.yaml` is present, the Gateway operates in "Open Mode" for local development, allowing all requests (logging a security warning).

---

### 3.8 Feedback & Relevance Tuning

The system uses a binary feedback mechanism (👍/👎) to refine its proactive behavior and semantic retrieval.

#### 3.5.1 Mechanics

Feedback is stored directly on the relationships (Edges) between nodes as a `feedback_score` property.

- **Positive (+1)**: Reinforces the link. Increases the probability of the relationship being used for context injection and sidebar initiatives.
- **Negative (-1)**: Acts as a "Veto". If the cumulative score falls below zero, the relationship is ignored by the `InitiativeEngine`.

#### 3.5.2 Impact on Interaction

1. **Initiative Engine (Sidebar)**: Negative feedback hides the suggestion immediately and permanently for the current relationship.
2. **Contextual Retrieval (The Butler)**: The Butler's responses are grounded in "hot" semantic paths. High feedback scores act as a preference signal during the selection of which facts to retrieve from the Connectome.

---

## 4. Mnemosyne-Standard Protocol

Mnemosyne comunica via a structured JSON protocol per rimanere client-agnostic.

### Node Management (REST)

Il sistema espone API REST universali per la gestione dei nodi (CRUD). Vedi sezione **3.5 Mnemosyne REST API**.

### Interactive Chat Schema

`POST /process_input`

```json
{
  "content": "string",
  "source": "string (e.g., chat, filesystem_watcher, ide)",
  "mode": "string (interactive, background)"
}
```

### Response Schema

```json
{
  "response": "string (The Butler's answer)",
  "metadata": {
    "active_nodes": ["list"],
    "attention_delta": "float"
  },
  "proposed_actions": [
    { "type": "task", "content": "string" }
  ]
}
```

### Document Management Endpoints

#### `GET /documents`

Lists all documents in the Connectome, filtered by scope.

- **Returns**: `{"documents": [{"name": "doc_title", "scope": "Public", "properties": {...}}]}`

#### `GET /document/{name}/download`

Downloads the original archived file from the physical storage.

#### `DELETE /document/{name}`

Performs a **deep delete**: removes the Document node, all its Chunks, and the physical file from disk.

- **Params**: `scope` (default: "Public")

## 5. Implementation Constraints & Principles

- **Hardware Agnostic**: The core logic (Graph + Attention) runs on CPU/RAM. The GPU is only required for occasional LLM inference.
- **Privacy First**: All data lives locally.
- **Transparency**: The user must be able to inspect *why* a node is active or why an initiative was triggered ("Explainability").

## 5. Directory Structure

```text
/home/giorgio/Projects/Mnemosyne gateway/
├── config/             # YAML configuration (decay rates, thresholds)
├── core/               # Python modules for Graph and Attention
├── gateway/            # FastAPI Server & CLI Bridge
├── integrations/       # Application-specific connectors (OpenClaw)
├── workers/            # The Gardener implementation
├── interface/          # Streamlit Dashboard (Visualizer)
├── docker/             # Docker compose files & Neo4j data
└── project_documentation/
```
