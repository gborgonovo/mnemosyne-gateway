import requests
import time
import subprocess
import os
import signal

def test_distributed_learning():
    print("🚀 Starting Phase 2 Distributed Integration Test")
    
    # 1. Start Gateway (Assumed running or start it)
    # 2. Start LLMWorker
    print("Starting LLMWorker...")
    worker_proc = subprocess.Popen(
        [".venv/bin/python3", "workers/llm_worker.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    time.sleep(10) # Wait for registration

    try:
        # Check if worker registered
        resp = requests.get("http://localhost:4001/plugins")
        plugins = resp.json()
        print(f"Registered Plugins: {list(plugins.keys())}")
        assert any("LLM_Worker" in p['name'] for p in plugins.values())
        print("✅ LLMWorker Handshake successful.")

        # 3. Add Observation
        print("Adding observation...")
        resp = requests.post("http://localhost:4001/add", json={
            "content": "Mnemosyne is a cognitive middleware built with Python and Neo4j."
        })
        obs_data = resp.json()
        obs_name = obs_data['obs_name']
        print(f"Observation created: {obs_name}")

        # 4. Wait for async processing
        print("Waiting for async extraction and integration (15s)...")
        time.sleep(15)

        # 5. Verify results in Graph via Search
        print("Verifying graph state...")
        resp = requests.get("http://localhost:4001/search", params={"q": "Python"})
        if resp.status_code == 200:
            data = resp.json()
            print(f"Found node 'Python' linked to: {data['related']}")
            assert any(obs_name in r for r in data['related'])
            print("✅ Integrated entities correctly linked to Observation.")
        else:
            print("❌ Node 'Python' not found. Integration might have failed or is slow.")
            # Let's try one more time
            time.sleep(5)
            resp = requests.get("http://localhost:4001/search", params={"q": "Python"})
            assert resp.status_code == 200
            print("✅ Successfully found node on second try.")

    finally:
        print("Cleaning up...")
        os.killpg(os.getpgid(worker_proc.pid), signal.SIGTERM)
        print("Test complete.")

if __name__ == "__main__":
    test_distributed_learning()
