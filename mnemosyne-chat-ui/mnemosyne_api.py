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
        clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
        words = [w for w in clean_query.split() if len(w) > 3]
        
        # Add the whole (cleaned) query as the first priority
        search_terms = []
        if len(clean_query) > 3:
            search_terms.append(clean_query)
        
        # Add individual words, preventing duplicates
        for w in reversed(words):
            if w not in search_terms:
                search_terms.append(w)
        
        found_concepts = []
        
        # Search backward through priority terms
        for term in search_terms:
            # Increase timeout to 10s to allow for semantic search/LLM processing
            resp = requests.get(url, params={"q": term}, headers=get_auth_header(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                
                # Extract summary/description safely
                props = data.get('properties', {})
                summary = props.get('summary') or props.get('description') or props.get('content', '')
                if summary:
                    summary = summary.strip()
                else:
                    summary = "(Solo nome del nodo, nessun dettaglio aggiuntivo presente nel grafo)"
                    
                details = f"- {data.get('name', word)}: {summary}"
                if data.get("related"):
                    related_details = []
                    for rel in data["related"][:15]: # Increased limit for better breadth
                        if isinstance(rel, dict):
                            # Try multiple possible keys for the neighbor description
                            n_summary = rel.get('summary') or rel.get('description') or rel.get('content')
                            rel_info = f"{rel['name']} ({rel['rel']})"
                            if n_summary:
                                rel_info += f": {n_summary[:200]}" # Limit neighbor snippets
                        else:
                            rel_info = str(rel)
                        related_details.append(rel_info)
                    details += f"\n  - Connessioni e dettagli correlati: {'; '.join(related_details)}"
                
                if details not in found_concepts:
                    found_concepts.append(details)
                    print(f"DEBUG: Found concept '{data.get('name')}' with {len(data.get('related', []))} neighbors.")
                    
            if len(found_concepts) >= 5: # Increased limit for better breadth
                break
                
        if found_concepts:
            context = "Specific Memories:\n" + "\n".join(found_concepts)
            print(f"DEBUG: Total context size: {len(context)} chars")
            return context
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
