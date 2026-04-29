# Mnemosyne: Distributed Cognitive Middleware

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Neo4j](https://img.shields.io/badge/Graph-Neo4j-008CC1.svg)](https://neo4j.com/)

**Mnemosyne** is a headless cognitive middleware designed to act as a "Second Brain" for AI agents and human users. Unlike simple RAG (Retrieval-Augmented Generation) systems, Mnemosyne implements a **semantic graph memory** (the Connectome) with a mathematical **Attention Model** that simulates human-like focus, activation propagation, and temporal decay.

## 🧠 Core Vision

Mnemosyne is not a chatbot; it's the **Knowledge OS** that sits between you and your AI agents (like OpenClaw or Open WebUI). It ensures that your knowledge is **Immortal** (persistent), **Private** (local-first), and **Active** (proactive initiatives).

📖 **[Read the Mnemosyne Story](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Theory_The_Story)**: Discover the origin of this project and the "Cognitive Partner" vision.

---

## 🏗️ Architecture: Hybrid File-First (v0.3)

The project is a distributed ecosystem designed for modularity:

1. **Micro-Kernel (Core)**: A lightweight, LLM-free engine that manages the Neo4j graph and the "heat" (activation) of nodes.
2. **Mnemosyne Gateway**: A FastAPI-based hub that handles REST requests and coordinates communication via an Event Bus.
3. **Distributed Workers**:
    * **LLMWorker**: Asynchronously enriches the graph by extracting entities and relationships using local LLMs (Ollama).
    * **BriefingWorker**: Generates proactive suggestions and insights when concepts become "hot".
4. **The Butler Persona**: A relational layer that interacts with the user, providing a professional and empathetic personality.

---

## 🛡️ Key Features

* **Document Management**: Physical archiving of original sources with deep-deletion logic syncing disk and graph.
* **Cognitive Dashboard**: API-first Streamlit interface with a dynamic visual Connectome and Document Manager.
* **Knowledge Scopes**: Multi-layered privacy pools (`Private`, `Internal`, `Public`).
* **Attention Model**: Nodes gain "heat" through interaction and lose it over time (decay), highlighting what's relevant *now*.
* **Massive Ingestion**: Zero-LLM semantic chunking for large document repositories.
* **Longitudinal Analysis**: Historical trend detection and recovery of dormant projects.
* **Mnemosyne-RPC**: A lightweight protocol for registering external workers and plugins.
* **MCP Support**: Native implementation of the **Model Context Protocol**.

---

## 🚀 Getting Started

### Prerequisites

* **Python 3.10+**
* **Ollama** (Recommended for local LLM inference)

### Quick Setup (Production)

Se sei sul tuo server di produzione, abbiamo creato uno script che automatizza tutto:

```bash
chmod +x scripts/setup_production.sh
./scripts/setup_production.sh
```

### Manual Installation

1. **Clone & Environment**:
    ```bash
    git clone https://github.com/gborgonovo/mnemosyne-gateway.git
    cd mnemosyne-gateway
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

2. **Initial Ingestion (Cold Boot)**:
    Se hai già dei file Markdown in `knowledge/`, esegui l'indicizzazione iniziale:
    ```bash
    python3 workers/file_watcher.py --once
    ```

3. **Run**:
    ```bash
    ./scripts/start.sh
    ```

---

## 🛠️ Utility Scripts

* **`./scripts/setup_production.sh`**: Configurazione automatica e indicizzazione iniziale.
* **`./scripts/start.sh`**: Avvia Gateway e File Watcher in background.
* **`./scripts/stop.sh`**: Ferma tutti i processi Mnemosyne.
* **`./scripts/monitor.sh`**: Controllo stato e salute del sistema.

---

> *"Mnemosyne is not just storing data; it's learning to know you."*
