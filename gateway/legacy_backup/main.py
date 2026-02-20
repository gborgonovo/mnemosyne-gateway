import sys
import os
import yaml
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Core Imports
from core.graph_manager import GraphManager
from core.attention import AttentionModel
from butler.perception import PerceptionModule
from butler.initiative import InitiativeEngine
from butler.feedback import FeedbackManager
from butler.llm import get_llm_provider

# Gateway Imports
from .state import state
from .proxy import router as proxy_router

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🧠 Mnemosyne Gateway Starting...")
    state.config = load_config()
    
    # Initialize Core Modules
    state.gm = GraphManager(
        state.config['graph']['uri'], 
        state.config['graph']['user'], 
        state.config['graph']['password']
    )
    state.am = AttentionModel(state.gm, config=state.config.get('attention', {}))
    state.llm = get_llm_provider(state.config)
    state.pm = PerceptionModule(state.gm, state.llm, state.am)
    state.ie = InitiativeEngine(state.gm, config=state.config.get('initiative', {}))
    state.fm = FeedbackManager(state.gm)
    
    print("✅ Connected to Connectome and Core Modules Initialized")
    
    yield
    
    # Shutdown
    if state.gm:
        state.gm.close()
    print("💤 Mnemosyne Gateway Shutdown")

from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request

app = FastAPI(title="Mnemosyne API", version="0.1.0", lifespan=lifespan)

# Debug Middleware: Print every request to help with Open WebUI discovery
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"DEBUG: {request.method} {request.url.path}")
    response = await call_next(request)
    return response

# Add CORS Middleware for Open WebUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Mount Routers
app.include_router(proxy_router)

# --- Pydantic Models ---

class ContextQuery(BaseModel):
    query: str
    limit: int = 5

class ObservationInput(BaseModel):
    content: str
    source: str = "api"
    metadata: Optional[Dict[str, Any]] = None

# --- Direct Endpoints (Bypassing Proxy) ---

@app.get("/")
async def root():
    return {"status": "online", "system": "Mnemosyne Cognitive Middleware", "mode": "headless"}

@app.get("/status")
async def get_status():
    if not state.gm:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    node_count = len(state.gm.get_all_nodes())
    return {
        "nodes": node_count,
        "active_nodes": len(state.gm.get_active_nodes(threshold=0.1)),
        "llm_provider": state.config.get('llm', {}).get('provider', 'unknown')
    }

@app.post("/observe")
async def add_observation(obs: ObservationInput, background_tasks: BackgroundTasks):
    """
    Inject an observation directly.
    """
    if not state.pm:
        raise HTTPException(status_code=503, detail="Perception Module not ready")
    
    entities = state.pm.process_input(obs.content)
    return {"status": "processed", "entities_extracted": entities}

@app.post("/context")
async def get_context(query: ContextQuery):
    """
    Direct context retrieval endpoint (for debugging or custom clients).
    """
    if not state.pm:
        raise HTTPException(status_code=503, detail="Core modules not ready")
    
    # 1. Extract entities from query
    entities = state.pm.process_input(query.query)
    
    # 2. Retrieve Context
    context_text = ""
    if entities:
        context_text += "=== MNEMOSYNE CONTEXT ===\n"
        for entity in entities:
             # Basic implementation
             node = state.gm.get_node(entity)
             if node:
                context_text += f"- Entity: {entity}\n"
    
    return {
        "entities": entities,
        "context_text": context_text
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4001)
