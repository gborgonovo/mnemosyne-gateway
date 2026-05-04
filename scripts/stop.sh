#!/bin/bash
# stop.sh - Stop Mnemosyne and its workers

cd "$(dirname "$0")/.."

echo "🛑 Shutting down Mnemosyne..."

# Stop the Gateway
# 1. Try PID file first (if it exists)
if [ -f logs/gateway.pid ]; then
  PID=$(cat logs/gateway.pid)
  # kill -0 checks if process exists without sending a signal
  if kill -0 $PID 2>/dev/null; then
    kill $PID 2>/dev/null && echo "✅ Gateway stopped via PID ($PID)"
  fi
  rm logs/gateway.pid
fi

# Extract port (Python -> Grep -> Default)
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then
    PORT=$(grep "port:" config/settings.yaml | sed 's/[^0-9]*//g' | head -n 1)
fi
if [ -z "$PORT" ]; then PORT=4002; fi

# 2. ESSENTIAL FALLBACK: check if port is still occupied
# (regardless of PID file, a busy port will cause restart to fail)
PORT_PID=$(lsof -t -i :$PORT 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
  echo "⚠  Port $PORT still in use by process $PORT_PID. Force terminating..."
  kill -9 $PORT_PID 2>/dev/null && echo "✅ Gateway removed from port $PORT"
fi

# 3. FINAL CLEANUP: kill any remaining processes by name
pkill -f "gateway/http_server.py" 2>/dev/null

# Stop LLM Worker
if [ -f logs/llm_worker.pid ]; then
  PID=$(cat logs/llm_worker.pid)
  kill $PID 2>/dev/null && echo "✅ LLM Worker stopped ($PID)"
  rm logs/llm_worker.pid
fi

# Stop Briefing Worker
if [ -f logs/briefing_worker.pid ]; then
  PID=$(cat logs/briefing_worker.pid)
  kill $PID 2>/dev/null && echo "✅ Briefing Worker stopped ($PID)"
  rm logs/briefing_worker.pid
fi

# Stop File Watcher
if [ -f logs/file_watcher.pid ]; then
  PID=$(cat logs/file_watcher.pid)
  kill $PID 2>/dev/null && echo "✅ File Watcher stopped ($PID)"
  rm logs/file_watcher.pid
fi

# Kill any zombie processes
pkill -f "gateway/http_server.py" 2>/dev/null
pkill -f "workers/file_watcher.py" 2>/dev/null
pkill -f "workers/llm_worker.py" 2>/dev/null
pkill -f "workers/briefing_worker.py" 2>/dev/null

echo "💤 All processes have been stopped."
