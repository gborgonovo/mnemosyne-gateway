import sys
import os
import yaml
import uvicorn
import logging
import uuid
import re
from contextlib import asynccontextmanager
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
from pydantic import BaseModel, Field
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
    vector_store = VectorStore(db_path=os.path.join(BASE_DIR, "data", "chroma_db"), embedding_config=config.get('llm', {}).get('embeddings'))
    am = AttentionModel(kuzu_mgr, config=config.get('attention', {}))

    from butler.llm import get_llm_provider
    butler_config = config.get('llm', {}).get('butler', {})
    llm = get_llm_provider(butler_config, root_config=config)
    logger.info(f"LLM provider: {llm.get_info()}")

    # File Watcher runs inside the Gateway to hold the exclusive KuzuDB writer lock
    logger.info(f"Starting internal FileWatcher on {KNOWLEDGE_DIR}...")
    event_handler = WikiSyncHandler(kuzu_mgr, vector_store, KNOWLEDGE_DIR, am=am, llm=llm)
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

    from workers.gardener import Gardener
    gd = Gardener(am, config=config, vector_store=vector_store)
    mcp_instance = create_mcp_server(kuzu_mgr, vector_store, am, gd, config, KNOWLEDGE_DIR)
    mcp_app = mcp_instance.streamable_http_app()
    
except Exception as e:
    logger.error(f"❌ Error initializing backend: {e}")
    sys.exit(1)

def get_file_path(name: str):
    safe_name = re.sub(r'[^\w\s-]', '', name).strip()
    return os.path.join(KNOWLEDGE_DIR, f"{safe_name}.md")

def _resolve_write_path(name: str, folder: str = "") -> str:
    """Resolve the markdown path for a NEW node, optionally inside a subfolder.

    Shared by /nodes, /goals and /tasks. If `folder` is set it must already exist
    under KNOWLEDGE_DIR (400 otherwise); without it the node lands in the root.
    """
    safe_name = re.sub(r'[^\w\s-]', '', name).strip()
    if folder:
        target_dir = os.path.join(KNOWLEDGE_DIR, folder)
        if not os.path.isdir(target_dir):
            raise HTTPException(status_code=400, detail=f"Folder '{folder}' does not exist.")
        return os.path.join(target_dir, f"{safe_name}.md")
    return os.path.join(KNOWLEDGE_DIR, f"{safe_name}.md")

def read_markdown(name: str):
    path = get_file_path(name)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

@asynccontextmanager
async def lifespan(app):
    async with mcp_instance.session_manager.run():
        yield

app = FastAPI(title="Mnemosyne File-First API", version="2.0.0", lifespan=lifespan)

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
    name: str = Field(..., description="Stable identifier chosen by the client; reused for upserts.")
    description: str = ""
    deadline: str = Field("", description="Optional, ISO date 'YYYY-MM-DD'. Empty/omitted means no deadline.")
    scope: Optional[str] = Field(None, description="Preferred: a single scope (e.g. 'Private'). Takes precedence over 'scopes'.")
    scopes: str = Field("Private,Public", description="Legacy/compat: comma-separated; only the first scope is used.")
    folder: str = Field("", description="Existing project subfolder under knowledge/.")
    relations: str = Field("", description="Typed edges as 'Target:TYPE,Other:TYPE' (default type RELATED_TO).")

class Task(BaseModel):
    name: str = Field(..., description="Stable identifier chosen by the client; reused for upserts.")
    goal_name: Optional[str] = Field(None, description="If set, recorded as a CONTRIBUTES_TO relation to that goal.")
    description: str = ""
    deadline: str = Field("", description="Optional, ISO date 'YYYY-MM-DD'. Empty/omitted means no deadline.")
    scope: Optional[str] = Field(None, description="Preferred: a single scope (e.g. 'Private'). Takes precedence over 'scopes'.")
    scopes: str = Field("Private,Public", description="Legacy/compat: comma-separated; only the first scope is used.")
    folder: str = Field("", description="Existing project subfolder under knowledge/.")
    relations: str = Field("", description="Typed edges as 'Target:TYPE,Other:TYPE' (default type RELATED_TO).")

