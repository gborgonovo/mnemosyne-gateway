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

# Tentativo di estrazione porta (Python -> Grep -> Default)
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null)
if [ -z "$PORT" ]; then
    PORT=$(grep "port:" config/settings.yaml | sed 's/[^0-9]*//g' | head -n 1)
fi
if [ -z "$PORT" ]; then PORT=4002; fi

# Estrazione chiave API (prende la prima disponibile)
API_KEY=$($PYTHON_CMD -c "import yaml, os; 
try:
    with open('config/api_keys.yaml', 'r') as f:
        keys = yaml.safe_load(f)
        print(next(iter(keys)) if keys else '')
except:
    print('')" 2>/dev/null)


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
echo -ne "  Interrogazione Gateway in corso (max 30s)... \r"

STATUS_JSON=$(curl -s --max-time 30 -H "X-API-Key: $API_KEY" http://localhost:$PORT/status)

if [ $? -eq 0 ] && [ ! -z "$STATUS_JSON" ]; then
    echo -e "  Gateway API: ${GREEN}● RAGGIUNGIBILE${NC}                       "
    
    # Unica chiamata Python per estrarre tutto in modo sicuro
    $PYTHON_CMD -c "
import sys, json

try:
    data = json.load(sys.stdin)
except:
    print('  ${RED}○ Errore: Risposta API non valida${NC}')
    sys.exit(0)

def fmt_status(name, label):
    # Cerca Butler sia in 'butler' che 'llm' per compatibilità
    obj = data.get(name)
    if not obj and name == 'butler':
        obj = data.get('llm', {})
    if not obj: obj = {}
    
    mode = obj.get('mode', 'unknown')
    model = obj.get('model', 'unknown')
    status = obj.get('status', 'unknown')
    url = obj.get('base_url', 'unknown')
    
    color = '\033[0;32m●' if 'error' not in str(status).lower() else '\033[0;31m○'
    nc = '\033[0m'
    red = '\033[0;31m'
    
    print(f'  {label:<12} {color} {mode} | {model}{nc}')
    if 'error' in str(status).lower():
        print(f'               {red}Stat: {status}{nc}')
        print(f'               {red}URL:  {url}{nc}')
    else:
        print(f'               URL:  {url}')

# Neo4j
n_status = data.get('neo4j', 'unknown')
n_color = '\033[0;32m● CONNESSO' if n_status == 'connected' else f'\033[0;31m○ ERRORE ({n_status})'
print(f'  Neo4j DB:    {n_color}\033[0m')

fmt_status('butler', 'Butler:')
fmt_status('embeddings', 'Embeddings:')
" <<< "$STATUS_JSON"
else
    echo -e "  Gateway API: ${RED}○ NON RAGGIUNGIBILE${NC}                       "
    echo -e "               (Timeout dopo 30s o Errore Auth. Controlla porta e chiavi)"
    STATUS_JSON="{}" 
fi
echo ""

# 3. STATISTICHE CONNECTOME
echo -e "${BLUE}${BOLD}[ 3. Salute del Connectome ]${NC}"
$PYTHON_CMD -c "
import sys, json

try:
    data = json.load(sys.stdin)
    stats = data.get('stats', {})
    nodes = stats.get('nodes') or stats.get('total_nodes')
    edges = stats.get('relationships') or stats.get('total_relationships')
    
    if nodes and nodes > 0:
        density = round(edges/nodes, 2) if nodes > 0 else 0
        print(f'  Nodi totali: \033[1m{nodes}\033[0m')
        print(f'  Relazioni:   \033[1m{edges}\033[0m')
        print(f'  Densità:     \033[1m{density}\033[0m (Relazioni/Nodo)')
    else:
        print('  \033[1;33mDati non disponibili o database vuoto.\033[0m')
except:
    print('  \033[1;33mDati non disponibili o database vuoto.\033[0m')
" <<< "$STATUS_JSON"

# Statistiche già stampate dal blocco Python sopra
echo ""

# 4. CODA DI APPRENDIMENTO (QUEUE)
echo -e "${BLUE}${BOLD}[ 4. Coda di Apprendimento ]${NC}"
if [ -d "data/queue" ]; then
    # Conta solo i file con status pending o failed
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
