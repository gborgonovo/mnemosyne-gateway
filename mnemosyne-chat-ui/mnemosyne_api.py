import requests
import json
from config_reader import get_gateway_config, get_api_key

def get_base_url():
    config = get_gateway_config()
    return f"http://{config['host']}:{config['port']}"

def get_auth_header():
    key = get_api_key()
    return {"X-API-Key": key} if key else {}

def fetch_briefing() -> str:
    """Fetch the longitudinal briefing from Mnemosyne."""
    try:
        url = f"{get_base_url()}/briefing"
        response = requests.get(url, headers=get_auth_header(), timeout=5)
        if response.status_code == 200:
            data = response.json()
            parts = []
            if data.get("hot_topics"):
                parts.append(f"Hot Topics: {', '.join(data['hot_topics'])}")
            if data.get("butler_log"):
                parts.append(f"The Butler's Insight: {data['butler_log']}")
            return "\n".join(parts)
        return ""
    except Exception as e:
        print(f"Error fetching briefing: {e}")
        return ""

def generate_context_from_query(query: str) -> str:
    """Search Mnemosyne for concepts related to the query."""
    try:
        url = f"{get_base_url()}/search"
        import re
        # Clean punctuation and split into keywords
        clean_query = re.sub(r'[^\w\s]', ' ', query)
        words = [w for w in clean_query.split() if len(w) > 3]
        
        found_concepts = []
        
        # Search backwards to prioritize the latest concepts in the sentence
        for word in reversed(words):
            # Increase timeout to 10s to allow for semantic search/LLM processing
            resp = requests.get(url, params={"q": word}, headers=get_auth_header(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                
                # Extract summary safely
                summary = data.get('properties', {}).get('summary', '').strip()
                if not summary:
                    summary = "(Solo nome del nodo, nessun dettaglio aggiuntivo presente nel grafo)"
                    
                details = f"- {data.get('name', word)}: {summary}"
                if data.get("related"):
                    related_details = []
                    for rel in data["related"][:10]:
                        if isinstance(rel, dict):
                            rel_info = f"{rel['name']} ({rel['rel']})"
                            if rel.get('summary'):
                                rel_info += f": {rel['summary']}"
                        else:
                            # Backward compatibility if Gateway is not yet restarted
                            rel_info = str(rel)
                        related_details.append(rel_info)
                    details += f" (Contesto correlato: {'; '.join(related_details)})"
                
                if details not in found_concepts:
                    found_concepts.append(details)
                    
            if len(found_concepts) >= 3: # Limit to top 3 hits to keep context small
                break
                
        if found_concepts:
            return "Specific Memories:\n" + "\n".join(found_concepts)
        return ""
    except Exception as e:
        print(f"Error fetching search context: {e}")
        return ""

def add_memory(user_input: str, assistant_response: str):
    """Save a conversational exchange to Mnemosyne."""
    try:
        url = f"{get_base_url()}/add"
        content = f"User: {user_input}\nAssistant: {assistant_response}"
        payload = {"content": content}
        
        response = requests.post(url, json=payload, headers=get_auth_header(), timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error adding memory: {e}")
        return False
