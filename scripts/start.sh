#!/bin/bash
# start.sh - Start Mnemosyne (File-First) and workers in background

cd "$(dirname "$0")/.."

# Create required directories
mkdir -p logs
mkdir -p knowledge
mkdir -p data

export PYTHONPATH=.

echo "🧠 Starting Mnemosyne (Hybrid File-First) in background..."

# Check if the DB has been initialized
if [ ! -d "data/kuzu_db" ] || [ -z "$(ls -A data/kuzu_db)" ]; then
    echo "⚠️  WARNING: The Kùzu database appears empty."
    echo "Run 'python3 workers/file_watcher.py --once' to index the files in 'knowledge/'."
fi

# Start the Gateway (HTTP and MCP)
nohup .venv/bin/python3 gateway/http_server.py > logs/gateway.log 2>&1 &
GATEWAY_PID=$!
echo $GATEWAY_PID > logs/gateway.pid
echo "✅ Gateway started (PID: $GATEWAY_PID). Log: logs/gateway.log"

# The File Watcher runs inside the Gateway (http_server.py)
# to hold the exclusive KuzuDB writer lock.

# Start intelligence workers (optional but recommended)
nohup .venv/bin/python3 workers/llm_worker.py > logs/llm_worker.log 2>&1 &
LLM_PID=$!
echo $LLM_PID > logs/llm_worker.pid
echo "✅ LLM Worker started (PID: $LLM_PID). Log: logs/llm_worker.log"

nohup .venv/bin/python3 workers/briefing_worker.py > logs/briefing_worker.log 2>&1 &
BRIEFING_PID=$!
echo $BRIEFING_PID > logs/briefing_worker.pid
echo "✅ Briefing Worker started (PID: $BRIEFING_PID). Log: logs/briefing_worker.log"

# Extract port from settings
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then PORT=4002; fi

echo ""
echo "🚀 System fully operational in background!"
echo "To stop everything, run: ./scripts/stop.sh"
echo "To check status: curl http://localhost:$PORT/"
