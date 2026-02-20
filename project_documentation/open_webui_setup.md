# Configurazione Mnemosyne per Open WebUI

Questa guida spiega come integrare Mnemosyne Gateway all'interno di **Open WebUI** utilizzando una "Function" (Filtro).

## 1. Installazione della Function

1. Accedi a Open WebUI come amministratore.
2. Vai in **Workspace** -> **Functions**.
3. Clicca su **+ Create Function**.
4. Copia e incolla il contenuto del file `integrations/open_webui/mnemosyne_function.py`.
5. Clicca su **Save**.

## 2. Configurazione (Valves)

Una volta salvata, clicca sull'icona delle impostazioni (ingranaggio) della funzione per configurare i parametri:

- **Mnemosyne URL**: Imposta l'indirizzo del tuo Gateway (es. `http://host.docker.internal:8000` se corre su Docker).
- **Enable Search**: Se attivo, Mnemosyne inietterà il contesto ad ogni messaggio.
- **Enable Learning**: Se attivo, cercherà il tag `#memo` per salvare i dati.

## 3. Strategia di Apprendimento Ibrida

Hai due modi per far imparare Mnemosyne su Open WebUI:

### A. Manuale

Aggiungi `#memo` alla tua richiesta o chiedi espressamente all'assistente di includerlo se ritiene la cosa importante.

### B. Autonoma (via System Prompt)

Per rendere l'assistente capace di decidere cosa salvare, aggiungi questa frase al **System Prompt** del tuo modello o nelle **Personal Instructions**:

> "Se ritieni che questa conversazione contenga informazioni importanti, progetti o decisioni da ricordare a lungo termine, inserisci alla fine della tua risposta il tag `#memo`. Mnemosyne salverà automaticamente queste informazioni nel tuo Connectome."

## 5. Verifica Manuale via Browser

Prima di impazzire con la configurazione di Open WebUI, puoi verificare se il Gateway funziona correttamente aprendo questi indirizzi nel tuo browser (assumendo la porta 4001):

- **Stato Core**: [http://localhost:4001/status](http://localhost:4001/status) (Verifica connessione Neo4j e LLM)
- **Briefing**: [http://localhost:4001/briefing](http://localhost:4001/briefing) (Vedi i temi caldi e i suggerimenti del Butler)
- **Documentazione API**: [http://localhost:4001/docs](http://localhost:4001/docs) (Interfaccia Swagger per testare tutti i comandi)

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
