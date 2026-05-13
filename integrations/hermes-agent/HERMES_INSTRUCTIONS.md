# Mnemosyne Integration: Hermes Agent (Remote Runtime v0.3)

Questa è la configurazione per l'integrazione di Mnemosyne con l'agente Hermes, configurata per connettersi al server remoto `https://memory.borgonovo.org`.

## 1. Struttura del Runtime Locale

- **Cartella Runtime**: `/home/giorgio/.hermes/mnemosyne`
- **Bridge MCP**: `mcp_remote_bridge.py` (usa il protocollo standard MCP via stdio, espande tutti gli strumenti v0.3)
- **Configurazione Sicurezza**: File `.env` locale contenente `MNEMOSYNE_API_KEY`
- **Guida per l'Agente**: `README_AGENTE.md` (da far leggere ad Hermes per spiegargli i suoi superpoteri cognitivi)

## 2. Configurazione MCP

Aggiungi questa configurazione al tuo file di impostazioni di Hermes (es. `hermes_config.json` o analogo). Puoi passare l'API Key direttamente tramite la variabile d'ambiente `MNEMOSYNE_API_KEY` oppure lasciarla nel file `.env` dentro la cartella del runtime.

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "/home/giorgio/.hermes/mnemosyne/.venv/bin/python3",
      "args": [
        "/home/giorgio/.hermes/mnemosyne/mcp_remote_bridge.py"
      ],
      "env": {
        "PYTHONPATH": "/home/giorgio/.hermes/mnemosyne",
        "MNEMOSYNE_API_KEY": "tuo_api_key_qui"
      }
    }
  }
}
```

> [!IMPORTANT]
> Se preferisci non inserire la chiave nel file JSON di configurazione, puoi creare un file denominato `.env` nella cartella `/home/giorgio/.hermes/mnemosyne/` scrivendo:
> ```env
> MNEMOSYNE_API_KEY=tuo_api_key_qui
> ```
> Il bridge rileverà automaticamente il file e lo caricherà all'avvio. Se la chiave non viene configurata in alcuno dei due modi, il bridge si arresterà segnalando l'errore su `stderr`.

## 3. Istruzioni di Sistema (System Prompt)

Incolla queste istruzioni aggiornate nel System Prompt di Hermes:

---
### Memory Integration Instructions (Mnemosyne)
Sei connesso a Mnemosyne, il "Middleware Cognitivo" di Giorgio. Hai accesso completo ai seguenti strumenti avanzati tramite MCP:

#### Strumenti di Lettura e Sintesi:
- **query_knowledge**: Cerca concetti, note e file tramite ricerca semantica con reranking termico. *USALO SEMPRE prima di dichiarare ignoranza su temi passati.*
- **get_memory_briefing**: Chiedi quali sono i topic "caldi" e attivi in questo momento e ricevi un elenco delle note dormienti.
- **get_longitudinal_briefing**: Ottieni il briefing a lungo termine (goal, task, topic inattivi e "hub dimenticati") per proporre azioni di manutenzione della memoria.
- **get_node_details**: Ispeziona il contenuto completo di un nodo specifico della memoria e visualizza i nodi connessi nel grafo.
- **get_system_status**: Verifica la salute e le statistiche globali della memoria remota (nodi in ChromaDB e KùzuDB).

#### Strumenti di Scrittura e Modifica:
- **add_observation**: Registra un'osservazione o nota estemporanea (fleeting note) usando i wikilink `[[Concetto]]` per collegarla ad altri nodi.
- **create_goal**: Definisci un nuovo obiettivo strategico a lungo termine.
- **create_task**: Crea un'azione concreta e collegala a un obiettivo (Goal) preesistente.
- **delete_knowledge_node**: Rimuovi permanentemente un nodo eliminando il file markdown associato.

Leggi il file `/home/giorgio/.hermes/mnemosyne/README_AGENTE.md` per una spiegazione dettagliata del sistema, della fisica del calore del grafo e del tuo ruolo attivo.
---

## 4. Manutenzione e Sicurezza

Tutte le elaborazioni pesanti e l'allineamento dei database semantici (ChromaDB) e topologici (KùzuDB) avvengono sul server remoto. La cartella locale `/home/giorgio/.hermes/mnemosyne` contiene solo l'interfaccia minima e sicura di connessione standard.
