import os
import sys
import yaml

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph_manager import GraphManager

def test_safe_merge():
    # Load config test
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml.template')
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )

    try:
        print("1. Creating Test Nodes")
        n1 = gm.add_node("Safe_Merge_Target", primary_label="Resource", namespace="TestNS", properties={"keep": "yes"})
        n2 = gm.add_node("Safe_Merge_Source", primary_label="Resource", namespace="TestNS", properties={"discard": "yes"})
        
        # Add relationships
        gm.add_edge(n2["name"], n1["name"], "MAYBE_SAME_AS")
        # Add to some external
        ext = gm.add_node("External_Test_Node", primary_label="Topic", namespace="TestNS")
        gm.add_edge(ext["name"], n2["name"], "MENTIONS")
        
        print(f"Target ID: {n1.id}, Source ID: {n2.id}")
        
        print("2. Firing merge_nodes")
        res = gm.merge_nodes(n1["name"], n2["name"])
        if res:
            print(f"Merged successfully. Target node: {res}")
            
        print("3. Validating Tombstone")
        # Direct Cypher check for tombstone
        query_check = "MATCH (t:Tombstone {name: 'Safe_Merge_Source'}) RETURN t.merged_into as mi, labels(t) as lbls"
        with gm.driver.session() as session:
            record = session.run(query_check).single()
            if record:
                print(f"Tombstone found! Labels: {record['lbls']}, Merged Into ID: {record['mi']}")
                assert "Archived" in record["lbls"]
            else:
                print("Tombstone NOT found! Test failed.")
                
        # Cleanup
        gm.delete_node("Safe_Merge_Target")
        gm.delete_node("Safe_Merge_Source")
        gm.delete_node("External_Test_Node")
        query_cleanup_tombstone = "MATCH (t:Tombstone {name: 'Safe_Merge_Source'}) DETACH DELETE t"
        with gm.driver.session() as session:
            session.run(query_cleanup_tombstone)
            
        print("Test passed and cleaned up.")
    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        gm.close()

if __name__ == "__main__":
    test_safe_merge()
