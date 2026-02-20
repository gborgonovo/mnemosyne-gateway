import sys
import os
sys.path.append(os.getcwd())

from core.graph_manager import GraphManager
from core.attention import AttentionModel
import time

def test_core_logic():
    print("Initializing GraphManager...")
    # Using default credentials from docker-compose
    gm = GraphManager("bolt://localhost:7687", "neo4j", "mnemosyne")
    
    print("Cleaning database...")
    with gm.driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

    print("Creating nodes...")
    # Create specific nodes
    n1 = gm.add_node("Python", "Topic", tags=["Language"])
    n2 = gm.add_node("Mnemosyne", "Entity", tags=["Project"])
    n3 = gm.add_node("GraphDB", "Topic")

    print("Creating relationships...")
    # Mnemosyne DEPENDS_ON Python
    gm.add_edge("Mnemosyne", "Python", "DEPENDS_ON") 
    # Mnemosyne LINKED_TO GraphDB
    gm.add_edge("Mnemosyne", "GraphDB", "LINKED_TO")

    from core.event_bus import EventBus
    eb = EventBus()
    eb.start()

    print("Initializing AttentionModel...")
    am = AttentionModel(gm, config={"decay_rate": 0.1}, event_bus=eb)

    print("Testing Stimulation...")
    # Stimulate Mnemosyne
    am.stimulate(["Mnemosyne"], boost_amount=0.5)

    # Check activation
    mnemosyne = gm.get_node("Mnemosyne", scopes=["Public"])
    python = gm.get_node("Python", scopes=["Public"])
    print(f"Mnemosyne Activation: {mnemosyne['activation_level']}")
    print(f"Python Activation (should be > 0 due to propagation): {python.get('activation_level', 0)}")

    if python.get('activation_level', 0) > 0:
        print("SUCCESS: Propagation working.")
    else:
        print("FAILURE: Propagation not working.")

    print("Testing Decay...")
    old_val = mnemosyne['activation_level']
    am.apply_decay()
    new_val = gm.get_node("Mnemosyne", scopes=["Public"])['activation_level']
    print(f"Old: {old_val:.4f}, New: {new_val:.4f}")

    if new_val < old_val:
        print("SUCCESS: Decay working.")
    else:
         print("FAILURE: Decay not working.")

    eb.stop()
    gm.close()

if __name__ == "__main__":
    test_core_logic()
