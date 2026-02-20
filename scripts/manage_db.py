import os
import sys
import yaml
import argparse
from neo4j import GraphDatabase
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def clear_db(driver):
    confirm = input("⚠️  Are you sure you want to clear the entire database? (y/N): ")
    if confirm.lower() == 'y':
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("✅ Database cleared.")
    else:
        print("Operation cancelled.")

def backup_db(driver, filename):
    print(f"📦 Exporting database to {filename}...")
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    # Note: This is a simple export for Mnemosyne nodes and relationships.
    # For a full industrial backup, use 'neo4j-admin dump' on the Docker volume.
    try:
        with driver.session() as session:
            # Export nodes
            nodes_result = session.run("MATCH (n) RETURN n, labels(n) as labels")
            nodes = [record.data() for record in nodes_result]
            
            # Export edges
            edges_result = session.run("MATCH (n)-[r]->(m) RETURN n.name as start, m.name as end, type(r) as type, r as props")
            edges = [record.data() for record in edges_result]
            
            import json
            data = {
                "timestamp": datetime.now().isoformat(),
                "nodes": nodes,
                "edges": edges
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Backup complete: {len(nodes)} nodes, {len(edges)} relations exported.")
    except Exception as e:
        print(f"❌ Backup failed: {e}")

def restore_db(driver, filename):
    print(f"📥 Restoring database from {filename}...")
    import json
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            
        with driver.session() as session:
            # Optional: Clear before restore
            # session.run("MATCH (n) DETACH DELETE n")
            
            for n in data['nodes']:
                node = n['n']
                labels = ":".join(n['labels'])
                session.run(f"MERGE (n {{name: $name}}) SET n:{labels}, n += $props", 
                           name=node['name'], props=node)
                
            for e in data['edges']:
                session.run("""
                    MATCH (a {name: $start}), (b {name: $end})
                    MERGE (a)-[r:%s]->(b)
                    SET r += $props
                """ % e['type'], start=e['start'], end=e['end'], props=e['props'])
                
        print("✅ Restore complete.")
    except Exception as e:
        print(f"❌ Restore failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mnemosyne Connectome Manager")
    parser.add_argument("action", choices=["clear", "backup", "restore"], help="Action to perform")
    parser.add_argument("--file", default="data/backup_connectome.json", help="Backup file path")
    
    args = parser.parse_args()
    config = load_config()
    
    driver = GraphDatabase.driver(
        config['graph']['uri'], 
        auth=(config['graph']['user'], config['graph']['password'])
    )
    
    try:
        if args.action == "clear":
            clear_db(driver)
        elif args.action == "backup":
            backup_db(driver, args.file)
        elif args.action == "restore":
            restore_db(driver, args.file)
    finally:
        driver.close()
