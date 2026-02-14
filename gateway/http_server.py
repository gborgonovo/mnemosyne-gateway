import sys
import os
import yaml
import uvicorn
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph_manager import GraphManager
from core.llm import get_llm_provider
from core.perception import PerceptionModule
from core.attention import AttentionModel
from core.initiative import InitiativeEngine

# Load Configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Initialize Core Components
try:
    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )
    llm = get_llm_provider(config)
    am = AttentionModel(gm, config=config.get('attention', {}))
    pm = PerceptionModule(gm, llm, am)
    ie = InitiativeEngine(gm, config=config.get('initiative', {}))
    print("✅ Mnemosyne Core Initialized")
except Exception as e:
    print(f"❌ Error initializing Mnemosyne: {e}", file=sys.stderr)
    sys.exit(1)

app = FastAPI(title="Mnemosyne HTTP Bridge", version="1.0.0")

class Observation(BaseModel):
    content: str
    
class SearchResponse(BaseModel):
    name: str
    properties: Dict[str, Any]
    related: List[str]

@app.get("/")
def health_check():
    return {"status": "ok", "service": "mnemosyne-gateway"}

@app.get("/search")
def search(q: str):
    node = gm.get_node(q)
    if not node:
        raise HTTPException(status_code=404, detail=f"Concept '{q}' not found.")
    
    props = {k: v for k, v in dict(node).items() if k not in ['name', 'labels']}
    
    neighbors = gm.get_neighbors(q)
    related = []
    if neighbors:
        for n in neighbors[:10]:
            related.append(f"{n['node']['name']} ({n['rel_type']})")
            
    return {
        "name": node['name'],
        "properties": props,
        "related": related
    }

@app.post("/add")
def add_observation(obs: Observation):
    entities = pm.process_input(obs.content)
    return {
        "status": "success", 
        "message": "Observation recorded",
        "extracted_entities": entities or []
    }

@app.get("/briefing")
def get_briefing():
    # 1. Active Topics
    active_nodes = gm.get_active_nodes(threshold=0.7)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]
    
    # 2. Proactive Context (Alfred)
    proactive_context = ie.get_proactive_context()
    
    # 3. Suggestions
    suggestions = ie.generate_initiatives()
    
    return {
        "hot_topics": hot_topics,
        "alfred_log": proactive_context,
        "suggestions": [s['message'] for s in suggestions]
    }

@app.get("/status")
def get_status():
    status = {"neo4j": "unknown", "llm": "unknown", "stats": {}}
    
    # Neo4j Check
    try:
        gm.verify_connection()
        stats = gm.get_stats()
        status["neo4j"] = "connected"
        status["stats"] = stats
    except Exception as e:
        status["neo4j"] = f"error: {str(e)}"

    # LLM Check
    try:
        llm.generate("test")
        status["llm"] = "connected"
    except Exception as e:
        status["llm"] = f"error: {str(e)}"
        
    return status

@app.get("/history")
def get_history():
    query = """
    MATCH (n) 
    WHERE n.last_seen IS NOT NULL
    RETURN n.name as name, labels(n)[0] as label, n.last_seen as last_seen
    ORDER BY n.last_seen DESC 
    LIMIT 10
    """
    history = []
    try:
        with gm.driver.session() as session:
            result = session.run(query)
            for record in result:
                history.append({
                    "name": record["name"],
                    "label": record["label"],
                    "timestamp": record["last_seen"]
                })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"history": history}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
