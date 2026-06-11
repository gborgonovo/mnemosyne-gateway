# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mnemosyne Gateway is a distributed cognitive middleware ("Knowledge OS") — a semantic graph memory system for Claude. It exposes a FastAPI HTTP server and an MCP Streamable HTTP server that Claude.ai connects to. Knowledge lives as markdown files in `/knowledge/`; two embedded databases (KuzuDB for graph topology, ChromaDB for semantic vectors) are derived state.

## Commands

### Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Run
```bash
./scripts/start.sh          # Start gateway (dev)
./scripts/stop.sh           # Stop gateway, release port locks
./scripts/monitor.sh        # Health check
curl http://localhost:4001/status
```

### Individual components
```bash
python3 gateway/http_server.py           # Gateway (HTTP :4001 + MCP Streamable HTTP) — includes file watcher, LLM enrichment, gardener thread
python3 workers/file_watcher.py --once   # One-time cold-boot sync — only when gateway is STOPPED (gateway holds the KuzuDB lock)
python3 workers/plugin_runner.py --plugin morning_briefing   # Alfred daily email (production cron at 7:00)
```

### Production (TavernaVPS)
```bash
sudo systemctl start mnemosyne           # Start via systemd (deploy/mnemosyne.service)
sudo systemctl status mnemosyne
journalctl -u mnemosyne -f               # Logs
sudo systemctl list-timers | grep knowledge   # Daily knowledge git backup
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
python3 evals/run_eval.py                           # Retrieval eval (offline, direct ChromaDB)
python3 evals/run_eval.py --api http://localhost:4001 --key <key>   # Full eval with thermal re-rank
```
Tests use isolated databases (temp dirs / `data/test_*`) and never touch production knowledge.

## Architecture

### Data flow
1. User writes/edits markdown in `/knowledge/` with YAML frontmatter and `[[WikiLink]]` syntax
2. **File Watcher** (`workers/file_watcher.py`) detects changes, parses frontmatter + body, computes body hash
3. **KuzuDB** (`core/kuzu_manager.py`) stores the topological graph — nodes (path-based IDs), edges from wikilinks + typed relations, activation levels
4. **ChromaDB** (`core/vector_store.py`) stores semantic embeddings; bodies > 4000 chars are split into chunks (`{node_id}__c0`, `__c1`, ...) and each chunk is embedded separately
5. **LLM Enrichment** (background thread inside the gateway): if the file has no `relations:` and body > 150 chars, calls `llm.extract_entities()` and writes the result to the frontmatter. Gated on `enriched_hash` so unchanged bodies are never re-enriched.
6. **Gardener** (background thread inside the gateway): runs every `interval_seconds` (default 3600), applying thermal decay, resurfacing dormant nodes, building `SEMANTICALLY_RELATED` edges between hot nodes
7. **Gateway** (`gateway/http_server.py`) exposes both REST and MCP Streamable HTTP endpoints

