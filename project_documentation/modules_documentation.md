# Mnemosyne - Module Documentation

This document provides a technical overview of the python modules and workers that constitute the Mnemosyne architecture. It is intended for developers and maintainers of the project.

---

## 1. Core Modules (`/core`)

### 1.1 `graph_manager.py` (The Connectome Interface)

**Purpose**: Manages all direct interactions with the Neo4j graph database. It handles node creation, relationship mapping, and retrieval of active context.

- **Main Class**: `GraphManager`
- **Key Methods**:
  - `add_node(name, primary_label, properties)`: Creates or updates a node in the graph.
  - `get_node(name)`: Retrieves a node by name or its `aliases`.
  - `add_alias(node_name, alias)`: Appends an alias to a node for semantic harmonization.
  - `get_active_nodes(threshold)`: Returns nodes with activation levels above a certain value.
  - `update_activation(name, value)`: Directly modifies a node's heat level.
  - `trace_dependencies(start_node_name, max_depth)`: Traces downstream `DEPENDS_ON` or `IS_A` links for Impact Analysis (Sandbox Reasoning).
  - `get_neighbors(name)`: Returns all nodes connected to a specific entry.

### 1.2 `attention.py` (The Metabolic Engine)

**Purpose**: Implements the Graph Attention Mechanism. It governs how energy flows through the graph, simulating focus, memory decay, and spreading activation.

- **Main Class**: `AttentionModel`
- **Key Methods**:
  - `stimulate(node_names, boost_amount)`: Injects "heat" into specific nodes (e.g., when mentioned).
  - `propagate()`: Conducts activation from hot nodes to their neighbors, attenuated by relationship weights.
  - `apply_decay()`: Gradually lowers activation levels across all nodes (forgetting). Note: Nodes with `persistence: high` are exempt from decay.

### 1.3 `initiative.py` (The Decision Layer)

**Purpose**: Analyzes the current state of the graph to determine when the system should proactively intervene through Alfred.

- **Main Class**: `InitiativeEngine`
- **Key Methods**:
  - `get_proactive_context()`: Identifies "hot" topics that haven't been discussed recently and returns a summary for the LLM.
  - `generate_initiatives()`: Evaluates specific strategies (e.g., Goal Decomposition) to suggest actions to the user.
  - `get_initiatives(limit)`: Returns a list of formatted suggestions based on graph triggers.

### 1.4 `perception.py` (The Input Gateway)

**Purpose**: Processes raw user input into structured graph data. It acts as the "eyes and ears" of the system.

- **Main Class**: `PerceptionModule`
- **Key Methods**:
  - `process_input(text)`:
        1. Creates an `Observation` node.
        2. Uses the LLM to extract entities/topics (mentioning existing active nodes as context).
        3. Updates or creates nodes in the Connectome.
        4. Links entities to the Observation.
        5. Stimulates the mentioned nodes via the `AttentionModel`.

### 1.5 `llm.py` (The Linguistic & Semantic Gland)

**Purpose**: Provides an abstraction layer for LLM providers (Ollama, OpenAI, Mock). It is used for text generation, entity extraction, and semantic comparisons.

- **Key Classes**: `LLMProvider` (Abstract), `OpenAILLM`, `OllamaLLM`, `MockLLM`.
- **Key Methods**:
  - `generate_response(user_text, proactive_context, impact_context, semantic_context)`: Generates Alfred's response.
  - `extract_entities(text, context_nodes)`: Identifies `Entity`, `Topic`, `Goal`, and `Task` items in raw text. Uses JSON mode for reliability.
  - `compare_entities(e1, e2)`: Deep semantic comparison used by the Gardener for deduplication.

### 1.6 `feedback.py` (The Learning Layer)

**Purpose**: Captures user interactions (like 👍/👎) to adjust the weights of relationships over time.

- **Main Class**: `FeedbackManager`
- **Key Methods**:
  - `record_feedback(source, target, score)`: Updates the `feedback_score` property on relationships. High scores increase the probability of future initiatives; negative scores suppress them.

---

## 2. Background Workers (`/workers`)

### 2.1 `gardener.py` (The Hygiene Worker)

**Purpose**: Operates as a "Timid Gardener" in the background, performing maintenance tasks that don't require immediate user attention but are vital for long-term health.

- **Main Class**: `Gardener`
- **Key Methods**:
  - `apply_temporal_decay()`: Calls the Attention Engine's decay cycle.
  - `find_and_mark_duplicates()`: Scans the graph for potential duplicate nodes using string heuristics and LLM comparison, creating `MAYBE_SAME_AS` links.
  - `check_deadlines()`: Scans for `Task` nodes with upcoming or overdue deadlines and injects massive activation boosts to grab Alfred's attention.
  - `run_once()`: Orchestrates one full cycle of maintenance.

---

## 3. Gateway Layer (`/gateway`)

### 3.1 `http_server.py` (The API Bridge)

**Purpose**: Exposes Mnemosyne core functionality as a REST API using FastAPI. This allows remote applications (like OpenClaw in Docker or Open WebUI) to interact with the memory.

- **Endpoints**:
  - `GET /status`: Health check for Neo4j and LLM.
  - `POST /add`: Submits a new observation.
  - `GET /search`: Semantic search on the graph.
  - `GET /briefing`: Fetches the proactive context from the Initiative Engine.
  - `GET /history`: Retrieves the audit trail of recent memories.

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
