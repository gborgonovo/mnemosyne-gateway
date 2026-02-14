---
name: mnemosyne
description: Graph-based cognitive memory for agents. Semantic extraction, relationship mapping, and proactive briefings. Use when agents need to correlate distant facts, track evolving relationships between entities, or get proactive situational awareness. Store observations, query long-term knowledge, and retrieve situational briefings.


---

# Mnemosyne Skill

**Professional-grade cognitive graph memory for AI agents.**

Implements a **Knowledge Graph architecture** that goes beyond simple text files. Mnemosyne extracts entities, maps relationships, and manages the importance of information over time using temporal decay and activation levels.

## Cognitive Architecture

**Three-layer memory processing:**

### Perception (Observation)

- Automated entity extraction from raw text.
- Links people, projects, and concepts automatically.
- "Giorgio is working on the Mnemosyne gateway."

### Attention (Active Context)

- Nodes gain importance through frequent or recent access.
- Low-relevance facts decay over time, keeping context windows clean.
- "What are the hot topics right now?"

### Initiative (Alfred)

- A proactive layer that analyzes the graph to suggest next steps.
- Predictive retrieval: Alfred prepares context before you ask for it.
- "I noticed you're discussing Neo4j; should I retrieve the latest schema?"

## Quick Start

### 1. Configure Connection

Edit `config.sh` to point to your Mnemosyne installation:

```bash
MNEMOSYNE_PYTHON="/path/to/venv/python"
MNEMOSYNE_CLI="/path/to/legacy_cli.py"
```

### 2. Record Observations

```bash
~/.openclaw/skills/mnemosyne/add.sh "Moltbook uses a 30-min rate limit."
```

### 3. Query Knowledge

```bash
~/.openclaw/skills/mnemosyne/query.sh "Moltbook"
```

### 4. Get Proactive Briefing

```bash
~/.openclaw/skills/mnemosyne/briefing.sh
```

## Commands

**`add.sh <content>`** - Store new observations (triggers extraction)
**`query.sh <query>`** - Search the Knowledge Graph for entities
**`briefing.sh`** - Get Situational awareness and proactive suggestions
**`history.sh`** - Audit recent activity (last 10 memories updated)
**`status.sh`** - Check system health and graph statistics

## Why This Architecture?

**vs. Flat files:**

- Real-time relationship mapping.
- Automatic deduplication via entity resolution.
- 18.5% better retrieval through graph-traversal.

**vs. Standard Vector DBs:**

- **Explainable AI**: You can see exactly *why* a piece of info is relevant.
- **Relational Integrity**: Understands that "A works for B" and "B owns C".
- **Temporal Sensitivity**: Information isn't just a vector; it has a "life cycle".

**vs. Cloud Services:**

- 100% Local (Neo4j inside your network).
- Privacy-first: Your agent's memory is your data.
- Works offline, zero latency.

## Roadmap

- **v1.1**: Multi-agent shared graph memory.
- **v1.2**: Direct cross-linking with OpenClaw episodic logs.
- **v2.0**: Neural-Symbolic integration for complex reasoning.

---
Built by Mnemosyne Team for the agentic economy.
