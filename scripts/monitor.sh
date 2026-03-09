#!/bin/bash
# monitor.sh - Pannello di controllo e monitoraggio per Mnemosyne

# Root directory
cd "$(dirname "$0")/.."

# Colori
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Estrazione porta e chiave API
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null || echo 4001)

# Estrazione chiave API (prende la prima disponibile)
API_KEY=$($PYTHON_CMD -c "import yaml, os; 
try:
    with open('config/api_keys.yaml', 'r') as f:
        keys = yaml.safe_load(f)
        print(next(iter(keys)) if keys else '')
except:
    print('')" 2>/dev/null)

clear
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}           Mnemosyne: Pannello di Controllo Cognitivo           ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "Data: $(date)"
echo -e "Porta Gateway: ${BOLD}$PORT${NC}"
if [ ! -z "$API_KEY" ]; then echo -e "Auth:          ${GREEN}Configurata${NC}"; else echo -e "Auth:          ${YELLOW}Nessuna chiave (Open Mode?)${NC}"; fi
echo -e ""

# 1. CONTROLLO PROCESSI (LIFECYCLE)
echo -e "${BLUE}${BOLD}[ 1. Stato Processi di Sistema ]${NC}"

check_process() {
    local name=$1
    local file=$2
    if [ -f "$file" ]; then
        local pid=$(cat "$file")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "  $name: ${GREEN}● ATTIVO${NC} (PID: $pid)"
            return 0
        else
            echo -e "  $name: ${RED}○ FERMO${NC} (File PID orfano)"
            return 1
        fi
    else
        echo -e "  $name: ${RED}○ FERMO${NC}"
        return 1
    fi
}

check_process "Gateway HTTP  " "logs/gateway.pid"
check_process "LLM Worker    " "logs/llm_worker.pid"
check_process "Briefing Worker" "logs/briefing_worker.pid"
echo ""

# 2. CONTROLLO CONNETTIVITÀ & AI
echo -e "${BLUE}${BOLD}[ 2. Stato Connettività & AI ]${NC}"
# Timeout aumentato a 10 secondi per gestire risposte lente da OpenAI
STATUS_JSON=$(curl -s --max-time 10 -H "X-API-Key: $API_KEY" http://localhost:$PORT/status)

if [ $? -eq 0 ] && [ ! -z "$STATUS_JSON" ]; then
    echo -e "  Gateway API: ${GREEN}● RAGGIUNGIBILE${NC}"
    
    # Parsing dello stato con gestione errori Python
    PARSE_CMD="import sys, json; 
try:
    data = json.load(sys.stdin)
except:
    data = {}"
    
    NEO4J=$($PYTHON_CMD -c "$PARSE_CMD; print(data.get('neo4j', 'unknown'))" <<< "$STATUS_JSON")
    
    # Butler Info (check both 'butler' and 'llm' keys for compatibility)
    B_DATA=$($PYTHON_CMD -c "$PARSE_CMD; print(json.dumps(data.get('butler', data.get('llm', {}))))" <<< "$STATUS_JSON")
    BUTLER_MODE=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('mode', 'unknown'))" <<< "$B_DATA")
    BUTLER_MODEL=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('model', 'unknown'))" <<< "$B_DATA")
    BUTLER_STATUS=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('status', 'unknown'))" <<< "$B_DATA")
    BUTLER_URL=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('base_url', 'unknown'))" <<< "$B_DATA")
    
    # Embeddings Info
    E_DATA=$($PYTHON_CMD -c "$PARSE_CMD; print(json.dumps(data.get('embeddings', {})))" <<< "$STATUS_JSON")
    EMB_MODE=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('mode', 'unknown'))" <<< "$E_DATA")
    EMB_MODEL=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('model', 'unknown'))" <<< "$E_DATA")
    EMB_STATUS=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('status', 'unknown'))" <<< "$E_DATA")
    EMB_URL=$($PYTHON_CMD -c "import json; d=json.loads(input()); print(d.get('base_url', 'unknown'))" <<< "$E_DATA")
    
    echo -n "  Neo4j DB:    "
    if [[ "$NEO4J" == "connected" ]]; then echo -e "${GREEN}● CONNESSO${NC}"; else echo -e "${RED}○ ERRORE ($NEO4J)${NC}"; fi
    
    echo -n "  Butler:      "
    if [[ "$BUTLER_STATUS" == *"error"* ]]; then 
        echo -e "${RED}○ $BUTLER_MODE | $BUTLER_MODEL${NC}"
        echo -e "               ${RED}Stat: $BUTLER_STATUS${NC}"
        echo -e "               ${RED}URL:  $BUTLER_URL${NC}"
    else 
        echo -e "${GREEN}● $BUTLER_MODE | $BUTLER_MODEL${NC}"
        echo -e "               URL:  $BUTLER_URL"
    fi
    
    echo -n "  Embeddings:  "
    if [[ "$EMB_STATUS" == *"error"* ]]; then 
        echo -e "${RED}○ $EMB_MODE | $EMB_MODEL${NC}"
        echo -e "               ${RED}Stat: $EMB_STATUS${NC}"
        echo -e "               ${RED}URL:  $EMB_URL${NC}"
    else 
        echo -e "${GREEN}● $EMB_MODE | $EMB_MODEL${NC}"
        echo -e "               URL:  $EMB_URL"
    fi
