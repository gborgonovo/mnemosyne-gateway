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

# Estrazione porta da configurazione
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null || echo 4001)

clear
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}           Mnemosyne: Pannello di Controllo Cognitivo           ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "Data: $(date)"
echo -e "Porta Gateway: ${BOLD}$PORT${NC}"
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

# 2. CONTROLLO CONNETTIVITÀ & API
echo -e "${BLUE}${BOLD}[ 2. Stato Connettività & AI ]${NC}"
STATUS_JSON=$(curl -s --max-time 2 http://localhost:$PORT/status)

if [ $? -eq 0 ]; then
    echo -e "  Gateway API: ${GREEN}● RAGGIUNGIBILE${NC}"
    
    # Parsing dello stato tramite il metodo get_info che abbiamo aggiunto
    NEO4J=$(echo "$STATUS_JSON" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('neo4j', 'unknown'))")
    BUTLER_MODE=$(echo "$STATUS_JSON" | $PYTHON_CMD -c "import sys, json; s=json.load(sys.stdin).get('butler', {}); print(s.get('mode', 'unknown'))")
    BUTLER_STATUS=$(echo "$STATUS_JSON" | $PYTHON_CMD -c "import sys, json; s=json.load(sys.stdin).get('butler', {}); print(s.get('status', 'unknown'))")
    EMB_MODE=$(echo "$STATUS_JSON" | $PYTHON_CMD -c "import sys, json; s=json.load(sys.stdin).get('embeddings', {}); print(s.get('mode', 'unknown'))")
    
    echo -n "  Neo4j DB:    "
    if [[ "$NEO4J" == "connected" ]]; then echo -e "${GREEN}● CONNESSO${NC}"; else echo -e "${RED}○ ERRORE ($NEO4J)${NC}"; fi
    
    echo -e "  Butler Mode: ${BOLD}$BUTLER_MODE${NC} ($BUTLER_STATUS)"
    echo -e "  Embeddings:  ${BOLD}$EMB_MODE${NC}"
else
    echo -e "  Gateway API: ${RED}○ NON RAGGIUNGIBILE${NC} (Il gateway è spento o bloccato)"
fi
echo ""

# 3. STATISTICHE CONNECTOME
echo -e "${BLUE}${BOLD}[ 3. Salute del Connectome ]${NC}"
STATS_JSON=$(curl -s --max-time 2 http://localhost:$PORT/stats)

if [ $? -eq 0 ]; then
    NODES=$(echo "$STATS_JSON" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('total_nodes', 0))")
    EDGES=$(echo "$STATS_JSON" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('total_relationships', 0))")
    echo -e "  Nodi totali: ${BOLD}$NODES${NC}"
    echo -e "  Relazioni:   ${BOLD}$EDGES${NC}"
    
    # Calcolo densità (molto base)
    if [ "$NODES" -gt 0 ]; then
        DENSITY=$($PYTHON_CMD -c "print(round($EDGES/$NODES, 2))")
        echo -e "  Densità:     ${BOLD}$DENSITY${NC} (Relazioni/Nodo)"
    fi
else
    echo -e "  ${YELLOW}Indisponibile.${NC} Avvia il Gateway per vedere le statistiche del grafo."
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
