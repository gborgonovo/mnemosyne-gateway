import os
import sys
import yaml
from neo4j import GraphDatabase

# Setup root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def main():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Remote values
    uri = "bolt://memory.giodalab.com:7687"
    user = "neo4j"
    password = "mnemosyne"

    print(f"Connecting to remote Neo4j at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    try:
        with driver.session() as session:
            print("Tagging all existing nodes with ':Public' label...")
            result = session.run("MATCH (n) SET n:Public RETURN count(n) as count")
            record = result.single()
            print(f"✅ Success! {record['count']} nodes updated to Public scope.")
            
            print("Checking total nodes...")
            result = session.run("MATCH (n:Public) RETURN count(n) as count")
            print(f"Nodes in Public scope: {result.single()['count']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    main()