else
    echo -e "  Gateway API: ${RED}○ NON RAGGIUNGIBILE${NC}"
    echo -e "               (Timeout o Errore Auth. Controlla porta e chiavi)"
    STATUS_JSON="{}" 
fi
echo ""

# 3. STATISTICHE CONNECTOME
echo -e "${BLUE}${BOLD}[ 3. Salute del Connectome ]${NC}"
# Estraiamo le statistiche con protezione contro errori di parsing
STATS_PARSE="import sys, json;
try:
    d = json.load(sys.stdin)
    s = d.get('stats', d) if 'stats' in d or 'nodes' in d or 'total_nodes' in d else {}
    print(s.get('nodes') or s.get('total_nodes') or 0)
except:
    print(0)"

NODES=$($PYTHON_CMD -c "$STATS_PARSE" <<< "$STATUS_JSON")

if [ "$NODES" -eq "0" ] 2>/dev/null; then
    # Se non c'erano nello stato, prova l'endpoint dedicato con Auth
    STATS_JSON=$(curl -s --max-time 3 -H "X-API-Key: $API_KEY" http://localhost:$PORT/stats)
    if [ ! -z "$STATS_JSON" ]; then
        NODES=$($PYTHON_CMD -c "$STATS_PARSE" <<< "$STATS_JSON")
        EDGES=$($PYTHON_CMD -c "import sys, json; 
try:
    d = json.load(sys.stdin)
    print(d.get('relationships') or d.get('total_relationships') or 0)
except:
    print(0)" <<< "$STATS_JSON")
    else
        NODES=0
        EDGES=0
    fi
else
    EDGES=$($PYTHON_CMD -c "import sys, json; d=json.load(sys.stdin).get('stats', {}); print(d.get('relationships') or d.get('total_relationships') or 0)" <<< "$STATUS_JSON")
fi

if [ ! -z "$NODES" ] && [ "$NODES" -gt 0 ] 2>/dev/null; then
    echo -e "  Nodi totali: ${BOLD}$NODES${NC}"
    echo -e "  Relazioni:   ${BOLD}$EDGES${NC}"
    DENSITY=$($PYTHON_CMD -c "print(round($EDGES/$NODES, 2))" 2>/dev/null || echo "0")
    echo -e "  Densità:     ${BOLD}$DENSITY${NC} (Relazioni/Nodo)"
else
    echo -e "  ${YELLOW}Dati non disponibili o database vuoto.${NC}"
fi
echo ""

# 4. CODA DI APPRENDIMENTO (QUEUE)
echo -e "${BLUE}${BOLD}[ 4. Coda di Apprendimento ]${NC}"
if [ -d "data/queue" ]; then
    PENDING=$(ls -1 data/queue/*.json 2>/dev/null | wc -l)
    if [ "$PENDING" -gt 0 ]; then
        echo -e "  Pending:     ${YELLOW}$PENDING osservazioni da processare${NC}"
    else
        echo -e "  Status:      ${GREEN}Vuota${NC} (Tutto appreso)"
    fi
else
     echo -e "  Status:      Sconosciuto (Cartella data/queue non trovata)"
fi
echo ""

# 5. ULTIMI EVENTI
echo -e "${BLUE}${BOLD}[ 5. Ultime Attività (Log) ]${NC}"
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
echo -e "Comandi utili: ${BOLD}./scripts/restart.sh${NC} | ${BOLD}./scripts/backup.sh${NC} | ${BOLD}tail -f logs/gateway.log${NC}"
echo -e "${CYAN}================================================================${NC}"
