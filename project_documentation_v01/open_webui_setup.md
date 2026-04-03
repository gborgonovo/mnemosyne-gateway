# Configurazione Mnemosyne per Open WebUI

Questa guida spiega come integrare Mnemosyne Gateway all'interno di **Open WebUI** utilizzando una "Function" (Filtro).

## 1. Installazione del Filtro (Memoria Passiva)

Il filtro agisce silenziosamente in background, iniettando il contesto quando l'utente parla e salvando le memorie dopo che l'AI ha risposto.

1. Accedi a Open WebUI come amministratore.
2. Vai in **Workspace** -> **Functions**.
3. Clicca su **+ Create Function**.
4. Copia e incolla il contenuto del file `integrations/open_webui/mnemosyne_function.py`.
5. Clicca su **Save**.

## 2. Configurazione (Valves) del Filtro

Una volta salvata, clicca sull'icona delle impostazioni (ingranaggio) della funzione per configurare i parametri:

- **Mnemosyne URL**: Imposta l'indirizzo del tuo Gateway (es. `http://host.docker.internal:4001` - la porta di default è 4001).
- **Project Context**: Una categoria opzionale (es. "Progetto Ganaghello") che verrà aggiunta a tutti i tuoi messaggi per organizzare le memorie all'interno di un'area semantica specifica.
- **Enable Search** & **Search Context Limit**: Controlla come e quanto Mnemosyne inietta memorie passate nella chat corrente, con un limite massimo di caratteri per non sovraccaricare i modelli locali.
- **Enable Continuous Learning**: Se attivo, il sistema apprende continuamente dalle tue conversazioni in background.
- **Incognito Command**: Scrivi questo comando (default: `/incognito`) in qualsiasi punto della chat per sospendere la registrazione e il recupero della memoria per l'intera durata della sessione corrente.

## 3. Installazione del Tool (Ricerca Attiva)

Mentre il filtro inietta passivamente i "temi caldi" e il contesto correlato, il tool permette all'AI di interrogare autonomamente Mnemosyne quando si accorge di aver bisogno di informazioni specifiche del passato.

1. Vai in **Workspace** -> **Tools**.
2. Clicca su **+ Create Tool**.
3. Copia e incolla il contenuto del file `integrations/open_webui/mnemosyne_tool.py`.
4. Abilita il tool per i tuoi modelli LLM.
5. Se un utente fa una domanda complessa su eventi passati, l'AI potrà chiamare `search_memory(query, project_context)` per recuperare i dettagli esatti prima di generare una risposta.

## 5. Verifica Manuale via Browser

Prima di impazzire con la configurazione di Open WebUI, puoi verificare se il Gateway funziona correttamente aprendo questi indirizzi nel tuo browser (assumendo la porta 4001):

- **Stato Core**: [http://localhost:4001/status](http://localhost:4001/status) (Verifica connessione Neo4j ed EventBus)
- **Briefing**: [http://localhost:4001/briefing](http://localhost:4001/briefing) (Vedi i temi caldi generati dal `BriefingWorker`)
- **Documentazione API**: [http://localhost:4001/docs](http://localhost:4001/docs) (Interfaccia Swagger per testare scopes e promotion)

Se questi link non funzionano, il problema è nel Gateway. Se funzionano ma Open WebUI non vede nulla, il problema è nella rete/Docker.

## 6. Risoluzione dei Problemi

Se Open WebUI non riceve il contesto:

1. **Verifica il Log**: Controlla il file `/tmp/mnemosyne.log` sul server Mnemosyne. Dovresti vedere le chiamate `GET /briefing` ogni volta che invii un messaggio.
2. **Porta del Gateway**: Assicurati che il Gateway stia girando sulla porta **4001** (come definito in `settings.yaml`).
3. **Indirizzo di Rete**: Se Open WebUI gira in Docker, usa `http://host.docker.internal:4001`.
   - **Fix per Linux**: Su Linux, `host.docker.internal` non è risolto automaticamente. Devi avviare il container di Open WebUI aggiungendo questa opzione al comando `docker run`:
     `--add-host=host.docker.internal:host-gateway`
     (O se usi `docker-compose`, aggiungi `extra_hosts: ["host.docker.internal:host-gateway"]`).
4. **Enable Search**: Verifica che l'interruttore "Enable Search" nelle impostazioni della funzione su Open WebUI sia attivo.
