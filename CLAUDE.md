# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mnemosyne Gateway is a distributed cognitive middleware ("Knowledge OS") — a semantic graph memory system for Claude. It exposes a FastAPI HTTP server and an MCP SSE server that Claude.ai connects to. Knowledge lives as markdown files in `/knowledge/`; two embedded databases (KuzuDB for graph topology, ChromaDB for semantic vectors) are derived state.

## Commands

### Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Run
```bash
./scripts/start.sh          # Start all services (gateway + workers)
./scripts/stop.sh           # Stop all services, release port locks
./scripts/monitor.sh        # Health check
curl http://localhost:4001/status
```

### Individual components
```bash
python3 gateway/http_server.py           # Gateway (HTTP :4001 + MCP SSE) — includes file watcher + LLM enrichment
python3 workers/file_watcher.py --once   # One-time cold-boot sync (outside gateway)
python3 workers/gardener.py              # Temporal decay worker
python3 workers/briefing_worker.py       # Proactive insights
```

### Chat UI (separate venv)
```bash
cd mnemosyne-chat-ui
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### Tests
```bash
python3 -m unittest tests/test_hybrid_architecture.py
python3 test_kuzu.py
```

## Architecture

### Data flow
1. User writes/edits markdown in `/knowledge/` with YAML frontmatter and `[[WikiLink]]` syntax
2. **File Watcher** (`workers/file_watcher.py`) detects changes, parses frontmatter + body, normalizes node names
3. **KuzuDB** (`core/kuzu_manager.py`) stores the topological graph — nodes, edges from wikilinks + typed relations, activation levels
4. **ChromaDB** (`core/vector_store.py`) stores semantic embeddings for similarity search
5. **LLM Enrichment** (background thread inside the gateway): if the file has no `relations:` and body > 150 chars, calls `llm.extract_entities()` and writes the result to the frontmatter. The File Watcher picks up the re-write and syncs the new edges to KuzuDB.
6. **Gardener** (`workers/gardener.py`) runs hourly, applying thermal decay to activation values
7. **Gateway** (`gateway/http_server.py`) exposes both REST and MCP SSE endpoints

### Key design decisions
- **File-first**: Databases are derived from markdown files, not the other way around. The source of truth is `/knowledge/`.
- **Embedded DBs**: KuzuDB replaced Neo4j to eliminate external service dependencies. KuzuDB allows only one writer at a time — the file watcher runs inside the gateway process to avoid lock conflicts.
- **Activation model**: Each node has a heat value [0.0, 1.0] representing recency/relevance. Decay is applied continuously; adding observations raises activation and propagates to neighbors.
- **In-process workers**: both the file watcher and the LLM enrichment thread run inside the gateway process. The standalone `workers/llm_worker.py` (PluginBase/HTTP architecture) is superseded and no longer launched by `start.sh`.

### Components

| Component | File | Role |
|---|---|---|
| Gateway | `gateway/http_server.py` | FastAPI app, mounts REST + MCP |
| MCP Server | `gateway/mcp_app.py` | MCP tools exposed via SSE transport |
| Graph DB | `core/kuzu_manager.py` | KuzuDB wrapper — nodes, edges, activation |
| Vector Store | `core/vector_store.py` | ChromaDB wrapper — semantic search |
| Attention | `core/attention.py` | Activation propagation + decay math |
| Butler | `butler/llm.py` | LLM reasoning layer (mock/ollama/openai/remote) |
| File Watcher | `workers/file_watcher.py` | Markdown sync → graph + vectors + LLM enrichment queue |

### Node data model
Markdown files use YAML frontmatter:
```markdown
---
type: Goal|Task|Observation|Node|Reference|Topic
status: active|todo|done
scope: Private|Internal|Public
deadline: YYYY-MM-DD
created_at: YYYY-MM-DD
relations:
  - target: "Other Node"
    type: PART_OF       # PART_OF | BELONGS_TO | REQUIRES | MANAGES | IS_A | RELATED_TO | LINKED_TO
  - target: "Another Node"
    type: MANAGES
---
Content with [[WikiLinks]] creating LINKED_TO graph edges.
```
Node names are normalized to lowercase with underscores internally; display names preserve original casing.

**Folder defaults**: placing a `_defaults.yaml` file in any `knowledge/` subdirectory applies its keys as frontmatter defaults to all `.md` files in that folder (e.g. `project: Ganaghello`, `scope: Private`). File-level frontmatter takes precedence.

**Typed relations**: the `relations:` list is the persistent source of truth for typed graph edges. On every file sync, the File Watcher creates the corresponding KuzuDB edges (`PART_OF`, `MANAGES`, etc.). This means typed relations survive a full database rebuild — unlike `SEMANTICALLY_RELATED` edges, which are ephemeral state computed by the Gardener.

### Configuration
- `config/settings.yaml` — all runtime settings: decay rate, LLM mode, gateway host/port, retrieval limits
- `config/api_keys.yaml` — optional API key auth mapped to scopes (Private/Internal/Public)
- `.env` — `OPENAI_API_KEY`, `OLLAMA_URL`, etc. (see `.env.example`)

### MCP tools exposed to Claude
**Knowledge retrieval**: `query_knowledge`, `get_memory_briefing`, `get_system_status`

**Observation & authoring**: `add_observation`, `create_node`, `create_goal`, `create_task`
- All create tools accept `folder` (subfolder under `knowledge/`), `relations` (`"Target:TYPE,Other:TYPE"` comma-separated string), and standard frontmatter fields.

**Maintenance**: `update_task_status`, `update_knowledge_frontmatter`, `forget_knowledge_node`, `trigger_gardening_cycle`

**Project/folder management**: `list_projects`, `create_project`, `update_project`
- `create_project(name, description, scope)` → creates `knowledge/<name>/` with `_defaults.yaml`
- `update_project(name, description, scope)` → updates the folder's `_defaults.yaml`

**Diagnostics**: `inspect_file_raw`, `debug_filesystem`

### API endpoints (REST)
`GET /status`, `GET /search?q=`, `GET /nodes/{name}`, `GET /graph/stats`, `GET /briefing`, `POST /observations`, `POST /goals`, `POST /tasks`, `DELETE /nodes/{name}`

## Production

- Gateway runs on port 4001, reverse-proxied by Nginx at `memory.borgonovo.org`
- Chat UI runs on port 8501, proxied at `/chat`
- MCP SSE transport requires `allowed_hosts` whitelist in `config/settings.yaml` (DNS rebinding protection)
- Tests use isolated databases at `data/test_kuzu` and `data/test_chroma`
