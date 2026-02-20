import sys
import os
import yaml
import uvicorn
import requests
import threading
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

# Load Configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Initialize Core Components
try:
    eb = EventBus()
    eb.start()
    
    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )
    llm = get_llm_provider(config)
    am = AttentionModel(gm, config=config.get('attention', {}), event_bus=eb)
    pm = PerceptionModule(gm, eb, am)
    ie = InitiativeEngine(gm, config=config)
    
    # Initialize Background Queue and Worker
    kq = KnowledgeQueue()
    worker = LearningWorker(kq, pm)
    worker.start()

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

@app.get("/search")
def search(q: str, scopes: Optional[str] = "Public"):
    scope_list = scopes.split(",") if scopes else ["Public"]
    node = gm.get_node(q, scopes=scope_list)
    if not node:
        raise HTTPException(status_code=404, detail=f"Concept '{q}' not found in scopes {scope_list}.")
    
    # Energize the node to trigger initiatives/propagation
    am.propagate_activation(q, initial_boost=1.0)
    
    props = {k: v for k, v in dict(node).items() if k not in ['name', 'labels']}
    
    neighbors = gm.get_neighbors(q, scopes=scope_list)
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
def add_observation(obs: Observation, scope: Optional[str] = "Public"):
    logger.info(f"API: Adding observation to scope {scope}")
    # 1. Immediate step: Create the observation node
    obs_name = pm.create_observation(obs.content, scope=scope)
    
    # 2. Background step: Enqueue for entity extraction
    job_id = kq.enqueue(obs.content, obs_name, scope=scope)
    
    return {
        "status": "success", 
        "message": "Observation recorded and enqueued for learning",
        "obs_name": obs_name,
        "job_id": job_id
    }

@app.post("/share")
def share_knowledge(node_name: str, from_scope: str, to_scope: str):
    """
    Explicitly moves/links knowledge between scopes.
    """
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
def get_briefing(scopes: Optional[str] = "Public"):
    scope_list = scopes.split(",") if scopes else ["Public"]
    # 1. Active Topics
    active_nodes = gm.get_active_nodes(threshold=0.7, scopes=scope_list)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]
    
    # 2. Proactive Context (The Butler)
    proactive_context = ie.get_proactive_context(scopes=scope_list) 
    
    # 3. Suggestions (Mix local and plugin-based)
    local_suggestions = ie.generate_initiatives(scopes=scope_list)
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
def get_stats(scopes: Optional[str] = "Public"):
    scope_list = scopes.split(",") if scopes else ["Public"]
    return gm.get_stats(scopes=scope_list)

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
