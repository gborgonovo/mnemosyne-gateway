import asyncio
import sys
import os
import yaml
import logging
import json
from datetime import datetime

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

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp.server.fastmcp import FastMCP
from core.graph_manager import GraphManager
from butler.llm import get_llm_provider
from butler.perception import PerceptionModule
from core.attention import AttentionModel
from butler.initiative import InitiativeEngine
from workers.gardener import Gardener

# Configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Initialize Core
gm = GraphManager(
    config['graph']['uri'], 
    config['graph']['user'], 
    config['graph']['password']
)
llm = get_llm_provider(config)
am = AttentionModel(gm, config=config.get('attention', {}))
pm = PerceptionModule(gm, llm, am)
ie = InitiativeEngine(gm, config=config)
gd = Gardener(gm, llm, am, config=config)

# Create FastMCP Server
mcp = FastMCP("Mnemosyne-Memory")

@mcp.tool()
def trigger_gardening_cycle() -> str:
    """
    Manually trigger a gardening cycle to clean up duplicates, 
    apply temporal decay to thoughts, and check for urgent deadlines.
    """
    gd.run_once()
    return "Gardening cycle completed successfully. Memory sanitized and updated."

@mcp.tool()
def query_knowledge(query: str, scopes: str = "Public", depth: int = 1) -> str:
    """
    Search the Mnemosyne knowledge graph for entities and their relationships.
    Use this to retrieve context about specific people, projects, or concepts.
    scopes: Comma-separated list of scopes to search (e.g., 'Private,Public').
    """
    scope_list = scopes.split(",") if scopes else ["Public"]
    node = gm.get_node(query, scopes=scope_list)
    if not node:
        return f"Concept '{query}' not found in memory (Scopes: {scopes})."
    
    # Build a readable summary of the node and its neighbors
    res = f"### [CONCEPT: {node['name']}]\n"
    props = {k: v for k, v in dict(node).items() if k not in ['name', 'last_seen', 'activation_level', 'labels']}
    if props:
        res += "Properties:\n"
        for k, v in props.items():
            res += f"  - {k}: {v}\n"
    
    neighbors = gm.get_neighbors(query, scopes=scope_list)
    if neighbors:
        limit = config.get("retrieval", {}).get("search_neighbors_limit", 10)
        res += "Related Context:\n"
        for n in neighbors[:limit]:
            res += f"  - {n['node']['name']} ({n['rel_type']})\n"
    
    return res

from butler.knowledge_queue import KnowledgeQueue
kq = KnowledgeQueue()

@mcp.tool()
def add_observation(content: str, scope: str = "Public") -> str:
    """
    Record a new piece of information into memory. 
    This triggers entity extraction and relationship mapping automatically via background workers.
    scope: The privacy scope for this observation (Private, Internal, Public).
    """
    try:
        obs_name = pm.create_observation(content, scope=scope)
        job_id = kq.enqueue(content, obs_name, scope=scope)
        return f"Observation recorded in scope '{scope}' and queued for semantic enrichment (Job ID: {job_id})."
    except Exception as e:
        return f"Error recording observation: {e}"

@mcp.tool()
def get_memory_briefing(scopes: str = "Public") -> str:
    """
    Get a briefing on currently active (hot) topics and proactive suggestions from The Butler.
    Useful at the start of a session or when feeling lost.
    scopes: Comma-separated list of scopes (e.g., 'Private,Public').
    """
    scope_list = scopes.split(",") if scopes else ["Public"]
    active_nodes = gm.get_active_nodes(threshold=0.7, scopes=scope_list)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]
    
    # The Butler's Proactive Voice
    briefing = f"Current active entities: {', '.join(hot_topics) if hot_topics else 'None'}\n"
    proactive_context = ie.get_proactive_context(scopes=scope_list)
    if proactive_context:
        briefing += f"\n#### The Butler's Internal Log:\n{proactive_context}\n"
        
    # Specific Suggestions
    suggestions = ie.generate_initiatives(scopes=scope_list)
    if suggestions:
        briefing += "\n#### The Butler's Suggestions:\n"
        for s in suggestions:
            briefing += f"- {s['message']} (Context: {s['reason']})\n"
            
    return briefing

@mcp.tool()
def get_system_status() -> str:
    """
    Checks the health of Mnemosyne's core components (Neo4j, Ollama).
    Returns a JSON string with connection status and graph statistics.
    """
    status = {
        "timestamp": datetime.now().isoformat(),
        "components": {
            "neo4j": "unknown",
            "ollama": "unknown"
        },
        "graph_stats": {
            "nodes": 0,
            "relationships": 0
        }
    }
    
    # Check Neo4j
    try:
        gm.verify_connection()
        status["components"]["neo4j"] = "connected"
        stats = gm.get_stats()
        status["graph_stats"] = stats
    except Exception as e:
        status["components"]["neo4j"] = f"error: {str(e)}"
        
    # Check Ollama/LLM
    try:
        # Simple generation check
        llm.generate("test")
        status["components"]["ollama"] = "connected" if config["llm"]["mode"] == "ollama" else "mock/start"
    except Exception as e:
        status["components"]["ollama"] = f"error: {str(e)}"
        
    return json.dumps(status, indent=2)

@mcp.tool()
def inspect_node_details(name: str) -> str:
    """
    Returns the raw internal metadata of a specific node in JSON format.
    Useful for debugging entity properties and labels.
    """
    node = gm.get_node(name)
    if not node:
        return json.dumps({"error": f"Node '{name}' not found"}, indent=2)
    
    # Convert Neo4j node to dict
    node_dict = dict(node)
    node_dict["labels"] = list(node.labels)
    return json.dumps(node_dict, indent=2)

@mcp.tool()
def get_recent_logs(lines: int = 20) -> str:
    """
    Retrieves the last N lines from the Mnemosyne debug log.
    Returns plain text.
    """
    log_path = "/tmp/mnemosyne.log"
    if not os.path.exists(log_path):
        return "Log file not found."
        
    try:
        # Simple tail implementation
        with open(log_path, 'r') as f:
            all_lines = f.readlines()
            last_n = all_lines[-lines:]
            return "".join(last_n)
    except Exception as e:
        return f"Error reading logs: {str(e)}"

@mcp.tool()
def provide_feedback(target_id: str, feedback_type: str, comment: str = "") -> str:
    """
    Log user or agent feedback about a specific entity or interaction.
    target_id: The name of the node or ID of the interaction.
    feedback_type: 'positive', 'negative', 'correction', 'missing_info'
    """
    # For now, just log it. Future: Store in a 'Feedback' node or dedicated DB.
    logger.info(f"FEEDBACK [{feedback_type}] for '{target_id}': {comment}")
    return json.dumps({"status": "received", "message": "Feedback logged successfully."}, indent=2)

async def background_gardener():
    """Periodically runs the gardener in the background."""
    interval = config.get("gardener", {}).get("interval_seconds", 3600)
    while True:
        try:
            logger.info("Background Gardener: Starting cycle...")
            # Run blocking gardener in a separate thread to avoid freezing the MCP server
            await asyncio.to_thread(gd.run_once)
            logger.info(f"Background Gardener: Cycle complete. Sleeping for {interval}s")
        except Exception as e:
            logger.error(f"Background Gardener Error: {e}")
        await asyncio.sleep(interval)

if __name__ == "__main__":
    async def run_server():
        # Create background task and run MCP together
        await asyncio.gather(
            background_gardener(),
            mcp.run_stdio_async()
        )
    
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
