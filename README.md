# Mnemosyne: Personal Knowledge OS

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![KuzuDB](https://img.shields.io/badge/Graph-KùzuDB-orange.svg)](https://kuzudb.com/)
[![MCP](https://img.shields.io/badge/Protocol-MCP-purple.svg)](https://modelcontextprotocol.io/)

**Mnemosyne** is a self-hosted cognitive middleware that acts as a long-term memory layer for AI agents. Unlike simple RAG systems, Mnemosyne implements a **Liquid Graph** — a semantic knowledge graph with a thermal attention model that tracks which concepts are *currently relevant to you*, not just what exists in the database.

Your knowledge lives as plain **Markdown files** you own. Two embedded databases (KùzuDB for graph topology, ChromaDB for semantic search) are derived state — disposable indices rebuilt automatically from your files.

📖 **[Read the Mnemosyne Story](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Theory_The_Story)**: The origin of the cognitive partner vision.

---

## How It Works

```
You write a Markdown file  →  File Watcher detects it  →  KùzuDB + ChromaDB updated
                                                              ↓
AI Agent queries via MCP  →  Gateway retrieves context  →  Hot nodes surface first
```

Every node in the graph has an **activation heat** (0.0–1.0). Heat rises when you interact with a concept and decays over time at a rate proportional to the node type:

| Node type | Decay half-life |
|---|---|
| Observation | ~7 days |
| Topic (Node) | ~11 days |
| Task | ~2 months |
| Goal | ~4 months |

When an AI agent queries your knowledge, it retrieves not just semantically similar content, but the concepts that are *hot right now* — the ones you've been working on recently.

---

## Key Features

- **File-First**: Your knowledge is Markdown files in a `knowledge/` directory. No proprietary format. Works with Obsidian.
- **Thermal Attention Model**: Nodes gain heat through interaction (`file_edit`, `mcp_query`) and propagate warmth to linked neighbors. Decay is usage-based, not calendar-based.
- **Dormant Resurfacing**: Projects you haven't touched in weeks gradually resurface in the briefing, preventing forgotten work from disappearing entirely.
- **Semantic Edge Discovery**: The Gardener periodically finds implicit relationships via ChromaDB similarity and creates graph edges automatically.
- **MCP Native**: Claude.ai and other MCP-compatible agents connect directly. No plugins, no wrappers.
- **Scoped Privacy**: Nodes are tagged `Private`, `Internal`, or `Public`. API keys map to allowed scopes.
- **Zero External Services**: No cloud databases, no mandatory LLMs. Runs on modest hardware.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Git

### Installation

```bash
git clone https://github.com/gborgonovo/mnemosyne-gateway.git
cd mnemosyne-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp config/settings.yaml.template config/settings.yaml
cp config/api_keys.yaml.example config/api_keys.yaml
```

Edit `config/api_keys.yaml` to set your API keys. Edit `config/settings.yaml` to configure the LLM backend (defaults to `mock` mode — no LLM required to start).

### Run

```bash
./scripts/start.sh
curl http://localhost:4001/status
```

The File Watcher runs inside the Gateway process (required for KùzuDB's single-writer constraint). Add your first Markdown file to `knowledge/` and the graph updates automatically.

---

## Connecting to Claude.ai

Add Mnemosyne as an MCP server in your Claude.ai settings:

```
URL: https://your-server/sse
Header: X-API-Key: your_key_here
```

Or for local use with Claude Desktop, add to your MCP config:

```json
{
  "mcpServers": {
    "mnemosyne": {
      "url": "http://localhost:4001/sse",
      "headers": { "X-API-Key": "your_key_here" }
    }
  }
}
```

Available MCP tools: `query_knowledge`, `add_observation`, `get_memory_briefing`, `create_goal`, `create_task`, `update_task_status`, `update_knowledge_frontmatter`, `forget_knowledge_node`, `trigger_gardening_cycle`, `get_system_status`.

---

## Utility Scripts

| Script | Description |
|---|---|
| `./scripts/start.sh` | Start Gateway and workers in background |
| `./scripts/stop.sh` | Stop all Mnemosyne processes |
| `./scripts/restart.sh` | Stop and restart, then verify |
| `./scripts/monitor.sh` | Health check and system status |
| `python3 scripts/simulate_decay.py` | Visualize decay curves for current settings |

---

## Architecture

```
knowledge/*.md          ← Source of Truth (your Markdown files)
    │
    ▼
File Watcher            ← Detects changes, parses frontmatter + [[WikiLinks]]
    │
    ├──▶ KùzuDB         ← Graph topology + activation heat (embedded)
    └──▶ ChromaDB        ← Semantic embeddings (embedded)
         │
         ▼
    Gateway (FastAPI)   ← REST API + MCP SSE on :4001
    Gardener (hourly)   ← Decay + dormant resurfacing + semantic edge discovery
```

For a deeper dive: [Architecture Overview](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Dev_Architecture_Overview) · [The Liquid Graph](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Theory_Liquid_Graph) · [Module Reference](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Dev_Core_Modules)

---

> *"Mnemosyne is not just storing data; it is learning to know you."*
