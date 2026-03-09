#!/bin/bash
# test_llm.sh - Verifica la connettività OpenAI utilizzando la configurazione di progetto

# Root directory
cd "$(dirname "$0")/.."

# Colori
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Rilevazione python dal venv
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi


echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}           Mnemosyne: Test Connettività OpenAI                  ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo ""

# Script Python inline per il test
$PYTHON_CMD -c "
import os
import sys
import yaml
import json
try:
    from openai import OpenAI
except ImportError:
    print('${RED}Errore: Libreria openai non trovata nel venv!${NC}')
    print('Prova a installarla con: pip install openai')
    sys.exit(1)

# Caricamento configurazione
try:
    with open('config/settings.yaml', 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f'${RED}Errore caricamento settings.yaml: {e}${NC}')
    sys.exit(1)

butler_config = config.get('llm', {}).get('butler', {})
mode = butler_config.get('mode')
model = butler_config.get('model_name')
api_key = butler_config.get('api_key')
base_url = butler_config.get('base_url')

print(f'Configurazione rilevata:')
print(f'  Mode:  {mode}')
print(f'  Model: {model}')
print(f'  URL:   {base_url or \"Default OpenAI\"}')
print(f'  Key:   {api_key[:10]}... (lunghezza {len(api_key)})')

if mode != 'openai':
    print('\n${YELLOW}AVVISO: La modalità non è impostata su \"openai\" in settings.yaml!${NC}')
    sys.exit(1)

print('\nTentativo di connessione a OpenAI (timeout 15s)...')
try:
    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
    response = client.chat.completions.create(
        model=model,
        messages=[{'role': 'user', 'content': 'health check'}],
        timeout=15
    )
    print('\n${GREEN}✅ TEST RIUSCITO!${NC}')
    print(f'Risposta dell\'IA: {response.choices[0].message.content}')
except Exception as e:
    print(f'\n${RED}❌ TEST FALLITO!${NC}')
    print(f'Errore riportato: {e}')
    
    if '404' in str(e):
        print('\n${YELLOW}SUGGERIMENTO: Modello non trovato. Verifica che gpt-4o-mini sia corretto.${NC}')
    elif '401' in str(e):
        print('\n${YELLOW}SUGGERIMENTO: Chiave API non valida o scaduta.${NC}')
    elif 'timeout' in str(e).lower():
        print('\n${YELLOW}SUGGERIMENTO: Timeout di rete. Potrebbe essere un problema di firewall o proxy.${NC}')
"
echo ""
echo -e "${CYAN}================================================================${NC}"
