# Guida all'Utente: Mnemosyne & The Butler

Benvenuto in **Mnemosyne**, il tuo partner cognitivo locale. Questa guida ti aiuterà a navigare nell'interfaccia e a sfruttare al meglio le capacità di The Butler, il layer relazionale del sistema.

## 🚀 Avvio Rapido

L'applicazione si basa su componenti core che devono essere attivi:

1. **Neo4j**: Il database a grafo (Connectome).
2. **Ollama**: Il motore di inferenza locale.
3. **Mnemosyne Gateway**: Il server FastAPI che fa da hub distribuito.

Mnemosyne è ora un sistema distribuito. Per avviare il Gateway e tutti i worker in background in modo sicuro (senza che si chiudano con il terminale), esegui dalla cartella principale:

```bash
./scripts/start.sh
```

Questo avvierà:

1. **Il Gateway** (in ascolto sulla porta 4001).
2. **L'LLM Worker** (per l'estensione semantica asincrona).
3. **Il Briefing Worker** (per le iniziative proattive).

Per fermare il sistema, esegui:

```bash
./scripts/stop.sh
```

### D. Configurazione e Segreti (.env)

Mnemosyne utilizza un file `.env` (opzionale ma consigliato) per gestire le chiavi sensibili come `OPENAI_API_KEY`.

**Configurazione rapida**:
Crea un file chiamato `.env` nella cartella principale e aggiungi la tua chiave:

```bash
OPENAI_API_KEY=tua_chiave_openai_qui
```

**Ricerca Vettoriale**:
Se vuoi abilitare la ricerca per similarità semantica, modifica `config/settings.yaml` impostando `enable_embeddings: true`. Assicurati di avere il modello necessario scaricato in Ollama (es. `ollama pull nomic-embed-text`).

### A. Tramite App Esterne (OpenClaw, Open WebUI)

Questa è la modalità principale. Usando lo **HTTP Bridge**, le tue app preferite interrogano Mnemosyne in background.

- L'agente riceve automaticamente i briefing.
- Ogni tua parola viene memorizzata nel grafo senza che tu debba fare nulla.

### B. Tramite la Dashboard (Streamlit)

Usa la dashboard per una gestione visiva del "cervello":

- **Tab Chat**: Per interagire direttamente con The Butler.
- **Tab Connectome**: Per esplorare graficamente le relazioni calde e stimolare nodi specifici.
- **Tab Gardener**: Per la manutenzione del grafo e il merge dei duplicati.
- **Tab Documents**: Per caricare nuovi file e gestire l'archivio fisico.

### C. Tramite CLI (Manuale)

Per operazioni rapide o per alimentare il sistema via script:

```bash
python3 gateway/legacy_cli.py add "Nuova osservazione"
```

---

## 🕸️ 2. Esplorazione del Connectome (Tab "Connectome")

In questa sezione puoi osservare e influenzare lo stato "termico" della tua memoria digitale tramite un **Grafo Dinamico**.

- **Grafo Visuale (Plotly)**: Digita il nome di un concetto nella barra di ricerca per centrare il grafo. Vedrai i nodi correlati e la forza dei loro legami.
- **Ricerca Semantica & Ibrida**: La ricerca di Mnemosyne è ora resiliente. Se cerchi un termine che non esiste esattamente (es. "prezzo" invece di "listino"), il sistema scala automaticamente su un indice **Full-Text (Lucene)** che analizza titoli e descrizioni per trovare il miglior match concettuale, mantenendo alte performance anche senza LLM attivi.
- **Stimolazione Manuale**: Se desideri che The Butler inizi a considerare un vecchio progetto, puoi stimolare i nodi o semplicemente parlarne in chat. Il "calore" (attivazione) si propagherà automaticamente ai concetti vicini.
- **Focalizzazione**: Mnemosyne dà la priorità a ciò che è rilevante *ora*. Gli argomenti non nominati scivolano gradualmente nel "dimenticatoio" (dormancy) tramite il decadimento temporale.

---

## 🧹 3. Manutenzione e Igiene (Tab "Gardener")

Il **Gardener** (Giardiniere) assicura che Mnemosyne rimanga efficiente, prevenendo la frammentazione della conoscenza.

### Ciclo di Manutenzione Manuale

Cliccando su **"Esegui Ciclo Manutenzione"**, il sistema esegue:

- **Temporal Decay**: Applica l'invecchiamento alle attivazioni dei nodi (oblio).
- **Deadline Monitoring**: I `Task` con scadenze imminenti o superate ricevono un boost automatico di calore per essere riportati all'attenzione di The Butler.
- **Analisi Semantica**: Scansiona il grafo alla ricerca di potenziali duplicati.

### Gestione dei Duplicati

Se Mnemosyne individua concetti simili (es. *"Bed & Breakfast"* e *"B&B"*):

1. Crea una relazione `MAYBE_SAME_AS` tra i due nodi.
2. Ti mostra il suggerimento nella tab.
3. **Azione di Merge**: Cliccando su **Merge**, Mnemosyne fonde i due nodi.

**Cosa implica il Merge?**

