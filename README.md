# Mnemosyne: Distributed Cognitive Middleware

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Neo4j](https://img.shields.io/badge/Graph-Neo4j-008CC1.svg)](https://neo4j.com/)

**Mnemosyne** is a headless cognitive middleware designed to act as a "Second Brain" for AI agents and human users. Unlike simple RAG (Retrieval-Augmented Generation) systems, Mnemosyne implements a **semantic graph memory** (the Connectome) with a mathematical **Attention Model** that simulates human-like focus, activation propagation, and temporal decay.

## 🧠 Core Vision

Mnemosyne is not a chatbot; it's the **Knowledge OS** that sits between you and your AI agents (like OpenClaw or Open WebUI). It ensures that your knowledge is **Immortale** (persistent), **Private** (local-first), and **Active** (proactive initiatives).

📖 **[Leggi la storia di Mnemosyne](project_documentation/mnemosyne_story.md)**: Scopri come è nato questo progetto e la visione del "Partner Cognitivo" che lo guida.

---

## 🏗️ Architecture: The Micro-Kernel Approach

The project has been refactored from a monolith into a distributed ecosystem:

1. **Micro-Kernel (Core)**: A lightweight, LLM-free engine that manages the Neo4j graph and the "heat" (activation) of nodes.
2. **Mnemosyne Gateway**: A FastAPI-based distributed hub that handles REST requests and coordinates communication via an Event Bus.
3. **Distributed Workers**:
    * **LLMWorker**: Asynchronously enriches the graph by extracting entities and relationships using local LLMs (Ollama).
    * **BriefingWorker**: Generates proactive suggestions and insights when specific concepts become "hot".
4. **The Butler Persona**: A relational layer that interacts with the user, providing a consistent and professional personality.

---

## 🛡️ Key Features

* **Knowledge Scopes**: Multi-layered privacy pools (`Private`, `Internal`, `Public`). Knowledge is strictly isolated at the database level.
* **Attention Model**: Nodes gain "heat" through interaction and lose it over time (decay), automatically highlighting what's relevant *now*.
* **Proactive Planning (Intentionality)**: The system tracks `Goal` and `Task` nodes. It uses "Differential Decay" to keep objectives in mind longer and a "TimeWatcher" to boost the activation of overdue tasks.
* **Explicit Memory Control**: Users (and AI agents) can explicitly update or delete node properties and relationships via MCP tools, moving beyond passive decay.
* **Mnemosyne-RPC**: A lightweight protocol for registering external workers and plugins.
* **MCP Integration**: Native Support for the **Model Context Protocol**, allowing any MCP-compatible agent (like Claude Desktop or OpenClaw) to use Mnemosyne as a specialized memory tool.
* **LLM-Agnostic Core**: The central engine doesn't depend on LLMs, delegating all semantic tasks to dedicated workers.

---

## 🚀 Getting Started

### Prerequisites

* **Python 3.10+**
* **Docker** (for Neo4j)
* **Ollama** (for local LLM inference)

### Installation

1. **Clone the repository**:

    ```bash
    git clone https://github.com/your-username/mnemosyne-gateway.git
    cd mnemosyne-gateway
    ```

2. **Start Neo4j**:

    ```bash
    docker run -d --name mnemosyne-db -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/your_password neo4j:latest
    ```

3. **Setup Virtual Environment**:

    ```bash
    python3 -m venv .venv
    source .venv/bin/python3
    pip install -r requirements.txt
    ```

4. **Configure**:
    Update `config/settings.yaml` with your Neo4j credentials and Ollama endpoint.

5. **Maintenance (Backups)**:
    Keep your Connectome safe by exporting it to JSON:

    ```bash
    .venv/bin/python3 scripts/manage_db.py backup --file data/my_brain.json
    ```

6. **Run the System**:
    To start the Gateway and all background workers safely (detached from the terminal):

    ```bash
    ./scripts/start.sh
    ```

    To stop the system later:

    ```bash
    ./scripts/stop.sh
    ```

---

## 🔌 Integrations

* **OpenClaw**: Use the provided Skill in `integrations/openclaw/` to connect OpenClaw to Mnemosyne.
* **Open WebUI**: Use the Filter Function in `integrations/open_webui/` for seamless context injection.
* **MCP Clients**: Point your MCP settings to `gateway/mcp_server.py`.

---

## 📄 Documentation

For more deep dives, check the `project_documentation/` folder:

* [Technical Specifications](file:///project_documentation/technical_specifications.md)
* [User Guide](file:///project_documentation/user_guide.md)
* [Modules Documentation](file:///project_documentation/modules_documentation.md)
* [Project Roadmap](file:///project_documentation/roadmap%202026-02.md)

---

## 🤝 Contributing

We welcome contributions! Please refer to the [Mnemosyne Project Document](file:///project_documentation/mnemosyne_project.md) for the long-term vision and architectural principles.

## ⚖️ License

This project is licensed under the MIT License - see the LICENSE file for details.

---

> *"Mnemosyne is not just storing data; it's learning to know you."*
