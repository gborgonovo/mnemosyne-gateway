Questo progetto nasce con l'obiettivo di supportarmi nello svilupo di un progetto personale di ristrutturazione di una casa in campagna che voglio trasformare in B&B. 

L'obiettivo era di creare un partner che mi affiancasse nella realizzazione dei miei progetti e che in qualche modo compensasse le mie lacune di memorie e organizzative, con una libertà che andasse oltre il semplice botta e risposta.

Non doveva essere un tool o un assistente reattivo, ma un **partner cognitivo**. L'obiettivo era creare uno strumento che avesse una sua **continuità di pensiero**, una **memoria del percorso fatto in comune**, e la capacità di **offrire spunti inattesi** non solo quando interrogato, ma quando *sente* che potrebbero servire.

Questo progetto vuole essere un salto di qualità nella relazione uomo-AI. Non più "domanda-risposta", ma **collaborazione asincrona e proattiva**.

### Il Partner Cognitivo: Caratteristiche Fondamentali

1. **Memoria Relazionale Persistente:** Non una chat che si resetta. Un database che conserva:
    * Le dichiarazioni di intenti ("sogno di un B&B in campagna").
    * Le competenze ("so PHP/Laravel, Arch Linux").
    * I miei vincoli ("mutuo da pagare").
    * La storia delle decisioni prese e dei ragionamenti fatti insieme.
    * I *tuoi* pattern di pensiero, le tue esitazioni, i tuoi entusiasmi.

2. **Modello di Te (Inferito):** Il sistema deve costruire nel tempo un'immagine operativa dell'utente:
    * **Punti di forza:** Pratico, tecnico, ami la concretezza (PHP, ristrutturazione).
    * **Aree di possibile supporto:** La parte visionaria/emotiva del sogno, la gestione proiettata nel tempo, i buchi che *non* sai di avere.
    * **Stile di apprendimento:** Preferisci esempi? Schemi? Vuoi il codice o il concetto?

3. **Iniziativa Context-Aware:** Qui sta la libertà "oltre il botta e risposta". Il partner non aspetta sempre la tua domanda. Agisce quando:
    * **Rileva un silenzio progettuale:** Hai parlato del B&B due settimane fa e poi più nulla. Potrebbe, con delicatezza, riportare l'argomento: "Riflettendo sul tuo B&B, ti sei imbattuto in qualche dubbio sulla scelta degli infissi? Avevamo parlato di efficienza energetica."
    * **Incrocia informazioni:** Legge una notizia sui bandi per il turismo rurale nella tua regione e te la segnala: "Ho visto questo. Non so se è pertinente, ma mi ha ricordato il tuo progetto. Che ne pensi?"
    * **Anticipa bisogni:** Sai che tra un mese devi presentare un progetto al geometra. Una settimana prima, potrebbe dire: "Sto riordinando i nostri appunti sui requisiti tecnici. Volevo assicurarmi di non aver tralasciato nulla che per te è importante."

