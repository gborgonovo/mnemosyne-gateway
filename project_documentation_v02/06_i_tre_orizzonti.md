# I tre orizzonti

## Una roadmap che parte dal perché

Le roadmap tecniche elencano feature. Questa no — o almeno, non solo.

Ogni decisione di sviluppo in Mnemosyne si colloca in uno di tre orizzonti temporali, ciascuno con un obiettivo preciso. Sapere a quale orizzonte appartiene una scelta aiuta a capire perché è stata presa, e cosa deve essere vero prima che abbia senso farla.

Il principio guida è semplice: **si costruisce dal kernel verso l'esterno**. Un'interfaccia brillante su un kernel instabile è inutile. Un'integrazione sofisticata su una memoria inaffidabile è rumorosa. L'ordine non è arbitrario.

---

## Le fondamenta: fasi 1–9 (completate)

Le prime nove fasi hanno costruito il kernel e i primi due cerchi. Esistono e funzionano.

**Il kernel distribuito (fasi 1–3)**: il Connectome Neo4j, il modello di attenzione con propagazione e decadimento, il Gateway FastAPI come punto di ingresso unico, il sistema di Worker distribuiti (LLMWorker, BriefingWorker), la Knowledge Queue per l'elaborazione asincrona, e il protocollo Mnemosyne-RPC per l'estensione tramite plugin.

**Sovranità e intenzionalità (fasi 4–7)**: il sistema di Knowledge Scopes per la privacy, gli strumenti MCP per la gestione diretta della memoria, il modello di attenzione differenziale (Goals e Task decadono più lentamente dei Topic), il TimeWatcher per il monitoraggio delle scadenze, e la gestione di Goal e Task come entità di primo livello nel grafo.

**Intelligenza emergente (fasi 8–9)**: l'ingestione documentale massiva con HeuristicChunker zero-LLM, il Semantic Firewall per proteggere il contesto attivo dal rumore documentale, l'analisi longitudinale per il rilevamento di trend e progetti dormienti, la Dashboard Streamlit con visualizzazione del Connectome, e il Document Manager con archiviazione fisica e Deep Delete.

---

## Orizzonte vicino — Memoria affidabile

*Obiettivo: niente si perde, tutto è recuperabile, il contesto sopravvive tra sessioni e progetti.*

Questo orizzonte non aggiunge funzionalità nuove — consolida quelle esistenti e risolve le frizioni operative che impediscono a Mnemosyne di entrare nel flusso quotidiano.

**Stabilizzazione delle integrazioni**: verifica e debug delle integrazioni esistenti (Open WebUI Filter e Tool), con particolare attenzione alla catena Gateway → LLMWorker → grafo. Il sistema deve essere trasparente: quando qualcosa non funziona, deve essere chiaro dove e perché.

**Namespace applicativo**: introduzione del namespace come layer di isolamento per applicazione, sopra gli scope di visibilità. Permette a strumenti diversi di condividere Mnemosyne senza contaminarsi — ogni applicazione accede solo ai propri nodi.

**CRUD per tipo di entità**: endpoint dedicati per la gestione esplicita di Goal, Task, Topic, Observation e Document — con semantica appropriata per ogni tipo. Observation e Document non sono aggiornabili, solo sostituibili.

**Filesystem Watcher**: monitoraggio silente di cartelle di lavoro. Se un file viene modificato, il nodo corrispondente nel grafo si scalda automaticamente. Elimina l'attrito dell'alimentazione manuale per chi lavora con file locali.

**Butler — primo livello**: prima istanza operativa del Butler, con contratto di osservazione minimale (scadenze, nodi energizzati) e un canale di notifica configurato. L'obiettivo non è un Butler completo — è un Butler che funziona e non fa rumore.

---

## Orizzonte medio — Connessione tra i mattoncini