- **Struttura**: Tutte le relazioni (collegamenti) e le etichette (labels) di entrambi i nodi vengono unite sul nodo principale. Il doppione viene eliminato per pulire la memoria.
- **Cognizione**: The Butler smette di avere "visione doppia". I ricordi e le osservazioni di entrambi i nodi ora puntano a un unico concetto, permettendo a The Butler di unire i puntini in modo più intelligente.
- **Attenzione**: Invece di avere due nodi "tiepidi", avrai un unico nodo solido che accumula calore più velocemente, facilitando la generazione di iniziative proattive coerenti.

### ⚖️ Merge vs. Ignora: Guida Decisionale

Il Gardener è un assistente, ma sei tu il custode del significato. Segui questa guida per decidere:

- **✅ Usa il MERGE (Identità)**: Quando i due concetti sono **lo stesso oggetto mentale**.
  - *Sinonimi/Acronimi*: "B&B" ↔️ "Bed & Breakfast", "AI" ↔️ "Intelligenza Artificiale".
  - *Varianti/Errori*: "Stalla" ↔️ "Stalla (ID errato)".
  - *Lingue*: "Tetto" ↔️ "Roof".
- **❌ Usa IGNORA (Relazione)**: Quando i concetti sono diversi ma collegati.
  - *Gerarchia*: "Tetto" ↔️ "Tettoie" (la tettoia è un tipo di tetto, non il tetto stesso).
  - *Parte-Tutto*: "Motore" ↔️ "Auto".
  - *Somiglianza*: "Stalla" ↔️ "Fienile".
  - **Consiglio**: In questi casi, clicca su **Ignora** e, se vuoi, crea il legame gerarchico esplicito in Chat (es. *"Ricorda che le tettoie sono un tipo di tetto"*).

---

## 💡 4. Iniziative Proattive e Pianificazione (Proactive Planning)

Sulla sidebar troverai la sezione **"Mnemosyne Says..."**. Qui The Butler prende l'iniziativa senza essere interrogato:

- **Associazioni Inattese**: Se parli di un argomento, Mnemosyne potrebbe riproporti un tema correlato che non tocchi da tempo.
- **Pianificazione**: Mnemosyne monitora i tuoi `Goal` e `Task`. Grazie al **TimeWatcher**, verrai avvisato tramite suggerimenti proattivi se un obiettivo ha una scadenza imminente o superata.

---

## � 5. Analisi Longitudinale (Historical Briefing)

Oltre alla memoria a breve termine, Mnemosyne offre una **visione d'insieme** sulla tua evoluzione cognitiva.

### Cosa puoi scoprire

- **Progetti Dormienti**: Se avevi un obiettivo o un tema molto "caldo" un mese fa ma non lo tocchi da tempo, Mnemosyne lo identificherà come dormiente e te lo riproporrà come suggerimento proattivo.
- **Trend Settimanali**: Una sintesi dei concetti che hanno ricevuto più attenzione negli ultimi 7 giorni.

### Configurazione

Puoi personalizzare o disattivare questa funzione nel file `config/settings.yaml`:

```yaml
longitudinal_analysis:
  enabled: true              # Attiva/Disattiva l'analisi storica
  frequency: "weekly"        # Cadenza del report (weekly, monthly)
  dormancy_threshold_days: 30 # Soglia di inattività per i progetti
```

### Richiamare il Briefing Storico via API

Se vuoi consultare manualmente l'analisi dei trend e dei progetti dormienti:

```bash
curl http://localhost:4001/briefing/longitudinal?scopes=Private
```

---

## �🛠️ 5. Controllo Manuale tramite MCP (Model Context Protocol)

Se utilizzi un client compatibile con MCP (come Claude Desktop o OpenClaw), The Butler ha accesso a strumenti di gestione diretta della memoria:

### Gestione Conoscenza

- `forget_knowledge_node`: Permette di eliminare fisicamente un nodo dal grafo.
- `update_knowledge_node`: Per correggere proprietà o dettagli di un concetto esistente.

### Pianificazione

- `create_goal`: Crea un nuovo obiettivo strategico con una deadline.
- `create_task`: Crea un'azione collegata a un Goal.
- `update_task_status`: Per segnare un task come `done`, `in_progress` o `discarded`.

**Consiglio**: Puoi chiedere a voce a The Butler: *"Crea un nuovo obiettivo per il lancio del sito entro Giugno e aggiungi il task di scrivere i testi"*. Lui userà questi tool per te.

---

## 🛡️ 6. Knowledge Scopes (Privacy e Visibilità)

Mnemosyne protegge la tua conoscenza tramite pool di visibilità isolati.

- **Public**: Conoscenza condivisibile con agenti esterni.
- **Internal**: Procedure e documentazione tecnica interna.
- **Private**: I tuoi pensieri, segreti e bozze di progetto.

### Come usare gli Scopes

Quando aggiungi un'informazione tramite il Gateway, puoi specificare lo scope:

```url
POST /add?scope=Private
```

Per cercare informazioni in ambiti specifici:

```url
GET /search?q=progetto&scopes=Private,Public
```

### Knowledge Promotion (Condivisione)

