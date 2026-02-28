import sys
import os
import yaml
import uvicorn
import requests
import threading
from fastapi import FastAPI, HTTPException, Body, BackgroundTasks, UploadFile, File, Header, Depends
from fastapi.responses import FileResponse
import shutil
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load environmental variables from .env
load_dotenv()

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

def verify_api_key(x_api_key: Optional[str] = Header(None)) -> List[str]:
    """
    Dependency to check the API Key against the configured api_keys.yaml.
    If no config exists, it returns a wildcard to allow any scope.
    If it exists, it expects the header X-API-Key to be valid.
    """
    if not api_keys:
        return ["*"] # Wildcard for 'allow all' when no auth is configured
        
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header missing")
        
    if x_api_key not in api_keys:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    return api_keys[x_api_key]

def intersect_scopes(requested: str, allowed: List[str]) -> List[str]:
    requested_list = requested.split(",") if requested else ["Public"]
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
    
    llm = get_llm_provider(config)
    am = AttentionModel(gm, config=config.get('attention', {}), event_bus=eb)
    pm = PerceptionModule(gm, eb, am)
    ie = InitiativeEngine(gm, config=config)
    
    # Initialize Background Queue and Worker
    kq = KnowledgeQueue()
    worker = LearningWorker(kq, pm)
    worker.start()
    
    chunker = HeuristicChunker()

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
        obs_name = nested_payload.get("obs_name")
        scope = payload.get("scope", ["Public"])[0]
        
        if entities and obs_name:
             pm.integrate_entities(entities, obs_name, scope=scope)
             logger.info(f"PERCEPTION: Integrated {len(entities)} entities for {obs_name}")

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

