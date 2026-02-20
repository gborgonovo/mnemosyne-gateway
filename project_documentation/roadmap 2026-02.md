# **Capitolo 0: Filosofia e Cambio di Rotta**

## **1\. La Crisi del Monolite**

Mnemosyne è nato come un "Secondo Cervello" integrato. Tuttavia, l'evoluzione del progetto ha evidenziato tre limiti critici dell'approccio monolitico:

1. **Saturazione Risorse:** L'ingestione massiva e l'analisi semantica caricano eccessivamente la GPU, rendendo il sistema inutilizzabile su macchine locali standard.  
2. **Rigidità Operativa:** Un unico "blocco" di codice è difficile da estendere e proteggere in contesti multi-utente o aziendali.  
3. **Dipendenza Hardware:** Il sistema deve poter "pensare" anche su un vecchio laptop, delegando il ragionamento pesante a macchine esterne solo quando necessario.

## **2\. Il Nuovo Paradigma: Il Middleware Cognitivo**

Il cambio di rotta trasforma Mnemosyne da un'applicazione a un **Middleware Cognitivo**. La filosofia si sposta dalla "risposta al prompt" alla **"gestione del flusso di conoscenza"**.

Mnemosyne non è più il bot; è il tessuto connettivo (il Connectome) che sta tra l'utente e qualunque intelligenza (locale o remota).

## **3\. I Tre Pilastri della Nuova Architettura**

### **A. Minimalismo del Nucleo (Micro-kernel)**

Il "cuore" del sistema gestisce solo la topologia del grafo e l'energia dei nodi. È agnostico rispetto ai dati che riceve. Se il nucleo è leggero, può restare sempre attivo (Always-on) su Arch Linux o server Ubuntu con un impatto trascurabile sulle prestazioni.

### **B. Estensibilità Distribuita (Plugin)**

Le funzionalità non sono più funzioni interne, ma **Worker esterni**. Un plugin di ingestione può girare su un server dedicato, mentre il core resta protetto sulla tua macchina. Questo permette a terzi di aggiungere capacità (es. connettori Git, sensori IoT, analisi finanziaria) senza toccare il codice sorgente.

### **C. Opportunità del Contesto (Knowledge Scopes)**

Abbandoniamo la sicurezza binaria (SI/NO) per la **Visibilità Contestuale**. Il sistema non "censura", ma "maschera". La conoscenza è una sola, ma ogni interfaccia la guarda attraverso una lente diversa (Scope), garantendo che l'assistente pubblico non sappia nulla delle procedure private, pur attingendo dallo stesso database.

## **4\. L'Obiettivo Finale**

