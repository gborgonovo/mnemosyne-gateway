# Mnemosyne - Technical Specifications

**Version:** 1.0 (Draft)
**Date:** 2026-01-12
**Status:** Approved for Implementation

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
- **Storage Pools**: Knowledge Scopes (Private, Internal, Public)

### 2.2 Functional Blocks

1. **The Connectome (Core)**: The semantic graph storage (LLM-Free).
2. **Mnemosyne Gateway**: Distributed FastAPI server and Event Bus hub.
3. **MCP Interface**: Server FastMCP for direct tool integration.
4. **Attention Engine**: Mathematical model for activation & decay.
5. **Knowledge Scopes**: Hierarchical visibility filtering (Private/Public).
6. **Distributed Workers**:
    - **LLMWorker**: Asynchronous entity extraction and enrichment.
    - **BriefingWorker**: Plugin-based proactive initiative generation.
7. **The Butler Persona**: Relational layer for user interaction.

---

## 3. Core Modules Specification

### 3.1 The Connectome (Graph Schema)

Il Connectome implementa la visione del **"Grafo Liquido"**: la conoscenza non è una gerarchia statica, ma una rete di nodi che cambiano importanza (attivazione) in base all'uso. Invece di una ontologia rigida, utilizziamo un set minimo di "Micro-Types" per fornire una grammatica di base al sistema.

#### Filosofia: Emergenza vs. Struttura

- **Emergenza**: Il sistema permette a nuove connessioni di formarsi liberamente tramite le `Observation` e il feedback dell'utente.
- **Struttura (Micro-Types)**: I tipi fondamentali aiutano The Butler a capire *come* usare le informazioni:
  - `Entity`: Nodi-ancora (Persone, Strumenti, Luoghi). The Butler li usa per estrarre fatti univoci.
  - `Topic`: Nodi-tema. Rappresentano il "colore" del discorso e guidano le iniziative proattive.
  - `Resource`: Collegamenti a dati esterni (Files, Links).
  - `Observation`: La memoria episodica. Ogni frase che scrivi è una "osservazione" collegata al tempo.
  - `Goal & Task`: Nodi teleologici. Rappresentano la direzione del sistema e godono di "boost" preferenziali dal Gardener.
  - `Node`: Tipo generico per concetti ancora in fase di definizione.

*Note: Qualsiasi altro descrittore (es. "Progetto", "Urgente", "Sogno") viene applicato come etichetta secondaria o proprietà, permettendo al grafo di evolvere organicamente senza rompere la logica di base.*

#### Relationship Primitives

To allow heuristic emergence, relationships are mapped to four fundamental vectors:

1. `LINKED_TO` (Weight: **Low**, Bidirectional): Generic semantic association.
2. `DEPENDS_ON` (Weight: **High**, Directional): Structural blockage or requirement (e.g., Roof -> Walls).
3. `EVOKES` (Weight: **Medium**, Bidirectional): Emotional or mnemonic trigger.
4. `IS_A` (Weight: **Technical**, Directional): Taxonomic classification.
5. `MENTIONED_IN` (Weight: **Low**, Directional): Link between an Entity/Topic and an Observation.
6. `MAYBE_SAME_AS` (Weight: **Gardener**, Bidirectional): Suggested merge by the Gardener.
7. `FEEDBACK` (Property): Each relationship can store a `feedback_score` (negative scores hide initiatives).

### 3.2 The Attention Engine

This module gives the graph "life" by simulating heat (activation) flow.

#### Decay Model

Decadimento temporale **esponenziale discreto**: i dati perdono attivazione in base a cicli periodici, simulando la dimenticanza naturale.
$$ A_{t} = A_{t-1} \times (1 - K_{decay}) $$
dove $K_{decay}$ è il tasso di decadimento configurabile.

#### Modificatore "Pedanteria" (Persistence)

I nodi marcati con `persistence: high` (Pedanteria) hanno un coefficiente $K_{decay} \approx 0$ e un moltiplicatore di priorità nell'Initiative Engine, garantendo che rimangano "caldi" e visibili fino alla rimozione del tag.

#### Propagation Model

**Bidirectional with Back-Propagation Attenuation**.

- **Forward (A $\to$ B)**: Full strength transfer. If A is active, B becomes relevant.
- **Backward (B $\to$ A)**: Attenuated transfer (e.g., 50%). If B is discussed, A is "remembered" faintly.
  - *Example*: Discussing "Permits" (B) faintly activates "Veranda" (A), triggering the system to check if the permits are for the veranda.

### 3.3 The Gardener (Hygiene Worker)

A background process responsible for "Graph Hygiene".

- **Strategy**: "Timid Suggestion" (creates `MAYBE_SAME_AS`) + Automated Maintenance.
- **Temporal Decay**: Automatically triggers the Attention Engine decay cycle to simulate long-term forgetfulness.
- **Smart Analysis**: Combines string heuristics with **LLM Semantic Comparison** to find non-obvious duplicates (e.g., "IA" vs "Artificial Intelligence").
- **Action**: It does **not** auto-merge. It creates a special `MAYBE_SAME_AS` edge.
- **User Interaction**: The Dashboard visualizes these edges and allows manual merging/dismissal.

### 3.4 Knowledge Scopes (Visibility & Privacy)

Mnemosyne implementa un modello di visibilità gerarchico direttamente a livello di query database.

- **Private**: Visibile solo all'istanza/utente proprietario.
- **Internal**: Visibile internamente al sistema (es. per analisi cross-progetto).
- **Public**: Esponibile ad agenti esterni o alla conoscenza globale.

**Ereditarietà**: Uno scope superiore (es. `Private`) ha accesso a tutta la conoscenza degli scope inferiori (`Internal`, `Public`), ma non viceversa. Questo garantisce che i "segreti" non trapelino mai nelle interazioni pubbliche.

### 3.5 Mnemosyne-RPC Protocol (Plugin System)

Il sistema supporta l'estensione tramite worker distribuiti che comunicano tramite il protocollo **Mnemosyne-RPC**.

1. **Registrazione**: I worker si registrano al Gateway tramite `/register`.
2. **Pub/Sub**: Il Gateway pubblica eventi (es. `NODE_ENERGIZED`, `NEW_OBSERVATION`).
3. **Risposta**: I worker elaborano e restituiscono risultati (es. `INITIATIVE_READY`, `ENRICHMENT_RESULT`).

### 3.5 Asynchronous Learning Pipeline

To ensure a non-blocking user experience and handle potential local LLM latencies (cold starts), the learning process is decoupled from the main request cycle.

- **Immediate Action**: The system creates the `Observation` node and returns a success response to the client instantly.
- **Persistent Queue**: A job is created in a persistent disk-based queue (`data/queue/`) containing the raw text and metadata.
- **Background Worker**: A dedicated `LearningWorker` thread monitors the queue and performs the heavy LLM extraction and graph integration tasks.
- **Resilience**: If the LLM provider is unavailable or slow, jobs are retried automatically without data loss.

### 3.6 Feedback & Relevance Tuning

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

Mnemosyne communicates via a structured JSON protocol to remain client-agnostic.

### Request Schema

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

## 5. Implementation Constraints & Principles

- **Hardware Agnostic**: The core logic (Graph + Attention) runs on CPU/RAM. The GPU is only required for occasional LLM inference.
- **Privacy First**: All data lives locally.
- **Transparency**: The user must be able to inspect *why* a node is active or why an initiative was triggered ("Explainability").

## 5. Directory Structure

```
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
