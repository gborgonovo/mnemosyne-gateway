#!/bin/bash
# start.sh - Avvia Mnemosyne e i Worker in background

# Spostati nella root del progetto
cd "$(dirname "$0")/.."

# Crea la cartella per i log se non esiste
mkdir -p logs

export PYTHONPATH=.

echo "🧠 Avvio di Mnemosyne in background..."

# Avvia il Gateway
nohup .venv/bin/python3 gateway/http_server.py > logs/gateway.log 2>&1 &
GATEWAY_PID=$!
echo $GATEWAY_PID > logs/gateway.pid
echo "✅ Gateway avviato (PID: $GATEWAY_PID). Log: logs/gateway.log"

# Avvia i Worker
nohup .venv/bin/python3 workers/llm_worker.py > logs/llm_worker.log 2>&1 &
LLM_PID=$!
echo $LLM_PID > logs/llm_worker.pid
echo "✅ LLM Worker avviato (PID: $LLM_PID). Log: logs/llm_worker.log"

nohup .venv/bin/python3 workers/briefing_worker.py > logs/briefing_worker.log 2>&1 &
BRIEFING_PID=$!
echo $BRIEFING_PID > logs/briefing_worker.pid
echo "✅ Briefing Worker avviato (PID: $BRIEFING_PID). Log: logs/briefing_worker.log"

# Estrai la porta dalla configurazione (default 4001) per il messaggio finale
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null || echo 4001)

echo ""
echo "🚀 Sistema completamente operativo in background!"
echo "Per fermare tutto, esegui: ./scripts/stop.sh"
echo "Per controllare lo stato: curl http://localhost:$PORT/status"
