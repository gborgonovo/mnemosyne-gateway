# Guida all'Utente: Mnemosyne & The Butler

Benvenuto in **Mnemosyne**, il tuo partner cognitivo locale. Questa guida ti aiuterà a navigare nell'interfaccia e a sfruttare al meglio le capacità di The Butler, il layer relazionale del sistema.

## 🚀 Avvio Rapido

L'applicazione si basa su componenti core che devono essere attivi:

1. **Neo4j**: Il database a grafo (Connectome).
2. **Ollama**: Il motore di inferenza locale.
3. **Mnemosyne Gateway**: Il server FastAPI che fa da bridge.

Per avviare il Gateway (necessario per OpenClaw e altre app):

```bash
PYTHONPATH=. .venv/bin/python3 gateway/http_server.py
```

Per avviare la Dashboard di visualizzazione (opzionale):

```bash
streamlit run interface/app.py
```

---

## 🔌 Modalità di Utilizzo

Mnemosyne è un **Middleware**. Puoi interagirci in diversi modi:

### A. Tramite App Esterne (OpenClaw, Open WebUI)

Questa è la modalità principale. Usando lo **HTTP Bridge**, le tue app preferite interrogano Mnemosyne in background.

- L'agente riceve automaticamente i briefing.
- Ogni tua parola viene memorizzata nel grafo senza che tu debba fare nulla.

### B. Tramite la Dashboard (Streamlit)

Usa la dashboard per una gestione visiva del "cervello":

- **Tab Connectome**: Per vedere quali argomenti sono "caldi".
- **Tab Gardener**: Per pulire i duplicati e gestire le scadenze.

### C. Tramite CLI (Manuale)

Per operazioni rapide o per alimentare il sistema via script:

```bash
python3 gateway/legacy_cli.py add "Nuova osservazione"
```

---

## 🕸️ 2. Esplorazione del Connectome (Tab "Connectome")

In questa sezione puoi osservare e influenzare lo stato "termico" della tua memoria digitale. Il Connectome non è un archivio statico, ma un sistema dinamico che dà la priorità a ciò che è rilevante *ora*.

- **Heatmap delle Attivazioni**: Visualizza i concetti attualmente nella tua "faci di attenzione". Le barre di progresso indicano quanto un argomento è "caldo":
  - **Barra Piena**: Argomento focale. The Butler lo userà come contesto principale e genererà iniziative su questo tema.
  - **Barra Media**: Argomento latente. The Butler lo "ricorda" ma non ci si sofferma a meno che tu non lo nomini.
- **Stimolazione Manuale**: Se desideri che The Butler inizi a considerare un vecchio progetto, puoi selezionarlo e premere **Stimulate**. Questo inietta "calore" artificiale nel nodo, riportandolo al centro del discorso.
- **Reset All Heat (Cold Start)**: Utile quando cambi drasticamente argomento (es. passi dal lavoro al tempo libero) e vuoi che The Butler smetta di suggerire temi della sessione precedente.
- **🌫️ Forgotten Topics (Dormant)**: Qui finiscono i concetti che non vengono nominati o stimolati da tempo. Non sono cancellati, ma sono in uno stato di "sonno profondo". Possono essere risvegliati in qualsiasi momento semplicemente nominandoli in chat.

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

## 💡 4. Iniziative Proattive

Sulla sidebar troverai la sezione **"Mnemosyne Says..."**. Qui The Butler prende l'iniziativa senza essere interrogato:

- **Associazioni Inattese**: Se parli di un argomento, Mnemosyne potrebbe riproporti un tema correlato che non tocchi da tempo.
- **Domande Aperte**: The Butler ti ricorderà dubbi o decisioni in sospeso legati ai temi caldi del momento.

---

## 🌫️ 5. Focalizzazione e Oblio: Cambiare Argomento

Mnemosyne è progettata per seguire l'evoluzione dei tuoi interessi. Cosa succede se passi improvvisamente dal parlare del tuo "B&B" a un tema completamente diverso, come l'"Astrofisica"?

### Lo "Spostamento del Calore" (Attention Shift)

- **Nuovi Cluster**: Mnemosyne creerà una nuova "isola" di concetti nel grafo, inizialmente scollegata dai tuoi progetti precedenti.
- **Decadimento Attivo**: Man mano che parli del nuovo argomento, i vecchi nodi (B&B, PHP, ecc.) inizieranno a "raffreddarsi" (Decay). The Butler sentirà questo spostamento e smetterà gradualmente di proporti iniziative sul vecchio tema.
- **Memoria Silente**: Mnemosyne non dimentica. Se dopo mesi nomini un vecchio vincolo, The Butler riattiverà istantaneamente quel cluster ("evocazione"), dimostrando di avere ancora il filo della tua storia.

### Il Valore dei Ponti

La vera potenza del sistema emerge quando Mnemosyne identifica un **ponte** tra argomenti distanti. Se trovi un punto di contatto tra i due mondi, The Butler ti aiuterà a integrare le nuove scoperte nei tuoi progetti esistenti, creando connessioni proattive che non avresti considerato.

---

## 🛠️ Risoluzione Problemi

- **Connessione Persa**: Se vedi un errore di connessione, verifica che il container Docker di Neo4j sia attivo (`docker ps`).
- **Lentezza nelle Risposte**: Mnemosyne esegue i modelli LLM localmente via Ollama. Se le risposte sono lente, assicurati che la tua GPU sia correttamente utilizzata da Ollama.

---

> *"Mnemosyne non è un magazzino di dati, ma un compagno di viaggio che impara a conoscerti."*