### Key design decisions
- **File-first**: Databases are derived from markdown files, not the other way around. The source of truth is `/knowledge/`.
- **Embedded DBs**: KuzuDB replaced Neo4j to eliminate external service dependencies. KuzuDB allows only one writer at a time — the file watcher, enrichment thread, and gardener all run inside the gateway process to avoid lock conflicts.
- **Path-based node IDs**: node identity is the full relative path normalized with `__` as separator (e.g. `ganaghello__spazi__stalla__stalla`). This eliminates collisions between files with the same basename in different folders. Display names (human-readable basenames) are preserved in ChromaDB metadata as `original_name` and returned by the API as `name`. `core/utils.py::node_id_from_path()` is the canonical derivation.
- **WikiLink disambiguation**: when `[[Stalla]]` appears in a file, the watcher resolves it by preferring the candidate that shares the same top-level project folder as the source file. A two-pass cold boot ensures the full basename index is built before any wikilink is resolved.
- **Activation model**: Each node has a heat value [0.0, 1.0] representing recency/relevance. Decay is applied per node type; adding observations or querying raises activation and propagates to neighbors. Thermal re-rank weights semantic similarity by activation: `score = similarity * (1 + alpha * activation)`.
- **Content-hash sync**: re-embedding and re-enrichment are gated on a sha256 of the node *body*, not on mtime. `_body_hash` (in ChromaDB metadata) decides re-embed; `enriched_hash` (in frontmatter) decides re-enrichment. A system-triggered frontmatter rewrite leaves the body identical — recognised as a no-op: no re-embed, no activation boost, no enrichment loop.
- **Chunking**: bodies > 4000 chars are split via `HeuristicChunker` (2000 chars/chunk, 200 overlap) and stored as separate ChromaDB documents. `semantic_search` and `find_similar_nodes` deduplicate results by parent node so callers always receive canonical node IDs, never chunk-suffixed IDs.
- **Thread safety**: `KuzuManager` serializes every DB operation behind a reentrant lock (`threading.RLock`), since one `kuzu.Connection` is shared by the FastAPI threadpool, the watcher, enrichment, and gardener threads.
- **Scope policy**: API keys declare allowed scopes (`Private`, `Internal`, `Public`) in `config/api_keys.yaml`. Write endpoints enforce that the node's scope is in the key's allowed scopes; delete reads the file's frontmatter scope before removing. Read endpoints filter via `intersect_scopes`. Scope is match-exact (no implicit hierarchy).
- **In-process workers**: file watcher, LLM enrichment, and gardener all run as threads inside the gateway. The old standalone PluginBase/HTTP worker architecture and the pre-Kuzu Neo4j layer have been removed; they live in git history if ever needed.
- **Plugin runner (Alfred)**: `workers/plugin_runner.py` is LIVE. Invoked by a production cron (`0 7 * * *`) to generate Giorgio's daily "Alfred" briefing email: loads `plugins/morning_briefing.yaml`, pulls context from `/briefing`, `/briefing/longitudinal`, `/briefing/initiatives` over HTTP using `MNEMOSYNE_API_KEY` from `.env`, composes via `butler.llm`, delivers via `adapters/smtp.py`.

### Components

| Component | File | Role |
|---|---|---|
| Gateway | `gateway/http_server.py` | FastAPI app, mounts REST + MCP; hosts watcher, enrichment, gardener threads |
| MCP Server | `gateway/mcp_app.py` | MCP tools via Streamable HTTP (`/mcp/`) |
| Graph DB | `core/kuzu_manager.py` | KuzuDB wrapper — nodes (path-based IDs), edges, activation, stats |
| Vector Store | `core/vector_store.py` | ChromaDB wrapper — semantic search, chunked embeddings |
| Chunker | `core/chunking.py` | `HeuristicChunker` — paragraph-aware text splitting with overlap |
| Attention | `core/attention.py` | Activation propagation, decay math, thermal re-rank |
| Utils | `core/utils.py` | `node_id_from_path`, `normalize_node_name`, `resolve_safe_folder` |
| Butler | `butler/llm.py` | LLM reasoning layer (mock/ollama/openai/remote) |
| Initiatives | `butler/initiative.py` | `InitiativeEngine` — proactive suggestions from graph topology |
| File Watcher | `workers/file_watcher.py` | Markdown sync: graph + vectors + enrichment queue + basename index |
| Gardener | `workers/gardener.py` | Thermal decay, dormant resurfacing, semantic edge building |
| Plugin Runner | `workers/plugin_runner.py` | Alfred daily email — gateway HTTP client, invoked by cron |

### Node data model
Markdown files use YAML frontmatter:
```markdown
---
type: Goal|Task|Observation|Node|Reference|Topic|Journal
status: active|todo|done|in_progress|archived
scope: Private|Internal|Public
deadline: YYYY-MM-DD
created_at: YYYY-MM-DD
relations:
  - target: "Other Node"
    type: PART_OF       # PART_OF | BELONGS_TO | REQUIRES | MANAGES | IS_A | RELATED_TO | LINKED_TO | CONTRIBUTES_TO
  - target: "Another Node"
    type: MANAGES
    # source: llm      # written by enrichment — safe to overwrite; omit or set "user" to protect
enriched_at: YYYY-MM-DD HH:MM:SS   # set by enrichment worker; do not edit manually
enriched_hash: <sha256>            # body hash at last enrichment; guards against re-enriching unchanged content (do not edit)
---
Content with [[WikiLinks]] creating LINKED_TO graph edges.
```
Node IDs are path-based (`folder__subfolder__basename`); display names preserve original casing.

