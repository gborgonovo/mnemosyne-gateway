#!/bin/bash
# start.sh - Start Mnemosyne (File-First) and workers in background

cd "$(dirname "$0")/.."

# Create required directories
mkdir -p logs
mkdir -p knowledge
mkdir -p data

export PYTHONPATH=.

echo "🧠 Starting Mnemosyne (Hybrid File-First) in background..."

# Check if the DB has been initialized. The gateway cold-boots and indexes
# all files in knowledge/ on startup (see http_server.py), so an empty DB here
# is only informational — it does not require a manual --once sync.
if [ ! -d "data/kuzu_main" ] || [ -z "$(ls -A data/kuzu_main 2>/dev/null)" ]; then
    echo "ℹ️  Kùzu database not yet initialized — the gateway will index knowledge/ on startup."
fi

# Start the Gateway (HTTP and MCP)
nohup .venv/bin/python3 gateway/http_server.py > logs/gateway.log 2>&1 &
GATEWAY_PID=$!
echo $GATEWAY_PID > logs/gateway.pid
echo "✅ Gateway started (PID: $GATEWAY_PID). Log: logs/gateway.log"

# The File Watcher runs inside the Gateway (http_server.py)
# to hold the exclusive KuzuDB writer lock.

# LLM enrichment runs in-process inside the Gateway (see workers/file_watcher.py)

# Proactive initiatives are served in-process by the gateway at
# GET /briefing/initiatives and delivered daily by the Alfred cron
# (workers/plugin_runner.py --plugin morning_briefing). No extra worker needed.

# Extract port from settings
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then PORT=4002; fi

echo ""
echo "🚀 System fully operational in background!"
echo "To stop everything, run: ./scripts/stop.sh"
echo "To check status: curl http://localhost:$PORT/"
