import sys
import os
import yaml
import uvicorn
import requests
import threading
import time
from fastapi import FastAPI, HTTPException, Body, BackgroundTasks, UploadFile, File, Header, Depends
from fastapi.responses import FileResponse
import shutil
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environmental variables from .env file
load_dotenv()
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

# Plugin Caches (Module Level for FastAPI access)
plugin_registry: Dict[str, Dict[str, Any]] = {}
plugin_suggestions: List[str] = []

from core.graph_manager import GraphManager
from core.attention import AttentionModel
from core.event_bus import EventBus

# Note: Butler modules will eventually be externalized. 
# For now, we import them but the gateway will transition to RPC.
from butler.llm import get_llm_provider
from butler.perception import PerceptionModule
from butler.initiative import InitiativeEngine
from butler.knowledge_queue import KnowledgeQueue
from workers.learning_worker import LearningWorker
from workers.gardener import Gardener
from core.chunking import HeuristicChunker

# Load Configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Load API Keys
API_KEYS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'api_keys.yaml')
api_keys = {}
if os.path.exists(API_KEYS_FILE):
    with open(API_KEYS_FILE, 'r') as f:
        api_keys = yaml.safe_load(f) or {}
    logger.info(f"Loaded {len(api_keys)} API keys for authentication.")
else:
    logger.warning("No api_keys.yaml found. Gateway running WITHOUT authentication.")

def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Dict[str, List[str]]:
    """
    Dependency to check the API Key against the configured api_keys.yaml.
    If no config exists, it returns a wildcard to allow any scope and namespace.
    If it exists, it expects the header X-API-Key to be valid.
    Returns a dict with 'scopes' and 'namespaces' extracted from the key.
    """
    if not api_keys:
        return {"scopes": ["*"], "namespaces": ["*:rw", ":r"]} # Wildcard for 'allow all' when no auth is configured
        
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header missing")
        
    if x_api_key not in api_keys:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    key_config = api_keys[x_api_key]
    scopes = key_config if isinstance(key_config, list) else key_config.get("scopes", ["Public"])
    namespaces = key_config.get("namespaces", [":r"]) if isinstance(key_config, dict) else [":r"]
    
    return {"scopes": scopes, "namespaces": namespaces}

def intersect_scopes(requested: str, allowed: List[str]) -> List[str]:
    if not requested:
        return allowed
    requested_list = requested.split(",")
    if "*" in allowed:
        return requested_list
    return list(set(requested_list) & set(allowed))

