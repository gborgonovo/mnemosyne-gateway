# Mnemosyne: Distributed Cognitive Middleware

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Neo4j](https://img.shields.io/badge/Graph-Neo4j-008CC1.svg)](https://neo4j.com/)

**Mnemosyne** is a headless cognitive middleware designed to act as a "Second Brain" for AI agents and human users. Unlike simple RAG (Retrieval-Augmented Generation) systems, Mnemosyne implements a **semantic graph memory** (the Connectome) with a mathematical **Attention Model** that simulates human-like focus, activation propagation, and temporal decay.

## 🧠 Core Vision

Mnemosyne is not a chatbot; it's the **Knowledge OS** that sits between you and your AI agents (like OpenClaw or Open WebUI). It ensures that your knowledge is **Immortal** (persistent), **Private** (local-first), and **Active** (proactive initiatives).

📖 **[Read the Mnemosyne Story](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Theory_The_Story)**: Discover the origin of this project and the "Cognitive Partner" vision.

---

## 🏗️ Architecture: The Micro-Kernel Approach

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
* **Docker** (for Neo4j)
* **Ollama** (for local LLM inference)

### Installation

1. **Clone the repository**:

    ```bash
    git clone https://github.com/gborgonovo/mnemosyne-gateway.git
    cd mnemosyne-gateway
    ```

2. **Start Neo4j**:

    ```bash
    docker run -d --name mnemosyne-db -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/your_password neo4j:latest
    ```

3. **Setup Environment**:

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

4. **Run the System**:

    ```bash
    ./scripts/start.sh
    ```

---

## 🛠️ Utility Scripts

The `scripts/` directory contains tools for managing the Mnemosyne lifecycle and data:

### Lifecycle Management

* **`./scripts/start.sh`**: Launches the Gateway and background Workers in `nohup` mode.
* **`./scripts/stop.sh`**: Gracefully (and forcibly if needed) terminates all Mnemosyne processes.
* **`./scripts/restart.sh`**: Performs a full stop, wait, and start cycle, followed by a health check of the API.
* **`./scripts/monitor.sh`**: **(Recommended)** A comprehensive control panel showing process health, DB connectivity, AI status, and graph statistics.

### Data & Connectome

* **`./scripts/backup.sh`**: Exports the entire graph memory to a timestamped JSON file in `data/backups/`.
* **`./scripts/restore.sh`**: Restores the graph from a backup file (defaults to the latest available).
* **`./scripts/manage_db.py`**: Python utility for administrative tasks (clear, backup, restore).

---

## 🔌 Integrations

* **OpenClaw**: Use the Skill in `integrations/openclaw/`.
* **Open WebUI**: Use the Filter Function in `integrations/open_webui/`.
* **MCP Clients**: Point your settings to `gateway/mcp_server.py`.

---

## 📄 Documentation

For detailed guides, please visit our **[GitHub Wiki](https://github.com/gborgonovo/mnemosyne-gateway/wiki)**:

* [Getting Started](https://github.com/gborgonovo/mnemosyne-gateway/wiki/User_Getting_Started)
* [Architecture Overview](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Dev_Architecture_Overview)
* [The Theory of the Liquid Graph](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Theory_Liquid_Graph)

---

## 🤝 Contributing

We welcome contributions! Please refer to the **[Long-term Vision](https://github.com/gborgonovo/mnemosyne-gateway/wiki/Theory_Semantic_Gland)** for architectural principles.

## ⚖️ License

Project licensed under the MIT License.

---

> *"Mnemosyne is not just storing data; it's learning to know you."*