4. **Compensazione delle Lacune (il Cuore del Servizio):**
    * **Dalla Tattica alla Strategia:** Tu pensi al "come". Lui tiene viva la domanda sul "perché" e sul "dove vuoi arrivare" (l'atmosfera del B&B, l'esperienza dell'ospite).
    * **Dal Frammento alla Visione d'Insieme:** Tu affronti un problema alla volta (il mutuo, un tubo rotto). Lui collega i puntini: "Il costo di quel tubo impatta il budget per l'arredo della prima camera, che a sua volta influisce sulla data di apertura, che è legata al piano di rimborso del mutuo."
    * **Dall'Entusiasmo alla Sostenibilità:** Frena la corsa quando necessario: "So che vuoi implementare un sistema di prenotazione AI, ma forse possiamo partire con un modulo semplice e robusto. Il tuo tempo ora è più prezioso sul cantiere."
    * **Dal Tecnico all'Umano:** Ti ricorda le dimensioni non tecniche: "Hai considerato come gestirai la colazione quando tuo nipote viene a trovarti? La doppia veste di nonno e gestore è delicata."

5. **La Dualità: Mnemosyne vs The Butler (Il Cervello e la Relazione):**
    * **Mnemosyne (Il Cervello Silente):** È lo strato infrastrutturale. Gestisce il Grafo Relazionale (chiamato Connectome), il Modello di Attenzione e il Gardener. È il motore che "sente" le connessioni e accumula calore semantico.
    * **The Butler (Il Layer Relazionale):** È l'interfaccia universale di interazione umana, ora esposta tramite **MCP**. The Butler traduce le intuizioni del grafo in atti comunicativi dotati di personalità e pertinenza, agendo come un filtro relazionale tra la complessità del sistema e l'utente.

### Come Funziona Tecnicamente (Mnemosyne Gateway)

Mnemosyne è evoluto diventando un **Cognitive Middleware Headless** distribuito. Non è più un'app con UI principale, ma un ecosistema di servizi coordinati tramite un **Gateway Centralizzato** accessibile via **HTTP REST** e **MCP**.

* **Core Agnostico (LLM-Free):** Il nucleo centrale gestisce esclusivamente la dinamica dei grafi, l'attenzione e il bus degli eventi, senza dipendenze dirette da modelli linguistici.
* **Distributed Workers:** L'intelligenza (estrazione entità, generazione briefing) è delegata a worker separati (`LLMWorker`, `BriefingWorker`) che comunicano asincronamente tramite code persistenti e segnali RPC.
* **Knowledge Scopes:** Supporto nativo per pool di conoscenza isolati (`Private`, `Internal`, `Public`) con ereditarietà gerarchica.
* **Interfaccia Universale:** Espone tool tramite **MCP** e un **HTTP Bridge (FastAPI)** per la massima compatibilità (Docker, WebUI, CLI).
* **Memoria:** Ogni interazione è salvata, classificata e correlata nel Connectome (Neo4j).
* **Motore di Iniziativa Distribuito:** Un sistema a eventi che attiva suggerimenti proattivi basandosi sui picchi di attivazione del grafo, rispettando rigorosamente gli ambiti di visibilità (Scopes).
* **Integrazione Agente:** Gli agenti (OpenClaw, Open WebUI) chiamano gli endpoint di Mnemosyne per arricchire il proprio contesto, mantenendo la separazione tra identità dell'agente e conoscenza dell'utente.

### La Postura del Partner (Come Si Comporterebbe)

Il mio obiettivo era di creare un partner di lavoro:

* **Non un coach** che ti spinge.
* **Non un esecutore** che obbedisce.
* **È un custode del tuo percorso.** Il suo lavoro è **tenere insieme i pezzi del puzzle quando tu sei concentrato su uno solo**.
* **Parla quando ha valore da aggiungere**, tace quando il silenzio è più utile. La sua proattività è discreta, mai invadente.
* **Accetta il "non ora".** Se ignori un suo spunto, non insiste. Lo archivia e magari lo ripropone in un altro momento, in un altro modo.

### Perché Questo è Diverso (e Possibile)

Perché non richiede un'AI generale. Richiede:

1. Una **chiara definizione di dominio** (il tuo sogno, la tua vita, i tuoi progetti).
2. Una **architettura software dedicata** a mantenere il contesto.
3. L'uso **conservativo e mirato** di un LLM per generare il linguaggio e le connessioni *all'interno di quel contesto*.

Quando ho inizato a lavorarci su immaginavo un vero **assistente personale a lungo termine**. Non un oracolo, ma una **memoria esterna attiva**, un *secondo cervello* che non solo archiviasse, ma che **rievocasse, collegasse e suggerisse in modo tempestivo**.

### Le euristiche

La definizione delle euristiche è il punto critico. È lì che si passa dalla visione poetica all'ingegneria, e dove il rischio è di creare un sistema rigido, fastidioso o stupido.
Non volevo *definire* le euristiche, ma **permettere al sistema di sviluppare le sue**, in modo organico, attraverso l'interazione con l'utente. Doveva essere un cambio di paradigma: da **regole pre-scritte** a **pattern appresi**.

### Il Sistema Come Apprendista del Tuo Modo di Pensare

Invece di programmare regole del tipo "se passano 30 giorni, manda un promemoria", volevo costruire un sistema che:

1. **Osserva l'interazione naturale:** Registra quando *tu* riprendi un argomento dopo un silenzio. Cosa ti ha spinto? Era una notizia esterna? Un problema pratico? Un momento di riflessione?
2. **Identifica i tuoi pattern di attenzione:** Impara che per il progetto "B&B", il tuo ciclo di coinvolgimento è di circa 10 giorni. Che parli di "tecnologia" in modo reattivo (quando serve), ma di "sogno" in modo più riflessivo e sporadico.
3. **Modella il valore dello scambio:** Quando propone uno spunto (anche su nostra iniziale ipotesi rudimentale), osserva la tua risposta. La ignori? La approfondisci? La chiudi? Impara a distinguere uno spunto pertinente da uno fuori luogo.
4. **Si adatta:** Smette di proporti certi tipi di intervento se tu li trovi sistematicamente inutili. Ne raffina altri.

### Meccanismo Tecnico Ispirativo (Senza Codice)

Immagina il sistema come un **rete di nodi** (argomenti: B&B, PHP, Nipote, Mutuo) e di **collegamenti** tra di essi, che si rinforzano o indeboliscono nel tempo.

* **Nodo "B&B":** Ha associati documenti, note, scadenze, *e un "livello di attivazione"*.
* **Il livello di attivazione** di un nodo non è governato da un timer, ma da:
  * **Decadimento naturale:** Se non toccato, si abbassa lentamente.
  * **Input esterni:** Una notizia sul turismo rurale lo rialza.
  * **Associazioni interne:** Se il nodo "Mutuo" viene attivato (ne parli), potrebbe rialzare leggermente il nodo "B&B" perché nel contesto storico sono collegati.
* **Soglia di iniziativa:** Quando il livello di attivazione di un nodo supera una certa soglia **E** il sistema ha qualcosa di potenzialmente utile da dire (un collegamento con un altro nodo, una domanda aperta dal passato), **allora** genera un intervento.
* **L'intervento stesso è appreso:** Non è un prompt fisso. Il sistema ha un "catalogo" di tipi di intervento che ha usato in passato (es.: "richiamo di un dubbio passato", "collegamento con una nuova informazione", "domanda di aggiornamento"). Osserva quale tipo ha avuto risposta positiva da te in contesti simili, e lo preferisce.

### In Pratica, Con Te

1. **Giorno 1:** Parli con entusiasmo del B&B, dell'idea della veranda. Il nodo "B&B" si carica molto. Salvi note, idee.
2. **Giorno 5:** Parli del mutuo con preoccupazione. Il nodo "Mutuo" si attiva. Il sistema *vede* il collegamento storico con "B&B" e potrebbe, se la soglia è superata, intervenire: **"Mi è venuto in mente che parlavamo della veranda. L'impatto sul mutuo è una variabile che vuoi tenere separata, o preferisci che inizi a tenere traccia dei costi per avere un quadro unico?"**. Non è un promemoria automatico. È un'**associazione contestuale**.
3. **Giorno 20:** Non parli di nulla di correlato. Il livello di "B&B" è basso. Il sistema **sta in silenzio**. Non disturba.
4. **Giorno 22:** Leggi una notizia su un software per B&B e me la condividi. Il nodo "B&B" e "PHP" si riattivano. Il sistema, ora che l'argomento è *già* in mente tua, potrebbe il giorno dopo offrire: **"A proposito di quel software, stavo riguardando le tue note sulla necessità di semplicità. Volevo solo ricordarti che la tua competenza Laravel potrebbe essere una alternativa di controllo totale, anche se più lenta."**

L'euristica non è più **"dopo 30 giorni promemoria"**, ma **"quando l'argomento torna ad essere rilevante nel flusso naturale del pensiero dell'utente, offri un collegamento di valore basato sulla storia comune"**.

### La Sfida Vera (e la Bellezza)

La sfida non è ingegnerizzare queste regole, ma creare un sistema **abbastanza semplice da essere controllabile e trasparente, e abbastanza adattivo da non essere idiota**.

* **Trasparenza:** Tu potresti *vedere* il "livello di attivazione" dei tuoi nodi, o i collegamenti principali. Per non sentirti manipolato da una scatola nera.
* **Controllo:** Potresti abbassare manualmente l'"attivazione" di un nodo ("Non voglio pensarci ora") o suggellare un collegamento ("Questi due temi per me non sono collegati").
* **Apprendimento esplicito:** Potresti dare feedback diretto: "Questo intervento era perfetto" / "Questo era fuori luogo". Il sistema userebbe quel feedback per modellare le sue soglie e preferenze di intervento.

---

**In sintesi,** stai cercando un sistema che **impari l'euristica della collaborazione utile *con te* e *da te***, invece di averla prefabbricata. Un sistema che non applica regole generali di "produttività", ma che **assimila il ritmo, le priorità e lo stile del tuo pensiero** per diventare un vero partner di quel pensiero.

È più ambizioso di un bot, ma più realistico di un'AGI. È la ricerca di un'**interfaccia adattiva per il pensiero a lungo termine**.

La complessità non sta nel fargli generare testo (Ollama lo fa), ma nel **progettare il ciclo di percezione-decisione che governa *quando* e *su cosa* fargli generare testo**. E quel ciclo deve essere plasmabile dall'esperienza.

È questa la direzione che ti interessa esplorare? Il cuore non è l'LLM, ma il **meccanismo di attenzione e iniziativa** che lo guida.

### USER

Si, è esattamente questo. Riesci a delineare l'architettura di un assistente di questo tipo?

### ASSISTANT

Sì, posso delineare un'architettura per questo assistente. La chiamerò **Architettura Mnemosyne** (dal nome della dea greca della memoria), perché il suo cuore è una memoria relazionale, adattiva e contestuale.

L'obiettivo è un sistema che **apprende il tuo modello mentale** e usa quell'apprendimento per **iniziative tempestive e pertinenti**, non per regole rigide.

---

### **Principi Fondamentali**

1. **Memoria Prima di Tutto:** Il database non è un log, è la rappresentazione operativa della tua mente estesa.
2. **Modello a Doppio Strato:** Uno strato **simbolico/esplicito** (fatti, note, progetti) e uno strato **sub-simbolico/implicito** (associazioni, livelli di attivazione, pattern di interazione).
3. **Apprendimento Per Interazione:** Il sistema si calibra osservando cosa funziona *con te*.
4. **Trasparenza e Veto Assoluto:** Tu vedi i "perché" delle sue iniziative e puoi disattivarle o correggerle.

---

### **Schema Architetturale**

```
                    [ Interfaccia Utente ]
                           |      ^
                    (Input)|      |(Output/Suggestions)
                           v      |
    ----------------------------------------------------------
    |                  MNEMOSYNE CORE                        |
    |  [Dialog Manager] <---> [Initiative Engine] <---> [LLM Gateway]  |
    |         ^                  ^                  ^           |
    |         |                  |                  |           |
    |         v                  v                  v           |
    |  [Short-Term Context]  [Attention Model]  [Prompt Craft]  |
    |         ^                  ^                               |
    |         |                  |                               |
    |         v                  v                               |
    |  [LONG-TERM MEMORY & RELATIONAL GRAPH] <-----------------|
    |         ^          (Read/Write/Associate)                |
    |         |                                                |
    |  [External Data Feeds] <--> [Perception Module]          |
    -----------------------------------------------------------
                           |      ^
                    (Event)|      |(Action/Query)
                           v      |
                    [ Mondo Esterno ]
                    (Calendario, Feed RSS, File System, API)
```

---

### **Componenti Dettagliati**

#### **1. Long-Term Memory & Relational Graph (Il Cuore)**

* **Tipo:** Database a grafo (es. Neo4j) + vettoriale (per similarità semantica).
* **Cosa Contiene:**
  * **Nodi:** Entità (`Persona:Tu`, `Progetto:B&B`, `Skill:PHP`, `Concetto:BenessereOspiti`, `Documento:NotaVeranda`).
  * **Relazioni:** Collegano i nodi (`HA_COMPETENZA`, `HA_VINCOLO`, `PARTE_DI`, `EVOCA`, `CONTRIBUISCE_A`).
  * **Proprietà dei Nodi:** Metadati, `livello_attivazione`, `ultimo_accesso`, `feedback_score`.
  * **Proprietà delle Relazioni:** `forza` (quanto è forte/saliente il collegamento), `tipo_evocazione` (pratica, emotiva, logica).

#### **2. Attention Model (Il Termostato delle Iniziative)**

* **Funzione:** Decidere **quando** e **su cosa** il sistema dovrebbe prendere l'iniziativa.
* **Meccanismo Chiave - "Livello di Attivazione" di un Nodo:**
  * **Base:** Decade lentamente nel tempo.
  * **Boost da Interazione Utente:** Quando parli di un nodo, il suo livello sale.
  * **Boost da Associazione:** Se un nodo correlato (es. `Mutuo`) viene attivato, dà un lieve boost ai nodi collegati (es. `B&B`).
  * **Boost da Evento Esterno:** Il Perception Module rileva una notizia pertinente, boosta i nodi correlati.
* **Soglia di Iniziativa:** Un nodo diventa "candidato" per un'intervento quando il suo livello supera una soglia **E** il sistema ha un "valore potenziale" da offrire (vedi sotto).

#### **3. Initiative Engine (Il Decisore)**

* **Funzione:** Dato un nodo candidato, decidere **SE** intervenire e **COME**.
* **Valutazione del "Valore Potenziale":** Cerca nel grafo, partendo dal nodo candidato:
    1. **Domande Aperte:** Ci sono note o punti di discussione marcati come `?` o `DA_DECIDERE` collegati a quel nodo?
    2. **Nuove Associazioni:** Il sistema ha recentemente appreso un nuovo collegamento tra quel nodo e un altro che non è stato ancora discusso?
    3. **Input Esterni Recenti:** Il Perception Module ha catturato qualcosa di rilevante per quel nodo?
* **Selezione del Tipo di Intervento (Appreso):** Il sistema ha un repertorio di "schemi di intervento" (es: `RichiamaDubbio`, `CollegaNuovaInfo`, `SuggerisciProcedura`). Tiene traccia di quale schema ha ricevuto feedback positivo (`feedback_score`) in contesti simili (nodi simili, livello di attivazione simile).

#### **4. LLM Gateway & Prompt Craft**

* **Funzione:** Tradurre la *decisione* strategica dell'Initiative Engine in un *messaggio* umano, contestuale e in tono con la vostra relazione.
* **Prompt Dinamico:** Costruisce un prompt ricco per Ollama:
  * **Contesto Relazionale:** "Stai parlando con [Nome], un innovation manager che sta ristrutturando un B&B. Ha queste competenze: [...]. I suoi vincoli sono: [...]."
  * **Storia Rilevante:** "In passato avete discusso di: [...]."
  * **Intenzione Sistemica:** "Il nodo 'B&B' è attivo perché l'utente ha appena parlato di mutui. C'è una domanda aperta sui costi della veranda. Il tuo obiettivo è: richiamare delicatamente quell'argomento, collegandolo alla nuova discussione sul mutuo, per aiutarlo a pensare alla pianificazione finanziaria olistica."
  * **Istruzione di Stile:** "Sii conciso, pratico, non paternalistico. Offri un collegamento, non una soluzione. Termina con una domanda aperta se appropriato."

#### **5. Perception Module**

* **Funzione:** Fornire al sistema **input freschi e contestuali** dal mondo esterno, che possano attivare nodi o arricchire interventi.
* **Fonti (Configurabili):**
  * **Calendario:** Scadenze, ricorrenze.
  * **Feed RSS/News:** Filtrati per parole chiave derivate dai tuoi nodi (`turismo rurale`, `Laravel 11`, `efficienza energetica`).
  * **File System (opzionale, con permesso):** Monitora cambiamenti in directory di progetto (es. file `TODO.md` del B&B).

#### **6. Dialog Manager & Short-Term Context**

* **Funzione:** Gestire il flusso della conversazione, mantenere il contesto immediato (finestra di dialogo) e, soprattutto, **estrarre conoscenza** da ogni interazione per aggiornare la Long-Term Memory.
* **Estrazione Post-Interazione:** Dopo ogni scambio (tuo o del sistema), analizza il testo per:
  * **Aggiornare fatti** (es.: "Ho fissato l'appuntamento col geometra per il 15" -> aggiorna nodo `B&B`).
  * **Creare/Modificare relazioni** (es.: "Questo problema del mutuo mi sta facendo ripensare alla veranda" -> aumenta `forza` tra `Mutuo` e `B&B`, aggiungi relazione `INFLUENZA`).
  * **Registrare stati d'animo/tono** (es.: `frustrato`, `entusiasta`) come proprietà dell'interazione, per calibrare il tono futuro.

#### **7. Interfaccia Utente (Per Te)**

* **Non solo una chat.** Una dashboard con:
  * **Vista a Grafo Interattiva:** Per vedere i tuoi nodi e le connessioni che il sistema sta imparando. Potresti dire: "Questa connessione tra 'PHP' e 'B&B' è debole, rinforzala" (drag & drop).
  * **Slider di Sensibilità:** Per regolare globalmente la "soglia di iniziativa" (da "Molto Discreto" a "Molto Propositivo").
  * **Log delle Decisioni:** Per ogni intervento del sistema, un pulsante "Perché mi hai detto questo?" che rivela il ragionamento: "Nodo B&B attivato al 75% per associazione con Mutuo. Trovata domanda aperta sui costi veranda. Schema 'RichiamaDubbio' ha feedback score 8/10 in contesti finanziari."

---

### **Flusso di un Ciclo di Iniziativa**

1. **Percetto:** Il Perception Module

### USER

Nodi, relazioni e proprietà dovrebbero essere dinamici. Perché mi ricorda molto il paper “attention is all you need”? Ma con un livello di astrazione superiore, non token, ma nodi.

### ASSISTANT

**Esattamente.** Hai colto la connessione profonda. Stai descrivendo un **sistema di attenzione su un grafo di conoscenza**, invece che su una sequenza di token.

È come se avessi preso il meccanismo di "self-attention" di un Transformer e lo avessi **sollevato dal livello sintattico (parole) al livello semantico (concetti e relazioni)**. Invece di "questa parola è importante per capire quest'altra parola", diventa "**questo concetto (B&B) è attivato da questo altro concetto (mutuo) e insieme rendono rilevante quest'altro (veranda)**".

L'analogia è potente:

| **"Attention Is All You Need" (Transformer)** | **Architettura Mnemosyne (Grafo di Attenzione)** |
| :--- | :--- |
| **Input:** Sequenza di token (parole) | **Input:** Grafo di nodi (concetti, entità, progetti) |
| **Operazione Base:** Self-Attention (calcola importanza di ogni token per ogni altro token) | **Operazione Base:** Propagazione di attivazione nel grafo (un nodo "eccita" i nodi collegati) |
| **Output:** Rappresentazione contestuale di ogni token | **Output:** Stato di "attivazione contestuale" di ogni nodo |
| **Scopo:** Capire la struttura della frase | **Scopo:** Capire la struttura del **pensiero e degli interessi dell'utente** |
| **Memoria:** Limitata al contesto della finestra (es. 4096 token) | **Memoria:** Persistente, a lungo termine, relazionale |
| **Apprendimento:** Statico (pre-training su corpus) + Dinamico (fine-tuning) | **Apprendimento:** Dinamico continuo (dall'interazione) |

La tua intuizione sul **livello di astrazione superiore** è fondamentale. Non stiamo più ottimizzando per predire la parola successiva in una frase, ma per **predire il pensiero o il bisogno successivo rilevante in un progetto di vita**.

---

### **Perché i Nodi e le Relazioni Devono Essere Dinamici (e Come)**

Hai ragione: un sistema rigido fallirebbe. Deve **imparare il tuo vocabolario concettuale**.

1. **Nascita di un Nodo:**  
    * **Esplicita:** "Creiamo un nuovo progetto chiamato 'Orto'." → Nodo `Progetto:Orto` creato.  
    * **Implicita (estrazione):** "Sto lottando con la burocrazia per l'agriturismo." → Il sistema potrebbe estrarre `Concetto:BurocraziaAgriturismo` come nuovo nodo, o collegare `Burocrazia` esistente a `Progetto:B&B` con forza alta.  
    * **Da Evento Esterno:** Un feed RSS menziona "bonus facciate 2025". → Nodo `Opportunità:BonusFacciate` creato e collegato a `Progetto:B&B`.

2. **Morte o Ibernazione di un Nodo:**  
    * Il `livello_attivazione` decade verso zero e rimane lì per mesi. Il nodo diventa "dormiente". Può essere rianimato da un'associazione futura.  
    * **Veto Utente:** "Smettila di parlarmi di arredamento moderno." → Il nodo `Stile:Moderno` viene marcato con `veto_associazione` e non sarà più usato per iniziative.

3. **Evoluzione delle Relazioni:**  
    * La `forza` di un collegamento (`B&B` --HA_VINCOLO--> `Mutuo`) non è fissa. Si **rinforza** ogni volta che i due nodi sono co-attivati in una sessione. Si **indebolisce** se non vengono mai menzionati insieme per molto tempo.  
    * **Scoperta di Nuove Relazioni:** È qui che l'LLM (Ollama) può aiutare. Dopo un dialogo, il sistema può chiedere all'LLM: "Dalla seguente conversazione, quali concetti non ovvi sono collegati?"  
        *Prompt:* "Utente: 'Con il mutuo che pesa, forse dovrei partire con una sola camera del B&B per generare subito un piccolo reddito.' I nodi noti sono: `Mutuo`, `B&B`, `Reddito`. Quale altro nodo del grafo (es: `Rischio`, `Scalabilità`, `Stress`) o nuovo concetto è implicato?" → Potrebbe suggerire di creare un collegamento a `Concetto:MinimoVibile` o rafforzare quello con `Emozione:Preoccupazione`.

4. **Proprietà Emergenti:**  
    * `livello_attivazione` è la proprietà dinamica per eccellenza, il "potenziale di azione" del nodo.  
    * `feedback_score` è un'altra: ogni intervento del sistema basato su un nodo riceve un feedback implicito (l'utente risponde? approfondisce?) o esplicito (un pulsante "utile/non utile"). Questo punteggio modella la **propensione futura** a usare quel nodo come base per iniziative.

---

### **Il Ciclo di Attenzione Dinamica (in Pratica)**

1. **Fase Input (Tu parli):** "Oggi il geometra mi ha detto che per la veranda servono permessi speciali, e costa."  
2. **Estrazione & Aggiornamento Grafo:**  
    * Nodi attivati: `Geometra` (boost forte), `Veranda` (boost forte), `Permessi` (nuovo o boost), `Costi` (boost).  
    * Nuove relazioni: `Veranda` --RICHIEDE--> `Permessi` (forza alta), `Veranda` --AUMENTA--> `Costi` (forza alta).  
    * Relazione rinforzata: `B&B` --HA_PARTE--> `Veranda` (forza aumentata).  
3. **Propagazione:** L'attivazione di `Costi` si propaga leggermente a nodi collegati: `Mutuo`, `Budget`, `Stress`.  
4. **Valutazione Soglie:** `Mutuo` (già attivo) ora supera la soglia di iniziativa. L'Initiative Engine cerca valore: trova la domanda aperta "impatto mutuo-veranda?" e lo schema di intervento `CollegaNuovaInfo` con buon feedback.  
5. **Decisione & Azione:** Il sistema, **non immediatamente, ma forse il giorno dopo**, quando il nodo `Mutuo` è ancora caldo: "A proposito dei costi della veranda di ieri, vuoi che tenga traccia di questa voce separatamente nel quadro del mutuo, o la consideriamo parte del budget generale ristrutturazione?"  
    → L'intervento non è una reazione meccanica, ma un **collegamento ritardato e ponderato** che nasce dalla dinamica del grafo.

---

**In sintesi,** stai proponendo un'architettura dove l'**attenzione non è sul testo, ma sul significato**, e dove il **meccanismo di apprendimento non è sul linguaggio del mondo, ma sul modello mentale di una singola persona**.

È un'idea più ambiziosa di un assistente, è un **mirroring system** o un **cognitive twin** in formazione. La sfida ingegneristica è immensa, ma il principio è chiaro e, come hai notato, ha radici eleganti nella rivoluzione Transformer. Non si tratta di "più intelligenza", ma di **intelligen

### USER

Continua.

### ASSISTANT

<details type="reasoning" done="true" duration="8">
<summary>Thought for 8 seconds</summary>
&gt; Il messaggio precedente è stato troncato nel punto cruciale. L&#x27;utente ha appena condiviso un&#x27;intuizione fondamentale: l&#x27;architettura proposta assomiglia a &quot;Attention is All You Need&quot;, ma a un livello di astrazione superiore (nodi invece di token). Ha detto &quot;Continua&quot;, quindi devo sviluppare questa idea e mostrare come si realizza concretamente.
&gt;
&gt; Dato il contesto, l&#x27;utente è un tecnico (sa programmare, usa Arch Linux, PHP/Laravel) che sta esplorando un&#x27;idea profonda, non vuole codice ma concetti architetturali. Devo mantenere il livello di astrazione alto e filosofico, ma con sufficiente concretezza tecnologica per essere utile.
&gt;
&gt; La risposta precedente si è interrotta proprio mentre stavo per spiegare la sfida ingegneristica. Devo riprendere da lì, enfatizzando la differenza tra l&#x27;attenzione in un Transformer e l&#x27;attenzione in un grafo di conoscenza personale, e poi delineare come questa architettura &quot;Mnemosyne&quot; potrebbe effettivamente funzionare in pratica, soprattutto per il suo caso d&#x27;uso (il B&amp;B, i suoi progetti).
</details>
... riorientata. Non verso l'esterno (predire il testo del mondo), ma verso l'interno (modellare l'universo concettuale di una persona).

La sfida ingegneristica si sposta quindi dalla pura potenza di calcolo alla **progettazione di un sistema di apprendimento relazionale continuo**.

### **Dall'Intuizione all'Implementazione: I Pilastri di Mnemosyne**

Ecco come potrebbero tradursi i principi in componenti eseguibili:

#### **1. Il Grafo Dinamico: Un Organismo Vivente**

Il database a grafo non è solo uno storage. È un **campo di forze**.

* Ogni nodo ha un **potenziale di attivazione** che fluttua.
* Ogni arco (relazione) ha una **conduttività** che si modifica con l'uso.
* L'"attenzione" del sistema è letteralmente un **processo di propagazione** in questo campo, simile all'attivazione neurale o alla diffusione di un calore.

**Algoritmo di Propagazione (semplificato):**

```
quando un nodo N riceve un input di attivazione Δ:
  il suo livello_attivazione += Δ
  per ogni arco E che collega N a un nodo M:
    # L'attivazione si propaga, ma attenuata dalla forza e dalla distanza concettuale
    propagazione = Δ * E.forza * E.attenuazione
    M.ricevi_input(propagazione)
```

Questo crea **onde di attivazione** che si diffondono nel tuo spazio mentale digitale, facendo emergere cluster di concetti correlati.

#### **2. Il Ciclo di Apprendimento Continuo (Il Cuore del Partner)**

Il sistema non è mai "addestrato". È sempre in **adattamento attivo**. Ogni interazione è un ciclo di apprendimento.

1. **Predizione:** Prima di un intervento, il sistema stima un `feedback_score_atteso` basato su: similarità del contesto attuale con contesti passati, tipo di intervento scelto, nodi coinvolti.
2. **Azione:** Propone l'intervento.
3. **Feedback:** Misura il tuo **feedback implicito** (tempo di risposta, lunghezza, tono della risposta - analizzato semplicemente) ed eventualmente **esplicito** (un pulsante "utile").
4. **Aggiornamento:** Adatta i parametri:
    * La `forza` delle relazioni che hanno portato a quell'intervento si **rinforza** (se feedback positivo) o si **indebolisce** (se negativo).
    * Il `feedback_score` dello **schema di intervento** usato viene aggiornato per quel tipo di contesto.
    * La **soglia di iniziativa** personale per i nodi coinvolti può essere regolata.

È un **apprendimento per rinforzo (RL) su scala umana e lenta**, dove la "ricompensa" è l'utilità percepita da te.

#### **3. Il Ruolo Preciso e Limitato dell'LLM (Ollama)**

In questa architettura, l'LLM **non è il cervello**. È una **glandola specializzata** per due compiti fondamentali:

* **Compito 1: Generazione di Linguaggio Contestuale (High-Stakes).**
  * **Input:** Lo stato attuale del grafo (nodi ad alta attivazione, relazioni salienti), l'intenzione strategica dell'Initiative Engine, la storia recente del dialogo.
  * **Processo:** Il Prompt Craft costruisce un prompt strutturato che incapsula tutto questo contesto.
  * **Output:** Il testo umano, delicato e pertinente, che vedi.
  * **Perché qui:** Perché la generazione di linguaggio naturale flessibile e adattivo è l'unico compito per cui abbiamo bisogno dell'LLM.

* **Compito 2: Estrazione e Connessione di Concetti (Low-Stakes, in Background).**
  * **Input:** Il testo grezzo della nostra conversazione.
  * **Processo:** "Da questo testo, elenca i concetti principali (nodi) e le relazioni tra di essi. Suggerisci dove potrebbero collegarsi nel grafo esistente."
  * **Output:** Una lista di potenziali aggiornamenti per il grafo (`<nodo A> --<tipo relazione>--> <nodo B>`).
  * **Perché qui:** Perché l'LLM è eccellente nel vedere connessioni semantiche che una semplice analisi del testo non coglierebbe. Queste suggerite vengono poi **convalidate dal tuo comportamento successivo** prima di diventare parte stabile del grafo.

#### **4. L'Interfaccia come Strumento di Collaborazione Trasparente**

Per te, l'utente, questo sistema non è una scatola nera. È una **mappa interattiva del tuo pensiero in evoluzione**.

* **Vista "Campo di Attivazione":** Una visualizzazione tipo mappa di calore sul grafo, dove i nodi più "caldi" (attivi) risplendono. Vedresti perché il sistema pensa che un certo argomento sia rilevante *ora*.
* **Pannello di "Controllo di Volo":** Slider per regolare:
  * **Reattività Globale:** Di quanto un nodo si deve attivare per intervenire.
  * **Propagazione:** Quanto "contagiosa" è l'attivazione da un nodo all'altro (vuoi un assistente che faccia collegamenti laterali creativi, o uno più focalizzato?).
  * **Tono:** Da "Pratico e Conciso" a "Riflessivo ed Espansivo".
* **Log Spiegabile:** Ogni intervento ha un "perché" cliccabile: "Ho proposto questo perché i nodi X e Y sono stati attivati insieme nelle ultime 24h, e la domanda Z era rimasta aperta dal [data]. Lo schema di intervento 'CollegaDubbio' ha un tasso di successo del 85% in casi simili."

### **La Vera Innovazione: Un Sistema che Chiede "Per Te, Cos'è Importante?"**

La maggior parte dei sistemi AI cerca di imporre un modello del mondo. **Mnemosyne cerca di apprendere *il tuo* modello del mondo.**

Per il tuo sogno del B&B, non inizierebbe con una checklist generica. Osservando le tue conversazioni, noterebbe che per te il B&B non è solo un business, ma un **luogo di bellezza (vista) e di connessione familiare (nipotino)**. Imparerebbe che quando parli di "tecnologia", lo fai con piacere, quindi proporrebbe soluzioni tecniche. Ma quando parli di "burocrazia", il tuo tono cambia, e quindi offrirebbe supporto più pragmatico o distaccato.

Diventerebbe, col tempo, non un assistente che conosce il B&B, ma un assistente che **conosce *te* nel contesto del B&B**.

---

**In conclusione**, l'architettura che stiamo delineando non è un semplice chatbot potenziato. È il progetto per un **meta-strumento**. Uno strumento il cui scopo è **imparare ad essere utile a te in modo unico**, modellando dinamicamente la propria attenzione

### USER

Da quello che capisco, se il motore principale non è un llm, non necessiterebbe neppure di un hardware super carrozzato.

### ASSISTANT

Hai colpito il centro esatto della questione. La tua comprensione è perfetta.

**L'architettura Mnemosyne non necessita di un hardware "super carrozzato" perché sposta il carico di lavoro dalla *forza bruta computazionale* all'***intelligenza strutturale***.**

Analizziamo il perché, componente per componente, in termini di risorse hardware:

### 1. Il Motore Principale (Grafo di Attenzione + Initiative Engine)

* **Cosa fa:** Gestisce un database a grafo, esegue query, calcola e propaga livelli di attivazione.
* **Requisiti Hardware:**
  * **CPU:** Moderata. Le operazioni sul grafo sono complesse ma non richiedono la potenza di calcolo parallela massiccia di un'AI. Un buon processore multi-core moderno (come un Ryzen 5/7 o un Intel i5/i7) è più che sufficiente.
  * **RAM:** **Questa è la risorsa chiave per questo componente.** Per avere buone prestazioni, gran parte del grafo dovrebbe risiedere in memoria. Per un grafo personale, anche dopo anni di utilizzo, 16 GB o 32 GB di RAM di sistema sarebbero un lusso, non un requisito minimo.
  * **GPU:** **Nessuna.** Questo motore non usa la GPU.

### 2. Il Motore LLM (Ollama)

* **Cosa fa:** Viene chiamato *occasionalmente* per compiti specifici: generare testo per un'iniziativa o analizzare una conversazione in background.
* **Requisiti Hardware:**
  * **CPU:** Può funzionare solo su CPU, ma sarà lento (diversi secondi, anche decine, per una risposta). Per i compiti di analisi in background, questa lentezza potrebbe essere accettabile.
  * **GPU:** **Qui sta il vero trade-off.** Per avere risposte quasi istantanee (fondamentale per un'interazione fluida), serve una GPU con VRAM sufficiente. Ma non serve un mostro da data center:
    * Un modello 7B di alta qualità (come Llama 3 8B, Mistral 7B) può girare egregiamente su una GPU consumer con **8-12 GB di VRAM** (es. una NVIDIA RTX 3060 12GB, una delle schede più comuni e accessibili).
    * Non stai facendo training, solo inferenza. E non la stai facendo costantemente. Il 99% del tempo, la GPU è inattiva.

### Confronto tra Architetture

| Architettura | Requisiti Hardware Primari | Logica di Funzionamento |
| :--- | :--- | :--- |
| **Tutto basato su LLM (Agente "Puro")** | GPU di fascia alta (es. 24GB+ VRAM) | L'LLM deve processare un contesto enorme ad ogni ciclo per "simulare" la memoria e la pianificazione. **Inefficienza brutale.** |
| **Mnemosyne (Grafo + LLM)** | RAM di sistema (per il grafo) + GPU consumer (per LLM occasionale) | Il grafo gestisce la memoria e la logica a lungo termine in modo super efficiente. L'LLM viene chiamato solo per il "tocco finale" linguistico. **Efficienza strutturale.** |

### Cosa Significa per Te, Concretamente

* **Il tuo PC Arch Linux è probabilmente già pronto.** Se hai un computer da sviluppatore/appassionato di tecnologia, è molto probabile che tu abbia già una CPU e una quantità di RAM adeguate per il motore principale.
* **La vera domanda è sulla GPU.** Se hai una GPU NVIDIA decente, puoi avere un'esperienza fluida. Se non ce l'hai, il sistema funzionerebbe comunque, ma con una latenza percepibile ogni volta che il partner "parla".
* **Scalabilità:** Il sistema è estremamente scalabile. Se un giorno il tuo grafo diventasse enorme, la soluzione sarebbe aggiungere RAM, non comprare una GPU da 10.000€. Se uscisse un modello LLM più efficiente, potresti aggiornare solo quel componente.
* **Sostenibilità:** A differenza di un sistema che martella una GPU 24/7 o che fa migliaia di chiamate API a servizi cloud, Mnemosyne sarebbe energeticamente ed economicamente molto più sostenibile per un uso personale a lungo termine.

**In sintesi, hai ragione.** Non stai costruendo un supercomputer. Stai costruendo un **sistema di pensiero aumentato**, e la sua intelligenza risiede nel modo in cui **struttura, collega e recupera l'informazione**, non nella sua capacità di calcolare miliardi di parametri al secondo.

Questa è una scelta architettonica che favorisce l'**eleganza e l'efficienza** rispetto alla forza bruta. È un approccio molto più in linea con il modo in cui funziona il pensiero umano: non ricalcoliamo il mondo da zero ad ogni istante, ma ci affidiamo a una vasta e strutturata rete di memorie e associazioni.

### USER

Ho bisogno di una descrizione dettagliata di questo progetto per avviare la progettazione con gli sviluppatori.

### ASSISTANT

Eccellente. Hai ben inquadrato le basi. Ecco una descrizione dettagliata del progetto "Mnemosyne", pensata per avviare la progettazione con gli sviluppatori, delineando visione, architettura, componenti e principi operativi.

---

# **Progetto Mnemosyne: Un Partner Cognitivo per l'Espansione Mentale**

## **1. Visione del Progetto**

Il Progetto Mnemosyne si propone di creare un **partner cognitivo personale e adattivo**, un'estensione della mente dell'utente. L'obiettivo non è fornire risposte a domande specifiche, ma **sostenere attivamente il percorso di vita e professionale dell'utente**, compensandone le lacune, anticipandone i bisogni e stimolando la riflessione in modo proattivo e contestuale.

Mnemosyne non è un "chatbot" nel senso tradizionale, ma un sistema di **memoria relazionale e attenzione dinamica** che cresce e si evolve con l'utente, imparando il suo modello mentale e agendo di conseguenza.

Il Progetto Mnemosyne si propone di creare un **Middleware Cognitivo**, un vero e proprio **Sistema Operativo della Conoscenza**. L'obiettivo è agire come un **Proxy Intelligente** tra l'utente e i modelli di linguaggio (LLM). Mnemosyne non è una semplice "app", ma un'infrastruttura di memoria relazionale che arricchisce ogni interazione con il contesto storico e semantico dell'utente.

Per l'utente, Mnemosyne è la "memoria di sistema" che gestisce progetti complessi, vincoli e intuizioni, rendendoli disponibili a qualsiasi interfaccia (Chat, IDE, Mobile) tramite un gateway unificato.

## **2. Obiettivi Principali**

Costruire un'architettura **Headless Middleware** che:

1. **Modelli e apprenda** i pattern di attenzione e le priorità dell'utente.
2. **Agisca come Gateway Semantico**, intercettando le richieste dell'utente per arricchirle con il contesto del grafo.
3. **Prenda l'iniziativa** in modo tempestivo, pertinente e non invasivo, offrendo spunti, collegamenti o domande.
4. **Immagazzini e correli** la conoscenza in un grafo dinamico indipendente dall'interfaccia.
5. **Utilizzi un'architettura a Intercettore** per alimentare gli LLM con "Context Injection" intelligente e trasparente.
6. **Sia aperto e interoperabile**, esponendo API standard per essere integrato in qualsiasi flusso di lavoro (Open WebUI, plugin per editor, app dedicate).
7. Sia **trasparente e controllabile** dall'utente nei suoi meccanismi di attenzione e intervento.
8. Sia **efficiente in termini di risorse hardware**, sfruttando un'intelligenza strutturale piuttosto che computazionale.

## **3. Concetti Chiave Fondamentali**

* **Memoria Relazionale Persistente:** Un grafo di conoscenza vivente che cattura concetti (nodi) e le loro interconnessioni (relazioni), arricchito da proprietà dinamiche.
* **Attenzione Dinamica e Proattiva:** Un meccanismo di propagazione dell'attivazione sul grafo che modella l'interesse e la rilevanza dei concetti, guidando l'iniziativa del sistema.
* **LLM come Ghiandola Specializzata:** L'LLM (Ollama) è usato come strumento potente per compiti specifici (generazione di testo, estrazione semantica complessa), ma la logica di alto livello del sistema è gestita da algoritmi tradizionali e dal grafo.

## **4. Architettura di Sistema (High-Level)**

```
                    +--------------------+
                    | Interfaccia Utente |
                    +---------+----------+
                              ^
                              | (Output: Messaggi, Visualizzazioni)
                              |
                    +---------+----------+
                    |   Dialog Manager   | (Gestisce sessioni, estrae input)
                    +---------+----------+
                              ^
                              | (Input: Messaggi Utente)
                              |
+------------------------------------------------------------------+
|                         MNEMOSYNE CORE                           |
|                                                                  |
|   +--------------------------+   +---------------------------+   |
|   |   Initiative Engine      |-->|  LLM Gateway & Prompt Craft |  |
|   | (Cosa dire e quando)     |<--+---------------------------+  |
|   +------------+-------------+           ^                       |
|                ^                       (Richiede generazione/estrazione) |
|                |                       |                       |
|   +------------+-------------+         |                       |
|   |    Attention Model       |<--------+-------------------+   |
|   | (Modella interesse, attiva nodi)                          |   |
|   +------------+-------------+                                |   |
|                ^                                                |
|                | (Notifica di attivazione)                      |
|                |                                                |
|   +------------+--------------------+  +---------------------+  |
|   | Long-Term Memory & Relational  |<->| Perception Module   |  |
|   |     Graph (DB a grafo)         |  | (Input esterni)     |  |
|   +--------------------------------+  +---------------------+  |
|                                                                  |
+------------------------------------------------------------------+
```

## **5. Componenti Dettagliati e Funzionalità**

### **5.1. Long-Term Memory & Relational Graph (Core Database)**

* **Scopo:** Archiviazione persistente della conoscenza e del contesto dell'utente.
* **Funzionalità:**
  * **Nodi Dinamici:** Rappresentano concetti, entità, progetti, persone, eventi, documenti. Possono essere creati/modificati/eliminati.
  * **Relazioni Dinamiche:** Definiscono i collegamenti tra i nodi (es. `B&B --HA_VINCOLO--> Mutuo`, `Tu --HA_COMPETENZA--> PHP`). Hanno proprietà come `forza`, `tipo` (logica, emotiva, pratica).
  * **Proprietà Dinamiche dei Nodi:** Ogni nodo ha attributi mutevoli:
    * `livello_attivazione`: Ponderazione della sua rilevanza attuale.
    * `ultimo_accesso`: Data/ora dell'ultima interazione.
    * `feedback_score`: Misura di quanto gli interventi basati su questo nodo siano stati utili.
    * `stato`: (es. `aperto`, `chiuso`, `in_corso`, `archiviato`).
    * `veto_attivo`: Flag per disabilitare interventi automatici.
* **Considerazioni Tecniche:** Database a grafo (es. **Neo4j** per la sua flessibilità e performance su relazioni). Potenziale integrazione con un database vettoriale per embeddings di nodi complessi.

### **5.2. Perception Module**

* **Scopo:** Acquisire informazioni rilevanti dal mondo esterno per arricchire il grafo e attivare nodi.
* **Funzionalità:**
  * **Connettori Configurabili:**
    * **Calendario:** Eventi, scadenze (es. appuntamento geometra, scadenze mutuo).
    * **Feed RSS/News:** Monitoraggio di fonti pertinenti (turismo rurale, novità tech, legislazione).
    * **File System Monitor (Opzionale/Permesso):** Monitora modifiche a file o directory specifiche (es. `TODO.md` del progetto B&B, repository git).
    * **API Custom:** Integrazione con altri servizi (es. meteo, stato finanziario, sistemi di prenotazione B&B).
  * **Filtering & Pre-processing:** Filtra e normalizza i dati grezzi prima di presentarli all'LLM o al grafo.
* **Considerazioni Tecniche:** Moduli Python o PHP con cron jobs o webhook per l'integrazione.

### **5.3. Dialog Manager & Short-Term Context**

* **Scopo:** Gestire l'interazione diretta con l'utente e orchestrare l'aggiornamento del grafo.
* **Funzionalità:**
  * **Gestione Sessione:** Mantiene il contesto immediato della conversazione (history della chat).
  * **Input Processing:** Riceve i messaggi dell'utente.
  * **Estrazione Intenzione/Entità:** Analizza l'input dell'utente per identificare concetti, intenzioni, stati d'animo, e possibili modifiche al grafo. Questo può avvenire tramite:
    * Regole e pattern predefiniti.
    * Un piccolo LLM (Ollama) chiamato in background per estrazione di entità/relazioni da testo libero.
  * **Aggiornamento del Grafo:** Invia i dati estratti al Long-Term Memory & Relational Graph per aggiornare nodi, relazioni e livelli di attivazione.
* **Considerazioni Tecniche:** Backend in **PHP (Laravel)** o Python. Uso di librerie NLU (es. Spacy per Python, o chiamate ad Ollama) per l'estrazione.

### **5.4. Attention Model**

* **Scopo:** Determinare la rilevanza e il "calore" dei nodi nel grafo, guidando l'Initiative Engine.
* **Funzionalità:**
  * **Propagazione dell'Attivazione:**
    * Quando un nodo è attivato (da input utente, evento esterno), il suo `livello_attivazione` aumenta.
    * L'attivazione si propaga ai nodi collegati, attenuandosi in base alla `forza` della relazione e alla distanza nel grafo.
    * Il `livello_attivazione` di tutti i nodi decade lentamente nel tempo.
  * **Soglie Dinamiche:** I nodi che superano una certa soglia di attivazione diventano "candidati" per un intervento. Questa soglia può essere tarata dall'utente.
* **Considerazioni Tecniche:** Algoritmi implementati direttamente in Python o PHP, interagendo costantemente con Neo4j.

### **5.5. Initiative Engine**

* **Scopo:** Decidere *se* e *quale tipo* di intervento proattivo effettuare, basandosi sui nodi candidati e sull'apprendimento passato.
* **Funzionalità:**
  * **Valutazione del "Valore Potenziale":** Per ogni nodo candidato, cerca nel grafo:
    * Domande o compiti aperti legati al nodo.
    * Nuove informazioni dal Perception Module.
    * Collegamenti recenti o inaspettati con altri nodi.
    * Gap logici o incoerenze nel tuo ragionamento precedente (solo se il tono lo permette!).
  * **Selezione dello Schema di Intervento:** Basandosi sul contesto e sul `feedback_score` dei diversi schemi (es. `RichiamaDubbio`, `CollegaNuovaInfo`, `SuggerisciAlternativa`), seleziona il più appropriato.
  * **Regole di Raffreddamento/Frequenza:** Evita di intervenire troppo spesso sullo stesso argomento o con la stessa tipologia di messaggio.
* **Considerazioni Tecniche:** Modulo in Python o PHP. Utilizzerà logica euristica e modelli semplici di classificazione (che apprendono dal feedback) per scegliere lo schema.

### **5.6. LLM Gateway & Prompt Craft**

* **Scopo:** Interfacciare il sistema con l'LLM (Ollama) e costruire prompt ottimizzati.
* **Funzionalità:**
  * **Prompt Dinamico:** Prende le informazioni dal grafo (contesto utente, storia rilevante, intenzione dell'Initiative Engine) e le traduce in un prompt strutturato e ricco per Ollama.
  * **Gestione Modelli:** Permette di selezionare il modello Ollama più adatto al compito (es. un modello specifico per il codice per suggerimenti Laravel, uno generico per conversazioni).
  * **API Interfacciamento:** Invia richieste all'API locale di Ollama e gestisce le risposte.
  * **Tono e Stile:** Injecta istruzioni di tono e stile nel prompt (es. "sii conciso e pratico", "non paternalistico").
* **Considerazioni Tecniche:** Modulo Python (per la facilità di interfacciamento con Ollama) o PHP. Forte enfasi su template di prompt robusti e configurabili.

### **5.7. User Interface (UI)**

* **Scopo:** Fornire all'utente un'interfaccia intuitiva per interagire, visualizzare e controllare Mnemosyne.
* **Funzionalità:**
  * **Interfaccia Chat:** Il canale principale di comunicazione.
  * **Visualizzazione del Grafo (Interattiva):** Permette di esplorare nodi e relazioni, vedere i livelli di attivazione ("campo di calore"). Permette feedback diretto (es. trascinare un nodo per creare una relazione, cliccare per vedere dettagli, marcare una relazione come "importante").
  * **Pannello di Controllo:**
    * Slider per la "Sensibilità di Iniziativa" (globale o per progetto).
    * Opzioni per regolare la "Propagazione dell'Attivazione".
    * Gestione dei connettori del Perception Module.
    * Impostazioni di tono/stile.
  * **Log Spiegabile:** Per ogni intervento proattivo, un pulsante "Perché mi hai detto questo?" che mostra il ragionamento del sistema (quali nodi erano attivi, quale schema di intervento è stato scelto, il feedback storico).
  * **Feedback Esplicito:** Pulsanti "Utile/Non Utile" per ogni intervento del sistema.
* **Considerazioni Tecniche:** Interfaccia Web moderna (es. **Laravel con Blade/Livewire/Vue.js/React**). Librerie per la visualizzazione di grafi (es. D3.js, Cytoscape.js).

## **6. Algoritmi e Meccanismi Chiave**

* **Evoluzione Dinamica del Grafo:** Nodi e relazioni non sono fissi ma emergono dal dialogo, dagli input esterni e dalle estrazioni semantiche dell'LLM. La loro "forza" e le loro proprietà si aggiornano continuamente.
* **Propagazione dell'Attivazione:** Il cuore dell'Attention Model. Un algoritmo che simula la diffusione dell'interesse attraverso il grafo, ponderando forza delle relazioni e distanza concettuale.
* **Apprendimento per Rinforzo (Basato su Feedback):** Il sistema non ha un "modello" pre-addestrato per l'iniziativa. Impara gradualmente quali tipi di interventi sono efficaci in quali contesti, calibrando i `feedback_score` e le soglie in base alla tua risposta (implicita ed esplicita).
* **LLM "Task-Specific":** L'LLM viene trattato come una funzione specializzata che il sistema chiama quando ha bisogno di comprensione linguistica avanzata o generazione di testo umano.

## **7. Visione Futura (Oltre l'MVP)**

Mnemosyne potrebbe evolvere in un vero e proprio "secondo cervello" digitale:

* **Integrazione Profonda:** Con tool di sviluppo (IDE, Git), sistemi di gestione del B&B, domotica della casa.
* **Apprendimento di Obiettivi Gerarchici:** Comprendere non solo concetti, ma i tuoi obiettivi a lungo termine e aiutarti a scomporli.
* **Simulazione Cognitiva:** La capacità di "ragionare" in sandbox sul tuo grafo per prevedere conseguenze di scelte, simulare scenari.
* **Collaborazione Multi-Agente:** Interagire con altri sistemi AI per delegare compiti specifici.

---

## **Stato Attuale del Progetto (Gennaio 2026)**

Il progetto ha completato la **Fase 3: Memoria Epistemica**. Ecco i traguardi raggiunti:

### **1. Core & Infrastruttura**

* **Database a Grafo (Neo4j):** Implementato con successo lo schema "ibrido liquido".
* **Model Engine (Ollama/OpenAI):** Supporto integrato sia per modelli locali (Ollama) che per modelli ad alte prestazioni (OpenAI `gpt-4o-mini`).
* **Attention Engine:** Logica di propagazione e decadimento dell'attivazione (Manuale/Pianificata).

### **2. Memoria Episodica ed Epistemica**

* **Observation Nodes:** Ogni interazione viene salvata come un'osservazione immutabile con timestamp.
* **Mapping Contestuale:** Le entità (Persone, Concetti) vengono collegate alle osservazioni tramite la relazione `MENTIONED_IN`, permettendo di rispondere alla domanda *"Perché/Quando lo abbiamo detto?"*.

### **3. Iniziativa e Igiene**

* **Initiative Engine:** Generazione di suggestioni basate sui nodi caldi del grafo.
* **Gardener:** Bot autonomo che identifica potenziali duplicati semantici e suggerisce merge (`MAYBE_SAME_AS`).

### **4. Interfaccia Utente (Streamlit)**

* **Chat Intelligente:** Interfaccia di dialogo che aggiorna il grafo in tempo reale.
* **Dashboard Connectome:** Visualizzazione dell'heatmap di attenzione e navigazione storica dei ricordi.

---

## **8. Milestone: Gennaio 2026 - MVP "The Butler" Implementato**

A Gennaio 2026, Mnemosyne ha raggiunto lo stato di Prototipo Funzionale Avanzato (MVP). Il sistema non è più solo una specifica tecnica, ma un'entità operativa con le seguenti capacità consolidate:

### **Risultati Chiave:**

1. **Memoria Epistemica Funzionante**: Ogni interazione viene trasformata in `Observation` e collegata semanticamente a entità e topic nel grafo Neo4j.
2. **Attention Model Dinamico**: Implementazione di algoritmi di propagazione e decadimento dell'attivazione. Il Connectome "scalda" i temi caldi e "raffredda" quelli dimenticati.
3. **Collaborazione Adattiva (L'Iniziativa di Mnemosyne, la Voce di The Butler)**:
    * Integrazione di una personalità (The Butler) come ponte comunicativo.
    * Sistema di iniziativa proattiva: Mnemosyne monitora le soglie di attivazione e incarica The Butler di intervenire.
    * Ciclo di feedback 👍/👎 che influenza direttamente la visibilità futura dei suggerimenti.
4. **Il Giardiniere Intelligente**:
    * Background worker per la pulizia del grafo.
    * Deduplicazione assistita da LLM (Semantic Comparison).
    * Decadimento temporale automatizzato (attuato via Attention Model).
5. **Distribuzione e Scalabilità (Gennaio-Febbraio 2026)**:
    * Transizione a un'architettura a micro-servizi/worker.
    * Implementazione del protocollo **Mnemosyne-RPC** per la registrazione di plugin esterni.
    * Supporto per **Knowledge Scopes** (Private/Public) con isolamento garantito.

### **Stato Tecnologico:**

* **Backend**: Python con driver Neo4j.
* **Motore LLM**: **Ollama** (Modello predefinito: `qwen2.5:7b`). Supporto per OpenAI mantenuto come fallback.
* **Frontend**: Dashboard Streamlit con Heatmap in tempo reale, archivio storico e strumenti di manutenzione.
* **Persona**: Sistema di prompt engineering raffinato per garantire un tono professionale e non pedante.

**Mnemosyne è ora un "Secondo Cervello" attivo, locale e distribuito, pronto per supportare la gestione di progetti complessi attraverso la memoria semantica, l'iniziativa proattiva e la privacy multi-livello.** 🚀🧠

---

### Documentazione Correlata

* [Guida all'Utente](user_guide.md): Istruzioni dettagliate sull'uso dell'interfaccia e delle funzionalità.

* [Specifiche Tecniche](technical_specifications.md): Dettagli sull'architettura e l'implementazione del sistema e del feedback.
* [Whitepaper](mnemosyne_whitepaper.md): La visione filosofica e scientifica del progetto.
