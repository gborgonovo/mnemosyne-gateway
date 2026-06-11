import httpx
import json
import sys
import os
from mcp.server.fastmcp import FastMCP

# Configurazione Remota e Percorsi
BASE_URL = "https://memory.borgonovo.org"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(SCRIPT_DIR, ".env")

def load_dotenv_manually(path):
    """Carica un file .env senza dipendenze esterne."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Prova a caricare da .env se presente
load_dotenv_manually(DOTENV_PATH)

# Risoluzione della chiave API
API_KEY = os.environ.get("MNEMOSYNE_API_KEY") or os.environ.get("API_KEY")

if not API_KEY:
    print(
        "❌ ERRORE: Chiave API di Mnemosyne non trovata!\n"
        "Per far funzionare l'integrazione, configura la variabile d'ambiente 'MNEMOSYNE_API_KEY'\n"
        f"oppure crea un file '.env' in {SCRIPT_DIR} contenente:\n"
        "MNEMOSYNE_API_KEY=tua_chiave_api_qui",
        file=sys.stderr
    )
    sys.exit(1)

# Inizializzazione FastMCP
mcp = FastMCP("Mnemosyne-Remote")

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

@mcp.tool()
async def query_knowledge(query: str, limit: int = 3) -> str:
    """Ricerca semantica con reranking termico nella memoria Mnemosyne remota."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/search", params={"q": query}, headers=headers)
            if response.status_code == 200:
                data = response.json()
                res = f"### FILE: {data['name']}.md (Tipo: {data.get('type', 'Node')})\n"
                res += f"```markdown\n{data['document']}\n```\n"
                if data.get("related"):
                    related_names = [r['name'] if isinstance(r, dict) else r for r in data['related']]
                    res += f"\nConnessioni correlate: {', '.join(related_names)}"
                return res
            elif response.status_code == 404:
                return f"Nessun concetto trovato corrispondente a '{query}'."
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def add_observation(content: str, scope: str = "Public") -> str:
    """Aggiunge una nuova osservazione (fleeting note) alla memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/observations", 
                json={"content": content, "scope": scope}, 
                headers=headers
            )
            if response.status_code == 200:
                return f"Osservazione registrata con successo con ID: {response.json()['id']}"
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def get_memory_briefing() -> str:
    """Ottiene i topic caldi (attivi) e gli elementi dormienti dalla memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/briefing", headers=headers)
            if response.status_code == 200:
                data = response.json()
                topics = data.get("hot_topics", [])
                dormant = data.get("dormant", [])
                
                res = "### Topic Attivi (Hot Nodes):\n"
                if topics:
                    res += "\n".join(f"- {t}" for t in topics)
                else:
                    res += "Nessun topic caldo attivo al momento.\n"
                    
                if dormant:
                    res += "\n\n### Elementi Dormienti (da riattivare):\n"
                    res += "\n".join(f"- {d['name']} ({d['type']}, inattivo da {d['days_inactive']} giorni)" for d in dormant[:10])
                return res
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def get_longitudinal_briefing() -> str:
    """Ottiene un briefing a lungo termine (goal, task e topic dormienti, hub dimenticati) dalla memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/briefing/longitudinal", headers=headers)
            if response.status_code == 200:
                data = response.json()
                summary = data.get("summary", "")
                goals = data.get("dormant_goals", [])
                tasks = data.get("dormant_tasks", [])
                topics = data.get("dormant_topics", [])
                hubs = data.get("forgotten_hubs", [])
                
                res = "### Briefing Longitudinale (Manutenzione Memoria)\n"
                res += f"**Sintesi**: {summary}\n\n"
                
                if goals:
                    res += "**Goal Dormienti**:\n"
                    res += "\n".join(f"- {g['name']} (inattivo da {g['days_inactive']} giorni)" for g in goals) + "\n\n"
                    
                if tasks:
                    res += "**Task Dormienti**:\n"
                    res += "\n".join(f"- {t['name']} (inattivo da {t['days_inactive']} giorni)" for t in tasks) + "\n\n"
                    
                if topics:
                    res += "**Topic Dormienti**:\n"
                    res += "\n".join(f"- {t['name']} (inattivo da {t['days_inactive']} giorni)" for t in topics) + "\n\n"
                    
                if hubs:
                    res += "**Hub Dimenticati (connessioni inattive)**:\n"
                    res += "\n".join(f"- {h['name']} (tipo: {h['type']}, {h['edge_count']} connessioni, inattivo da {h['days_inactive']} giorni)" for h in hubs) + "\n"
                    
                return res
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def create_goal(name: str, description: str = "", deadline: str = "", scopes: str = "Private,Public") -> str:
    """Crea un nuovo obiettivo strategico (Goal) nella memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "name": name,
                "description": description,
                "deadline": deadline,
                "scopes": scopes
            }
            response = await client.post(f"{BASE_URL}/goals", json=payload, headers=headers)
            if response.status_code == 200:
                return f"Goal '{name}' creato con successo."
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def create_task(name: str, goal_name: str, description: str = "", deadline: str = "", scopes: str = "Private,Public") -> str:
    """Crea un nuovo task azionabile collegato a un Goal nella memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "name": name,
                "goal_name": goal_name,
                "description": description,
                "deadline": deadline,
                "scopes": scopes
            }
            response = await client.post(f"{BASE_URL}/tasks", json=payload, headers=headers)
            if response.status_code == 200:
                return f"Task '{name}' creato e collegato a '{goal_name}' con successo."
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def get_node_details(name: str) -> str:
    """Ottiene i dettagli e le connessioni di un nodo specifico della memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/nodes/{name}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                node_data = data.get("data", {})
                neighbors = data.get("neighbors", [])
                
                res = f"### Dettagli del Nodo: {name}\n"
                res += f"**Tipo**: {node_data.get('metadata', {}).get('type', 'Node')}\n"
                res += f"**Ambito**: {node_data.get('metadata', {}).get('scope', 'Public')}\n"
                if node_data.get('document'):
                    res += f"\n**Contenuto**:\n{node_data['document']}\n"
                
                if neighbors:
                    res += "\n**Connessioni nel Grafo**:\n"
                    for n in neighbors:
                        res += f"- {n['node_name']} ({n['rel_type']})\n"
                return res
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def delete_knowledge_node(name: str) -> str:
    """Rimuove un nodo di conoscenza (elimina il file associato) nella memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(f"{BASE_URL}/nodes/{name}", headers=headers)
            if response.status_code == 200:
                return f"Nodo '{name}' rimosso con successo."
            return f"Errore: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Errore di connessione: {e}"

@mcp.tool()
async def get_system_status() -> str:
    """Verifica lo stato complessivo del sistema e le statistiche dei database di memoria remota."""
    async with httpx.AsyncClient() as client:
        try:
            # 1. Statistiche grafo
            stats_str = ""
            try:
                stats_resp = await client.get(f"{BASE_URL}/graph/stats", headers=headers)
                if stats_resp.status_code == 200:
                    g_data = stats_resp.json().get("data", {})
                    stats_str = f"- Nodi semantici (ChromaDB): {g_data.get('chroma_nodes', 0)}\n- Nodi attivi (KùzuDB): {g_data.get('kuzu_active', 0)}"
                else:
                    stats_str = f"Impossibile recuperare statistiche (Codice: {stats_resp.status_code})"
            except Exception as ex:
                stats_str = f"Errore nel recupero statistiche: {ex}"

            # 2. Status generale
            status_str = ""
            try:
                status_resp = await client.get(f"{BASE_URL}/status")
                if status_resp.status_code == 200:
                    s_data = status_resp.json()
                    status_str = f"- Servizio: {s_data.get('service')}\n- Architettura: {s_data.get('architecture')}\n- Stato: {s_data.get('status')}"
                else:
                    status_str = f"Impossibile verificare status generale (Codice: {status_resp.status_code})"
            except Exception as ex:
                status_str = f"Errore nel controllo status: {ex}"

            return f"### Stato di Mnemosyne Remoto\n{status_str}\n\n### Statistiche Grafo\n{stats_str}"
        except Exception as e:
            return f"Errore generale: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
