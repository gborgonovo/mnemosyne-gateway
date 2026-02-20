#!/bin/bash
# stop.sh - Ferma Mnemosyne e i Worker

cd "$(dirname "$0")/.."

echo "🛑 Spegnimento di Mnemosyne..."

# Ferma il Gateway
if [ -f logs/gateway.pid ]; then
  PID=$(cat logs/gateway.pid)
  kill $PID 2>/dev/null && echo "✅ Gateway fermato ($PID)"
  rm logs/gateway.pid
else
  # Fallback
  fuser -k 4001/tcp 2>/dev/null && echo "✅ Gateway fermato tramite porta"
fi

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