# Initialize Core Components
try:
    eb = EventBus()
    eb.start()
    
    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )
    # Ensure Indexes are ready for Semantic Search
    gm.create_fulltext_index()
    gm.create_vector_index()
    
    # Initialize LLM providers
    llm_config = config.get('llm', {})
    
    # Provider for The Butler (Chat, Extraction)
    butler_config = llm_config.get('butler', llm_config)
    butler_llm = get_llm_provider(butler_config, root_config=config)
    
    # Provider for Embeddings (Vector Search)
    embedding_config = llm_config.get('embeddings', llm_config)
    embedding_llm = get_llm_provider(embedding_config, root_config=config)
    
    # Legacy 'llm' reference for backward compatibility (pointing to butler)
    llm = butler_llm
    am = AttentionModel(gm, config=config.get('attention', {}), event_bus=eb)
    pm = PerceptionModule(gm, eb, am)
    ie = InitiativeEngine(gm, config=config)
    
    # Initialize Background Queue and Worker
    kq = KnowledgeQueue()
    worker = LearningWorker(kq, pm)
    worker.start()
    
    chunker = HeuristicChunker()

    def gardener_loop(gm, llm, am, config):
        gardener = Gardener(gm, llm, am, config)
        # Give the server a moment to start before the first run
        time.sleep(60)
        while True:
            try:
                gardener.run_once()
            except Exception as e:
                logger.error(f"Gardener error: {e}")
            time.sleep(gardener.interval)

    threading.Thread(target=gardener_loop, args=(gm, butler_llm, am, config), daemon=True).start()

    def forward_event_to_plugins(event_type: str, payload: Dict[str, Any]):
        """
        Forward internal EventBus signals to registered external plugins.
        """
        for pid, pdata in list(plugin_registry.items()):
            if event_type in pdata.get("capabilities", []):
                url = f"{pdata['url']}/event"
                try:
                    logger.debug(f"Forwarding {event_type} to {pid} with scope {payload.get('scope')}")
                    # Non-blocking forward
                    threading.Thread(target=lambda: requests.post(
                        url, 
                        json={"event_type": event_type, "payload": payload.get("payload", payload), "scope": payload.get("scope", ["Public"])},
                        timeout=30
                    )).start()
                except Exception as e:
                    logger.error(f"Failed to forward {event_type} to plugin {pid}: {e}")

    # Register Local Bridge
    eb.subscribe("*", lambda et, p: forward_event_to_plugins(et, p)) # Wildcard subscription if supported, else we'll need to subscribe specifically
    
    # For now, let's subscribe to standard peaks
    eb.subscribe("NODE_ENERGIZED", lambda p: forward_event_to_plugins("NODE_ENERGIZED", p))
    eb.subscribe("GRAPH_UPDATE", lambda p: forward_event_to_plugins("GRAPH_UPDATE", p))
    eb.subscribe("REQ_ENRICHMENT", lambda p: forward_event_to_plugins("REQ_ENRICHMENT", p))
    
    # Register Local Plugins (Butler)
    eb.subscribe("NODE_ENERGIZED", lambda p: logger.info(f"CORE EVENT: Node {p['name']} reached peak attention ({p['level']})"))
    
    # Bridge ENRICHMENT_RESULT back to Perception
    def handle_enrichment_result(payload):
        # Payload format: {"scope": [...], "payload": {"obs_name": ..., "entities": [...]}}
        nested_payload = payload.get("payload", {})
        entities = nested_payload.get("entities", [])
        relationships = nested_payload.get("relationships", [])
        obs_name = nested_payload.get("obs_name")
        scope = payload.get("scope", ["Public"])[0]
        
        if entities and obs_name:
             pm.integrate_entities(entities, obs_name, scope=scope, relationships=relationships)
             logger.info(f"PERCEPTION: Integrated {len(entities)} entities and {len(relationships)} relations for {obs_name}")

    def handle_initiative_ready(payload):
        nested_payload = payload.get("payload", {})
        initiatives = nested_payload.get("initiatives", [])
        if initiatives:
            global plugin_suggestions
            # Keep the latest suggestions
            plugin_suggestions = [i['message'] for i in initiatives]
            logger.info(f"GATEWAY: Received {len(initiatives)} suggestions from BriefingWorker")

    eb.subscribe("ENRICHMENT_RESULT", handle_enrichment_result)
    eb.subscribe("INITIATIVE_READY", handle_initiative_ready)
    
    print("✅ Mnemosyne Core & Event Bus Initialized")
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

# --- STANDARD REST API (Nodes CRUD) ---
# --- SPECIFIC ENTITY CRUD (Phase 2) ---

class EntityPayload(BaseModel):
    description: str = ""
    status: str = "active"
    due_date: str = None
    goal_name: str = None

