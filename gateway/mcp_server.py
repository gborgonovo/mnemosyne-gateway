import asyncio
import sys
import os
import yaml
import logging
import json
import uuid
import re
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
from core.kuzu_manager import KuzuManager
from core.vector_store import VectorStore
from core.attention import AttentionModel
from workers.gardener import Gardener

# Configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

# Initialize Core Services (Reads only - Writes mostly go to FileSystem)
kuzu_mgr = KuzuManager(db_path=os.path.join(BASE_DIR, "data", "kuzu_db"))
vector_store = VectorStore(db_path=os.path.join(BASE_DIR, "data", "chroma_db"))
am = AttentionModel(kuzu_mgr, config=config.get('attention', {}))
gd = Gardener(am, config=config)

# Helper for local files
def get_file_path(name: str):
    # Basic sanitization
    safe_name = re.sub(r'[^\w\s-]', '', name).strip()
    return os.path.join(KNOWLEDGE_DIR, f"{safe_name}.md")

def read_markdown(name: str):
    path = get_file_path(name)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def write_markdown(name: str, frontmatter: dict, body: str):
    path = get_file_path(name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
        f.write("---\n\n")
        f.write(body)

# Create FastMCP Server
mcp = FastMCP("Mnemosyne-Memory")

@mcp.tool()
def trigger_gardening_cycle() -> str:
    """
    Manually trigger a gardening cycle to apply temporal decay to network heat.
    """
    gd.run_once()
    return "Gardening cycle completed successfully. Memory network heat decayed."

@mcp.tool()
def query_knowledge(query: str, limit: int = 3) -> str:
    """
    Semantic search of the Mnemosyne knowledge base.
    Returns the literal Markdown content of the most relevant files,
    reranked by their current cognitive heat (activation level) to provide the most relevant context.
    """
    # 1. Semantic Search
    results = vector_store.semantic_search(query, limit=limit * 2)
    
    if not results:
        return f"No concepts matching '{query}' found in memory."
        
    # 2. Thermal Re-ranking
    ranked_results = []
    for r in results:
        name = r['name']
        node_state = kuzu_mgr.get_node(name)
        heat = node_state['activation_level'] if node_state else 0.1
        # Score = Semantic Distance inverted (lower is closer) + Heat 
        # (This is a simplified reranking algorithm)
        combined_score = (1.0 / (r['distance'] + 0.001)) * (heat + 0.5)
        ranked_results.append((combined_score, name))
        
    ranked_results.sort(key=lambda x: x[0], reverse=True)
    
    # 3. Retrieve markdown content
    output = ""
    for score, name in ranked_results[:limit]:
        content = read_markdown(name)
        if content:
             output += f"### FILE: {name}.md (Relevance Score: {score:.2f})\n```markdown\n{content}\n```\n\n"
             # Simulate attention logic
             am.stimulate([name], boost_amount=0.5)
    
    return output

@mcp.tool()
def add_observation(content: str, scope: str = "Public") -> str:
    """
    Record a new raw piece of unstructured information into memory. 
    The background watcher will process it automatically.
    """
    obs_id = f"Obs_{uuid.uuid4().hex[:8]}"
    frontmatter = {"type": "Observation", "scope": scope}
    try:
        write_markdown(obs_id, frontmatter, content)
        return f"Observation recorded as {obs_id}.md in scope '{scope}'."
    except Exception as e:
        return f"Error recording observation: {e}"

@mcp.tool()
def get_memory_briefing() -> str:
    """
    Get a briefing on currently active (hot) topics in the system based on cognitive activation.
    """
    active_nodes = kuzu_mgr.get_active_nodes(threshold=0.5)
    
    if not active_nodes:
         return "The memory is currently resting. No active thoughts."
         
    # Sort by activation
    active_nodes.sort(key=lambda x: x['activation_level'], reverse=True)
    hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")][:10]
    
    briefing = f"Current active internal thoughts (Hot Nodes):\n"
    for title in hot_topics:
         # Read briefly from file
         content = read_markdown(title)
         preview = content[:150].replace('\n', ' ') + "..." if content else "File not found"
         briefing += f"- {title} (Context: {preview})\n"
            
    return briefing

@mcp.tool()
def get_system_status() -> str:
    """
    Checks the status of the hybrid architecture databases and file system.
    """
    status = {
        "timestamp": datetime.now().isoformat(),
        "architecture": "Hybrid File-First",
        "file_system": {
            "path": KNOWLEDGE_DIR,
            "markdown_files": len([f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith('.md')])
        },
        "kuzu_thermal_graph": {
            "active_nodes": len(kuzu_mgr.get_active_nodes(threshold=0.1))
        },
        "chromadb_semantic": {
            "total_documents": len(vector_store.list_nodes())
        }
    }
    return json.dumps(status, indent=2)

@mcp.tool()
def inspect_file_raw(name: str) -> str:
    """
    Read the direct markdown file from the file system.
    """
    content = read_markdown(name)
    if not content:
        return json.dumps({"error": f"File '{name}.md' not found"}, indent=2)
    return content

@mcp.tool()
def forget_knowledge_node(name: str) -> str:
    """
    Completely erases a concept by deleting its Markdown file.
    The background watcher will delete it from all databases.
    """
    path = get_file_path(name)
    if os.path.exists(path):
         os.remove(path)
         return json.dumps({"status": "success", "message": f"File '{name}.md' deleted."}, indent=2)
    return json.dumps({"status": "error", "message": f"File '{name}.md' not found."}, indent=2)

@mcp.tool()
def update_knowledge_frontmatter(name: str, updates: str) -> str:
    """
    Updates the YAML frontmatter properties of an existing entity.
    'updates' must be a JSON string of key-value pairs.
    """
    path = get_file_path(name)
    if not os.path.exists(path):
        return json.dumps({"status": "error", "message": f"Entity '{name}' not found."})
        
    try:
        properties_dict = json.loads(updates)
    except json.JSONDecodeError:
         return json.dumps({"error": "The 'updates' argument must be valid JSON."})
         
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        if yaml_match:
            frontmatter = yaml.safe_load(yaml_match.group(1)) or {}
            body = yaml_match.group(2)
        else:
            frontmatter = {}
            body = content
            
        # Update
        for k, v in properties_dict.items():
             frontmatter[k] = v
             
        write_markdown(name, frontmatter, body)
        return json.dumps({"status": "success", "message": f"File '{name}.md' frontmatter updated."})
    except Exception as e:
         return json.dumps({"error": str(e)})

@mcp.tool()
def create_goal(name: str, description: str = "", deadline: str = "", scopes: str = "Private,Public") -> str:
    """
    Creates a new high-level strategic Goal as a Markdown file.
    """
    scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
    frontmatter = {
         "type": "Goal",
         "status": "active",
         "scope": scope_list[0]
    }
    if deadline: frontmatter["deadline"] = deadline
    body = f"# {name}\n\n{description}"
    
    write_markdown(name, frontmatter, body)
    return json.dumps({"status": "success", "message": f"Goal '{name}' created."})

@mcp.tool()
def create_task(name: str, goal_name: str, description: str = "", due_date: str = "", scopes: str = "Private,Public") -> str:
    """
    Creates an actionable Task and links it to an existing Goal via wikilinks.
    """
    scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
    frontmatter = {
         "type": "Task",
         "status": "todo",
         "scope": scope_list[0]
    }
    if due_date: frontmatter["due_date"] = due_date
    
    body = f"# {name}\n\n**Linked Goal:** [[{goal_name}]]\n\n{description}"
    
    write_markdown(name, frontmatter, body)
    return json.dumps({"status": "success", "message": f"Task '{name}' created and linked to '{goal_name}'."})

@mcp.tool()
def update_task_status(name: str, status: str) -> str:
    """
    Updates the status of a Task or Goal. Valid: 'todo', 'in_progress', 'done', 'discarded' 
    """
    return update_knowledge_frontmatter(name, json.dumps({"status": status}))

async def background_gardener():
    """Periodically runs the gardener to trigger thermodynamic sleep in KuzuDB."""
    interval = config.get("gardener", {}).get("interval_seconds", 3600)
    while True:
        try:
            logger.info("Background Gardener: Starting cycle...")
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