class NodeUpsert(BaseModel):
    name: str = Field(..., description="Stable identifier chosen by the client; reused for upserts.")
    content: str
    node_type: str = Field("Node", description="e.g. Node, Reference, Goal, Task, Journal (Journal decays over ~40 days).")
    scope: str = "Private"
    folder: str = Field("", description="Existing project subfolder under knowledge/.")
    relations: str = Field("", description="Typed edges as 'Target:TYPE,Other:TYPE' (default type RELATED_TO).")

class NodeWriteResponse(BaseModel):
    """Canonical response of POST /goals, /tasks, /nodes (R4)."""
    status: str = "success"
    action: str = Field(..., description="'created' or 'updated'.")
    name: str = Field(..., description="Canonical slug actually stored; the client should save and reuse this for upserts.")
    type: str
    scope: str

class DormantItem(BaseModel):
    name: str
    type: str
    days_inactive: int

class BriefingResponse(BaseModel):
    """Response of GET /briefing and GET /briefing/{project} (C2)."""
    hot_topics: List[str] = Field(..., description="Display names of nodes above the activation threshold.")
    dormant: List[DormantItem] = Field(..., description="Cooled-down nodes, with type and days of inactivity.")
    timestamp: str

def _resolve_scope(scope: Optional[str], scopes: str) -> str:
    """Unify the scope vs scopes inconsistency (R6). Prefer the explicit singular
    `scope`; otherwise fall back to the first of the legacy comma-separated
    `scopes`; default Private (never silently Public)."""
    if scope:
        return scope.strip()
    if scopes:
        first = [s.strip() for s in scopes.split(",") if s.strip()]
        if first:
            return first[0]
    return "Private"

def write_markdown(name: str, frontmatter: dict, body: str, folder: str = ""):
    path = _resolve_write_path(name, folder)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
        f.write("---\n\n")
        f.write(body)

def _find_node_file(name: str) -> Optional[str]:
    """Search for a node's markdown file recursively under KNOWLEDGE_DIR."""
    cleaned = name.strip()
    if cleaned.lower().endswith(".md"):
        cleaned = cleaned[:-3]
    base = os.path.abspath(KNOWLEDGE_DIR)
    if "/" in cleaned:
        candidate = os.path.abspath(os.path.join(base, cleaned + ".md"))
        if candidate.startswith(base + os.sep) and os.path.isfile(candidate):
            return candidate
    target = os.path.basename(cleaned).lower()
    for root, dirs, files in os.walk(KNOWLEDGE_DIR):
        for f in files:
            if f.lower() == f"{target}.md":
                return os.path.join(root, f)
    return None

def _parse_relations_str(relations_str: str, source: Optional[str] = None) -> list:
    """Parse 'Target:TYPE,Other:PART_OF' into [{target, type}, ...] for frontmatter.

    If `source` is given (e.g. "user"), it is tagged on each relation so the LLM
    enrichment worker treats them as authoritative and never overwrites them.
    """
    result = []
    for item in relations_str.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            target, rel_type = item.rsplit(":", 1)
            rel = {"target": target.strip(), "type": rel_type.strip().upper()}
        else:
            rel = {"target": item, "type": "RELATED_TO"}
        if source:
            rel["source"] = source
        result.append(rel)
    return result

