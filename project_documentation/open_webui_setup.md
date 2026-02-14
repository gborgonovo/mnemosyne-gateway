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

## 4. Risultato

Quando il tag `#memo` viene rilevato:

1. Mnemosyne Gateway riceve il testo e lo indicizza nel Grafo.
2. Il tag `#memo` viene **rimosso** dalla risposta visualizzata, lasciando l'interfaccia pulita.
