#!/bin/bash
# start.sh - Avvia Mnemosyne (File-First) e i Worker in background

# Spostati nella root del progetto
cd "$(dirname "$0")/.."

# Crea le cartelle necessarie
mkdir -p logs
mkdir -p knowledge
mkdir -p data/kuzu_db
mkdir -p data/chroma_db

export PYTHONPATH=.

echo "🧠 Avvio di Mnemosyne (Hybrid File-First) in background..."

# Verifica se il DB è stato inizializzato
if [ ! -d "data/kuzu_db" ] || [ -z "$(ls -A data/kuzu_db)" ]; then
    echo "⚠️  ATTENZIONE: Il database Kùzu sembra vuoto."
    echo "Esegui 'python3 workers/file_watcher.py --once' per indicizzare i file in 'knowledge/'."
fi

# Avvia il Gateway (HTTP e MCP)
nohup .venv/bin/python3 gateway/http_server.py > logs/gateway.log 2>&1 &
GATEWAY_PID=$!
echo $GATEWAY_PID > logs/gateway.pid
echo "✅ Gateway avviato (PID: $GATEWAY_PID). Log: logs/gateway.log"

# Avvia il File Watcher (Sincronizzazione real-time)
nohup .venv/bin/python3 workers/file_watcher.py > logs/file_watcher.log 2>&1 &
WATCHER_PID=$!
echo $WATCHER_PID > logs/file_watcher.pid
echo "✅ File Watcher avviato (PID: $WATCHER_PID). Log: logs/file_watcher.log"

# Avvia i Worker di intelligenza (opzionali ma raccomandati)
nohup .venv/bin/python3 workers/llm_worker.py > logs/llm_worker.log 2>&1 &
LLM_PID=$!
echo $LLM_PID > logs/llm_worker.pid
echo "✅ LLM Worker avviato (PID: $LLM_PID). Log: logs/llm_worker.log"

nohup .venv/bin/python3 workers/briefing_worker.py > logs/briefing_worker.log 2>&1 &
BRIEFING_PID=$!
echo $BRIEFING_PID > logs/briefing_worker.pid
echo "✅ Briefing Worker avviato (PID: $BRIEFING_PID). Log: logs/briefing_worker.log"

# Estrazione porta
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then PORT=4002; fi

echo ""
echo "🚀 Sistema completamente operativo in background!"
echo "Per fermare tutto, esegui: ./scripts/stop.sh"
echo "Per controllare lo stato: curl http://localhost:$PORT/"