@app.post("/goals/{name}")
def create_goal_api(name: str, payload: EntityPayload, scopes: str = "Private", api_auth: dict = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    props = {"status": payload.status}
    if payload.description: props["description"] = payload.description
    if payload.due_date: props["deadline"] = payload.due_date
    
    node = gm.add_node(name, primary_label="Goal", properties=props, scope=actual_scopes[0], namespace=allowed_namespaces[0] if allowed_namespaces else None)
    return {"status": "success", "data": dict(node)}

@app.post("/tasks/{name}")
def create_task_api(name: str, payload: EntityPayload, scopes: str = "Private", api_auth: dict = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    props = {"status": payload.status or "todo"}
    if payload.description: props["description"] = payload.description
    if payload.due_date: props["due_date"] = payload.due_date
    
    node = gm.add_node(name, primary_label="Task", properties=props, scope=actual_scopes[0], namespace=allowed_namespaces[0] if allowed_namespaces else None)
    
    if payload.goal_name:
        gm.add_edge(payload.goal_name, name, "REQUIRES", weight=0.8)
        
    return {"status": "success", "data": dict(node)}

@app.post("/topics/{name}")
def create_topic_api(name: str, payload: EntityPayload, scopes: str = "Public", api_auth: dict = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    props = {}
    if payload.description: props["description"] = payload.description
    
    node = gm.add_node(name, primary_label="Topic", properties=props, scope=actual_scopes[0], namespace=allowed_namespaces[0] if allowed_namespaces else None)
    return {"status": "success", "data": dict(node)}



@app.get("/nodes")
def list_nodes(type: Optional[str] = None, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    
    nodes_raw = gm.get_all_nodes(label=type, scopes=actual_scopes, namespaces=allowed_namespaces)
    data = []
    for n in nodes_raw:
        # Determine primary type using GraphManager helper
        primary_type = gm._extract_primary_type(n["labels"])
        
        item = {
            "name": n["name"],
            "slug": n["name"],
            "labels": n["labels"],
            "type": primary_type,
            "scope": [l for l in n["labels"] if l in gm.scope_hierarchy][0] if any(l in gm.scope_hierarchy for l in n["labels"]) else "Public",
            "properties": n["props"]
        }
        for f in ["title", "description", "summary", "ai_context", "cover_image_id", "type"]:
             if f in n["props"]:
                  item[f] = n["props"][f]
        data.append(item)
    return {"data": data}

@app.get("/nodes/{name}")
def get_node(name: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    node = gm.get_node(name, scopes=actual_scopes, namespaces=allowed_namespaces)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{name}' not found")
        
    n_dict = dict(node)
    props = {k: v for k, v in n_dict.items() if k not in ['name', 'labels']}
    
    # Extract labels if available in the node object
    labels = list(node.labels) if hasattr(node, 'labels') else []
    primary_type = props.get("type") or gm._extract_primary_type(labels)

    item = {
        "name": n_dict.get("name"),
        "slug": n_dict.get("name"),
        "type": primary_type,
        "labels": labels,
        "properties": props
    }
    for f in ["title", "description", "summary", "ai_context", "cover_image_id", "type"]:
         if f in props:
              item[f] = props[f]
              
    return {"data": item}

@app.put("/nodes/{name}")
def upsert_node(name: str, payload: Dict[str, Any] = Body(...), scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    primary_label = payload.get("type", "Node")
    props = payload.get("properties", {})
    # Phase 2: Immutability for Observation and Document
    existing_node = gm.get_node(name, scopes=actual_scopes, namespaces=allowed_namespaces)
    if existing_node:
        existing_labels = list(existing_node.labels)
        if "Observation" in existing_labels or "Document" in existing_labels:
            raise HTTPException(status_code=405, detail="Method Not Allowed: Observation and Document nodes are immutable. Delete and recreate.")
    elif primary_label in ["Observation", "Document"]:
        raise HTTPException(status_code=405, detail="Method Not Allowed: Dedicated endpoints must be used to create Observation or Document.")
    
    # Flatten specific root fields into properties for graph storage
    for f in ["title", "description", "summary", "ai_context", "cover_image_id"]:
        if f in payload and payload[f] is not None:
            props[f] = payload[f]
            
    tags = payload.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    
    node = gm.add_node(name, primary_label=primary_label, tags=tags, properties=props, scope=actual_scope, namespace=allowed_namespaces[0] if allowed_namespaces else Nones[0])
    return {"status": "success", "data": dict(node)}

@app.delete("/nodes/{name}")
def delete_node_api(name: str, scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    success = gm.delete_node(name, scopes=actual_scopes, namespaces=allowed_namespaces)
    if not success:
         raise HTTPException(status_code=404, detail=f"Node '{name}' not found or already deleted")
         
    return {"status": "success", "message": f"Node '{name}' deleted"}

@app.patch("/nodes/{name}/allow_orphan")
def allow_orphan_task(name: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """
    Marks a Task as intentionally isolated so the Gardener stops suggesting to contextualize it.
    """
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    # We remove the hidden flag and set the explicit allow flag
    result = gm.update_node_properties(name, {"allow_orphan": True, "_is_orphan": None}, scopes=actual_scopes, namespaces=allowed_namespaces)
    if not result:
        raise HTTPException(status_code=404, detail=f"Node '{name}' not found")
        
    return {"status": "success", "message": f"Task '{name}' has been marked to float freely."}


@app.put("/goals/{name}")
def update_goal_api(name: str, payload: EntityPayload, scopes: str = "Private", api_auth: dict = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    props = {}
    if payload.description: props["description"] = payload.description
    if payload.status: props["status"] = payload.status
    if payload.due_date: props["deadline"] = payload.due_date
    
    result = gm.update_node_properties(name, props, scopes=actual_scopes, namespaces=allowed_namespaces)
    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"status": "success", "data": result}

@app.delete("/goals/{name}")
def delete_goal_api(name: str, scopes: str = "Private", api_auth: dict = Depends(verify_api_key)):
    return delete_node_api(name, scopes, api_auth)

@app.put("/tasks/{name}")
def update_task_api(name: str, payload: EntityPayload, scopes: str = "Private", api_auth: dict = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    props = {}
    if payload.description: props["description"] = payload.description
    if payload.status: props["status"] = payload.status
    if payload.due_date: props["due_date"] = payload.due_date
    
    result = gm.update_node_properties(name, props, scopes=actual_scopes, namespaces=allowed_namespaces)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if payload.goal_name:
        gm.add_edge(payload.goal_name, name, "REQUIRES", weight=0.8)
        
    return {"status": "success", "data": result}

@app.delete("/tasks/{name}")
def delete_task_api(name: str, scopes: str = "Private", api_auth: dict = Depends(verify_api_key)):
    return delete_node_api(name, scopes, api_auth)

@app.put("/topics/{name}")
def update_topic_api(name: str, payload: EntityPayload, scopes: str = "Public", api_auth: dict = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    props = {}
    if payload.description: props["description"] = payload.description
    
    result = gm.update_node_properties(name, props, scopes=actual_scopes, namespaces=allowed_namespaces)
    if not result:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"status": "success", "data": result}

@app.delete("/topics/{name}")
def delete_topic_api(name: str, scopes: str = "Public", api_auth: dict = Depends(verify_api_key)):
    return delete_node_api(name, scopes, api_auth)

@app.get("/graph/schema")
def get_graph_schema(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    schema = gm.get_schema(scopes=actual_scopes, namespaces=allowed_namespaces)
    return {"status": "success", "data": schema}

@app.get("/graph/stats")
def get_graph_stats(scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    stats = gm.get_stats(scopes=actual_scopes, namespaces=allowed_namespaces)
    return {"status": "success", "data": stats}

@app.get("/graph/export")
def get_graph_export(scopes: Optional[str] = None, limit: int = 5000, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    data = gm.export_graph(scopes=actual_scopes, namespaces=allowed_namespaces, limit=limit)
    return {"status": "success", "data": data}

@app.post("/search/advanced")
def search_advanced(payload: Dict[str, Any] = Body(...), scopes: Optional[str] = None, limit: int = 50, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    results = gm.advanced_search(filters=payload, scopes=actual_scopes, namespaces=allowed_namespaces, limit=limit)
    return {"status": "success", "data": results}

@app.get("/nodes/{name}/neighbors")
def get_neighbors(name: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    neighbors = gm.get_neighbors(name, scopes=actual_scopes, namespaces=allowed_namespaces)
    return {"status": "success", "data": neighbors}

@app.get("/search")
def search(q: str, scopes: Optional[str] = None, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    
    logger.info(f"API: Searching for '{q}' in scopes {actual_scopes}")
    
    # Semantic search with resilient fallback in GraphManager
    enable_embeddings = config.get("llm", {}).get("embeddings", {}).get("enabled", True)
    
    # Pre-processing: Clean query of trailing punctuation for better exact matching
    import re
    q_clean = re.sub(r'[^\w\s]', '', q).strip()
    
    try:
        best_match, search_type, score = gm.semantic_search(
            query=q_clean, 
            llm_provider=embedding_llm, 
            enable_embeddings=enable_embeddings, 
            scopes=actual_scopes, 
            limit=1
        )
        
        if not best_match:
            raise HTTPException(status_code=404, detail=f"Concept '{q}' not found in scopes {actual_scopes}.")
            
        name = best_match['name']
        props = {k: v for k, v in dict(best_match).items() if k not in ['name', 'labels']}
        logger.info(f"API Search: Used {search_type.upper()} search for '{q}' -> found '{name}' (Score: {score})")
        
        # Determine type
        labels = list(best_match.labels) if hasattr(best_match, 'labels') else []
        primary_type = props.get("type") or gm._extract_primary_type(labels)
        
        # Energize the node to trigger initiatives/propagation
        am.propagate_activation(name, initial_boost=1.0)
        
        neighbors = gm.get_neighbors(name, scopes=actual_scopes, namespaces=allowed_namespaces)
        related = []
        if neighbors:
            limit = config.get("retrieval", {}).get("search_neighbors_limit", 15)
            for n in neighbors[:limit]:
                # Extract summary or fallback to a snippet of content
                n_props = n['node']
                n_summary = n_props.get('summary') or n_props.get('description')
                if not n_summary and n_props.get('content'):
                    n_summary = n_props['content'][:100] + "..."
                
                related.append({
                    "name": n_props['name'],
                    "rel": n['rel_type'],
                    "summary": n_summary or ""
                })
                
        return {
            "name": name,
            "type": primary_type,
            "properties": props,
            "related": related
        }
    except HTTPException as he:
        # Re-raise FastAPIs internal exceptions so they aren't masked as 500
        raise he
    except Exception as e:
        logger.error(f"Internal Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error during search: {str(e)}")

@app.post("/add")
def add_observation(obs: Observation, scope: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scope, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    actual_scope = actual_scopes[0] # Using the first authorized scope

    logger.info(f"API: Adding observation to scope {actual_scope}")
    # 1. Immediate step: Create the observation node
    obs_name = pm.create_observation(obs.content, scope=actual_scope)
    
    # 2. Background step: Enqueue for entity extraction
    job_id = kq.enqueue(obs.content, obs_name, scope=actual_scope)
    
    return {
        "status": "success", 
        "message": "Observation recorded and enqueued for learning",
        "obs_name": obs_name,
        "job_id": job_id
    }

def background_ingest(title: str, text: str, scope: str, file_path: str = None):
    """Background task for heavy document ingestion."""
    try:
        logger.info(f"INGESTION: Starting background ingestion for '{title}'...")
        chunks = chunker.chunk_text(text)
        gm.add_document(title, chunks, scope=scope, file_path=file_path)
        logger.info(f"INGESTION: Complete. '{title}' processed into {len(chunks)} chunks.")
    except Exception as e:
        logger.error(f"INGESTION FAILED for '{title}': {e}")

@app.post("/ingest")
async def ingest_document(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    scope: Optional[str] = "Public",
    api_auth: Dict[str, List[str]] = Depends(verify_api_key)
):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scope, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    actual_scope = actual_scopes[0]
    """
    Ingests a massive document (txt, md) bypassing the LLM via Heuristic Chanking.
    Archives the original file in data/storage/documents.
    """
    content = await file.read()
    try:
         text = content.decode('utf-8')
    except UnicodeDecodeError:
         raise HTTPException(status_code=400, detail="Only UTF-8 text files are supported for now.")
         
    title = file.filename
    storage_path = os.path.join(os.getcwd(), 'data', 'storage', 'documents', title)
    
    # Save physical copy
    try:
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as buffer:
            buffer.write(content)
        logger.info(f"ARCHIVE: File saved to {storage_path}")
    except Exception as e:
        logger.error(f"ARCHIVE FAILED for {title}: {e}")
        # We continue ingestion even if archiving fails, but log it
    
    # Queue the background task to avoid blocking the Gateway
    background_tasks.add_task(background_ingest, title, text, actual_scope, storage_path)
    
    return {
        "status": "processing",
        "message": f"Document '{title}' queued for massive ingestion and archived.",
        "scope": actual_scope,
        "archive_path": storage_path
    }

@app.get("/documents")
def list_documents(scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """Lists all Document nodes in the graph."""
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    query = """
    MATCH (d:Document)
    WHERE """ + gm._get_scope_filter(actual_scopes, var_name="d") + """
    RETURN d.name as name, labels(d) as labels, properties(d) as props
    """
    documents = []
    with gm.driver.session() as session:
        result = session.run(query)
        for record in result:
            documents.append({
                "name": record["name"],
                "scope": [l for l in record["labels"] if l in gm.scope_hierarchy][0],
                "properties": record["props"]
            })
    return {"documents": documents}

@app.get("/document/{name}/download")
def download_document(name: str):
    """Downloads the original archived file."""
    storage_path = os.path.join(os.getcwd(), 'data', 'storage', 'documents', name)
    if not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Original file not found in archive.")
    
    return FileResponse(path=storage_path, filename=name, media_type='application/octet-stream')

@app.delete("/document/{name}")
def delete_document(name: str, scope: str = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """
    Deletes a document from the graph and the physical storage.
    This is a 'Deep Delete' that removes all associated chunks.
    """
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scope, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    actual_scope = actual_scopes[0]
    
    # 1. Remove from graph
    try:
        # We'll add a deep_delete_document to GraphManager
        success = gm.delete_document(name, scope=actual_scope, namespace=allowed_namespaces[0] if allowed_namespaces else None)
        if not success:
             logger.warning(f"DELETE: Document '{name}' not found in graph for scope '{actual_scope}'")
    except Exception as e:
        logger.error(f"DELETE GRAPH FAILED for {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # 2. Remove from storage
    storage_path = os.path.join(os.getcwd(), 'data', 'storage', 'documents', name)
    if os.path.exists(storage_path):
        try:
            os.remove(storage_path)
            logger.info(f"DELETE STORAGE: Removed {storage_path}")
        except Exception as e:
            logger.error(f"DELETE STORAGE FAILED for {name}: {e}")

    return {"status": "success", "message": f"Document '{name}' and its chunks have been removed."}


@app.post("/share")
def share_knowledge(node_name: str, from_scope: str, to_scope: str, api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """
    Explicitly moves/links knowledge between scopes.
    """
    allowed_scopes = api_auth["scopes"]
    if "*" not in allowed_scopes:
        if from_scope not in allowed_scopes or to_scope not in allowed_scopes:
            raise HTTPException(status_code=403, detail="Not authorized to share between requested scopes")
            
    node = gm.get_node(node_name, scopes=[from_scope])
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found in scope '{from_scope}'")
    
    # For this MVP, we re-label the node with the new scope as well
    # (Hierarchy already handles visibility, but this is an explicit 'promotion')
    query = f"""
    MATCH (n {{name: $name}})
    WHERE n:{from_scope}
    SET n:{to_scope}
    RETURN n
    """
    with gm.driver.session() as session:
        session.run(query, name=node_name)
    
    logger.info(f"KNOWLEDGE SHARED: {node_name} promoted from {from_scope} to {to_scope}")
    return {"status": "shared", "node": node_name, "new_scope": to_scope}

@app.get("/briefing")
def get_briefing(scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    # 1. Active Topics
    active_nodes = gm.get_active_nodes(threshold=0.7, scopes=actual_scopes, namespaces=allowed_namespaces)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]

    # 2. Proactive Context (The Butler)
    proactive_context = ie.get_proactive_context(scopes=actual_scopes)

    # 3. Suggestions (Mix local and plugin-based)
    local_suggestions = ie.generate_initiatives(scopes=actual_scopes)
    combined_suggestions = [s['message'] for s in local_suggestions] + plugin_suggestions

    return {
        "hot_topics": hot_topics,
        "butler_log": proactive_context,
        "suggestions": list(set(combined_suggestions)) # Deduplicate
    }

@app.get("/briefing/longitudinal")
def get_longitudinal_briefing(scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    """
    Generates a historical briefing of dormant projects and temporal trends.
    """
    long_cfg = config.get('longitudinal_analysis', {})
    if not long_cfg.get('enabled', True):
        raise HTTPException(status_code=403, detail="Longitudinal analysis is disabled in configuration.")
        
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    
    threshold = long_cfg.get('dormancy_threshold_days', 30)
    dormant_projects = gm.get_dormant_projects(threshold_days=threshold, limit=5, scopes=actual_scopes, namespaces=allowed_namespaces)
    recent_trends = gm.get_temporal_trends(days_ago=7, limit=5, scopes=actual_scopes, namespaces=allowed_namespaces)
    
    return {
        "status": "success",
        "dormant_projects": dormant_projects,
        "recent_trends": recent_trends,
        "message": f"Historical analysis generated for the past {threshold} days."
    }

# --- Mnemosyne-RPC Bridge (Cap. 2 Roadmap) ---

class RPCEvent(BaseModel):
    version: str = "1.0"
    event_type: str
    timestamp: str
    scope: List[str]
    payload: Dict[str, Any]

@app.post("/rpc")
def mnemosyne_rpc(event: RPCEvent):
    """
    Generic bridge for Mnemosyne-RPC protocol.
    Distributes events to the internal EventBus.
    """
    logger.info(f"RPC RECEIVED: {event.event_type} (Scope: {event.scope})")
    
    # Publish to internal bus
    eb.publish(event.event_type, {
        "scope": event.scope,
        "payload": event.payload,
        "rpc_version": event.version
    })
    
    return {"status": "received", "event_id": event.timestamp}

@app.post("/register")
def register_plugin(registration: Dict[str, Any]):
    """
    Plugin Handshake (Cap. 2.4 Roadmap)
    """
    plugin_name = registration.get("name", "Unknown")
    plugin_url = registration.get("url")
    capabilities = registration.get("capabilities", [])
    
    if not plugin_url:
        raise HTTPException(status_code=400, detail="Missing plugin URL")

    plugin_id = f"plg_{hash(plugin_name + plugin_url) % 10000}"
    plugin_registry[plugin_id] = {
        "name": plugin_name,
        "url": plugin_url,
        "capabilities": capabilities
    }
    
    logger.info(f"PLUGIN REGISTERED: {plugin_name} (ID: {plugin_id}, URL: {plugin_url}, Capabilities: {capabilities})")
    
    return {
        "status": "authorized",
        "plugin_id": plugin_id,
        "gateway_version": "1.0.0"
    }

@app.get("/plugins")
def list_plugins():
    return plugin_registry

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

    # 2. LLM Checks (with Timeout)
    for name, provider in [("butler", butler_llm), ("embeddings", embedding_llm)]:
        try:
            info = provider.get_info()
            status[name] = info # Start with config info
            
            # Connection probing
            if info["mode"] == "ollama":
                try:
                    resp = requests.get(f"{info['base_url'].rstrip('/')}/api/tags", timeout=2)
                    if resp.status_code == 200:
                         status[name]["status"] = "connected (Ollama is alive)"
                    else:
                         status[name]["status"] = f"error: Ollama returned {resp.status_code}"
                except Exception as e:
                    status[name]["status"] = f"error: {str(e)}"
            elif info["mode"] == "mock":
                 status[name]["status"] = "ready (local mock)"
            else:
                 # OpenAI or Remote
                 try:
                    # Aumentato timeout a 10s per latenza API/Proxy
                    provider.generate("health check", timeout=10)
                    status[name]["status"] = "connected"
                 except Exception as e:
                    status[name]["status"] = f"error: {str(e)}"
                    
        except Exception as e:
            status[name] = f"error: {str(e)}"
    
    # Legacy backward compatibility for old clients expecting 'llm' key
    status["llm"] = status["butler"]
    
    return status
        
@app.get("/stats")
def get_stats(scopes: Optional[str] = "Public", api_auth: Dict[str, List[str]] = Depends(verify_api_key)):
    allowed_scopes = api_auth["scopes"]
    allowed_namespaces = api_auth["namespaces"]
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    return gm.get_stats(scopes=actual_scopes, namespaces=allowed_namespaces)

@app.get("/history")
def get_history():
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
