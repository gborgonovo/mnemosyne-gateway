import requests
import time
import subprocess
import os
import signal
import json

def test_phase3_features():
    print("🚀 Starting Phase 3: Collective Cognition & Private Pools Test")
    
    # 1. Start Workers
    print("Starting LLMWorker...")
    llm_proc = subprocess.Popen(
        [".venv/bin/python3", "workers/llm_worker.py"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid
    )
    
    print("Starting BriefingWorker...")
    brief_proc = subprocess.Popen(
        [".venv/bin/python3", "workers/briefing_worker.py"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid
    )
    
    time.sleep(10) # Wait for registration

    try:
        # 2. Add Private knowledge
        unique_id = str(time.time())[-6:]
        print(f"Adding Private knowledge with ID: {unique_id}...")
        requests.post("http://localhost:4001/add", params={"scope": "Private"}, json={
            "content": f"L'antidoto segreto per il virus è KRYPTON_{unique_id}."
        })
        
        # 3. Add Public knowledge
        print("Adding Public knowledge...")
        requests.post("http://localhost:4001/add", params={"scope": "Public"}, json={
            "content": f"Mnemosyne_{unique_id} è un software open source."
        })

        time.sleep(20) # Wait for enrichment

        # 4. Verify Isolation
        print("\n--- Verifying Scope Isolation ---")
        # Find the entity name in Private scope
        private_terms = [f"krypton_{unique_id}"]
        found_entity = None
        for term in private_terms:
            resp = requests.get("http://localhost:4001/search", params={"q": term, "scopes": "Private"})
            if resp.status_code == 200:
                found_entity = term
                break
        
        if not found_entity:
             print("❌ FAILURE: Could not find any private entities.")
             # Diagnostics: What nodes DO exist in Private?
             resp = requests.get("http://localhost:4001/history") 
             history = resp.json().get('history', [])
             print(f"DEBUG: Recent nodes: {history}")
             
             # Dynamic discovery from history
             for record in history:
                 name = record['name']
                 if any(term in name.lower() for term in private_terms) and not name.startswith("Obs_"):
                     found_entity = name
                     break
        
        if not found_entity:
             print("❌ FAILURE: Extraction seems to have produced no matching entities.")
        else:
             # Progress with found_entity
            print(f"Found private entity: {found_entity}")
            # Verify it's NOT in Public
            resp = requests.get("http://localhost:4001/search", params={"q": found_entity, "scopes": "Public"})
            if resp.status_code == 404:
                print(f"✅ SUCCESS: Private node '{found_entity}' invisible to Public scope.")
            else:
                print(f"❌ FAILURE: Private node '{found_entity}' visible to Public scope!")

            # Verify it IS in Private
            resp = requests.get("http://localhost:4001/search", params={"q": found_entity, "scopes": "Private"})
            if resp.status_code == 200:
                print(f"✅ SUCCESS: Private node '{found_entity}' visible to Private scope.")

        # 5. Verify Collective Initiative (BriefingWorker)
        print("\n--- Verifying BriefingWorker suggestions ---")
        # Trigger activation peak
        requests.get("http://localhost:4001/search", params={"q": "Mnemosyne", "scopes": "Public"})
        time.sleep(5)
        
        resp = requests.get("http://localhost:4001/briefing", params={"scopes": "Public"})
        data = resp.json()
        print(f"Briefing suggestions: {data['suggestions']}")
        # BriefingWorker should have sent suggestions via INITIATIVE_READY
        if data['suggestions']:
            print("✅ SUCCESS: Received distributed suggestions.")
        else:
            print("⚠️ WARNING: No suggestions received (might be due to default config/thresholds).")

        # 6. Test Knowledge Sharing (Promotion)
        print("\n--- Testing Knowledge Sharing ---")
        if found_entity:
            requests.post("http://localhost:4001/share", params={
                "node_name": found_entity, 
                "from_scope": "Private", 
                "to_scope": "Public"
            })
            
            # Verify it's now public
            resp = requests.get("http://localhost:4001/search", params={"q": found_entity, "scopes": "Public"})
            if resp.status_code == 200:
                print("✅ SUCCESS: Knowledge promoted to Public scope.")
            else:
                print("❌ FAILURE: Knowledge promotion failed.")
        else:
            print("⏩ SKIPPED: Knowledge sharing test (no entity found).")

    finally:
        print("\nCleaning up...")
        os.killpg(os.getpgid(llm_proc.pid), signal.SIGTERM)
        os.killpg(os.getpgid(brief_proc.pid), signal.SIGTERM)
        print("Test complete.")

if __name__ == "__main__":
    test_phase3_features()
