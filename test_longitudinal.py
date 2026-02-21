import sys
import os
import yaml
from pprint import pprint

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.graph_manager import GraphManager

def main():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    gm = GraphManager(
        config['graph']['uri'], 
        config['graph']['user'], 
        config['graph']['password']
    )

    print("Adding test dormant project...")
    gm.add_node("Test_Dormant_Project", primary_label="Goal")

    query = """
    MATCH (n {name: 'Test_Dormant_Project'})
    SET n.last_seen = toString(datetime() - duration({days: 40}))
    RETURN n
    """
    with gm.driver.session() as session:
        session.run(query)

    gm.add_node("Fake_Dep_1", primary_label="Topic")
    gm.add_node("Fake_Dep_2", primary_label="Topic")
    gm.add_node("Fake_Dep_3", primary_label="Topic")
    gm.add_edge("Test_Dormant_Project", "Fake_Dep_1", "LINKED_TO")
    gm.add_edge("Test_Dormant_Project", "Fake_Dep_2", "LINKED_TO")
    gm.add_edge("Test_Dormant_Project", "Fake_Dep_3", "LINKED_TO")

    print("\nChecking for dormant projects...")
    dormant = gm.get_dormant_projects(threshold_days=30, limit=5)
    print("Dormant Projects Found:")
    pprint(dormant)

    print("\nChecking temporal trends...")
    trends = gm.get_temporal_trends(days_ago=7, limit=5)
    print("Temporal Trends Found:")
    pprint(trends[:3]) # Limit print

    print("\nCleaning up...")
    query = """
    MATCH (n) WHERE n.name STARTS WITH 'Test_Dormant' OR n.name STARTS WITH 'Fake_Dep'
    DETACH DELETE n
    """
    with gm.driver.session() as session:
        session.run(query)
    print("Cleanup done.")

if __name__ == "__main__":
    main()