**Folder defaults**: placing a `_defaults.yaml` file in any `knowledge/` subdirectory applies its keys as frontmatter defaults to all `.md` files in that folder (e.g. `project: Ganaghello`, `scope: Private`). File-level frontmatter takes precedence.

**Typed relations**: the `relations:` list is the persistent source of truth for typed graph edges. On every file sync, the File Watcher **reconciles** the node's outgoing edges against the frontmatter: it creates the corresponding KuzuDB edges and removes any file-derived edge no longer declared. Edges not derived from files (`SEMANTICALLY_RELATED`, computed by the Gardener) are preserved. This means typed relations survive a full database rebuild.

### Configuration
- `config/settings.yaml` — all runtime settings: decay rate, LLM mode, gateway host/port, retrieval limits, chunking thresholds
- `config/api_keys.yaml` — API key auth mapped to scopes (Private/Internal/Public); gitignored
- `.env` — `OPENAI_API_KEY`, `MNEMOSYNE_API_KEY`, `OLLAMA_URL`, etc. (see `.env.example`); gitignored

### MCP tools exposed to Claude
**Knowledge retrieval**: `query_knowledge`, `get_memory_briefing`, `get_system_status`

**Observation & authoring**: `add_observation`, `create_node`, `create_goal`, `create_task`
- All create tools accept `folder` (subfolder under `knowledge/`, nested paths allowed e.g. `Sistema/Claude_Code`), `relations` (`"Target:TYPE,Other:TYPE"` comma-separated string), and standard frontmatter fields.

**Maintenance**: `update_task_status`, `update_knowledge_frontmatter`, `forget_knowledge_node`, `trigger_gardening_cycle`

**Project/folder management**: `list_projects`, `create_project`, `update_project`
- `create_project(name, description, scope)` → creates `knowledge/<name>/` with `_defaults.yaml`
- `update_project(name, description, scope)` → updates the folder's `_defaults.yaml`

**Diagnostics**: `inspect_file_raw`, `debug_filesystem`

### API endpoints (REST)
`GET /status`, `GET /search?q=`, `GET /nodes/{name}`, `GET /graph/stats`, `GET /briefing`, `GET /briefing/longitudinal`, `GET /briefing/initiatives`, `GET /briefing/{project}`, `POST /observations`, `POST /goals`, `POST /tasks`, `POST /nodes`, `DELETE /nodes/{name}`

`GET /status` returns uptime, knowledge file count, KuzuDB node/edge counts (by type), ChromaDB document count, enrichment queue depth, gardener last run and interval.

`GET /search?q=` fetches top-k from ChromaDB, applies thermal re-rank (`score = similarity * (1 + alpha * activation)`), and returns the best match with its graph neighbors.

`POST /goals`, `/tasks`, `/nodes` are **upsert by name** — a second POST with the same name updates in place, preserving `created_at`/`enriched_at`. Return `NodeWriteResponse`: `{"status":"success","action":"created|updated","name":...,"type":...,"scope":...}`. The `name` field is the canonical path-based slug the client should store and reuse. Write endpoints enforce scope: the key must have the node's scope in its allowed scopes (403 otherwise).

`DELETE /nodes/{name}` reads the file's frontmatter scope before deleting and enforces the same write-scope check.

## Production

- Gateway runs as a systemd service (`deploy/mnemosyne.service`) on port 4001, reverse-proxied by Nginx at `memory.borgonovo.org`
- Chat UI runs on port 8501, proxied at `/chat`
- Knowledge base is snapshotted daily at 02:00 by a systemd timer (`deploy/mnemosyne-knowledge-backup.timer`) running `deploy/knowledge_backup.sh` — creates a git commit in the `knowledge/` directory. Syncthing ignores `.git/` via `KnowledgeBase/.stignore`.
- MCP Streamable HTTP transport (`stateless_http=True`) at `/mcp/` — requires `allowed_hosts` whitelist in `config/settings.yaml` (DNS rebinding protection)
- Register in Claude Code: `claude mcp add --transport http mnemosyne https://memory.borgonovo.org/mcp/`
