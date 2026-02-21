# Mnemosyne - Module Documentation

This document provides a technical overview of the python modules and workers that constitute the Mnemosyne architecture. It is intended for developers and maintainers of the project.

---

## 1. Core Modules (`/core`)

### 1.1 `graph_manager.py` (The Connectome Interface)

**Purpose**: Manages all direct interactions with the Neo4j graph database. È ora rigorosamente **LLM-Free**, occupandosi solo della gestione dei nodi, delle relazioni e del filtraggio degli Scopes.

- **Main Class**: `GraphManager`
- **Key Methods**:
  - `add_node(name, primary_label, properties, scope)`: Creates or updates a node within a specific Knowledge Scope.
  - `get_node(name, scopes)`: Retrieves a node, respecting hierarchical visibility.
  - `update_node_properties(name, properties, scopes)`: Safely updates properties on a node.
  - `delete_node(name, scopes)`: Physically removes a node and its relationships from the graph.
  - `get_neighbors(name, scopes)`: Returns connected nodes within the allowed scopes.
  - `get_active_nodes(threshold, scopes)`: Returns active context filtered by scope.
  - `get_dormant_projects(threshold_days, limit, scopes)`: Identifies historically high-heat nodes that have been inactive.
  - `get_temporal_trends(days_ago, limit, scopes)`: Extracts nodes active/created within a specific time window.
  - `add_document(title, chunks, scope)`: Ingests a Document and its constituent Chunks with structural links (`CONTAINS`, `NEXT_CHUNK`).
  - `_fuzzy_link_chunk(chunk_name, text, alias_map)`: Performs selective fuzzy matching to link chunks to existing Entities/Topics.
  - `get_all_aliases(scopes)`: Retrieves a mapping of aliases/names for fuzzy matching.

### 1.2 `attention.py` (The Metabolic Engine)

**Purpose**: Implements the Graph Attention Mechanism. It governs how energy flows through the graph, simulating focus, memory decay, and spreading activation.

- **Main Class**: `AttentionModel`
- **Key Methods**:
  - `stimulate(node_names, boost_amount)`: Injects "heat" into specific nodes (e.g., when mentioned).
  - `propagate()`: Conducts activation from hot nodes to their neighbors, attenuated by relationship weights.
  - `apply_decay()`: Gradually lowers activation levels across all nodes (forgetting).
    - Features **Differential Decay**: Goals and active Tasks decay slower than standard topics.
  - `attenuation`: Implements severe backward propagation penalty (x0.1) for `MENTIONED_IN` relationships (Semantic Firewall).

### 1.3 `chunking.py` (The Document Parser) [NEW]

**Purpose**: Implements zero-LLM text splitting. It uses structural heuristics to divide large documents into manageable chunks without saturating resources.

- **Main Class**: `HeuristicChunker`
- **Key Methods**:
  - `chunk_text(text)`: Splits text into semantic paragraphs with overlap to maintain context.
  - `_hard_split(text)`: Handles excessively long paragraphs by breaking them at sentence boundaries or spaces.

## 2. Butler Layer (`/butler`)

Il package `butler/` contiene la logica relazionale e perceptiva che un tempo risiedeva nel core.

### 2.1 `perception.py` (The Input Gateway)

**Purpose**: Gestisce l'integrazione iniziale delle osservazioni. Crea il nodo `Observation` e mette in coda il caricamento per l'arricchimento asincrono.

### 2.2 `knowledge_queue.py` (The Persistence Buffer)

**Purpose**: Gestisce una coda JSON su disco (`data/queue/`) per i compiti di arricchimento semantico.

### 2.3 `initiative.py` (The Initiative Engine)

**Purpose**: Versione specializzata per la gestione delle proattività, ora integrata nel flusso a eventi del Gateway.

## 3. Distributed Workers (`/workers`)

I worker sono processi indipendenti che estendono le capacità di Mnemosyne tramite il protocollo RPC.

### 3.1 `llm_worker.py` (The Knowledge Enricher)

**Purpose**: Consuma la `KnowledgeQueue` per estrarre entità e topic tramite LLM (Ollama) e reintegrarli nel grafo tramite il Gateway.

### 3.2 `briefing_worker.py` (The Proactive Plugin)

**Purpose**: Sottoscrive l'evento `NODE_ENERGIZED` e genera suggestioni proattive quando un concetto supera le soglie di attivazione.

### 1.6 `feedback.py` (The Learning Layer)

**Purpose**: Captures user interactions (like 👍/👎) to adjust the weights of relationships over time.

- **Main Class**: `FeedbackManager`
- **Key Methods**:
  - `record_feedback(source, target, score)`: Updates the `feedback_score` property on relationships. High scores increase the probability of future initiatives; negative scores suppress them.

---

## 2. Background Workers (`/workers`)

### 4.1 `gardener.py` (The Hygiene Worker)

**Purpose**: Operates as a "Timid Gardener" in the background, performing maintenance tasks that don't require immediate user attention but are vital for long-term health. It also implements the **TimeWatcher** logic for Proactive Planning.

- **Main Methods**:
  - `run_once()`: Executes a full gardening cycle.
  - `sanitize_duplicates()`: Merges nodes with identical names.
  - `check_deadlines()`: Scans for overdue/approaching tasks and goals, applying heat boosts to bring them to focus.
  - `check_dormant_projects()`: Detects abandoned high-connectivity projects and applies subtle activation boosts.
  - `apply_temporal_decay()`: Triggers the attention model's decay.

---

## 3. Gateway Layer (`/gateway`)

### 3.1 `http_server.py` (The API Bridge)

**Purpose**: Exposes Mnemosyne core functionality as a REST API using FastAPI. This allows remote applications (like OpenClaw in Docker or Open WebUI) to interact with the memory.

- **Endpoints**:
  - `GET /status`: Health check for Neo4j and EventBus.
  - `POST /add`: Submits a new observation into a specific scope.
  - `GET /search`: Semantic search with scope-aware filtering.
  - `GET /briefing`: Fetches suggestions generated by `BriefingWorker`.
  - `POST /rpc`: Gateway for internal signaling between workers.
  - `POST /register`: Handshake for external plugins/workers.
  - `POST /share`: Promotes a node from one scope to another.
  - `POST /ingest`: Massive ingestion endpoint for files (txt/md). Handled via background tasks.
  - `GET /briefing/longitudinal`: Returns historical analysis of trends and dormant projects.
  - `GET /stats`: Real-time graph statistics.

### 3.2 `legacy_cli.py` (The Command Line Bridge)

**Purpose**: Provides a shell interface for Mnemosyne, used by the skill scripts for direct host-side execution and testing.

---

## 4. Integrations (`/integrations`)

### 4.1 `openclaw/`

**Purpose**: Contains the OpenClaw skill package. These shell scripts (`add.sh`, `query.sh`, etc.) use `curl` to talk to the Mnemosyne Gateway, providing the agent with long-term memory capabilities.

---

## 5. Visualizer (`/interface`)

### 5.1 `app.py` (The Streamlit Dashboard)

**Purpose**: A secondary visualization tool for the Connectome. It provides a real-time heatmap of node activations and allows manual graph management and history browsing.