def _upsert_node_file(name: str, body: str, frontmatter_updates: Dict[str, Any],
                      folder: str = "") -> tuple:
    """Find-or-create a node markdown file, merging frontmatter (upsert by name).

    Locates an existing file anywhere under KNOWLEDGE_DIR (so a second write with
    the same name updates in place instead of duplicating), preserves fields like
    created_at/enriched_at, then applies frontmatter_updates on top. Keys absent
    from frontmatter_updates (e.g. relations when the caller passes none) are left
    untouched. Returns (canonical_name, action) where canonical_name is the slug
    actually written — the value the client should store and reuse for upserts.
    """
    existing_path = _find_node_file(name)
    action = "updated" if existing_path else "created"

    frontmatter: Dict[str, Any] = {}
    if existing_path:
        with open(existing_path, 'r', encoding='utf-8') as f:
            raw = f.read()
        m = re.match(r'^---\n(.*?)\n---\n', raw, re.DOTALL)
        if m:
            frontmatter = yaml.safe_load(m.group(1)) or {}

    frontmatter.update(frontmatter_updates)
    if not existing_path:
        frontmatter.setdefault('created_at', datetime.now().strftime('%Y-%m-%d'))

    path = existing_path or _resolve_write_path(name, folder)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
        f.write("---\n\n")
        f.write(body)

    canonical = os.path.splitext(os.path.basename(path))[0]
    return canonical, action

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
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    neighbors_data = kuzu_mgr.get_neighbors(name, scopes=scope_filter)
    
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
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    node_data = vector_store.get_node(name)
    if not node_data:
        raise HTTPException(status_code=404, detail=f"Node '{name}' not found")
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    neighbors = kuzu_mgr.get_neighbors(name, scopes=scope_filter)
    return {"data": node_data, "neighbors": neighbors}

