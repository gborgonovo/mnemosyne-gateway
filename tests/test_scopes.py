import sys
import os
sys.path.append(os.getcwd())

from core.graph_manager import GraphManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_scope_isolation():
    print("Initializing GraphManager for Scope Test...")
    gm = GraphManager("bolt://localhost:7687", "neo4j", "mnemosyne")
    
    print("Cleaning database...")
    with gm.driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

    print("Creating nodes with different scopes...")
    gm.add_node("PublicNode", scope="Public")
    gm.add_node("InternalNode", scope="Internal")
    gm.add_node("PrivateNode", scope="Private")

    # 1. Test "Public" Scope view
    print("\n--- Testing Public Scope ---")
    nodes = gm.get_all_nodes(scopes=["Public"])
    names = [n['name'] for n in nodes]
    print(f"Visible nodes: {names}")
    assert "PublicNode" in names
    assert "InternalNode" not in names
    assert "PrivateNode" not in names
    print("SUCCESS: Public scope restricted correctly.")

    # 2. Test "Internal" Scope view (should see Public too)
    print("\n--- Testing Internal Scope ---")
    nodes = gm.get_all_nodes(scopes=["Internal"])
    names = [n['name'] for n in nodes]
    print(f"Visible nodes: {names}")
    assert "PublicNode" in names
    assert "InternalNode" in names
    assert "PrivateNode" not in names
    print("SUCCESS: Internal scope sees Public + Internal.")

    # 3. Test "Private" Scope view (should see all)
    print("\n--- Testing Private Scope ---")
    nodes = gm.get_all_nodes(scopes=["Private"])
    names = [n['name'] for n in nodes]
    print(f"Visible nodes: {names}")
    assert "PublicNode" in names
    assert "InternalNode" in names
    assert "PrivateNode" in names
    print("SUCCESS: Private scope sees all.")

    gm.close()

if __name__ == "__main__":
    try:
        test_scope_isolation()
        print("\n🎉 ALL SCOPE TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
