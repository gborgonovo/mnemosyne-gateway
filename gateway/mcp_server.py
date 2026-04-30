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
kuzu_mgr = KuzuManager(db_path=os.path.join(BASE_DIR, "data", "kuzu_main"))
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

from gateway.mcp_app import create_mcp_server

# Create FastMCP Server using the shared factory
mcp = create_mcp_server(kuzu_mgr, vector_store, am, gd, config, KNOWLEDGE_DIR)

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
