# Mnemosyne Roadmap 2026.03: Il Partner Cognitivo Integrato

Questo documento rappresenta la visione consolidata di Mnemosyne, unendo i traguardi raggiunti con la nuova direzione strategica che punta alla piena orchestrazione tramite interfaccia web e percezione passiva.

---

## 🏛️ Fondamenta Realizzate (DONE)

### Fase 1-3: Micro-Kernel & Distributed Workers

- [x] **Micro-Kernel (Core)**: Motore agnostico e LLM-free per la gestione dei grafi (Neo4j).
- [x] **Event Bus**: Sistema di messaggistica interna per la sincronizzazione dei componenti.
- [x] **Plugin Framework**: Architettura a worker distribuiti (`LLMWorker`, `BriefingWorker`).
- [x] **Mnemosyne-RPC**: Protocollo per la registrazione e il coordinamento di worker esterni.

### Fase 4-7: Memory Sovereignty & Intentionality

- [x] **Knowledge Scopes**: Isolamento della conoscenza via label (`Private`, `Internal`, `Public`).
- [x] **Memory Tools (MCP)**: Primitive di modifica e cancellazione esplicita (`delete_node`, `update_node`).
- [x] **Attention Model**: Dinamica di propagazione e decadimento (calore semantico).
- [x] **TimeWatcher**: Monitoraggio delle scadenze e boost di attivazione per task/goal.

### Fase 8-9: Intelligence Emergent

- [x] **Massive Ingestion**: Pipeline RAM-centric per caricamento documenti via `/ingest`.
- [x] **Heuristic Chunker**: Spezzettamento semantico zero-LLM con link strutturali.
- [x] **Semantic Firewall**: Attenuazione delle relazioni documentali per ridurre il rumore.
- [x] **Longitudinal Analysis**: Rilevamento di trend storici e progetti dormienti.

---

## 🚀 Nuovi Orizzonti: Verso il "Cognitive Dashboard"

L'obiettivo per i prossimi mesi è spostare il fulcro dell'interazione dal solo prompt a un'interfaccia di orchestrazione visuale e a una percezione passiva dell'ambiente.

### **Fase 10: Cognitive Dashboard (L'Interfaccia di Orchestrazione)**

Vogliamo un portale web centralizzato che agisca da "Cockpit" del tuo pensiero:

- **Chat Evoluta**: Interfaccia di conversazione con *The Butler* con visualizzazione dei nodi attivati in tempo reale.
- **Node Explorer**: Navigazione visuale del Connectome (heatmap del calore e relazioni).
- **Control Center (Orchestrazione)**:
  - Configurazione drag-and-drop dei nodi e dei vincoli.
  - Monitoraggio e registrazione dei Workers (Tier 1, 2, 3).
  - Toggles per attivare/disattivare analisi (Longitudinale, Intentionalità).
- **Ingestion Portal**: Upload file facilitato con drag-and-drop e monitoraggio dello stato di chunking.

### **Fase 11: Cognitive Tiering & Orchestrazione Ibrida**

- **Routing Intelligente**: Il Gateway decide quale modello usare (Ollama locale vs Cloud) in base alla complessità del task e alla sensibilità dello Scope.
- **Failover**: Se un worker Tier 3 remoto cade, Mnemosyne ripiega su un'euristica locale Tier 1.

### **Fase 12: Percezione Passiva (Watchers)**

- **Filesystem Watchers**: Mnemosyne monitora le directory di lavoro. Se modifichi un file di progetto, il relativo nodo nel grafo si "scalda" automaticamente.
- **Perception Connectors**: Integrazione con Calendario (Google/CalDAV) e Feed RSS per iniettare eventi esterni nel flusso di suggerimenti.

### **Fase 13: Advanced Planning & Sandbox**

- **Decomposizione Strategica**: *The Butler* ti aiuta a spezzare macro-obiettivi in passi operativi.
- **Analytical Sandbox**: Simulazioni "What-If" basate sulla rete di dipendenze del grafo.
- **Pedanteria (Anti-Procrastinazione)**: Toggles per forzare l'attenzione su nodi critici bloccando il decadimento.

---

## 📅 Timeline Obiettivi 2026

1. **Marzo**: Lancio del **Mnemosyne Portal** (Web UI base + Chat + Config).
2. **Aprile**: Raffinamento dei **Filesystem Watchers** e Tiering dei modelli.
3. **Maggio**: Integrazione **Strategic Planning** e dashboard analitica.

**Visione Finale**: Mnemosyne non è un bot a cui chiedi informazioni, è un portale dove vedi la tua mente estesa operare, dove i file diventano concetti e dove l'intelligenza si orchestra tra locale e remoto sotto il tuo pieno controllo visivo.
