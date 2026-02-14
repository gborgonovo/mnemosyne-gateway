# Integrazione Mnemosyne + OpenClaw

Mnemosyne è ora un server **MCP (Model Context Protocol)** standalone. Questo documento spiega come collegarlo a OpenClaw.

## 1. Requisiti

- OpenClaw installato ed operativo.
- Un'istanza Neo4j attiva (accessibile tramite le credenziali in `config/settings.yaml`).
- L'ambiente virtuale di Mnemosyne configurato (`.venv`).

Il metodo più semplice per integrare Mnemosyne è usare lo **HTTP Bridge**. Questo permette a OpenClaw (dentro Docker) di comunicare con la tua istanza locale di Mnemosyne.

### A. Avvio del Server (sull'Host)

Prima di avviare OpenClaw, devi avviare il bridge sulla tua macchina:

```bash
PYTHONPATH=. .venv/bin/python3 gateway/http_server.py
```

Il server sarà in ascolto su `http://localhost:8000`.

### B. Installazione Skill

1. Copia la cartella `integrations/openclaw` nella directory delle skill di OpenClaw.
2. Assicurati che `openclaw/config.sh` punti correttamente ai tuoi parametri.
3. Riavvia OpenClaw.

L'agente avrà accesso ai tool `openclaw` (`query`, `add`, `briefing`) che interrogano direttamente il tuo grafo locale.

## 3. Configurazione MCP (Alternativa)

Se preferisci usare il protocollo MCP standard:

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "/home/giorgio/Projects/Mnemosyne gateway/.venv/bin/python3",
      "args": [
        "/home/giorgio/Projects/Mnemosyne gateway/gateway/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/home/giorgio/Projects/Mnemosyne gateway"
      }
    }
  }
}
```

## 4. Strumenti Disponibili

Indipendentemente dal metodo, le funzionalità principali sono:

### Funzioni Core

- **`query(query)`**: Cerca nel grafo della memoria per concetti, persone o progetti.
- **`add(content)`**: Salva nuove informazioni, estraendo entità e collegandole automaticamente.
- **`briefing()`**: Riassunto dei temi caldi e suggerimenti proattivi di Alfred.

### Diagnostica (Solo MCP)

- **`get_system_status()`**, **`inspect_node_details()`**, ecc.

## 4. Troubleshooting

Se l'integrazione non sembra funzionare:

1. Verifica che Neo4j sia attivo.
2. Controlla i log di OpenClaw. Mnemosyne emette log di debug su `stderr` che dovrebbero essere catturati dall'host MCP.
3. Esegui il test manuale:

   ```bash
   /home/giorgio/Projects/Mnemosyne\ gateway/.venv/bin/python3 /home/giorgio/Projects/Mnemosyne\ gateway/tests/test_mcp_client.py
   ```
