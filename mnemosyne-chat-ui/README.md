# Mnemosyne Chat UI

Interfaccia conversazionale basata su Streamlit per Mnemosyne Gateway.

## Avvio Locale
Per lo sviluppo o l'uso locale:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
L'app sarà disponibile su `http://localhost:8501/chat` (per via della configurazione `baseUrlPath` in `.streamlit/config.toml`).

---

## Deploy in Produzione (memory.borgonovo.org/chat)

Per funzionare correttamente sotto un sotto-dominio come `/chat`, Streamlit necessita di inoltrare il traffico HTTP e il traffico WebSocket (usato per l'aggiornamento in tempo reale dell'interfaccia) tramite un Reverse Proxy come Nginx.

### 1. Avvio del servizio (Systemd)
In produzione, fai partire l'applicazione tramite un servizio `systemd` (o Docker/PM2) che esegua lo script di avvio sulla porta `8501`.
```bash
# Esempio di comando di avvio per producción
# Dalla cartella mnemosyne-chat-ui
source .venv/bin/activate
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### 2. Configurazione NGINX
Aggiungi questo blocco `location` all'interno del blocco `server` che gestisce il tuo dominio `memory.borgonovo.org` nel file di configurazione di Nginx (di solito in `/etc/nginx/sites-available/...`):

```nginx
    # Configurazione per Mnemosyne Chat UI
    location /chat/ {
        proxy_pass http://127.0.0.1:8501/chat/;
        
        # Gestione WebSocket vitale per Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Headers standard
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Disabilita il buffering (migliora la risposta in streaming dell'LLM)
        proxy_buffering off;
        
        # Timeout per evitare disconnessioni se l'LLM è lento a rispondere
        proxy_read_timeout 86400;
    }
```

Riavvia nginx (`sudo systemctl restart nginx`) e l'interfaccia sarà raggiungibile su:
**https://memory.borgonovo.org/chat**
