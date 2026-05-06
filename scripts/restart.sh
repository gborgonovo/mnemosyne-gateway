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

# Extract port (Python -> Grep -> Default)
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then
    PORT=$(grep "port:" config/settings.yaml | sed 's/[^0-9]*//g' | head -n 1)
fi
if [ -z "$PORT" ]; then PORT=4002; fi

# 3. Wait for gateway to be ready (up to 30 seconds)
echo "⏳ Waiting for Gateway on port $PORT..."
for i in $(seq 1 15); do
    if curl -s -f http://localhost:$PORT/status > /dev/null 2>&1; then
        curl -s http://localhost:$PORT/status | $PYTHON_CMD -m json.tool
        echo "✅ System restarted successfully!"
        break
    fi
    sleep 2
    if [ $i -eq 15 ]; then
        echo "❌ Gateway did not respond after 30 seconds."
        echo "Check logs with: tail -n 20 logs/gateway.log"
    fi
done

echo ""
echo "🚀 Restart operation completed."
