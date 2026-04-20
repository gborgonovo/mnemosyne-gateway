# I tre orizzonti

## Una roadmap basata sul perché

Ogni decisione di sviluppo in Mnemosyne si colloca in uno di tre orizzonti temporali. Sapere a quale orizzonte appartiene una scelta aiuta a capire perché è stata presa e quali fondamenta richiede.

Dall'ingresso della versione 0.3, abbiamo ridefinito le basi: non più una complessa infrastruttura server-side (Neo4j), ma una solida struttura di file locali potenziata da indici AI invisibili.

---

## Orizzonte 1 — Memoria Sovrana e Affidabile (v0.3.x - Oggi)

*Obiettivo: Niente si perde, tu possiedi i tuoi dati, il sistema è trasparente e serverless.*

Questo orizzonte è il cuore del refactoring attuale. Abbiamo scelto la semplicità del file system per garantire che la memoria sia eterna e leggibile.
- **Transizione File-First**: Sostituzione di Neo4j con file Markdown + KùzuDB/ChromaDB.
- **Trasparenza**: La capacità dell'utente di "aprire la mente" di Mnemosyne semplicemente navigando in una cartella.
- **Resilienza**: Gli indici AI sono sacrificabili e ricreabili dai file sorgente in ogni momento.
- **Briefing & Diagnostica**: Strumenti leggeri per monitorare la salute termica e semantica del sistema.

---

## Orizzonte 2 — Connessione e Proattività (In corso)

*Obiettivo: Il sistema mostra il filo che collega i progetti, suggerisce le connessioni dormienti, agisce come un'ombra intelligente.*

In questo orizzonte, Mnemosyne smette di essere solo un archivio e inizia a comportarsi come un partner.
- **Initiative Engine**: Affinamento degli algoritmi che decidono quando iniettare un'osservazione o un suggerimento basandosi sui picchi di calore.
- **Scomposizione Obiettivi (Strategic Planning)**: L'AI usa il grafo in KùzuDB per aiutare l'utente a dividere un `Goal` in piccoli `Task` azionabili.
- **Integrazione Profonda (Obsidian-First)**: Creazione di plugin o workflow che rendono il loop Mnemosyne <-> Obsidian totalmente privo di frizione.
- **Risoluzione Ambiguità**: Il sistema rileva autonomamente se due note parlano della stessa cosa e suggerisce il merge testuale per mantenere la coerenza.

---

## Orizzonte 3 — L'Eredità Digitale (Futuro)

*Obiettivo: Una rappresentazione di ciò che ha reso felice l'utente, leggibile nel tempo e potenzialmente da altri.*

L'obiettivo finale è che Mnemosyne non sia solo utile per il "qui ed ora", ma diventi un distillato di saggezza ed esperienza personale.
- **Timeline Cognitiva**: Visualizzazione dell'evoluzione di un'idea, dalle prime osservazioni confuse fino alla realizzazione di un progetto.
- **Dimensione Emotiva**: Tracciamento dei momenti di alta energia creativa e dei blocchi, permettendo al sistema di "conoscere" il ritmo dell'utente.
- **Interoperabilità Totale**: Mnemosyne come layer di memoria standard per ogni strumento AI che l'utente deciderà di utilizzare nei prossimi decenni.

---

*Documento 6 di 7 — I tre orizzonti*
*Progetto Mnemosyne — GiodaLab*
