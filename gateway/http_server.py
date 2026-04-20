import sys
import os
import yaml
import uvicorn
import logging
import uuid
import re
from fastapi import FastAPI, HTTPException, Body, BackgroundTasks, UploadFile, File, Header, Depends
from typing import List, Optional, Dict, Any

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore
from core.attention import AttentionModel
from workers.gardener import Gardener
from pydantic import BaseModel

# Configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

# API Keys
API_KEYS_FILE = os.path.join(BASE_DIR, 'config', 'api_keys.yaml')
api_keys = {}
if os.path.exists(API_KEYS_FILE):
    with open(API_KEYS_FILE, 'r') as f:
        api_keys = yaml.safe_load(f) or {}

def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Dict[str, List[str]]:
    if not api_keys: return {"scopes": ["*"], "namespaces": ["*:rw", ":r"]}
    if not x_api_key: raise HTTPException(status_code=401, detail="X-API-Key header missing")
    if x_api_key not in api_keys: raise HTTPException(status_code=403, detail="Invalid API Key")
    key_config = api_keys[x_api_key]
    scopes = key_config if isinstance(key_config, list) else key_config.get("scopes", ["Public"])
    return {"scopes": scopes}

def intersect_scopes(requested: str, allowed: List[str]) -> List[str]:
    if not requested: return allowed
    requested_list = requested.split(",")
    if "*" in allowed: return requested_list
    return list(set(requested_list) & set(allowed))

# Initialize Core
try:
    kuzu_mgr = KuzuManager(db_path=os.path.join(BASE_DIR, "data", "kuzu_db"))
    vector_store = VectorStore(db_path=os.path.join(BASE_DIR, "data", "chroma_db"))
    am = AttentionModel(kuzu_mgr, config=config.get('attention', {}))
    logger.info("✅ Hybrid File-First Backend Initialized")
except Exception as e:
    logger.error(f"❌ Error initializing backend: {e}")
    sys.exit(1)

def get_file_path(name: str):
    safe_name = re.sub(r'[^\w\s-]', '', name).strip()
    return os.path.join(KNOWLEDGE_DIR, f"{safe_name}.md")

def read_markdown(name: str):
    path = get_file_path(name)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

app = FastAPI(title="Mnemosyne File-First API", version="2.0.0")

class Observation(BaseModel):
    content: str

@app.get("/")
def health_check():
    return {"status": "ok", "service": "mnemosyne-gateway", "architecture": "file-first"}

@app.get("/search")
def search(q: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    
    # 1. Semantic Search in Chroma
    results = vector_store.semantic_search(q, scopes=actual_scopes if '*' not in actual_scopes else None, limit=1)
    
    if not results:
        raise HTTPException(status_code=404, detail=f"Concept '{q}' not found.")
        
    best_match = results[0]
    name = best_match['name']
    
    # 2. Thermal stimulus and fetch neighbors from Kuzu
    am.stimulate([name], boost_amount=1.0)
    neighbors_data = kuzu_mgr.get_neighbors(name)
    
    related = []
    for n in neighbors_data[:15]:
        related.append({
            "name": n['node_name'],
            "rel": n['rel_type']
        })
        
    return {
        "name": name,
        "type": best_match['metadata'].get('type', 'Node'),
        "properties": best_match['metadata'],
        "related": related,
        "document": best_match['document']
    }

@app.get("/nodes/{name}")
def get_node(name: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    node_data = vector_store.get_node(name)
    if not node_data:
        raise HTTPException(status_code=404, detail=f"Node '{name}' not found")
        
    return {"data": node_data}

@app.delete("/nodes/{name}")
def delete_node_api(name: str, scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    path = get_file_path(name)
    if os.path.exists(path):
        os.remove(path)
        return {"status": "success", "message": f"Node '{name}' deleted"}
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/graph/stats")
def get_graph_stats():
    return {
         "status": "success", 
         "data": {
             "chroma_nodes": len(vector_store.list_nodes()), 
             "kuzu_active": len(kuzu_mgr.get_active_nodes(0.0))
        }
    }

@app.get("/briefing")
def get_briefing():
    active_nodes = kuzu_mgr.get_active_nodes(threshold=0.6)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]
    return {
        "hot_topics": hot_topics,
        "suggestions": ["System operates in file-first mode. Edit .md directly!"]
    }
