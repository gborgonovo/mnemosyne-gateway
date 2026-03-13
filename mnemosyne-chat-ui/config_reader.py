import yaml
import os

def load_settings():
    # Attempt to load settings from the mnemosyne-gateway config
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    settings_path = os.path.join(base_dir, "config", "settings.yaml")
    
    if not os.path.exists(settings_path):
        print(f"Warning: Settings file not found at {settings_path}")
        return None
        
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = yaml.safe_load(f)
        return settings
    except Exception as e:
        print(f"Error reading settings: {e}")
        return None

def get_llm_config():
    settings = load_settings()
    if not settings or 'llm' not in settings or 'butler' not in settings['llm']:
        return {
            "mode": "mock",
            "model_name": "gpt-4o-mini",
            "base_url": "",
            "api_key": ""
        }
    return settings['llm']['butler']

def get_gateway_config():
    settings = load_settings()
    if not settings or 'gateway' not in settings:
        return {
            "host": "localhost",
            "port": 4002
        }
    
    host = settings['gateway'].get('host', "0.0.0.0")
    if host == "0.0.0.0":
        host = "localhost" # Better for local client access
        
    return {
        "host": host,
        "port": settings['gateway'].get('port', 4002)
    }

def get_api_key():
    # 1. Environment variable (preferred)
    env_key = os.getenv("MNEMOSYNE_API_KEY")
    if env_key:
        return env_key
        
    # 2. Fallback to reading the first key from api_keys.yaml if it exists
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_keys_path = os.path.join(base_dir, "config", "api_keys.yaml")
    
    if os.path.exists(api_keys_path):
        try:
            with open(api_keys_path, 'r', encoding='utf-8') as f:
                keys = yaml.safe_load(f)
                if keys and isinstance(keys, dict):
                    # Return the first key available
                    return next(iter(keys))
        except Exception:
            pass
            
    return None

def get_tester_prompt():
    settings = load_settings()
    try:
        # Peskily look for the tester prompt first, fallback to the regular butler
        prompts = settings['llm']['prompts']
        return prompts.get('tester', prompts.get('butler', "Sei un assistente AI."))
    except (KeyError, TypeError):
        return "Sei un assistente AI."
