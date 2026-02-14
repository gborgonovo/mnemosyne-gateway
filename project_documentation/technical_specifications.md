# Mnemosyne - Technical Specifications

**Version:** 1.0 (Draft)
**Date:** 2026-01-12
**Status:** Approved for Implementation

---

## 1. Project Vision

Mnemosyne is not a chatbot; it is a **Cognitive Partner**. It acts as an extension of the user's mind, maintaining long-term context, evolving relationships between concepts, and offering proactive cognitive support.
Unlike traditional AI assistants that react to prompts, Mnemosyne maintains a persistent state of "attention" on the user's projects and life goals, intervening when it detects relevant connections or neglected areas.

## 2. System Architecture (MCP-First)

Mnemosyne is now a standalone **MCP (Model Context Protocol)** server. It exposes its cognitive capabilities as tools that any MCP-compatible agent can use.

### 2.1 Technology Stack

- **Core**: Python 3.10+
- **Graph Engine**: Neo4j (via Docker)
- **Interface**: FastMCP (stdio transport)
- **Knowledge OS**: Mnemosyne Core (Attention + Initiative + Perception)

### 2.2 Functional Blocks

1. **The Connectome (Core)**: The semantic graph storage.
2. **MCP Gateway**: FastMCP server that exposes tools to the agent.
3. **Attention Engine**: The mathematical model governing node activation.
4. **Perception Module**: Input processing and entity extraction.
5. **Initiative Engine (Mnemosyne)**: Decision engine for proactive support.
6. **Alfred Persona (The Relational Layer)**: Integrated into the MCP tools output for consistent personality.

---

## 3. Core Modules Specification

### 3.1 The Connectome (Graph Schema)

Il Connectome implementa la visione del **"Grafo Liquido"**: la conoscenza non è una gerarchia statica, ma una rete di nodi che cambiano importanza (attivazione) in base all'uso. Invece di una ontologia rigida, utilizziamo un set minimo di "Micro-Types" per fornire una grammatica di base al sistema.

#### Filosofia: Emergenza vs. Struttura

- **Emergenza**: Il sistema permette a nuove connessioni di formarsi liberamente tramite le `Observation` e il feedback dell'utente.
- **Struttura (Micro-Types)**: I tipi fondamentali aiutano Alfred a capire *come* usare le informazioni:
  - `Entity`: Nodi-ancora (Persone, Strumenti, Luoghi). Alfred li usa per estrarre fatti univoci.
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

Decadimento temporale lineare potenziato da un **Fattore di Obsolescenza**: i dati più vecchi perdono attivazione più velocemente se non rinforzati, per dare priorità alla pertinenza attuale.
$$ A_{t} = A_{t-1} - ( \Delta t \times K_{decay} \times \omega_{age} ) $$

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

### 3.4 Semantic Harmonization & Entity Resolution

To prevent the rigidity of string matching (e.g., failing to link "Veranda" and "Terrazzo"), Mnemosyne employs a multi-layered resolution strategy:

1. **Contextual Extraction (Input Stage)**: The Perception Module provides the LLM with a list of "hot" nodes (currently active topics). The LLM is instructed to map synonyms to existing nodes if the context is unambiguous.
2. **Alias Registry**: Nodes support an `aliases` property (e.g., `Veranda` -> `["terrazzo", "balcone"]`). The `GraphManager` lookups are performed across both the Primary Name and the Alias list.
3. **Post-Process Consolidation (Gardener)**: The Gardener identifies nodes with high co-occurrence or similar semantic proximity and proposes `MAYBE_SAME_AS` relationships for user-approved merging.

### 3.5 Feedback & Relevance Tuning

The system uses a binary feedback mechanism (👍/👎) to refine its proactive behavior and semantic retrieval.

#### 3.5.1 Mechanics

Feedback is stored directly on the relationships (Edges) between nodes as a `feedback_score` property.

- **Positive (+1)**: Reinforces the link. Increases the probability of the relationship being used for context injection and sidebar initiatives.
- **Negative (-1)**: Acts as a "Veto". If the cumulative score falls below zero, the relationship is ignored by the `InitiativeEngine`.

#### 3.5.2 Impact on Interaction

1. **Initiative Engine (Sidebar)**: Negative feedback hides the suggestion immediately and permanently for the current relationship.
2. **Contextual Retrieval (Alfred)**: Alfred's responses are grounded in "hot" semantic paths. High feedback scores act as a preference signal during the selection of which facts to retrieve from the Connectome.

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
  "response": "string (Alfred's answer)",
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
/home/giorgio/Projects/Mnemosyne/
├── config/             # YAML configuration (decay rates, thresholds)
├── core/               # Python modules for Graph and Attention
├── workers/            # The Gardener implementation
├── interface/          # Streamlit app
├── docker/             # Docker compose files
└── project_documentation/
```
