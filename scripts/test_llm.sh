#!/bin/bash
# test_llm.sh - Test LLM connectivity using the project configuration

cd "$(dirname "$0")/.."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi


echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}              Mnemosyne: LLM Connectivity Test                  ${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo ""

$PYTHON_CMD -c "
import os
import sys
import yaml
import json
try:
    from openai import OpenAI
except ImportError:
    print('${RED}Error: openai library not found in venv!${NC}')
    print('Try installing it with: pip install openai')
    sys.exit(1)

try:
    with open('config/settings.yaml', 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f'${RED}Error loading settings.yaml: {e}${NC}')
    sys.exit(1)

butler_config = config.get('llm', {}).get('butler', {})
mode = butler_config.get('mode')
model = butler_config.get('model_name')
api_key = butler_config.get('api_key')
base_url = butler_config.get('base_url')

print(f'Detected configuration:')
print(f'  Mode:  {mode}')
print(f'  Model: {model}')
print(f'  URL:   {base_url or \"Default OpenAI\"}')
print(f'  Key:   {api_key[:10]}... (length {len(api_key)})')

if mode != 'openai':
    print('\n${YELLOW}WARNING: Mode is not set to \"openai\" in settings.yaml!${NC}')
    sys.exit(1)

print('\nAttempting connection to OpenAI (timeout 15s)...')
try:
    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
    response = client.chat.completions.create(
        model=model,
        messages=[{'role': 'user', 'content': 'health check'}],
        timeout=15
    )
    print('\n${GREEN}✅ TEST PASSED!${NC}')
    print(f'AI response: {response.choices[0].message.content}')
except Exception as e:
    print(f'\n${RED}❌ TEST FAILED!${NC}')
    print(f'Error: {e}')

    if '404' in str(e):
        print('\n${YELLOW}HINT: Model not found. Verify that the model name is correct.${NC}')
    elif '401' in str(e):
        print('\n${YELLOW}HINT: Invalid or expired API key.${NC}')
    elif 'timeout' in str(e).lower():
        print('\n${YELLOW}HINT: Network timeout. Could be a firewall or proxy issue.${NC}')
"
echo ""
echo -e "${CYAN}================================================================${NC}"