Se un'idea nata in `Private` è pronta per essere condivisa, puoi usare l'endpoint `/share` per spostare il nodo nello scope `Public`.

---

📂 7. Document Manager & Ingestione Massiva

Per gestire grandi volumi di testo (documenti, repository, archivi), Mnemosyne offre un **Document Manager** integrato nella Dashboard.

### Caricamento e Archiviazione

Nel tab **Documents**, puoi trascinare file `.txt` o `.md`.

- **Archiviazione Fisica**: A differenza delle semplici osservazioni, i documenti vengono salvati stabilmente in `data/storage/documents/`.
- **Witnessing**: Il file fisico funge da "testimone" per la conoscenza estratta nel grafo. Se il file viene rimosso, Mnemosyne perde la traccia della fonte originale.

### Deep Delete (Eliminazione Sicura)

Se decidi di rimuovere un documento dall'archivio:

1. Clicca su **Elimina** accanto al nome del file nella Dashboard.
2. Mnemosyne rimuoverà il file dal disco.
3. Verranno eliminati dal Connectome il nodo `Document` e tutti i relativi `DocumentChunk`, pulendo completamente la memoria da quell'apporto informativo.

### Come funziona l'Ingestione

1. **Spezzettati (Chunking)**: Il testo viene diviso in frammenti logici (paragrafi).
2. **Scansionati**: Il sistema cerca riferimenti a concetti già presenti nel tuo Connectome.
3. **Background**: L'elaborazione avviene in sottofondo per non bloccare la tua operatività.

## 🌫️ 5. Focalizzazione e Oblio: Cambiare Argomento

Mnemosyne è progettata per seguire l'evoluzione dei tuoi interessi. Cosa succede se passi improvvisamente dal parlare del tuo "B&B" a un tema completamente diverso, come l'"Astrofisica"?

### Lo "Spostamento del Calore" (Attention Shift)

- **Nuovi Cluster**: Mnemosyne creerà una nuova "isola" di concetti nel grafo, inizialmente scollegata dai tuoi progetti precedenti.
- **Decadimento Attivo**: Man mano che parli del nuovo argomento, i vecchi nodi (B&B, PHP, ecc.) inizieranno a "raffreddarsi" (Decay). The Butler sentirà questo spostamento e smetterà gradualmente di proporti iniziative sul vecchio tema.
- **Memoria Silente**: Mnemosyne non dimentica. Se dopo mesi nomini un vecchio vincolo, The Butler riattiverà istantaneamente quel cluster ("evocazione"), dimostrando di avere ancora il filo della tua storia.

### Il Valore dei Ponti

La vera potenza del sistema emerge quando Mnemosyne identifica un **ponte** tra argomenti distanti. Se trovi un punto di contatto tra i due mondi, The Butler ti aiuterà a integrare le nuove scoperte nei tuoi progetti esistenti, creando connessioni proattive che non avresti considerato.

---

## 🛠️ Manutenzione e Backup

Per garantire la sicurezza del tuo Connectome, Mnemosyne include un'utility di gestione del database.

### Eseguire un Backup

Esegui questo comando periodicamente o prima di aggiornamenti importanti:

```bash
.venv/bin/python3 scripts/manage_db.py backup --file data/backup_memoria.json
```

### Ripristinare da un Backup

Per recuperare il grafo da un file JSON precedentemente esportato:

```bash
.venv/bin/python3 scripts/manage_db.py restore --file data/backup_memoria.json
```

### Svuotare il Grafo

Se vuoi ricominciare da zero in modo pulito:

```bash
.venv/bin/python3 scripts/manage_db.py clear
```

---

## 🛠️ Risoluzione Problemi

- **Connessione Persa**: Se vedi un errore di connessione, verifica che il container Docker di Neo4j sia attivo (`docker ps`).
- **Lentezza nelle Risposte**: Mnemosyne esegue i modelli LLM localmente via Ollama. Se le risposte sono lente, assicurati che la tua GPU sia correttamente utilizzata da Ollama.

---

---

## 🛡️ 8. Sicurezza e Accesso Esterno (API Keys)

Se prevedi di interagire con Mnemosyne da un altro server o di esporre il Gateway su internet, è fondamentale attivare l'autenticazione.

### Configurazione delle Chiavi

1. Copia il file template:

    ```bash
    cp config/api_keys.yaml.example config/api_keys.yaml
    ```

2. Modifica `config/api_keys.yaml` inserendo le tue chiavi e definendo a quali **Scopes** ognuna ha accesso.
3. Riavvia il sistema per applicare i cambiamenti: `./scripts/start.sh`.

### Utilizzo via API

Ogni chiamata dovrà includere l'header HTTP `X-API-Key`.
Esempio con `curl`:

```bash
curl -X GET "http://tuo-server:4001/search?q=progetto" \
     -H "X-API-Key: mnm_sk_tua_chiave_segreta"
```

**Nota:** Il sistema è intelligente: se richiedi uno scope (es. `Private`) ma la tua chiave ha accesso solo al `Public`, la richiesta verrà respinta automaticamente.

---

> *"Mnemosyne non è un magazzino di dati, ma un compagno di viaggio che impara a conoscerti."*
