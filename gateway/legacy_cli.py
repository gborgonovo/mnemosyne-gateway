import argparse
import sys
import os
import yaml
import json
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph_manager import GraphManager
from core.llm import get_llm_provider
from core.perception import PerceptionModule
from core.attention import AttentionModel
from core.initiative import InitiativeEngine

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

async def main():
    parser = argparse.ArgumentParser(description="Mnemosyne Legacy CLI for OpenClaw Integration")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search Command
    search_parser = subparsers.add_parser("search", help="Search the knowledge graph")
    search_parser.add_argument("query", type=str, help="The query string")

    # Add Command
    add_parser = subparsers.add_parser("add", help="Add an observation")
    add_parser.add_argument("content", type=str, help="The observation content")

    # Briefing Command
    subparsers.add_parser("briefing", help="Get a memory briefing")

    # Status Command
    subparsers.add_parser("status", help="Check system status and health")

    # History Command
    subparsers.add_parser("history", help="Show recently updated memories")

    args = parser.parse_args()
    config = load_config()

    # Initialize Core Components
    # Note: For CLI, we might want faster initialization or lazy loading if possible, 
    # but for now we init everything to ensure full functionality.
    try:
        gm = GraphManager(
            config['graph']['uri'], 
            config['graph']['user'], 
            config['graph']['password']
        )
        llm = get_llm_provider(config)
        am = AttentionModel(gm, config=config.get('attention', {}))
        pm = PerceptionModule(gm, llm, am)
        ie = InitiativeEngine(gm, config=config.get('initiative', {}))
    except Exception as e:
        print(f"Error initializing Mnemosyne: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "search":
        print(f"🔍 Searching for '{args.query}'...")
        node = gm.get_node(args.query)
        if node:
            print(f"### [CONCEPT: {node['name']}]")
            props = {k: v for k, v in dict(node).items() if k not in ['name', 'last_seen', 'activation_level', 'labels']}
            for k, v in props.items():
                print(f"  - {k}: {v}")
            
            neighbors = gm.get_neighbors(args.query)
            if neighbors:
                print("\nRelated Context:")
                for n in neighbors[:10]:
                    print(f"  - {n['node']['name']} ({n['rel_type']})")
        else:
            print(f"Concept '{args.query}' not found in memory.")

    elif args.command == "add":
        print(f"📝 Adding observation: '{args.content}'")
        entities = pm.process_input(args.content)
        if entities:
            print(f"✅ Observation recorded. Extracted entities: {', '.join(entities)}")
        else:
            print("✅ Observation recorded (no specific entities extracted).")

    elif args.command == "briefing":
        print("💡 Generating briefing...")
        active_nodes = gm.get_active_nodes(threshold=0.7)
        hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")]
        
        print("### MNEMOSYNE MEMORY BRIEFING")
        if hot_topics:
            print(f"Active topics: {', '.join(hot_topics)}")
        
        proactive_context = ie.get_proactive_context()
        if proactive_context:
            print(f"\n#### Alfred's Log:\n{proactive_context}")
            
        suggestions = ie.generate_initiatives()
        if suggestions:
            print("\n#### Suggestions:")
            for s in suggestions:
                print(f"- {s['message']}")

    elif args.command == "status":
        print("🩺 Mnemosyne System Status")
        print("-" * 30)
        
        # Neo4j Check
        try:
            gm.verify_connection()
            stats = gm.get_stats()
            print(f"✅ Neo4j: Connected ({stats['nodes']} nodes, {stats['relationships']} relationships)")
        except Exception as e:
            print(f"❌ Neo4j: Error - {e}")

        # LLM Check
        try:
            llm.generate("test")
            mode = config.get("llm", {}).get("mode", "unknown")
            print(f"✅ LLM: Connected (Mode: {mode})")
        except Exception as e:
            print(f"❌ LLM: Error - {e}")

    elif args.command == "history":
        print("🕒 Recent Memory Activity (Last 10 entries)")
        print("-" * 45)
        
        # Query for most recently seen nodes
        query = """
        MATCH (n) 
        WHERE n.last_seen IS NOT NULL
        RETURN n.name as name, labels(n)[0] as label, n.last_seen as last_seen
        ORDER BY n.last_seen DESC 
        LIMIT 10
        """
        try:
            with gm.driver.session() as session:
                result = session.run(query)
                for record in result:
                    dt = record["last_seen"]
                    # Format timestamp for readability
                    print(f"[{dt}] {record['name']} ({record['label']})")
        except Exception as e:
            print(f"Error retrieving history: {e}")

if __name__ == "__main__":
    asyncio.run(main())