*Obiettivo: il sistema mostra il filo che collega i progetti, suggerisce le connessioni, tiene viva la visione d'insieme mentre si lavora sui dettagli.*

Questo orizzonte aggiunge intelligenza al sistema — non solo memoria, ma comprensione dei pattern nel tempo.

**Cognitive Tiering**: il Gateway decide quale modello LLM usare in base alla complessità del task e alla sensibilità dello scope. Un Task di routine usa un modello leggero locale. Un'analisi strategica complessa può usare un modello più potente. Se un worker remoto cade, il sistema riparte su un'euristica locale. L'utente configura i tier; il sistema sceglie autonomamente.

**Strategic Planning**: il Butler aiuta a scomporre macro-obiettivi in passi operativi, usando il contesto del grafo come base. Quando un Goal è attivo ma senza Task, il Butler propone una decomposizione basata su quanto già sa del progetto.

**Analisi d'impatto (Sandbox)**: simulazione "what-if" sulla rete di dipendenze del grafo. Se un Task non viene completato, quali Goal sono a rischio? L'output non è un calcolo deterministico — è una mappa di dipendenze che aiuta l'utente a ragionare sulle conseguenze.

**Perception Connectors**: integrazione con fonti di contesto esterne — calendario, feed RSS, notifiche di strumenti — che iniettano eventi nel flusso di suggerimenti del Butler. Il sistema inizia a percepire non solo ciò che l'utente gli dice esplicitamente, ma anche ciò che accade nel suo ambiente digitale.

**Risoluzione guidata delle ambiguità**: flusso completo per la gestione dei `MAYBE_SAME_AS` — rilevamento da parte del Gardener, presentazione contestuale da parte del Butler durante le conversazioni, aggregazione nel briefing periodico per le ambiguità meno urgenti.

---

## Orizzonte lontano — Archivio emotivo

*Obiettivo: una rappresentazione di ciò che ha reso felice l'utente, leggibile nel tempo e potenzialmente da altri.*

Questo orizzonte è il più distante e il meno definito — intenzionalmente. Non si può progettare oggi qualcosa che dipende da quanto il sistema avrà imparato nel tempo. Si può però indicare la direzione.

**Dimensione emotiva**: le emozioni non sono dati strutturati, e Mnemosyne non è un diario. Ma è possibile aggiungere un layer di annotazione leggera — non "come ti senti", ma pattern emergenti: cosa genera energia, cosa la drena, quali progetti producono soddisfazione e quali rimangono bloccati. Questo layer si costruisce nel tempo, non si configura.

**Timeline cognitiva**: visualizzazione dell'evoluzione delle idee nel tempo. Come è nata un'idea, come si è trasformata, quando è diventata un progetto strutturato. Non una cronologia di eventi — una mappa dell'evoluzione del pensiero.

**Leggibilità nel tempo**: la memoria deve essere comprensibile non solo adesso, ma tra anni — e potenzialmente da qualcuno che non sa chi sei. Questo richiede che i nodi abbiano contesto sufficiente per essere interpretati senza il loro autore, e che il sistema mantenga la traccia del perché oltre che del cosa.

**Interoperabilità universale**: integrazione con qualsiasi strumento che contenga informazioni utili all'utente. Non un'isola — un layer universale di memoria condivisa tra tutto l'ecosistema digitale di una persona.

---

## Il principio che attraversa i tre orizzonti

Ogni fase si colloca in un orizzonte. Ogni orizzonte ha un obiettivo umano, non tecnico. Le scelte tecniche servono l'obiettivo — non il contrario.

Quando una nuova funzionalità viene proposta, la prima domanda non è "possiamo farlo" ma "a quale orizzonte appartiene, e siamo pronti per quell'orizzonte?". Aggiungere intelligenza emergente su fondamenta instabili non avvicina all'obiettivo — lo allontana.

---

*Documento 6 di 6 — I tre orizzonti*
*Progetto Mnemosyne — GiodaLab*
