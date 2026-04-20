# I quattro cerchi

## Una mappa del sistema

Mnemosyne è un sistema distribuito con molti componenti. Prima di addentrarsi nei dettagli tecnici, è utile avere una mappa — un'immagine mentale che permetta di orientarsi e di capire il ruolo di ogni pezzo nel tutto.

Quella mappa è una serie di cerchi concentrici. Ogni cerchio rappresenta uno strato del sistema, dal più fondamentale al più esteso. Si costruisce dall'interno verso l'esterno: ogni cerchio presuppone la stabilità di quello che lo contiene.

---

## Cerchio 1 — La stabilità (Hybrid File-First)

Il cerchio più interno è il kernel. È il cuore del sistema. Dalla versione 0.3, questo cerchio ha cambiato natura: non è più un database server-side opaco, ma un sistema **Hybrid File-First**.

L'essenza del kernel ora è:
- **La Source of Truth**: La directory locale `knowledge/` contenente file Markdown.
- **Il Connectome Liquido**: Indici embedded veloci (KùzuDB per il grafo e ChromaDB per la semantica) che "osservano" i file e ne estraggono le relazioni.
- **La Fisica dell'Attenzione**: Il modello che governa il calore semantico dei nodi in tempo reale.

Questo cerchio non produce output visibili. Mantiene la memoria in uno stato coerente e allineato ai tuoi file testuali.

*Componenti principali: Directory `knowledge/`, File Watcher, KùzuDB (Topology), ChromaDB (Vector Store).*

---

## Cerchio 2 — L'alimentazione

Il secondo cerchio sono i sensi del sistema — tutto ciò che porta informazioni dentro il grafo. In questa nuova architettura, il modo primario di alimentare Mnemosyne è semplicemente **scrivere file**.

Che tu stia usando Obsidian, un editor di testo o un'integrazione che salva markdown in `knowledge/`, il sistema percepisce il cambiamento e lo integra nel Connectome. I vecchi endpoint API sono ora dei gateway sottili che facilitano questa scrittura.

*Componenti principali: I/O su File System, Obsidian, Integrazioni esterne, File Watcher Sync logic.*

---

## Cerchio 3 — L'output verso gli LLM

Il terzo cerchio è il modo in cui Mnemosyne restituisce contesto agli strumenti intelligenti. Gli Agenti (come OpenClaw) interrogano la memoria via MCP (Model Context Protocol).

Il sistema interroga gli indici Kùzu e Chroma per trovare i file più rilevanti (quelli coerenti per significato e caldi per attenzione) e ne restituisce il contenuto Markdown originale. Questo garantisce che l'AI lavori sempre su ciò che tu vedi e possiedi.

*Componenti principali: MCP server, Hybrid Search (Semantic + Thermal Reranking).*

---

## Cerchio 4 — Il Butler

Il quarto cerchio è l'entità che *osserva* il grafo e *agisce* nel mondo. Il Butler osserva le fluttuazioni di calore in KùzuDB e i metadati nei file Markdown.

Nella versione 0.3, il Butler si è evoluto: non è più un processo rigido nel backend, ma una capacità distribuita che può essere invocata dagli Agenti via MCP. Il "Briefing" proattivo è lo strumento principale con cui il Butler ti ricorda ciò che stai dimenticando.

*Componenti principali: Briefing Worker, Initiative Engine, Event Loop dei picchi termici.*

---

## Il principio che lega i quattro cerchi

C'è un filo comune che attraversa tutti e quattro i cerchi: **Mnemosyne dovrebbe essere invisibile finché non è necessaria**.

Non è uno strumento che si apre e si usa. È un layer che lavora sotto, silenzioso, mentre l'utente fa altro. Si manifesta solo quando ha qualcosa di rilevante da offrire. Il fatto che ora sia basata su file la rende ancora più invisibile: è integrata nel tuo normale workflow di gestione della conoscenza.

---

## Come leggere il resto della documentazione

I documenti successivi scendono nel dettaglio di ciascuno strato:

- **Documento 3** descrive il kernel — Kùzu, Chroma e il File Watcher.
- **Documento 4** descrive le integrazioni e l'uso di Obsidian.
- **Documento 5** descrive il ruolo del Butler e degli strumenti proattivi.
- **Documento 6** traccia la roadmap del progetto.
- **Documento 7** approfondisce la filosofia architetturale dell'approccio Ibrido.

---

*Documento 2 di 7 — Il modello concettuale*
*Progetto Mnemosyne — GiodaLab*
