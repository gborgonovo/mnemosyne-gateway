import requests
import time

def test_ingestion():
    # Write a dummy markdown file
    dummy_text = """# Il B&B di Giorgione
Questo è un documento su un B&B. Il B&B si chiama La Tettoia e ha un grande tetto.
Speriamo che il B&B stia andando bene.
"""
    with open("dummy_doc.txt", "w") as f:
        f.write(dummy_text)
        
    url = "http://127.0.0.1:4002/ingest"  # Use testing port if needed, or 4001
    
    with open("dummy_doc.txt", "rb") as f:
        files = {"file": ("dummy_doc.txt", f, "text/plain")}
        try:
             # Assume gateway might be on 4001 normally
             # Since it's local we'll just test the GraphManager directly first 
             # to avoid requiring the full server to be running in the background.
             print("Please run the gateway, or we can just test the GraphManager.")
        except Exception as e:
             pass

if __name__ == "__main__":
    print("Run `python3 scripts/manage_db.py wipe` then test graph directly.")
