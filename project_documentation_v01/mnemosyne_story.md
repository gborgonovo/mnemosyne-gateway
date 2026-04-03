# Mnemosyne: La Storia di un Partner Cognitivo

Benvenuto in questo progetto. Se stai leggendo queste righe, probabilmente hai appena scaricato il codice di Mnemosyne e ti stai chiedendo cosa sia esattamente: un database? Un assistente AI? Un sistema di note?

Lascia che ti racconti come è nato, perché ha questa architettura e qual è la visione che lo guida. Ti porterò in un breve tour di quello che considero il mio "secondo cervello" attivo.

---

## 1. Il Sogno e la Lacuna

Tutto è iniziato con una casa in campagna da ristrutturare. Il mio obiettivo era trasformarla in un piccolo B&B, un progetto personale che amavo ma che mi sommergeva di dettagli: preventivi, scelte tecniche (dagli infissi al sistema di riscaldamento), vincoli burocratici e sogni ad occhi aperti sull'esperienza degli ospiti.

Mi sono accorto subito di un problema: il classico "botta e risposta" con i modelli linguistici (LLM) non bastava. Ogni volta dovevo rispiegare tutto. Le mie note erano frammentate. Quello che mi serviva non era un tool reattivo che rispondeva solo se interrogato, ma un **partner cognitivo**.

Volevo qualcosa che:

* Avesse una **continuità di pensiero** attraverso le settimane.
* Possedesse una **memoria storica** delle decisioni prese.
* Fosse capace di **offrire spunti inattesi**, non solo quando glielo chiedevo, ma quando "sentiva" che potevano servire.

## 2. Mnemosyne vs The Butler: Il Cervello e la Voce

Per realizzare questa visione, ho diviso il sistema in due entità distinte:

* **Mnemosyne (Il Cervello Silente):** È l'infrastruttura. È un grafo relazionale (che chiamo *Connectome*) basato su Neo4j. Non "parla" direttamente, ma accumula informazioni, crea collegamenti e gestisce il "calore" semantico.
* **The Butler (Il Layer Relazionale):** È l'interfaccia. È la personalità che traduce le intuizioni del grafo in atti comunicativi. Oggi lo incontri come server **MCP** o tramite il gateway, ed è lui a darti del tu (o del lei) con tatto e pertinenza.

## 3. L'Evoluzione: Da App a Middleware

All'inizio, Mnemosyne era un'applicazione monolitica. Ma ho capito presto che la conoscenza non dovrebbe essere prigioniera di un'unica interfaccia.

Oggi Mnemosyne è un **Cognitive Middleware Headless**. È un ecosistema distribuito:

* Un **Gateway Centrale (FastAPI)** coordina il traffico.
* Dei **Distributed Workers** si occupano dei compiti pesanti in background (estrazione di entità, generazione di briefing).
* Una **Knowledge Queue** gestisce i flussi di informazione in modo asincrono, così le tue conversazioni restano fluide mentre il sistema "pensa" e archivia.

## 4. Come Funziona la "Magia" (Intuizione Tecnica)

Se sei uno sviluppatore, ti interesserà sapere che il cuore non è l'LLM. L'LLM (uso spesso **Ollama** localmente) è come una ghiandola specializzata che interviene solo alla fine per dare forma al linguaggio.

Il vero motore è un **modello di attenzione su grafo**. Hai presente il paper *"Attention is All You Need"*? Ecco, immagina di trasportare quel concetto dai singoli token (parole) al livello dei concetti (nodi del grafo).

* **Nodi e Attivazione:** Argomenti come "B&B", "Mutuo" o "Progetto Veranda" sono nodi che si "scaldano" quando ne parliamo.
* **Propagazione:** Se parliamo del mutuo, il calore si propaga ai concetti collegati (come il B&B).
* **Iniziativa:** Quando un nodo supera una certa soglia di calore e il sistema trova una "domanda aperta" o una nuova informazione correlata, decide di prendere l'iniziativa.

Non è un timer che scatta dopo 30 giorni. È un'**associazione contestuale**: il sistema interviene perché l'argomento è tornato rilevante nel flusso naturale del tuo pensiero.

## 5. Privacy e Conoscenza: Gli Scopes

Lavorando a Mnemosyne, mi sono scontrato con un tema cruciale: la privacy. Non tutta la conoscenza è uguale.
Ho implementato i **Knowledge Scopes**:

* **Private:** Le mie riflessioni più intime, i miei vincoli personali.
* **Internal:** Dati di lavoro o di progetto, condivisi solo con partner stretti o script fidati.
* **Public:** Informazioni pronte per essere date in pasto al mondo o agli LLM più grandi.

Il sistema garantisce che un segreto salvato nello scope `Private` non venga mai usato per alimentare un contesto destinato a un'interfaccia pubblica.

## 6. Il Giardiniere (Deduplicazione Semantica)

Un grafo che cresce costantemente rischia di sporcarsi. Per questo esiste il **Gardener**. È un worker autonomo che periodicamente "pota" e pulisce la memoria. Cerca nodi che sembrano simili (magari chiamati in modo leggermente diverso) e suggerisce di unirli, mantenendo la memoria epistemica ordinata e coerente.

---

## 7. Verso il Futuro

Mnemosyne è un progetto in continua evoluzione. Dalla semplice gestione di note, sta diventando un sistema capace di **analisi longitudinale** (capire come le tue idee sono cambiate in un anno) e di **focalizzazione proattiva**.

È una ricerca verso un'interfaccia adattiva per il pensiero a lungo termine. Spero che questo "pezzo di codice" possa diventare anche per te un compagno di viaggio prezioso come lo è per me.

Buon viaggio cognitivo!

---
*Questa narrazione riflette la visione e lo stato del progetto a Febbraio 2026.*
