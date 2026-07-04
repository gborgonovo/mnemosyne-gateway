import sys
import os
import yaml
import uvicorn
import logging
import uuid
import re
import threading
import time
import random

_GATEWAY_START = time.time()


def _weighted_sample(items: list, k: int, weight_key: str = "edge_count") -> list:
    """Pick up to k items without replacement, weighted by weight_key.

    Used to resurface "forgotten hubs" one at a time on rotation: the more
    connected a node, the more often it surfaces, but a different one each
    briefing — so we never flood the mail with the same top hub every day.
    """
    pool = list(items)
    chosen = []
    while pool and len(chosen) < k:
        weights = [max(it.get(weight_key, 1) or 1, 1) for it in pool]
        pick = random.choices(pool, weights=weights, k=1)[0]
        chosen.append(pick)
        pool.remove(pick)
    return chosen
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
from core.attention import AttentionModel, thermal_rerank
from core.utils import node_id_from_path, readable_name as _readable_name, atomic_write, render_markdown
from core.authz import (validate_api_keys, format_validation_error, normalize_key_config,
                        territory_allows, filter_by_read)
from core import node_service
from butler.initiative import InitiativeEngine
from workers.gardener import Gardener
from workers.file_watcher import WikiSyncHandler, _is_indexable_md
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

RETRIEVAL_CFG = config.get('retrieval', {})
RERANK_ALPHA = float(RETRIEVAL_CFG.get('rerank_alpha', 0.0))
CHROMA_PREFETCH = int(RETRIEVAL_CFG.get('chroma_prefetch', 10))

# Fail-closed auth: in production (auth_required: true) refuse to start rather
# than serve open access or silently apply a permissive default. Two guards:
#   1. no keys at all → refuse (api_keys.yaml missing/empty).
#   2. any key under-specified (old list form, or missing read/write) → refuse
#      with an EXPLICIT, per-key message (never a silent exit).
GATEWAY_CFG = config.get('gateway', {})
AUTH_REQUIRED = GATEWAY_CFG.get('auth_required', False)
if AUTH_REQUIRED:
    if not api_keys:
        logger.error(
            "auth_required is true but no API keys are configured "
            "(config/api_keys.yaml missing or empty). Refusing to start with open access."
        )
        sys.exit(1)
    _key_problems = validate_api_keys(api_keys)
    if _key_problems:
        logger.error("\n" + format_validation_error(_key_problems))
        sys.exit(1)

# Pre-resolve every key to normalized grants {scopes, read, write} once, for
# O(1) lookup per request. Lenient (missing territory -> "*") only in dev
# (auth_required false); strict fail-closed default ([]) in production.
API_GRANTS = {k: normalize_key_config(v, lenient=not AUTH_REQUIRED) for k, v in api_keys.items()}

def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not api_keys: return {"scopes": ["*"], "read": ["*"], "write": ["*"]}
    if not x_api_key: raise HTTPException(status_code=401, detail="X-API-Key header missing")
    if x_api_key not in api_keys: raise HTTPException(status_code=403, detail="Invalid API Key")
    return API_GRANTS[x_api_key]

def intersect_scopes(requested: str, allowed: List[str]) -> List[str]:
    if not requested: return allowed
    requested_list = requested.split(",")
    if "*" in allowed: return requested_list
    return list(set(requested_list) & set(allowed))

def _assert_write_scope(scope: str, api_auth: dict):
    """Raise 403 if the API key is not allowed to write nodes of the given scope."""
    allowed = api_auth["scopes"]
    if "*" in allowed:
        return
    if scope not in allowed:
        raise HTTPException(status_code=403, detail=f"Key not permitted to write scope '{scope}'")

def _assert_write(scope: str, node_id: str, api_auth: dict):
    """Raise 403 unless the key may write BOTH this scope AND this node's territory.

    The two authorization axes are enforced in AND: confidentiality (scope) and
    namespace (folder territory). A key confined to write ['Ganaghello'] cannot
    write a Private node elsewhere even if it holds the Private scope.
    """
    _assert_write_scope(scope, api_auth)
    if not territory_allows(api_auth.get("write", []), node_id):
        raise HTTPException(
            status_code=403,
            detail=f"Key not permitted to write in the territory of '{node_id}'",
        )

def _read_grants(api_auth: dict):
    """Read-territory grants for filtering, or None when unrestricted ('*')."""
    grants = api_auth.get("read", ["*"])
    return None if "*" in grants else grants

