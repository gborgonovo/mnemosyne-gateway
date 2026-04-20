import sys
import os
import yaml
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("Briefing")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from butler.initiative import InitiativeEngine

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

def run_briefing():
    logger.info("Generazione del Briefing Proattivo in corso (Hybrid DB)...")
    config = load_config()
    kuzu_mgr = KuzuManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'kuzu_db'))
    ie = InitiativeEngine(kuzu_mgr, config=config)
    
    initiatives = ie.generate_initiatives()
    
    if not initiatives:
        logger.info("Il Kernel è in uno stato di quiete ideale. Nessun suggerimento proattivo al momento.")
        return
        
    print("\n" + "="*50)
    print(" 🎩 IL MAGGIORDOMO CONSIGLIA (Insight Termici)")
    print("="*50)
    for idx, ini in enumerate(initiatives, 1):
        print(f"\n⚡ Initiative #{idx}")
        print(f"Sorgente Calda  : {ini['source']}")
        print(f"Target Seggerito: {ini['target']}")
        print(f"Messaggio       : \"{ini['message']}\"")
        print(f"Logica          : {ini['reason']}")
    print("\n" + "="*50)

if __name__ == "__main__":
    run_briefing()
