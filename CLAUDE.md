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
python3 gateway/http_server.py           # Gateway (HTTP :4001 + MCP Streamable HTTP) — includes file watcher + LLM enrichment
python3 workers/file_watcher.py --once   # One-time cold-boot sync — only when gateway is STOPPED (gateway holds the KuzuDB lock; running this while gateway is up will fail)
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
python3 -m unittest tests/test_api_upsert.py        # API evolution: relations, upsert, scope inheritance
python3 -m unittest tests/test_security_folder.py   # A1 path traversal + A2 fail-closed auth/CORS
python3 -m unittest tests/test_robustness.py        # B3 content-hash sync + B2 collision detection
python3 -m unittest tests/test_kuzu_concurrency.py  # B5 KuzuManager reentrant lock under load
python3 -m unittest tests/test_base_hybrid.py       # hybrid file-first backend
python3 test_kuzu.py                                # KuzuDB smoke test
```
Tests use isolated databases (temp dirs / `data/test_*`) and never touch production knowledge.

## Architecture

### Data flow
1. User writes/edits markdown in `/knowledge/` with YAML frontmatter and `[[WikiLink]]` syntax
2. **File Watcher** (`workers/file_watcher.py`) detects changes, parses frontmatter + body, normalizes node names
3. **KuzuDB** (`core/kuzu_manager.py`) stores the topological graph — nodes, edges from wikilinks + typed relations, activation levels
4. **ChromaDB** (`core/vector_store.py`) stores semantic embeddings for similarity search
5. **LLM Enrichment** (background thread inside the gateway): if the file has no `relations:` and body > 150 chars, calls `llm.extract_entities()` and writes the result to the frontmatter. The File Watcher picks up the re-write and syncs the new edges to KuzuDB.
6. **Gardener** (`workers/gardener.py`) runs hourly, applying thermal decay to activation values
7. **Gateway** (`gateway/http_server.py`) exposes both REST and MCP Streamable HTTP endpoints

### Key design decisions
- **File-first**: Databases are derived from markdown files, not the other way around. The source of truth is `/knowledge/`.
- **Embedded DBs**: KuzuDB replaced Neo4j to eliminate external service dependencies. KuzuDB allows only one writer at a time — the file watcher runs inside the gateway process to avoid lock conflicts.
- **Activation model**: Each node has a heat value [0.0, 1.0] representing recency/relevance. Decay is applied continuously; adding observations raises activation and propagates to neighbors.
- **In-process workers**: both the file watcher and the LLM enrichment thread run inside the gateway process. The old standalone PluginBase/HTTP worker architecture (`llm_worker.py`, `plugin_base.py`, `plugin_runner.py`) and the pre-Kuzu Neo4j layer (`graph_manager.py`, `perception.py`, `knowledge_queue.py`, `feedback.py`, `learning_worker.py`, the legacy `mcp_server.py`) have been removed; they live in git history if ever needed.
- **Content-hash sync**: re-embedding and re-enrichment are gated on a sha256 of the node *body*, not on mtime. `_body_hash` (in ChromaDB metadata) decides re-embed; `enriched_hash` (in frontmatter) decides re-enrichment. A system-triggered frontmatter rewrite leaves the body identical, so it is recognised as a no-op: no re-embed, no activation boost, no enrichment loop. Body unchanged means a cheap metadata-only Chroma update.
- **Thread safety**: `KuzuManager` serializes every DB operation behind a reentrant lock, since one `kuzu.Connection` is shared by the FastAPI threadpool, the watcher and enrichment threads, and the gardener.
- **Name collisions**: node identity is the normalized file basename, so two files with the same name in different folders share one node (`a/x.md` and `b/x.md` → `x`). The watcher detects this, logs a warning, surfaces it under `name_collisions` in `/status`, and refuses to delete a node on file removal while another file still maps to it. A structural fix (path-based IDs) is deferred.

### Components

| Component | File | Role |
|---|---|---|
| Gateway | `gateway/http_server.py` | FastAPI app, mounts REST + MCP |
| MCP Server | `gateway/mcp_app.py` | MCP tools exposed via Streamable HTTP transport (`/mcp/`) |
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
    # source: llm      # written by enrichment — safe to overwrite; omit or set "user" to protect
enriched_at: YYYY-MM-DD HH:MM:SS   # set by enrichment worker; do not edit manually
enriched_hash: <sha256>            # body hash at last enrichment; guards against re-enriching unchanged content (do not edit)
---
Content with [[WikiLinks]] creating LINKED_TO graph edges.
```
Node names are normalized to lowercase with underscores internally; display names preserve original casing.

**Folder defaults**: placing a `_defaults.yaml` file in any `knowledge/` subdirectory applies its keys as frontmatter defaults to all `.md` files in that folder (e.g. `project: Ganaghello`, `scope: Private`). File-level frontmatter takes precedence.

**Typed relations**: the `relations:` list is the persistent source of truth for typed graph edges. On every file sync, the File Watcher **reconciles** the node's outgoing edges against the frontmatter: it creates the corresponding KuzuDB edges (`PART_OF`, `MANAGES`, etc.) and removes any file-derived edge (typed relation or `[[wikilink]]`/`LINKED_TO`) that is no longer declared. Edges not derived from files — `SEMANTICALLY_RELATED`, computed by the Gardener (see `EPHEMERAL_EDGE_TYPES` in `file_watcher.py`) — are preserved. This means typed relations survive a full database rebuild, and dropping a relation actually removes its edge.

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
`GET /status`, `GET /search?q=`, `GET /nodes/{name}`, `GET /graph/stats`, `GET /briefing`, `GET /briefing/{project}`, `POST /observations`, `POST /goals`, `POST /tasks`, `POST /nodes`, `DELETE /nodes/{name}`

`POST /goals`, `/tasks`, `/nodes` are **upsert by name** (a second POST with the same name updates in place, never duplicates, preserving `created_at`/`enriched_at`) and return the **canonical slug** plus `type`/`scope` (declared `NodeWriteResponse` in the OpenAPI): `{"status":"success","action":"created|updated","name":...,"type":...,"scope":...}`. All three accept `relations` (`"Target:TYPE,Other:TYPE"`) written to frontmatter tagged `source: user` so enrichment never overwrites them. On `/tasks`, `goal_name` is recorded as a `CONTRIBUTES_TO` relation (not an implicit `[[wikilink]]`/`LINKED_TO`). A relation/wikilink target with no file yet becomes a **stub inheriting the source node's scope/project** (a Private node never spawns a Public stub).

Scope on `/goals`,`/tasks`: prefer the singular `scope` field (e.g. `"Private"`); the legacy plural `scopes` is still accepted but only its first entry is used, and the default is `Private` (never silently Public). `GET /briefing` and `GET /briefing/{project}` return a `BriefingResponse` (`hot_topics` + `dormant`), the latter filtered to one project. `DELETE /nodes/{name}` removes a node of any type in any subfolder; its `scopes` param is accepted but not used to gate deletion.

## Production

- Gateway runs on port 4001, reverse-proxied by Nginx at `memory.borgonovo.org`
- Chat UI runs on port 8501, proxied at `/chat`
- MCP Streamable HTTP transport (`stateless_http=True`) at `/mcp/` — requires `allowed_hosts` whitelist in `config/settings.yaml` (DNS rebinding protection)
- Register in Claude Code: `claude mcp add --transport http mnemosyne https://memory.borgonovo.org/mcp/`
- Tests use isolated databases at `data/test_kuzu` and `data/test_chroma`
