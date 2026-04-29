# Mnemosyne Integration: Hermes Agent (Remote Runtime)

Questa è la configurazione per l'integrazione di Mnemosyne con l'agente Hermes, configurata per connettersi al server remoto `https://memory.borgonovo.org`.

## 1. Struttura del Runtime Locale

- **Cartella Runtime**: `/home/giorgio/.hermes/mnemosyne`
- **Bridge MCP**: `mcp_remote_bridge.py` (usa il protocollo standard MCP via stdio)
- **Guida per l'Agente**: `README_AGENTE.md` (da far leggere ad Hermes per fargli capire cos'è Mnemosyne)

## 2. Configurazione MCP

Aggiungi questa configurazione al tuo file di impostazioni di Hermes:

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "/home/giorgio/.hermes/mnemosyne/.venv/bin/python3",
      "args": [
        "/home/giorgio/.hermes/mnemosyne/mcp_remote_bridge.py"
      ],
      "env": {
        "PYTHONPATH": "/home/giorgio/.hermes/mnemosyne"
      }
    }
  }
}
```

## 3. Istruzioni di Sistema (System Prompt)

Incolla queste istruzioni nel System Prompt di Hermes:

---
### Memory Integration Instructions (Mnemosyne)
Sei collegato a Mnemosyne, il "Middleware Cognitivo" di Giorgio. Hai accesso ai seguenti strumenti tramite MCP:

- **query_knowledge**: Ricerca semantica. USALO SEMPRE prima di dichiarare ignoranza su temi passati.
- **add_observation**: Registra nuove informazioni usando i wikilink `[[Concetto]]`.
- **get_memory_briefing**: Chiedi quali sono i topic "caldi" e attivi in questo momento.

Leggi il file `/home/giorgio/.hermes/mnemosyne/README_AGENTE.md` per una spiegazione dettagliata del sistema e del tuo ruolo.
---

## 4. Manutenzione

Tutte le operazioni pesanti avvengono sul server remoto. La cartella locale `/home/giorgio/.hermes/mnemosyne` contiene solo il minimo indispensabile per il collegamento.