Vogliamo un sistema che sia **Immortale** (i dati restano nel tuo grafo, non in una chat), **Privato** (tutto gira sotto il tuo controllo) e **Scalabile** (si adatta dall'uso personale al supporto aziendale).

Mnemosyne diventa l'infrastruttura su cui poggia l'intelligenza, non l'intelligenza stessa.

# **Capitolo 1: Il Micro-Kernel (Core)**

## **1\. Definizione e Scopo**

Il Micro-Kernel è l'unico componente di Mnemosyne che deve rimanere costantemente in esecuzione (Always-on). Il suo scopo non è interpretare il linguaggio naturale, ma gestire la **topologia della memoria** e la **dinamica dell'attenzione**.

Per massimizzare la portabilità e minimizzare l'uso di risorse, il Core è rigorosamente **LLM-free**: non esegue inferenza, ma delega ogni compito semantico ai plugin esterni.

## **2\. Componenti Fondamentali**

### **2.1 Graph Manager (L'Interfaccia del Connectome)**

È il modulo che si interfaccia direttamente con Neo4j. Non contiene logica di business, ma espone primitive per la manipolazione del grafo:

* **Agnosticismo dei Dati:** Gestisce nodi e relazioni basandosi su label e proprietà, senza conoscerne il contenuto semantico.  
* **Ottimizzazione delle Query:** Esegue le operazioni di ricerca topologica e filtraggio per "Scope" (visibilità), assicurando che le risposte del database siano già modellate per il contesto richiesto.

### **2.2 Attention Model (Il Motore Metabolico)**

Gestisce la "vita" dei nodi attraverso il calcolo dell'attivazione. Le sue funzioni principali sono:

* **Spreading Activation:** Quando un nodo viene toccato da un input, il calore si propaga ai nodi vicini.  
* **Exponential Decay:** Riduce automaticamente l'energia dei nodi nel tempo per simulare l'oblio e mantenere il focus sul presente.  
* **Energy Thresholds:** Determina quali nodi sono "caldi" a sufficienza per essere estratti e inviati ai plugin di analisi.

## **3\. Logica Operativa: "The State Machine"**

Il Micro-Kernel opera come una macchina a stati finiti che reagisce a stimoli numerici o strutturali:

1. **Ricezione Stimolo:** Un evento esterno segnala un'interazione con un nodo.  
2. **Calcolo Dinamico:** Il kernel aggiorna i pesi delle relazioni e i livelli di calore.  
3. **Emissione Evento:** Se un cluster di nodi supera la soglia di attenzione, il kernel emette un segnale (EVENT\_ATTENTION\_PEAK) sull'Event Bus.

## **4\. Requisiti di Performance**

Per garantire il funzionamento su hardware limitato, il Micro-Kernel deve rispettare i seguenti vincoli:

* **Footprint di Memoria:** \< 256MB RAM (escludendo il DB Neo4j).  
* **Latenza:** Le operazioni di aggiornamento dell'attenzione devono completarsi in \< 50ms.  
* **Indipendenza:** Il crash di qualsiasi plugin non deve interrompere il ciclo di decadimento dell'attenzione del Core.

# **Capitolo 2: L'Event Bus e il Protocollo di Comunicazione**

## **1\. Il Sistema Nervoso Centrale: L'Event Bus**

L'Event Bus è il meccanismo di disaccoppiamento che permette al Core di rimanere leggero. Invece di chiamare direttamente le funzioni dei plugin, il Core pubblica segnali (Eventi) a cui i plugin possono "iscriversi".

### **Funzionamento**

* **Asincronia:** Il Core emette un evento e prosegue la sua esecuzione senza attendere la risposta (Fire-and-forget), a meno che non sia richiesta una sincronizzazione esplicita.  
* **Pub/Sub Pattern:** Più plugin possono ascoltare lo stesso evento. Ad esempio, un evento NEW\_OBSERVATION può attivare contemporaneamente il plugin di *Ingestione* e quello di *Notifica*.

---

## **2\. Il Protocollo di Comunicazione (Mnemosyne-RPC)**

Per garantire che i plugin possano girare su macchine differenti (es. Arch Linux locale e Server Ubuntu), la comunicazione avviene via **HTTP/JSON-RPC**.

### **Standard del Payload**

Ogni comunicazione deve seguire una struttura JSON rigida per essere processata dal Gateway:

JSON

{

  "version": "1.0",

  "event\_type": "string",

  "timestamp": "ISO8601",

  "scope": \["list\_of\_scopes"\],

  "payload": {

    "nodes": \[\],

    "relationships": \[\],

    "metadata": {}

  }

}

---

## **3\. Catalogo degli Eventi Standard**

Gli sviluppatori devono implementare i propri plugin in reazione a questi eventi fondamentali:

| Evento | Origine | Descrizione |
| :---- | :---- | :---- |
| IN\_RAW\_INPUT | Gateway | Input grezzo dall'utente (testo, file, log). |
| NODE\_ENERGIZED | Core | Un nodo ha superato la soglia di attenzione (Peak). |
| GRAPH\_UPDATE | Core | Notifica di avvenuta modifica alla struttura del grafo. |
| REQ\_ENRICHMENT | Plugin | Richiesta di analisi semantica profonda (delegata a worker GPU). |

---

## **4\. Lifecycle del Plugin: Handshake e Registration**

Per essere riconosciuto dal Micro-Kernel, un plugin (anche se remoto) deve eseguire una procedura di **Handshake**:

1. **Discovery:** Il plugin invia una richiesta POST /register al Gateway di Mnemosyne.  
2. **Capabilities:** Il plugin dichiara quali eventi vuole ascoltare e quale "Tier" di potenza offre (es. Tier: High\_GPU).  
3. **Authentication:** Il Gateway assegna un Plugin\_ID e valida lo scope di accesso (es. il plugin può solo leggere i nodi :Public).

---

## **5\. Gestione della Latenza e Failover**

* **Timeout:** Il Core non attende mai un plugin per più di $500ms$ nelle operazioni sincrone.  
* **Dead Letter Queue:** Se un plugin remoto non risponde, l'evento viene archiviato localmente e riproposto appena il plugin torna online, garantendo la coerenza del grafo.

# **Capitolo 3: Framework dei Plugin e Distributed Workers**

## **1\. Architettura del Plugin**

Per garantire l'estensibilità, ogni nuova funzionalità di Mnemosyne deve essere sviluppata come un modulo isolato (Plugin). Un plugin è un'entità software che estende le capacità del Core agendo su dati specifici o interfacciandosi con il mondo esterno.

### **Il Contratto del Plugin**

Ogni plugin deve implementare un'interfaccia standard che ne definisce il ciclo di vita:

* **Identity**: Nome unico, versione e requisiti hardware (es. "Richiede GPU").  
* **Handshake**: Procedura di registrazione presso il Gateway.  
* **Subscription**: Lista degli eventi dell'Event Bus a cui il plugin è interessato.

---

## **2\. Il Pipeline di Elaborazione (Hooks)**

L'interazione dei plugin con il flusso di dati avviene attraverso tre "ganci" (Hooks) sequenziali, permettendo un controllo granulare:

1. **Pre-process (Cleaning/Filtering)**: Il plugin riceve l'evento e prepara i dati (es. pulizia del testo da un PDF o normalizzazione di un log).  
2. **Enrich (Semantic Analysis)**: Il cuore dell'attività. Qui il plugin interroga un modello (LLM o euristico) per estrarre entità, relazioni o sentiment.  
3. **Post-process (Graph Injection)**: Il plugin restituisce al Core i nodi e le relazioni risultanti, pronti per essere scritti nel Connectome.

---

## **3\. Distributed Workers & Compute Tiering**

Il sistema supporta la distribuzione del carico su macchine diverse per ottimizzare le risorse.

### **3.1 Tiering Cognitivo (Agnosticismo del Backend)**

Non tutti i compiti richiedono la stessa potenza. Gli sviluppatori devono mappare i plugin su diversi **Tier**:

* **Tier 1 (Light/CPU)**: Plugin deterministici (es. Regex, matching di stringhe, calcolo di date). Girano sul Core (Arch Linux).  
* **Tier 2 (Medium/GPU-Local)**: Estrazione veloce di entità tramite modelli LLM piccoli (es. 1B-3B parametri). Girano su hardware locale.  
* **Tier 3 (Heavy/Distributed)**: Analisi profonda, sintesi storiche o ragionamento complesso. Girano su workstation dedicate o server (Ubuntu) usando modelli Large (es. 30B+ parametri).

---

## **4\. Gestione della Connessione e Discovery**

I plugin distribuiti utilizzano un meccanismo di **Service Discovery** gestito dal Gateway:

* Il Core mantiene una tabella dei plugin attivi e del loro stato di salute (Health Check).  
* Se un plugin Tier 3 (remoto) non è disponibile, il Core può decidere di eseguire una versione "degradata" del task su un plugin Tier 1 locale, garantendo la continuità operativa anche in assenza di risorse pesanti.

---

## **5\. Isolamento e Tolleranza ai Guasti**

Per proteggere l'integrità del sistema:

* **Sandbox**: I plugin non hanno accesso diretto alla memoria del Core o al file system del database, ma interagiscono solo tramite API JSON.  
* **Circuit Breaker**: Se un plugin genera errori ripetuti o latenze eccessive, il Gateway lo disconnette automaticamente (Shunning) per proteggere la stabilità del Micro-Kernel.

# **Capitolo 4: Knowledge Scopes (Visibilità Dinamica)**

## **1\. Filosofia: Dall'Access Control all'Opportunità**

In Mnemosyne, lo **Scope** non è un semplice sistema di permessi (ACL), ma un meccanismo di **pertinenza contestuale**. L'obiettivo non è solo proteggere i dati, ma garantire che ogni interfaccia veda solo ciò che è opportuno per il suo ruolo.

Un assistente sul sito web non deve tacere le procedure interne perché gli è "vietato", ma perché, all'interno del suo Scope, quelle informazioni **non esistono**.

## **2\. Implementazione nel Grafo (Labeling)**

La visibilità è gestita a livello atomico direttamente nel Connectome (Neo4j) tramite l'uso di **Label** di sistema.

### **2.1 Marcatori di Visibilità**

Ogni nodo e ogni relazione deve possedere almeno una label di Scope. Le label predefinite sono:

* :Public: Informazioni destinate all'esterno (prodotti, servizi, contatti).  
* :Internal: Procedure aziendali, metodologie, documentazione tecnica riservata.  
* :Private: Riflessioni personali, dati sensibili, bozze di progetto (es. il tuo "Sogno del B\&B").

---

## **3\. Il Filtro di "Cecità Selettiva" (Gateway Logic)**

Il filtraggio non avviene nell'LLM, ma a monte, nella query al database. Questo elimina il rischio di "allucinazioni di segretezza" o fughe di dati.

### **3.1 Iniezione della Clausola di Scope**

Quando il Gateway riceve una richiesta, identifica lo Scope del client e inietta dinamicamente una clausola WHERE in ogni query Cypher inviata al Micro-Kernel:

Cypher

// Esempio di query filtrata per lo Scope "Public"

MATCH (n:Entity)-\[r\]-\>(m:Entity)

WHERE (n:Public OR n:Global) AND (m:Public OR m:Global)

RETURN n, r, m

Se un'informazione è taggata come :Internal, la query restituirà un set vuoto. Il plugin di risposta riceverà "Nessuna informazione trovata" e agirà di conseguenza.

---

## **4\. Gerarchia ed Ereditarietà degli Scope**

Per evitare la duplicazione dei dati, il sistema supporta una gerarchia di visibilità. Chi ha accesso a uno scope superiore vede automaticamente quelli inferiori:

1. **Scope: Private** \-\> Vede Private \+ Internal \+ Public.  
2. **Scope: Internal** \-\> Vede Internal \+ Public.  
3. **Scope: Public** \-\> Vede solo Public.

---

## **5\. Dinamica di Assegnazione (Ingestion)**

Lo Scope viene definito nel momento in cui il dato entra nel sistema:

* **Plugin-Driven**: Un plugin di "Ingestione Documenti Tecnici" assegnerà di default la label :Internal.  
* **Interface-Driven**: I dati inseriti tramite la tua chat privata su Arch Linux riceveranno la label :Private.  
* **Promozione Manuale**: Alfred può suggerirti di "promuovere" un'informazione (es. una decisione presa in privato che deve diventare una procedura per i collaboratori).

---

## **6\. Sicurezza del Middleware**

Poiché Mnemosyne è un middleware distribuito, il Core deve poter girare su Ubuntu (produzione) gestendo scope diversi contemporaneamente. Il Gateway agisce come **Garante della Lente**: verifica l'autenticazione del client e applica la "lente" corretta prima di interrogare il Micro-Kernel.

# **Capitolo 5: Deployment & Infrastruttura**

## **1\. Filosofia del Deployment: "Install Anywhere"**

Mnemosyne deve poter girare su qualsiasi distribuzione Linux (Arch, Ubuntu, Debian, Fedora, ecc.) senza dipendere da pacchetti specifici della distro. La portabilità è garantita dall'uso di ambienti isolati e dalla separazione tra il database (pesante) e il core (leggero).

## **2\. Requisiti e Virtualizzazione**

Per mantenere il sistema "pulito" e portabile, utilizziamo un approccio ibrido:

* **Database (Neo4j)**: Distribuito esclusivamente via **Docker**. Questo evita conflitti con le versioni della JVM e permette di gestire i dati (il Connectome) come volumi persistenti facilmente migrabili.  
* **Micro-Kernel (Core)**: Eseguito in un **Python Virtual Environment (venv)**. A differenza di Docker, l'esecuzione nativa in venv riduce la latenza di I/O e l'overhead di memoria, fattore critico per macchine con meno di 8GB di RAM.  
* **Plugin**: Possono essere eseguiti in container, venv o come servizi di sistema (systemd), a seconda della necessità di accesso all'hardware (GPU).

---

## **3\. Profili Risorse (Hardware Mapping)**

Il sistema deve adattarsi all'hardware disponibile tramite file di configurazione (config.yaml) che definiscono il comportamento del Core:

| Profilo | Hardware Target | Strategia Cognitiva |
| :---- | :---- | :---- |
| **Edge/Low** | \< 4GB RAM, No GPU | Solo euristiche testuali, LLM disabilitato. |
| **Balanced** | 8-16GB RAM, GPU 4-8GB | LLM Tier 2 locale (Ollama) per compiti base. |
| **Power/Worker** | 32GB+ RAM, GPU 12GB+ | Full reasoning, analisi storica massiva. |

Il Core rileva le capacità del plugin registrato e gli assegna i compiti compatibili con il suo profilo di potenza.

---

## **4\. Orchestrazione Distribuita**

In una configurazione multi-macchina (es. il tuo setup Arch Linux \+ Server Ubuntu), la comunicazione avviene tramite il **Gateway**:

* **Discovery**: I plugin remoti si connettono all'indirizzo IP del Gateway. In reti locali, si consiglia l'uso di nomi host mDNS (es. mnemosyne-core.local).  
* **Proxying**: Il Gateway agisce come ponte. Se l'utente su Arch chiede un'analisi complessa, il Gateway invia il task al Worker su Ubuntu e restituisce il risultato al grafo locale.

---

## **5\. Sicurezza e Segregazione della Rete**

Dato che Mnemosyne trasporta dati potenzialmente sensibili (Scope :Private), l'infrastruttura deve prevedere:

* **Token di Autenticazione**: Ogni plugin (anche locale) deve autenticarsi presso il Gateway tramite una API\_KEY univoca.  
* **Network Binding**: Per default, il Gateway deve ascoltare solo su localhost. L'apertura alla rete esterna deve essere un'azione esplicita dell'utente nelle impostazioni di configurazione.  
* **Data Sovereignty**: Il database Neo4j risiede idealmente sulla macchina più sicura dell'utente; i Worker remoti ricevono solo i chunk di dati necessari all'elaborazione temporanea e non conservano copie locali del grafo.

---

## **6\. Procedura di Setup Generale (Standard Linux)**

1. **Host**: Installazione di Docker e Python 3.10+.  
2. **Storage**: Creazione della directory per il volume Neo4j (persistenza).  
3. **Kernel**: Setup del venv e installazione delle dipendenze del Micro-Kernel.  
4. **Plugin**: Registrazione dei plugin locali o remoti tramite il file plugins.json.

