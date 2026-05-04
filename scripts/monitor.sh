#!/bin/bash
# monitor.sh - Control panel and monitoring for Mnemosyne

cd "$(dirname "$0")/.."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Extract port and API key
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi

PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then
    PORT=$(grep "port:" config/settings.yaml | sed 's/[^0-9]*//g' | head -n 1)
fi
if [ -z "$PORT" ]; then PORT=4002; fi

# Extract first available API key
API_KEY=$($PYTHON_CMD -c "import yaml, os;
try:
    with open('config/api_keys.yaml', 'r') as f:
        keys = yaml.safe_load(f)
        print(next(iter(keys)) if keys else '')
except:
    print('')" 2>/dev/null)


echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}              Mnemosyne: Cognitive Control Panel                ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "Date: $(date)"
echo -e "Gateway Port: ${BOLD}$PORT${NC}"
if [ ! -z "$API_KEY" ]; then echo -e "Auth:         ${GREEN}Configured${NC}"; else echo -e "Auth:         ${YELLOW}No key found (Open Mode?)${NC}"; fi
echo -e ""

# 1. PROCESS STATUS
echo -e "${BLUE}${BOLD}[ 1. System Process Status ]${NC}"

check_process() {
    local name=$1
    local file=$2
    if [ -f "$file" ]; then
        local pid=$(cat "$file")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "  $name: ${GREEN}● RUNNING${NC} (PID: $pid)"
            return 0
        else
            echo -e "  $name: ${RED}○ STOPPED${NC} (orphan PID file)"
            return 1
        fi
    else
        echo -e "  $name: ${RED}○ STOPPED${NC}"
        return 1
    fi
}

check_process "Gateway HTTP   " "logs/gateway.pid"
check_process "LLM Worker     " "logs/llm_worker.pid"
check_process "Briefing Worker" "logs/briefing_worker.pid"
echo ""

# 2. CONNECTIVITY & AI STATUS
echo -e "${BLUE}${BOLD}[ 2. Connectivity & AI Status ]${NC}"
echo -ne "  Querying Gateway (max 30s)... \r"

STATUS_JSON=$(curl -s --max-time 30 -H "X-API-Key: $API_KEY" http://localhost:$PORT/status)

if [ $? -eq 0 ] && [ ! -z "$STATUS_JSON" ]; then
    echo -e "  Gateway API: ${GREEN}● REACHABLE${NC}                       "

    $PYTHON_CMD -c "
import sys, json

try:
    data = json.load(sys.stdin)
except:
    print(f'  ${RED}○ Error: Invalid API response${NC}')
    sys.exit(0)

def fmt_status(name, label):
    obj = data.get(name)
    if not obj and name == 'butler':
        obj = data.get('llm', {})
    if not obj: obj = {}

    mode = obj.get('mode', 'unknown')
    model = obj.get('model', 'unknown')
    status = obj.get('status', 'unknown')
    url = obj.get('base_url', 'unknown')

    color = f'${GREEN}●' if 'error' not in str(status).lower() else f'${RED}○'

    print(f'  {label:<12} {color} {mode} | {model}${NC}')
    if 'error' in str(status).lower():
        print(f'               ${RED}Stat: {status}${NC}')
        print(f'               ${RED}URL:  {url}${NC}')
    else:
        print(f'               URL:  {url}')

fmt_status('butler', 'Butler:')
fmt_status('embeddings', 'Embeddings:')
" <<< "$STATUS_JSON"
else
    echo -e "  Gateway API: ${RED}○ UNREACHABLE${NC}                       "
    echo -e "               (Timeout after 30s or Auth error. Check port and keys)"
    STATUS_JSON="{}"
fi
echo ""

# 3. CONNECTOME STATS
echo -e "${BLUE}${BOLD}[ 3. Connectome Health ]${NC}"
$PYTHON_CMD -c "
import sys, json

try:
    data = json.load(sys.stdin)
    stats = data.get('stats', {})
    nodes = stats.get('nodes') or stats.get('total_nodes')
    edges = stats.get('relationships') or stats.get('total_relationships')

    if nodes and nodes > 0:
        density = round(edges/nodes, 2) if nodes > 0 else 0
        print(f'  Total nodes:  ${BOLD}{nodes}${NC}')
        print(f'  Relationships:${BOLD}{edges}${NC}')
        print(f'  Density:      ${BOLD}{density}${NC} (Relationships/Node)')
    else:
        print(f'  ${YELLOW}Data unavailable or empty database.${NC}')
except:
    print(f'  ${YELLOW}Data unavailable or empty database.${NC}')
" <<< "$STATUS_JSON"
echo ""

# 4. LEARNING QUEUE
echo -e "${BLUE}${BOLD}[ 4. Learning Queue ]${NC}"
if [ -d "data/queue" ]; then
    PENDING=$($PYTHON_CMD -c "
import os, json
count = 0
for f in os.listdir('data/queue'):
    if f.endswith('.json'):
        try:
            with open(os.path.join('data/queue', f), 'r') as j:
                if json.load(j).get('status') in ['pending', 'failed']:
                    count += 1
        except: pass
print(count)
" 2>/dev/null || echo 0)
    if [ "$PENDING" -gt 0 ]; then
        echo -e "  Pending:   ${YELLOW}$PENDING observations to process${NC}"
    else
        echo -e "  Status:    ${GREEN}Empty${NC} (all processed)"
    fi
else
     echo -e "  Status:    Unknown (data/queue directory not found)"
fi
echo ""

# 5. RECENT ACTIVITY
echo -e "${BLUE}${BOLD}[ 5. Recent Activity (Log) ]${NC}"
if [ -f "logs/gateway.log" ]; then
    echo -e "  ${CYAN}Gateway:${NC}"
    tail -n 3 logs/gateway.log | sed 's/^/    /'
fi
if [ -f "logs/llm_worker.log" ]; then
    echo -e "  ${CYAN}LLM Worker:${NC}"
    tail -n 3 logs/llm_worker.log | sed 's/^/    /'
fi

echo -e ""
echo -e "${CYAN}================================================================${NC}"
echo -e "Useful commands: ${BOLD}./scripts/restart.sh${NC} | ${BOLD}./scripts/backup.sh${NC} | ${BOLD}tail -f logs/gateway.log${NC}"
echo -e "${CYAN}================================================================${NC}"
