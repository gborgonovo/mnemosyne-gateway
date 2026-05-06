import sys
import os
import yaml
import uvicorn
import logging
import uuid
import re
from fastapi import FastAPI, HTTPException, Body, BackgroundTasks, UploadFile, File, Header, Depends
from datetime import datetime
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
from workers.file_watcher import WikiSyncHandler
from watchdog.observers import Observer
from pydantic import BaseModel
from gateway.mcp_app import create_mcp_server
from fastapi.middleware.cors import CORSMiddleware

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
    kuzu_mgr = KuzuManager(db_path=os.path.join(BASE_DIR, "data", "kuzu_main"))
    vector_store = VectorStore(db_path=os.path.join(BASE_DIR, "data", "chroma_db"))
    am = AttentionModel(kuzu_mgr, config=config.get('attention', {}))
    
    # File Watcher runs inside the Gateway to hold the exclusive KuzuDB writer lock
    logger.info(f"Starting internal FileWatcher on {KNOWLEDGE_DIR}...")
    event_handler = WikiSyncHandler(kuzu_mgr, vector_store, KNOWLEDGE_DIR, am=am)
    # Cold boot: sync all existing files without triggering activation boosts
    import os as _os
    for _root, _dirs, _files in _os.walk(KNOWLEDGE_DIR):
        for _fname in _files:
            if _fname.endswith('.md'):
                event_handler._sync_file(_os.path.join(_root, _fname), is_startup_sync=True)
    observer = Observer()
    observer.schedule(event_handler, KNOWLEDGE_DIR, recursive=True)
    observer.start()
    
    logger.info("✅ Hybrid File-First Backend Initialized (with internal watcher)")

    # Mount MCP SSE app
    from workers.gardener import Gardener
    gd = Gardener(am, config=config, vector_store=vector_store)
    mcp_instance = create_mcp_server(kuzu_mgr, vector_store, am, gd, config, KNOWLEDGE_DIR)
    mcp_app = mcp_instance.sse_app()
    
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

# 🌍 CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Observation(BaseModel):
    content: str
    scope: str = "Public"

class Goal(BaseModel):
    name: str
    description: str = ""
    deadline: str = ""
    scopes: str = "Private,Public"

class Task(BaseModel):
    name: str
    goal_name: str
    description: str = ""
    due_date: str = ""
    scopes: str = "Private,Public"

def write_markdown(name: str, frontmatter: dict, body: str):
    path = get_file_path(name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
        f.write("---\n\n")
        f.write(body)

@app.get("/")
@app.get("/status")
def health_check():
    return {
        "status": "ok", 
        "service": "mnemosyne-gateway", 
        "architecture": "file-first",
        "timestamp": datetime.now().isoformat()
    }

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
    am.record_interaction(name, interaction_type="mcp_query")
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
def get_briefing(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    threshold = config.get("attention", {}).get("activation_threshold", 0.5)

    active_nodes = kuzu_mgr.get_active_nodes(threshold=threshold, scopes=scope_filter)
    hot_topics = [n for n in active_nodes if not n['name'].startswith("obs_")]

    dormant_cfg = config.get("attention", {}).get("dormant", {})
    dormant_nodes = kuzu_mgr.get_dormant_nodes(
        scopes=scope_filter,
        min_interactions=dormant_cfg.get("min_interactions", 5),
        days_node=dormant_cfg.get("days_node", 27),
        days_goal_task=dormant_cfg.get("days_goal_task", 30),
    )

    return {
        "hot_topics": [n['name'] for n in hot_topics],
        "dormant": [
            {"name": n['name'], "type": n['node_type'], "days_inactive": n['days_inactive']}
            for n in dormant_nodes
        ],
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/briefing/longitudinal")
def get_longitudinal_briefing(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None

    dormant_cfg = config.get("attention", {}).get("dormant", {})
    dormant_nodes = kuzu_mgr.get_dormant_nodes(
        scopes=scope_filter,
        min_interactions=dormant_cfg.get("min_interactions", 5),
        days_node=dormant_cfg.get("days_node", 27),
        days_goal_task=dormant_cfg.get("days_goal_task", 30),
    )

    goals  = [n for n in dormant_nodes if n['node_type'] == 'Goal']
    tasks  = [n for n in dormant_nodes if n['node_type'] == 'Task']
    topics = [n for n in dormant_nodes if n['node_type'] == 'Node']

    return {
        "timestamp": datetime.now().isoformat(),
        "dormant_goals":  goals,
        "dormant_tasks":  tasks,
        "dormant_topics": topics,
        "summary": (
            f"{len(dormant_nodes)} elementi dormienti: "
            f"{len(goals)} goal, {len(tasks)} task, {len(topics)} topic."
        ),
    }
@app.post("/observations")
def add_observation_api(obs: Observation, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    obs_id = f"Obs_{uuid.uuid4().hex[:8]}"
    frontmatter = {"type": "Observation", "scope": obs.scope}
    write_markdown(obs_id, frontmatter, obs.content)
    return {"status": "success", "id": obs_id}

@app.post("/goals")
def create_goal_api(goal: Goal, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    scope_list = [s.strip() for s in goal.scopes.split(",")] if goal.scopes else ["Private"]
    frontmatter = {
         "type": "Goal",
         "status": "active",
         "scope": scope_list[0]
    }
    if goal.deadline: frontmatter["deadline"] = goal.deadline
    body = f"# {goal.name}\n\n{goal.description}"
    write_markdown(goal.name, frontmatter, body)
    return {"status": "success", "name": goal.name}

@app.post("/tasks")
def create_task_api(task: Task, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    scope_list = [s.strip() for s in task.scopes.split(",")] if task.scopes else ["Private"]
    frontmatter = {
         "type": "Task",
         "status": "todo",
         "scope": scope_list[0]
    }
    if task.due_date: frontmatter["due_date"] = task.due_date
    body = f"# {task.name}\n\n**Linked Goal:** [[{task.goal_name}]]\n\n{task.description}"
    write_markdown(task.name, frontmatter, body)
    return {"status": "success", "name": task.name}

# Mount MCP
app.mount("/mcp", mcp_app)

if __name__ == "__main__":
    host = config.get('gateway', {}).get('host', "0.0.0.0")
    port = config.get('gateway', {}).get('port', 4001)
    uvicorn.run(app, host=host, port=port)