@app.delete("/nodes/{name}")
def delete_node_api(name: str, scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """Delete a node of ANY type (Node/Goal/Task/Journal/...) by name, in any
    project subfolder (C4). Deletes the markdown file; the watcher then removes
    it from the graph and vectors. The `scopes` query param is accepted for
    compatibility but not used to gate the deletion."""
    # Resolve recursively so nodes created inside a project subfolder are found too
    # (get_file_path only looks in the knowledge/ root).
    path = _find_node_file(name) or get_file_path(name)
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

def _compute_briefing(scope_filter: Optional[List[str]], project: Optional[str] = None) -> dict:
    """Build a briefing (hot topics + dormant nodes), optionally scoped to a project."""
    threshold = config.get("attention", {}).get("activation_threshold", 0.5)

    active_nodes = kuzu_mgr.get_active_nodes(threshold=threshold, scopes=scope_filter, project=project)
    hot_topics = [n for n in active_nodes if not n['name'].startswith("obs_")]

    dormant_cfg = config.get("attention", {}).get("dormant", {})
    dormant_nodes = kuzu_mgr.get_dormant_nodes(
        scopes=scope_filter,
        min_interactions=dormant_cfg.get("min_interactions", 5),
        days_node=dormant_cfg.get("days_node", 27),
        days_goal_task=dormant_cfg.get("days_goal_task", 30),
        days_journal=dormant_cfg.get("days_journal", 45),
        project=project,
    )

    return {
        "hot_topics": [n.get('display_name') or n['name'] for n in hot_topics],
        "dormant": [
            {"name": n.get('display_name') or n['name'], "type": n['node_type'], "days_inactive": n['days_inactive']}
            for n in dormant_nodes
        ],
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/briefing", response_model=BriefingResponse)
def get_briefing(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    return _compute_briefing(scope_filter)

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
        days_journal=dormant_cfg.get("days_journal", 45),
    )

    goals    = [n for n in dormant_nodes if n['node_type'] == 'Goal']
    tasks    = [n for n in dormant_nodes if n['node_type'] == 'Task']
    topics   = [n for n in dormant_nodes if n['node_type'] == 'Node']
    journals = [n for n in dormant_nodes if n['node_type'] == 'Journal']

    forgotten_hubs = kuzu_mgr.get_dormant_by_connectivity(
        min_edges=dormant_cfg.get("hub_min_edges", 2),
        activation_ceiling=dormant_cfg.get("hub_activation_ceiling", 0.3),
        days_inactive=dormant_cfg.get("hub_days_inactive", 14),
        scopes=scope_filter,
    )

    def fmt(nodes):
        return [{"name": n.get('display_name') or n['name'], "type": n['node_type'], "days_inactive": n['days_inactive']} for n in nodes]

    return {
        "timestamp": datetime.now().isoformat(),
        "dormant_goals":    fmt(goals),
        "dormant_tasks":    fmt(tasks),
        "dormant_topics":   fmt(topics),
        "dormant_journals": fmt(journals),
        "forgotten_hubs":   [{"name": n.get('display_name') or n['name'], "type": n['node_type'], "days_inactive": n['days_inactive'], "edge_count": n['edge_count']} for n in forgotten_hubs],
        "summary": (
            f"{len(dormant_nodes)} elementi dormienti: "
            f"{len(goals)} goal, {len(tasks)} task, {len(topics)} topic, {len(journals)} journal. "
            f"{len(forgotten_hubs)} hub dimenticati."
        ),
    }

@app.get("/briefing/{project}", response_model=BriefingResponse)
def get_project_briefing(project: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """Briefing filtered to a single project/folder: hot_topics + dormant nodes of that project."""
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    return _compute_briefing(scope_filter, project=project)
@app.post("/observations")
def add_observation_api(obs: Observation, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    obs_id = f"Obs_{uuid.uuid4().hex[:8]}"
    frontmatter = {"type": "Observation", "scope": obs.scope}
    write_markdown(obs_id, frontmatter, obs.content)
    return {"status": "success", "id": obs_id}

@app.post("/goals", response_model=NodeWriteResponse)
def create_goal_api(goal: Goal, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    scope = _resolve_scope(goal.scope, goal.scopes)
    frontmatter: Dict[str, Any] = {
         "type": "Goal",
         "status": "active",
         "scope": scope,
    }
    if goal.deadline: frontmatter["deadline"] = goal.deadline
    if goal.relations:
        frontmatter["relations"] = _parse_relations_str(goal.relations, source="user")
    body = f"# {goal.name}\n\n{goal.description}"
    canonical, action = _upsert_node_file(goal.name, body, frontmatter, folder=goal.folder)
    return {"status": "success", "action": action, "name": canonical, "type": "Goal", "scope": scope}

@app.post("/tasks", response_model=NodeWriteResponse)
def create_task_api(task: Task, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    scope = _resolve_scope(task.scope, task.scopes)
    frontmatter: Dict[str, Any] = {
         "type": "Task",
         "status": "todo",
         "scope": scope,
    }
    if task.deadline: frontmatter["deadline"] = task.deadline
    # Typed relations from the client; goal_name becomes a CONTRIBUTES_TO edge
    # rather than an implicit LINKED_TO wikilink in the body (R2).
    relations = _parse_relations_str(task.relations, source="user") if task.relations else []
    if task.goal_name:
        relations.append({"target": task.goal_name, "type": "CONTRIBUTES_TO", "source": "user"})
    if relations:
        frontmatter["relations"] = relations
    body = f"# {task.name}\n\n{task.description}"
    canonical, action = _upsert_node_file(task.name, body, frontmatter, folder=task.folder)
    return {"status": "success", "action": action, "name": canonical, "type": "Task", "scope": scope}

@app.post("/nodes", response_model=NodeWriteResponse)
def upsert_node(node: NodeUpsert, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    frontmatter: Dict[str, Any] = {
        "type": node.node_type,
        "scope": node.scope,
    }
    if node.relations:
        frontmatter["relations"] = _parse_relations_str(node.relations, source="user")
    canonical, action = _upsert_node_file(node.name, node.content, frontmatter, folder=node.folder)
    return {"status": "success", "action": action, "name": canonical,
            "type": node.node_type, "scope": node.scope}

# Mount MCP
app.mount("/mcp", mcp_app)

if __name__ == "__main__":
    host = config.get('gateway', {}).get('host', "0.0.0.0")
    port = config.get('gateway', {}).get('port', 4001)
    uvicorn.run(app, host=host, port=port)
