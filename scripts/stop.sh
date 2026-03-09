#!/bin/bash
# stop.sh - Ferma Mnemosyne e i Worker

cd "$(dirname "$0")/.."

echo "🛑 Spegnimento di Mnemosyne..."

# Ferma il Gateway
# 1. Tenta prima con il file PID (se esiste)
if [ -f logs/gateway.pid ]; then
  PID=$(cat logs/gateway.pid)
  # kill -0 verifica se il processo esiste senza inviare segnali
  if kill -0 $PID 2>/dev/null; then
    kill $PID 2>/dev/null && echo "✅ Gateway fermato tramite PID ($PID)"
  fi
  rm logs/gateway.pid
fi

# Estrai la porta dalla configurazione (default 4001)
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null || echo 4001)

# 2. FALLBACK FONDAMENTALE: Verifica se la porta è ancora occupata
# (Indipendentemente dal file PID, se la porta è piena il restart fallirà)
PORT_PID=$(lsof -t -i :$PORT 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
  echo "⚠  Porta $PORT ancora occupata dal processo $PORT_PID. Terminazione forzata..."
  kill -9 $PORT_PID 2>/dev/null && echo "✅ Gateway rimosso dalla porta $PORT"
fi

# 3. PULIZIA FINALE: Per sicurezza, cerca eventuali processi rimasti per nome
pkill -f "gateway/http_server.py" 2>/dev/null

# Ferma LLM Worker
if [ -f logs/llm_worker.pid ]; then
  PID=$(cat logs/llm_worker.pid)
  kill $PID 2>/dev/null && echo "✅ LLM Worker fermato ($PID)"
  rm logs/llm_worker.pid
fi

# Ferma Briefing Worker
if [ -f logs/briefing_worker.pid ]; then
  PID=$(cat logs/briefing_worker.pid)
  kill $PID 2>/dev/null && echo "✅ Briefing Worker fermato ($PID)"
  rm logs/briefing_worker.pid
fi

# Pulisci eventuali processi zombie
pkill -f "workers/llm_worker.py" 2>/dev/null
pkill -f "workers/briefing_worker.py" 2>/dev/null

echo "💤 Tutti i processi sono stati fermati."
