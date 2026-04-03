# I quattro cerchi

## Una mappa del sistema

Mnemosyne è un sistema distribuito con molti componenti. Prima di addentrarsi nei dettagli tecnici, è utile avere una mappa — un'immagine mentale che permetta di orientarsi e di capire il ruolo di ogni pezzo nel tutto.

Quella mappa è una serie di cerchi concentrici. Ogni cerchio rappresenta uno strato del sistema, dal più fondamentale al più esteso. Si costruisce dall'interno verso l'esterno: ogni cerchio presuppone la stabilità di quello che lo contiene.

---

## Cerchio 1 — La stabilità

Il cerchio più interno è il kernel. È il cuore del sistema: il grafo Neo4j dove vive la conoscenza, il modello di attenzione che governa il calore semantico dei nodi, il Gateway FastAPI che coordina il traffico tra i componenti.

Questo cerchio non produce output visibili. Non risponde a domande, non genera suggerimenti, non agisce nel mondo. Fa una cosa sola, ma la fa bene: mantiene la memoria in uno stato coerente, vivo e interrogabile.

Senza la stabilità di questo cerchio, tutto il resto è costruito sull'acqua. È il primo problema da risolvere e il primo da verificare quando qualcosa non funziona.

*Componenti principali: Neo4j (Connectome), AttentionModel, Gateway FastAPI, Knowledge Queue.*

---

## Cerchio 2 — L'alimentazione

Il secondo cerchio sono i sensi del sistema — tutto ciò che porta informazioni dentro il grafo. Documenti caricati manualmente, conversazioni con LLM, strumenti esterni che sincronizzano i propri dati, appunti e note.

La caratteristica fondamentale di questo cerchio è che dovrebbe essere **invisibile**. Il modello ideale non è "apro Mnemosyne e inserisco un'informazione". È "uso i miei strumenti normalmente, e Mnemosyne ascolta". Ogni strumento connesso diventa un senso: percepisce una parte del mondo dell'utente e la traduce in nodi e relazioni nel grafo.

Più ricco è questo cerchio, più il sistema diventa utile. Ma la ricchezza non si misura in quantità di dati — si misura in qualità delle connessioni che il grafo riesce a costruire.

*Componenti principali: endpoint `/add` e `/ingest`, Filter di Open WebUI, integrazioni con strumenti esterni, LLMWorker per l'estrazione semantica.*

---

## Cerchio 3 — L'output verso gli LLM

Il terzo cerchio è il modo in cui Mnemosyne restituisce contesto agli strumenti intelligenti — in particolare agli LLM. Quando un modello linguistico deve rispondere a una domanda, può interrogare Mnemosyne via MCP (Model Context Protocol) e ricevere il contesto rilevante: cosa è caldo in questo momento, quali progetti sono attivi, quali decisioni sono state prese in passato.

Questo cerchio trasforma Mnemosyne da sistema di archiviazione a amplificatore cognitivo. L'LLM non parte da zero — parte da un contesto costruito nel tempo, specifico per quell'utente, filtrato per rilevanza dal modello di attenzione.

Il protocollo MCP è la scelta architettuale chiave di questo cerchio: standardizza il modo in cui qualsiasi client compatibile può attingere alla memoria, senza integrazioni custom per ogni strumento.

*Componenti principali: MCP server, endpoint `/search` e `/briefing`, sistema di Knowledge Scopes per la privacy.*

---

## Cerchio 4 — Il Butler

Il quarto cerchio è qualitativamente diverso dai precedenti. Non è un modo di portare dati dentro o fuori dal sistema — è un'entità che *osserva* il grafo e *agisce* nel mondo in risposta ai suoi cambiamenti di stato.

Il Butler non aspetta di essere interrogato. Quando un nodo supera una soglia di calore, quando una scadenza si avvicina, quando un progetto dimenticato torna rilevante — il Butler se ne accorge e reagisce. Può inviare una notifica, aprire un documento, avviare un processo, o semplicemente ricordare all'utente che esiste qualcosa su cui vale la pena tornare.

La differenza fondamentale rispetto agli altri cerchi è questa: i primi tre cerchi rendono Mnemosyne uno strumento più intelligente. Il quarto cerchio la trasforma in un partner — qualcosa che ha iniziativa propria, calibrata sullo stato interno della memoria dell'utente.

Ogni utente può istanziare il proprio Butler con una personalità e comportamenti specifici, adattati al proprio contesto e ai propri strumenti.

*Componenti principali: Event Bus, BriefingWorker, contratto di osservazione, vocabolario delle azioni.*

---

## Il principio che lega i quattro cerchi

C'è un filo comune che attraversa tutti e quattro i cerchi: **Mnemosyne dovrebbe essere invisibile finché non è necessaria**.

Non è uno strumento che si apre e si usa. È un layer che lavora sotto, silenzioso, mentre l'utente fa altro. Si manifesta solo quando ha qualcosa di rilevante da offrire — un contesto, un suggerimento, un'azione. E anche allora, dovrebbe sembrare naturale, non invasivo.

Questo principio guida ogni decisione di design: dall'alimentazione automatica degli strumenti, alla selezione del contesto rilevante via MCP, fino alla soglia di intervento del Butler. Il sistema è tanto più riuscito quanto meno si nota — e quanto più, quando si nota, è perché stava facendo esattamente la cosa giusta.

---

## Come leggere il resto della documentazione

I documenti successivi scendono nel dettaglio di ciascuno strato:

- **Documento 3** descrive il kernel — i componenti del primo cerchio: Connectome, Gateway, Workers, Scopes. È il punto di partenza per chi vuole capire le fondamenta del sistema.
- **Documento 4** descrive le integrazioni — il secondo e terzo cerchio: come si alimenta il sistema e come restituisce contesto agli LLM via MCP.
- **Documento 5** è dedicato interamente al Butler — la sua architettura, il contratto con Mnemosyne, e come costruire la propria istanza.
- **Documento 6** traccia la roadmap del progetto — dove siamo, dove stiamo andando, e perché.

---

*Documento 2 di 6 — Il modello concettuale*
*Progetto Mnemosyne — GiodaLab*