def _target_node_id(name: str, folder: str = "") -> str:
    """Path-based node_id a write to (name, folder) will land on, for territory
    authz before anything is written. Invalid folder → HTTP 400."""
    try:
        return node_service.target_node_id(KNOWLEDGE_DIR, name, folder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Initialize Core
try:
    # Optional override: database.kuzu_buffer_pool_mb in settings.yaml. Absent →
    # KuzuManager's 512 MB default (prevents the ~80%-of-RAM default buffer pool).
    _kuzu_pool_mb = config.get('database', {}).get('kuzu_buffer_pool_mb')
    _kuzu_pool_bytes = int(_kuzu_pool_mb) * 1024 * 1024 if _kuzu_pool_mb else None
    kuzu_mgr = KuzuManager(db_path=os.path.join(BASE_DIR, "data", "kuzu_main"),
                           buffer_pool_size=_kuzu_pool_bytes)
    vector_store = VectorStore(db_path=os.path.join(BASE_DIR, "data", "chroma_db"), embedding_config=config.get('llm', {}).get('embeddings'))
    am = AttentionModel(kuzu_mgr, config=config.get('attention', {}))

    from butler.llm import get_llm_provider
    butler_config = config.get('llm', {}).get('butler', {})
    llm = get_llm_provider(butler_config, root_config=config)
    logger.info(f"LLM provider: {llm.get_info()}")

    # File Watcher runs inside the Gateway to hold the exclusive KuzuDB writer lock
    logger.info(f"Starting internal FileWatcher on {KNOWLEDGE_DIR}...")
    event_handler = WikiSyncHandler(kuzu_mgr, vector_store, KNOWLEDGE_DIR, am=am, llm=llm)
    # Cold boot: pass 1 builds the basename index, pass 2 syncs all files
    event_handler._build_basename_index()
    import os as _os
    for _root, _dirs, _files in _os.walk(KNOWLEDGE_DIR):
        for _fname in _files:
            if _is_indexable_md(_fname):
                event_handler._sync_file(_os.path.join(_root, _fname), is_startup_sync=True)
    observer = Observer()
    observer.schedule(event_handler, KNOWLEDGE_DIR, recursive=True)
    observer.start()
    
    logger.info("✅ Hybrid File-First Backend Initialized (with internal watcher)")

    from workers.gardener import Gardener
    gd = Gardener(am, config=config, vector_store=vector_store)
    mcp_instance = create_mcp_server(kuzu_mgr, vector_store, am, gd, config, KNOWLEDGE_DIR)
    mcp_app = mcp_instance.streamable_http_app()

    # Gardener background thread: runs run_once() every interval_seconds (default 3600)
    _gardener_interval = config.get("gardener", {}).get("interval_seconds", 3600)
    def _gardener_loop():
        time.sleep(_gardener_interval)  # first cycle after one interval, not on startup
        while True:
            try:
                gd.run_once()
            except Exception as _e:
                logger.error(f"Gardener cycle error: {_e}")
            time.sleep(_gardener_interval)
    threading.Thread(target=_gardener_loop, daemon=True, name="gardener").start()
    logger.info(f"Gardener thread started (interval: {_gardener_interval}s)")
    
except Exception as e:
    logger.error(f"❌ Error initializing backend: {e}")
    sys.exit(1)

def get_file_path(name: str):
    return node_service.resolve_write_path(KNOWLEDGE_DIR, name)

def _resolve_write_path(name: str, folder: str = "") -> str:
    """Resolve the markdown path for a NEW node, optionally inside a subfolder.
    Invalid folder (traversal or non-existent) → HTTP 400."""
    try:
        return node_service.resolve_write_path(KNOWLEDGE_DIR, name, folder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@asynccontextmanager
async def lifespan(app):
    async with mcp_instance.session_manager.run():
        try:
            yield
        finally:
            # Clean shutdown: checkpoint + close KuzuDB so SIGTERM (systemctl
            # stop|restart) never leaves a bloated WAL for the next boot to
            # replay into a "buffer pool is full" OOM loop.
            try:
                kuzu_mgr.close()
            except Exception as _e:
                logger.warning(f"KuzuDB close on shutdown failed: {_e}")

app = FastAPI(title="Mnemosyne File-First API", version="2.0.0", lifespan=lifespan)

# 🌍 CORS Configuration
# Origins come from settings.yaml. The wildcard "*" with credentials is invalid
# per the CORS spec (browsers reject it), so credentials are enabled only when
# the origin list is explicit.
CORS_ORIGINS = GATEWAY_CFG.get('cors_origins', ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials="*" not in CORS_ORIGINS,
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
    status: Optional[str] = Field(None, description="e.g. 'active', 'done'. Omit to leave unchanged on update (defaults to 'active' on creation only).")
    scope: Optional[str] = Field(None, description="Preferred: a single scope (e.g. 'Private'). Takes precedence over 'scopes'.")
    scopes: str = Field("Private,Public", description="Legacy/compat: comma-separated; only the first scope is used.")
    folder: str = Field("", description="Existing project subfolder under knowledge/.")
    relations: str = Field("", description="Typed edges as 'Target:TYPE,Other:TYPE' (default type RELATED_TO).")

class Task(BaseModel):
    name: str = Field(..., description="Stable identifier chosen by the client; reused for upserts.")
    goal_name: Optional[str] = Field(None, description="If set, recorded as a CONTRIBUTES_TO relation to that goal.")
    description: str = ""
    deadline: str = Field("", description="Optional, ISO date 'YYYY-MM-DD'. Empty/omitted means no deadline.")
    status: Optional[str] = Field(None, description="e.g. 'todo', 'in_progress', 'done'. Omit to leave unchanged on update (defaults to 'todo' on creation only).")
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

class HotItem(BaseModel):
    name: str
    type: str
    status: Optional[str] = None
    preview: Optional[str] = None

class BriefingResponse(BaseModel):
    """Response of GET /briefing and GET /briefing/{project} (C2)."""
    hot_topics: List[str] = Field(..., description="Display names of nodes above the activation threshold.")
    hot_details: List[HotItem] = Field(default_factory=list, description="Hot nodes with type, status and a body preview, so consumers can tell todo from done.")
    dormant: List[DormantItem] = Field(..., description="Cooled-down nodes, with type and days of inactivity.")
    timestamp: str

def _resolve_scope(scope: Optional[str], scopes: str) -> str:
    return node_service.resolve_scope(scope, scopes)

def write_markdown(name: str, frontmatter: dict, body: str, folder: str = ""):
    # Simple create-only write (Observations): no frontmatter merge, no created_at.
    path = _resolve_write_path(name, folder)
    atomic_write(path, render_markdown(frontmatter, body))

def _find_node_file(name: str) -> Optional[str]:
    return node_service.find_node_file(KNOWLEDGE_DIR, name)

def _parse_relations_str(relations_str: str, source: Optional[str] = None) -> list:
    """Parse 'Target:TYPE,Other:PART_OF' into [{target, type}, ...] for frontmatter.

    If `source` is given (e.g. "user"), it is tagged on each relation so the LLM
    enrichment worker treats them as authoritative and never overwrites them.
    """
    return node_service.parse_relations(relations_str, source)

def _upsert_node_file(name: str, body: str, frontmatter_updates: Dict[str, Any],
                      folder: str = "", defaults: Optional[Dict[str, Any]] = None) -> tuple:
    """Upsert a node markdown file by name (merge frontmatter). Invalid folder for
    a new node → HTTP 400. See core.node_service.upsert for the full semantics."""
    try:
        return node_service.upsert(KNOWLEDGE_DIR, name, body, frontmatter_updates,
                                   folder=folder, defaults=defaults)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
@app.get("/status")
def health_check():
    graph = kuzu_mgr.get_stats()
    knowledge_files = sum(
        1 for _, _, files in os.walk(KNOWLEDGE_DIR) for f in files if f.endswith(".md")
    )
    return {
        "status": "ok",
        "service": "mnemosyne-gateway",
        "architecture": "file-first",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": round(time.time() - _GATEWAY_START),
        "knowledge": {
            "files": knowledge_files,
            "nodes_kuzu": graph["nodes"],
            "edges_kuzu": graph["edges"],
            "nodes_by_type": graph["by_type"],
            "docs_chroma": vector_store.collection.count(),
        },
        "workers": {
            "enrich_queue_depth": event_handler._enrich_queue.qsize(),
            "gardener_last_run": gd.last_run,
            "gardener_interval_s": gd.interval,
            "basename_collisions": len(event_handler.collisions),
        },
    }

@app.get("/search")
def search(q: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    read_grants = _read_grants(api_auth)

    # 1. Fetch candidates from Chroma, drop those outside the read territory,
    #    then apply thermal re-rank.
    candidates = vector_store.semantic_search(q, scopes=scope_filter, limit=CHROMA_PREFETCH)
    candidates = filter_by_read(candidates, read_grants, "node_id")
    if not candidates:
        raise HTTPException(status_code=404, detail=f"Concept '{q}' not found.")

    reranked = thermal_rerank(candidates, kuzu_mgr, alpha=RERANK_ALPHA)
    best = reranked[0]
    display_name = best['name']
    node_id = best.get('node_id', best['name'])

    # 2. Thermal stimulus and fetch neighbors from Kuzu (use path-based ID),
    #    filtered to the read territory so we never surface off-limits links.
    am.record_interaction(node_id, interaction_type="mcp_query")
    neighbors_data = kuzu_mgr.get_neighbors(node_id, scopes=scope_filter)
    neighbors_data = filter_by_read(neighbors_data, read_grants, "node_name")

    related = [{"name": n['node_name'], "rel": n['rel_type']} for n in neighbors_data[:15]]

    return {
        "name": display_name,
        "node_id": node_id,
        "type": best['metadata'].get('type', 'Node'),
        "score": best['score'],
        "properties": best['metadata'],
        "related": related,
        "document": best['document'],
    }

@app.get("/nodes/{name}")
def get_node(name: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    read_grants = _read_grants(api_auth)
    # Try direct lookup (works for path-based IDs); fall back to basename resolution
    node_data = vector_store.get_node(name)
    if not node_data:
        path = _find_node_file(name)
        if path:
            resolved_id, _ = node_id_from_path(path, KNOWLEDGE_DIR)
            node_data = vector_store.get_node(resolved_id)
            name = resolved_id
    if not node_data:
        raise HTTPException(status_code=404, detail=f"Node '{name}' not found")
    resolved_id = node_data.get("name", name)
    # Territory check: a node outside the read grant is reported as not found
    # (404 rather than 403) so its existence isn't leaked to a confined key.
    if read_grants and not territory_allows(read_grants, resolved_id):
        raise HTTPException(status_code=404, detail=f"Node '{name}' not found")
    neighbors = kuzu_mgr.get_neighbors(resolved_id, scopes=scope_filter)
    neighbors = filter_by_read(neighbors, read_grants, "node_name")
    return {"data": node_data, "neighbors": neighbors}

@app.delete("/nodes/{name}")
def delete_node_api(name: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """Delete a node of ANY type (Node/Goal/Task/Journal/...) by name, in any
    project subfolder. Deletes the markdown file; the watcher then removes it
    from the graph and vectors. The key must have write permission for the
    node's actual scope (read from frontmatter before deletion)."""
    path = _find_node_file(name) or get_file_path(name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    node_scope = "Private"  # fail-safe: unknown scope treated as most restrictive
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = f.read()
        m = re.match(r'^---\n(.*?)\n---\n', raw, re.DOTALL)
        if m:
            fm = yaml.safe_load(m.group(1)) or {}
            node_scope = fm.get("scope", "Private")
    except Exception:
        pass
    del_node_id, _ = node_id_from_path(path, KNOWLEDGE_DIR)
    _assert_write(node_scope, del_node_id, api_auth)

    os.remove(path)
    return {"status": "success", "message": f"Node '{name}' deleted"}

@app.get("/graph/stats")
def get_graph_stats():
    return {
         "status": "success", 
         "data": {
             "chroma_nodes": len(vector_store.list_nodes()), 
             "kuzu_active": len(kuzu_mgr.get_active_nodes(0.0))
        }
    }

def _node_brief(node_id: str):
    """(status, body preview) for a node, read from ChromaDB. Lets the briefing
    distinguish a todo task from a finished one and quote actual content, instead
    of guessing from the title alone."""
    nd = vector_store.get_node(node_id)
    if not nd:
        return None, None
    meta = nd.get("metadata") or {}
    status = meta.get("status")
    doc = (nd.get("document") or "").strip()
    preview = " ".join(doc.split())[:220] if doc and doc != "_EMPTY_" else None
    return status, preview


def _compute_briefing(scope_filter: Optional[List[str]], project: Optional[str] = None,
                      read_grants: Optional[List[str]] = None) -> dict:
    """Build a briefing (hot topics + dormant nodes), optionally scoped to a project."""
    threshold = config.get("attention", {}).get("activation_threshold", 0.5)
    hot_limit = config.get("retrieval", {}).get("briefing_hot_limit", 12)

    active_nodes = kuzu_mgr.get_active_nodes(threshold=threshold, scopes=scope_filter, project=project)
    active_nodes = filter_by_read(active_nodes, read_grants, "name")
    hot_topics = [n for n in active_nodes if not n['name'].startswith("obs_")]
    hot_topics.sort(key=lambda n: n.get("activation_level", n.get("activation", 0)) or 0, reverse=True)

    hot_details = []
    for n in hot_topics[:hot_limit]:
        status, preview = _node_brief(n["name"])
        hot_details.append({
            "name": _readable_name(n),
            "type": n.get("node_type", "Node"),
            "status": status,
            "preview": preview,
        })

    dormant_cfg = config.get("attention", {}).get("dormant", {})
    dormant_nodes = kuzu_mgr.get_dormant_nodes(
        scopes=scope_filter,
        min_interactions=dormant_cfg.get("min_interactions", 5),
        days_node=dormant_cfg.get("days_node", 27),
        days_goal_task=dormant_cfg.get("days_goal_task", 30),
        days_journal=dormant_cfg.get("days_journal", 45),
        project=project,
    )
    dormant_nodes = filter_by_read(dormant_nodes, read_grants, "name")

    return {
        "hot_topics": [_readable_name(n) for n in hot_topics[:hot_limit]],
        "hot_details": hot_details,
        "dormant": [
            {"name": _readable_name(n), "type": n['node_type'], "days_inactive": n['days_inactive']}
            for n in dormant_nodes
        ],
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/briefing", response_model=BriefingResponse)
def get_briefing(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    return _compute_briefing(scope_filter, read_grants=_read_grants(api_auth))

@app.get("/briefing/initiatives")
def get_initiatives(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """Proactive Butler suggestions: hot nodes whose linked neighbors went cold.

    Replaces the standalone briefing_worker (which opened a second KuzuDB
    connection against the gateway's lock and died at startup): the engine runs
    in-process on the gateway's own connection. Consumed by the Alfred morning
    briefing plugin (plugins/morning_briefing.yaml) and available on demand.
    """
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    engine = InitiativeEngine(kuzu_mgr, config=config)
    items = engine.generate_initiatives(scopes=scope_filter, read_grants=_read_grants(api_auth))
    return {
        "timestamp": datetime.now().isoformat(),
        "count": len(items),
        "initiatives": items,
    }

@app.get("/briefing/longitudinal")
def get_longitudinal_briefing(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, api_auth["scopes"])
    scope_filter = actual_scopes if "*" not in actual_scopes else None
    read_grants = _read_grants(api_auth)

    dormant_cfg = config.get("attention", {}).get("dormant", {})
    dormant_nodes = kuzu_mgr.get_dormant_nodes(
        scopes=scope_filter,
        min_interactions=dormant_cfg.get("min_interactions", 5),
        days_node=dormant_cfg.get("days_node", 27),
        days_goal_task=dormant_cfg.get("days_goal_task", 30),
        days_journal=dormant_cfg.get("days_journal", 45),
    )
    dormant_nodes = filter_by_read(dormant_nodes, read_grants, "name")

    goals    = [n for n in dormant_nodes if n['node_type'] == 'Goal']
    tasks    = [n for n in dormant_nodes if n['node_type'] == 'Task']
    topics   = [n for n in dormant_nodes if n['node_type'] == 'Node']
    journals = [n for n in dormant_nodes if n['node_type'] == 'Journal']

    all_hubs = kuzu_mgr.get_dormant_by_connectivity(
        min_edges=dormant_cfg.get("hub_min_edges", 3),
        activation_ceiling=dormant_cfg.get("hub_activation_ceiling", 0.3),
        days_inactive=dormant_cfg.get("hub_days_inactive", 21),
        scopes=scope_filter,
    )
    all_hubs = filter_by_read(all_hubs, read_grants, "name")
    # Resurface a few forgotten hubs on rotation rather than always the most
    # connected ones: weighted-random pick keeps the briefing varied ("oh, do you
    # remember that important thing...") instead of repeating the same hubs daily.
    forgotten_hubs = _weighted_sample(all_hubs, dormant_cfg.get("hub_resurface_count", 1))

    def fmt(nodes):
        return [{"name": _readable_name(n), "type": n['node_type'], "days_inactive": n['days_inactive']} for n in nodes]

    def fmt_hub(n):
        _status, preview = _node_brief(n['name'])
        return {"name": _readable_name(n), "type": n['node_type'],
                "days_inactive": n['days_inactive'], "edge_count": n['edge_count'],
                "preview": preview}

    return {
        "timestamp": datetime.now().isoformat(),
        "dormant_goals":    fmt(goals),
        "dormant_tasks":    fmt(tasks),
        "dormant_topics":   fmt(topics),
        "dormant_journals": fmt(journals),
        "forgotten_hubs":   [fmt_hub(n) for n in forgotten_hubs],
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
    return _compute_briefing(scope_filter, project=project, read_grants=_read_grants(api_auth))
@app.post("/observations")
def add_observation_api(obs: Observation, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    obs_id = f"Obs_{uuid.uuid4().hex[:8]}"
    _assert_write(obs.scope, _target_node_id(obs_id), api_auth)
    frontmatter = {"type": "Observation", "scope": obs.scope}
    write_markdown(obs_id, frontmatter, obs.content)
    return {"status": "success", "id": obs_id}

@app.post("/goals", response_model=NodeWriteResponse)
def create_goal_api(goal: Goal, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    scope = _resolve_scope(goal.scope, goal.scopes)
    _assert_write(scope, _target_node_id(goal.name, goal.folder), api_auth)
    # "status" defaults to "active" on creation only (via _upsert_node_file's
    # `defaults`); an existing Goal's status is left untouched unless the caller
    # explicitly sets it here — a repeated POST (e.g. to change the deadline)
    # must never silently reset a Goal marked "done" back to "active".
    frontmatter: Dict[str, Any] = {"type": "Goal", "scope": scope}
    if goal.status:
        frontmatter["status"] = goal.status
    if goal.deadline: frontmatter["deadline"] = goal.deadline
    if goal.relations:
        frontmatter["relations"] = _parse_relations_str(goal.relations, source="user")
    body = f"# {goal.name}\n\n{goal.description}"
    canonical, action = _upsert_node_file(goal.name, body, frontmatter, folder=goal.folder,
                                          defaults={"status": "active"})
    return {"status": "success", "action": action, "name": canonical, "type": "Goal", "scope": scope}

@app.post("/tasks", response_model=NodeWriteResponse)
def create_task_api(task: Task, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    scope = _resolve_scope(task.scope, task.scopes)
    _assert_write(scope, _target_node_id(task.name, task.folder), api_auth)
    # Same create-only default as /goals: "status" defaults to "todo" on
    # creation, and is left untouched on update unless explicitly set here.
    frontmatter: Dict[str, Any] = {"type": "Task", "scope": scope}
    if task.status:
        frontmatter["status"] = task.status
    if task.deadline: frontmatter["deadline"] = task.deadline
    # Typed relations from the client; goal_name becomes a CONTRIBUTES_TO edge
    # rather than an implicit LINKED_TO wikilink in the body (R2).
    relations = _parse_relations_str(task.relations, source="user") if task.relations else []
    if task.goal_name:
        relations.append({"target": task.goal_name, "type": "CONTRIBUTES_TO", "source": "user"})
    if relations:
        frontmatter["relations"] = relations
    body = f"# {task.name}\n\n{task.description}"
    canonical, action = _upsert_node_file(task.name, body, frontmatter, folder=task.folder,
                                          defaults={"status": "todo"})
    return {"status": "success", "action": action, "name": canonical, "type": "Task", "scope": scope}

@app.post("/nodes", response_model=NodeWriteResponse)
def upsert_node(node: NodeUpsert, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    _assert_write(node.scope, _target_node_id(node.name, node.folder), api_auth)
    frontmatter: Dict[str, Any] = {
        "type": node.node_type,
        "scope": node.scope,
    }
    if node.relations:
        frontmatter["relations"] = _parse_relations_str(node.relations, source="user")
    canonical, action = _upsert_node_file(node.name, node.content, frontmatter, folder=node.folder)
    return {"status": "success", "action": action, "name": canonical,
            "type": node.node_type, "scope": node.scope}

# Mount MCP behind the auth middleware. FastAPI's Depends(verify_api_key) does
# NOT propagate to mounted sub-apps, so without this wrapper the entire MCP
# surface would be unauthenticated. The middleware validates X-API-Key and
# publishes the caller's scopes into a ContextVar the tools read.
from core.mcp_auth import MCPAuthMiddleware
app.mount("/mcp", MCPAuthMiddleware(mcp_app, grants_map=API_GRANTS))

if __name__ == "__main__":
    host = config.get('gateway', {}).get('host', "0.0.0.0")
    port = config.get('gateway', {}).get('port', 4001)
    # access_log disabled: the MCP API key travels in the ?k= query string, which
    # uvicorn's access log would write to journald. Nginx logs requests instead,
    # with a log_format that omits the query string (see deploy/nginx notes).
    uvicorn.run(app, host=host, port=port, access_log=False)
