# Integrazione Mnemosyne per ChatGPT Custom GPTs

Questo documento fornisce le istruzioni e gli schemi necessari per collegare la tua istanza privata di Mnemosyne a un GPT personalizzato su ChatGPT.

---

## 🚀 1. Strategia di Deployment (VPS + Nginx)

Per un'integrazione stabile, si consiglia di ospitare Mnemosyne su una VPS con **IP statico** e **dominio**.

### Requisiti

1. Una VPS (Ubuntu 22.04+ consigliata).
2. Un dominio o sottodominio (es. `memoria.tuodominio.it`).
3. Certificato SSL (Let's Encrypt).

### Configurazione Nginx (Reverse Proxy)

Crea un file in `/etc/nginx/sites-available/mnemosyne`:

```nginx
server {
    server_name memoria.tuodominio.it;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl; # Gestito da Certbot
}
```

### Configurazione Apache (Reverse Proxy)

Assicurati di aver abilitato i moduli `proxy` e `proxy_http` (`a2enmod proxy proxy_http`).
Crea un file in `/etc/apache2/sites-available/mnemosyne.conf`:

```apache
<VirtualHost *:443>
    ServerName memoria.tuodominio.it

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    # ... configurazione SSL (Certbot) ...
</VirtualHost>
```

---

## 🔑 2. Sicurezza (API Key)

Poiché Mnemosyne sarà esposta pubblicamente, la protezione tramite API Key è obbligatoria per impedire accessi non autorizzati al tuo grafo.

### Generazione della Chiave

Puoi generare una chiave sicura direttamente dal tuo terminale:

```bash
openssl rand -hex 32
```

### Configurazione sul Server

Inserisci la chiave nel file `config/settings.yaml` della tua istanza Mnemosyne (nella sezione dedicata alla sicurezza):

```yaml
security:
  api_key: "LA_TUA_CHIAVE_SICURA_GENERATA"
```

### Configurazione su ChatGPT

Nell'interfaccia di creazione del GPT, vai su **Configure** -> **Actions** -> **Authentication**:

- **Authentication Type**: `API Key`
- **Auth Type**: `Custom`
- **Header Name**: `X-API-Key`
- **Value**: La tua chiave (es. `LA_TUA_CHIAVE_SICURA_GENERATA`).

---

## 🛠️ 3. Schema OpenAPI (YAML)

Copia e incolla questo schema nella sezione "Actions" del tuo GPT.
**IMPORTANTE**: Sostituisci `https://memoria.tuodominio.it` con il tuo URL reale.

```yaml
openapi: 3.1.0
info:
  title: Mnemosyne Memory API
  description: Interfaccia per la memoria cognitiva a lungo termine di Mnemosyne.
  version: 1.0.0
servers:
  - url: https://memoria.tuodominio.it
    description: La tua istanza privata di Mnemosyne
paths:
  /search:
    get:
      operationId: searchMemory
      summary: Cerca concetti o ricordi nel grafo
      parameters:
        - name: q
          in: query
          required: true
          schema:
            type: string
          description: Il termine di ricerca o il concetto da trovare.
      responses:
        '200':
          description: Risultati della ricerca semantica
  /add:
    post:
      operationId: addObservation
      summary: Aggiungi un nuovo ricordo o informazione alla memoria
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                content:
                  type: string
                  description: Il testo dell'informazione da memorizzare.
      responses:
        '200':
          description: Informazione memorizzata con successo
  /briefing:
    get:
      operationId: getBriefing
      summary: Ottieni il contesto proattivo e i suggerimenti di The Butler
      responses:
        '200':
          description: Sintesi dello stato attuale del grafo
```

---

## 💡 4. Istruzioni per il GPT (System Prompt)

Configura il tuo GPT con queste istruzioni per massimizzare l'efficacia:

> "Sei un assistente potenziato da Mnemosyne, il mio cervello digitale esterno.
>
> 1. **Prima di rispondere**: Se l'utente fa riferimento a progetti passati, persone o concetti specifici, usa `searchMemory` per recuperare il contesto.
> 2. **Durante la conversazione**: Se l'utente condivide informazioni importanti, decisioni o nuovi task, usa `addObservation` per salvarli.
> 3. **Proattività**: Utilizza `getBriefing` esclusivamente nei seguenti scenari:
>    - All'inizio di una nuova sessione o di un nuovo argomento per "riscaldare" il contesto.
>    - Se avverti uno stallo nella conversazione o se l'utente chiede "di cosa dovremmo parlare?".
>    - Subito dopo aver memorizzato un'informazione critica, per vedere se Mnemosyne rileva conflitti o suggerimenti proattivi.
>
> Non dire mai 'Sto cercando nel database', agisci in modo naturale come se la tua memoria fosse stata appena rinfrescata."
