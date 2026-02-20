import sys
import os
import yaml
import uvicorn
import requests
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/mnemosyne.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

from core.graph_manager import GraphManager
from core.llm import get_llm_provider
from core.perception import PerceptionModule
from core.attention import AttentionModel
from core.initiative import InitiativeEngine
from core.knowledge_queue import KnowledgeQueue
from workers.learning_worker import LearningWorker

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
    ie = InitiativeEngine(gm, config=config)
    
    # Initialize Background Queue and Worker
    kq = KnowledgeQueue()
    worker = LearningWorker(kq, pm)
    worker.start()
    
    print("✅ Mnemosyne Core & Background Worker Initialized")
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
        limit = config.get("retrieval", {}).get("search_neighbors_limit", 10)
        for n in neighbors[:limit]:
            related.append(f"{n['node']['name']} ({n['rel_type']})")
            
    return {
        "name": node['name'],
        "properties": props,
        "related": related
    }

@app.post("/add")
def add_observation(obs: Observation):
    # 1. Immediate step: Create the observation node
    obs_name = pm.create_observation(obs.content)
    
    # 2. Background step: Enqueue for entity extraction
    job_id = kq.enqueue(obs.content, obs_name)
    
    return {
        "status": "success", 
        "message": "Observation recorded and enqueued for learning",
        "obs_name": obs_name,
        "job_id": job_id
    }

@app.get("/briefing")
def get_briefing():
    # 1. Active Topics
    active_nodes = gm.get_active_nodes(threshold=0.7)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]
    
    # 2. Proactive Context (The Butler)
    proactive_context = ie.get_proactive_context()
    
    # 3. Suggestions
    suggestions = ie.generate_initiatives()
    
    return {
        "hot_topics": hot_topics,
        "butler_log": proactive_context,
        "suggestions": [s['message'] for s in suggestions]
    }

@app.get("/status")
def get_status():
    status = {"neo4j": "unknown", "llm": "unknown", "stats": {}}
    
    # 1. Neo4j Check (Fast)
    try:
        gm.verify_connection()
        stats = gm.get_stats()
        status["neo4j"] = "connected"
        status["stats"] = stats
    except Exception as e:
        status["neo4j"] = f"error: {str(e)}"

    # 2. LLM Check (with Timeout)
    # We use a shortcut to avoid full model loading if possible
    try:
        # If it's Ollama, we check the version/tags first (very fast)
        if hasattr(llm, 'base_url'):
            resp = requests.get(f"{llm.base_url.rstrip('/')}/api/tags", timeout=2)
            if resp.status_code == 200:
                status["llm"] = "connected (Ollama service alive)"
            else:
                status["llm"] = f"error: Ollama returned {resp.status_code}"
        else:
            # For OpenAI or others, we do a very small generation with a tight timeout
            # Note: This might still trigger a model load in Ollama if not caught above
            llm.generate("health check", timeout=3)
            status["llm"] = "connected"
    except requests.exceptions.Timeout:
        status["llm"] = "timeout (service is running but slow/loading model)"
    except Exception as e:
        status["llm"] = f"error: {str(e)}"
        
    return status

    history_limit = config.get("retrieval", {}).get("history_limit", 10)
    query = f"""
    MATCH (n) 
    WHERE n.last_seen IS NOT NULL
    RETURN n.name as name, labels(n)[0] as label, n.last_seen as last_seen
    ORDER BY n.last_seen DESC 
    LIMIT {history_limit}
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
    host = config.get("gateway", {}).get("host", "0.0.0.0")
    port = config.get("gateway", {}).get("port", 4001)
    logger.info(f"Starting Mnemosyne HTTP Gateway on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
