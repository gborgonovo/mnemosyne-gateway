#!/usr/bin/env python3
import os
import sys
import yaml
import logging
from openai import OpenAI

# Root directory
cdir = os.path.dirname(os.path.abspath(__file__))
rdir = os.path.abspath(os.path.join(cdir, '..'))
sys.path.append(rdir)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_openai")

try:
    with open(os.path.join(rdir, 'config/settings.yaml'), 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"Errore nel caricamento di settings.yaml: {e}")
    sys.exit(1)

butler_config = config.get('llm', {}).get('butler', {})
mode = butler_config.get('mode')
model = butler_config.get('model_name')
api_key = butler_config.get('api_key')

print(f"Configurazione rilevata:")
print(f"  Mode:  {mode}")
print(f"  Model: {model}")
print(f"  Key:   {api_key[:10]}... (lunghezza {len(api_key)})")

if mode != "openai":
    print("\nAVVISO: La modalità non è impostata su 'openai' in settings.yaml!")
    print("Correggi settings.yaml impostando mode: 'openai'")
    sys.exit(1)

print("\nTentativo di connessione a OpenAI...")
client = OpenAI(api_key=api_key)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "health check"}],
        timeout=10
    )
    print("✅ CONNESSIONE RIUSCITA!")
    print(f"Risposta: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ CONNESSIONE FALLITA!")
    print(f"Dettaglio Errore: {e}")
    
    if "404" in str(e) and "gpt-5-nano" in str(e):
        print("\nSUGGERIMENTO: Il modello 'gpt-5-nano' non esiste o non è disponibile.")
        print("Prova a usare 'gpt-4o-mini' o 'gpt-4o'.")
    elif "401" in str(e):
        print("\nSUGGERIMENTO: La chiave API sembra non essere valida.")
