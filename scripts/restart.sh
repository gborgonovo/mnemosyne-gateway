#!/bin/bash
# restart.sh - Restart Mnemosyne and workers, then verify status

cd "$(dirname "$0")/.."

echo "♻️  Restarting Mnemosyne..."

# 1. Stop everything
./scripts/stop.sh

# Brief pause to ensure ports are free
sleep 1

# 2. Start everything
./scripts/start.sh

echo "⏳ Waiting for Gateway to be ready..."
sleep 5

# Extract port (Python -> Grep -> Default)
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then
    PORT=$(grep "port:" config/settings.yaml | sed 's/[^0-9]*//g' | head -n 1)
fi
if [ -z "$PORT" ]; then PORT=4002; fi

# 3. Verify status
echo "🔍 Checking Gateway status on port $PORT..."
if curl -s -f http://localhost:$PORT/status > /dev/null; then
    curl -s http://localhost:$PORT/status | $PYTHON_CMD -m json.tool
    echo "✅ System restarted successfully!"
else
    echo "❌ Error checking Gateway on port $PORT."
    echo "Check logs with: tail -n 20 logs/gateway.log"
fi

echo ""
echo "🚀 Restart operation completed."