@app.get("/nodes")
def list_nodes(type: Optional[str] = None, scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    
    nodes_raw = gm.get_all_nodes(label=type, scopes=actual_scopes)
    data = []
    for n in nodes_raw:
        # Determine primary type (the label that isn't 'Node', 'Public', 'Internal', or 'Private')
        exclusion_list = ["Node", "Public", "Internal", "Private"]
        type_labels = [l for l in n["labels"] if l not in exclusion_list]
        primary_type = type_labels[0] if type_labels else (n["labels"][0] if n["labels"] else "Node")
        
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
def get_node(name: str, scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    node = gm.get_node(name, scopes=actual_scopes)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{name}' not found")
        
    n_dict = dict(node)
    props = {k: v for k, v in n_dict.items() if k not in ['name', 'labels']}
    
    # Extract labels if available in the node object
    labels = list(node.labels) if hasattr(node, 'labels') else []
    exclusion_list = ["Node", "Public", "Internal", "Private"]
    type_labels = [l for l in labels if l not in exclusion_list]
    primary_type = props.get("type") or (type_labels[0] if type_labels else "Node")

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
def upsert_node(name: str, payload: Dict[str, Any] = Body(...), scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    primary_label = payload.get("type", "Node")
    props = payload.get("properties", {})
    
    # Flatten specific root fields into properties for graph storage
    for f in ["title", "description", "summary", "ai_context", "cover_image_id"]:
        if f in payload and payload[f] is not None:
            props[f] = payload[f]
            
    tags = payload.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    
    node = gm.add_node(name, primary_label=primary_label, tags=tags, properties=props, scope=actual_scopes[0])
    return {"status": "success", "data": dict(node)}

@app.delete("/nodes/{name}")
def delete_node_api(name: str, scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    success = gm.delete_node(name, scopes=actual_scopes)
    if not success:
         raise HTTPException(status_code=404, detail=f"Node '{name}' not found or already deleted")
         
    return {"status": "success", "message": f"Node '{name}' deleted"}

@app.get("/search")
def search(q: str, scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    node = gm.get_node(q, scopes=actual_scopes)
    if node:
        # 1. EXACT MATCH
        n_dict = dict(node)
        name = n_dict['name']
        props = {k: v for k, v in n_dict.items() if k not in ['name', 'labels']}
    else:
        # 2. VECTOR SEMANTIC SEARCH
        vector_results = []
        if config.get("llm", {}).get("enable_embeddings", False):
            try:
                query_embedding = llm.embed(q)
                if query_embedding:
                    vector_results = gm.search_nodes_vector(query_embedding, scopes=actual_scopes, limit=1)
            except Exception as e:
                logger.warning(f"Vector embedding failed, falling back to full-text: {e}")

        if vector_results:
            best_match = vector_results[0]['node']
            name = best_match['name']
            props = {k: v for k, v in dict(best_match).items() if k not in ['name', 'labels']}
            
            labels = list(best_match.labels) if hasattr(best_match, 'labels') else []
            exclusion_list = ["Node", "Public", "Internal", "Private"]
            type_labels = [l for l in labels if l not in exclusion_list]
            primary_type = props.get("type") or (type_labels[0] if type_labels else "Node")
            
            logger.info(f"API Search: Used VECTOR search for '{q}' -> found '{name}' (Score: {vector_results[0]['score']})")
        else:
            # 3. SEMANTIC FALLBACK (Full-Text)
            results = gm.search_nodes_fulltext(q, scopes=actual_scopes, limit=1)
            if not results:
                raise HTTPException(status_code=404, detail=f"Concept '{q}' not found in scopes {actual_scopes}.")
                
            best_match = results[0]['node']
            name = best_match['name']
            props = {k: v for k, v in dict(best_match).items() if k not in ['name', 'labels']}
            
            labels = list(best_match.labels) if hasattr(best_match, 'labels') else []
            exclusion_list = ["Node", "Public", "Internal", "Private"]
            type_labels = [l for l in labels if l not in exclusion_list]
            primary_type = props.get("type") or (type_labels[0] if type_labels else "Node")
            
            logger.info(f"API Search: Used FULL-TEXT fallback for '{q}' -> found '{name}' (Score: {results[0]['score']})")
    
    # Determine type for exact match if needed (exact match fallback)
    if not 'primary_type' in locals():
         labels = list(node.labels) if hasattr(node, 'labels') else []
         exclusion_list = ["Node", "Public", "Internal", "Private"]
         type_labels = [l for l in labels if l not in exclusion_list]
         primary_type = props.get("type") or (type_labels[0] if type_labels else "Node")
    
    # Energize the node to trigger initiatives/propagation
    am.propagate_activation(name, initial_boost=1.0)
    
    neighbors = gm.get_neighbors(name, scopes=actual_scopes)
    related = []
    if neighbors:
        limit = config.get("retrieval", {}).get("search_neighbors_limit", 10)
        for n in neighbors[:limit]:
            related.append(f"{n['node']['name']} ({n['rel_type']})")
            
    return {
        "name": name,
        "type": primary_type,
        "properties": props,
        "related": related
    }

@app.post("/add")
def add_observation(obs: Observation, scope: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
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
    allowed_scopes: List[str] = Depends(verify_api_key)
):
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
def list_documents(scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    """Lists all Document nodes in the graph."""
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
def delete_document(name: str, scope: str = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    """
    Deletes a document from the graph and the physical storage.
    This is a 'Deep Delete' that removes all associated chunks.
    """
    actual_scopes = intersect_scopes(scope, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    actual_scope = actual_scopes[0]
    
    # 1. Remove from graph
    try:
        # We'll add a deep_delete_document to GraphManager
        success = gm.delete_document(name, scope=actual_scope)
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
def share_knowledge(node_name: str, from_scope: str, to_scope: str, allowed_scopes: List[str] = Depends(verify_api_key)):
    """
    Explicitly moves/links knowledge between scopes.
    """
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
def get_briefing(scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
        
    # 1. Active Topics
    active_nodes = gm.get_active_nodes(threshold=0.7, scopes=actual_scopes)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]

@app.get("/briefing/longitudinal")
def get_longitudinal_briefing(scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    """
    Generates a historical briefing of dormant projects and temporal trends.
    """
    long_cfg = config.get('longitudinal_analysis', {})
    if not long_cfg.get('enabled', True):
        raise HTTPException(status_code=403, detail="Longitudinal analysis is disabled in configuration.")
        
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    
    threshold = long_cfg.get('dormancy_threshold_days', 30)
    dormant_projects = gm.get_dormant_projects(threshold_days=threshold, limit=5, scopes=actual_scopes)
    recent_trends = gm.get_temporal_trends(days_ago=7, limit=5, scopes=actual_scopes)
    
    return {
        "status": "success",
        "dormant_projects": dormant_projects,
        "recent_trends": recent_trends,
        "message": f"Historical analysis generated for the past {threshold} days."
    }
    
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
        
@app.get("/stats")
def get_stats(scopes: Optional[str] = "Public", allowed_scopes: List[str] = Depends(verify_api_key)):
    actual_scopes = intersect_scopes(scopes, allowed_scopes)
    if not actual_scopes:
        raise HTTPException(status_code=403, detail="Not authorized to access requested scopes")
    return gm.get_stats(scopes=actual_scopes)

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
