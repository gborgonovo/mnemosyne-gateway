# Mnemosyne Roadmap 2026: Verso il Middleware Cognitivo

Questo documento delinea la strategia di evoluzione di Mnemosyne, prioritizzando l'intenzionalità, la pianificazione e l'analisi nel tempo.

---

## ✅ Fase 6: Mnemosyne Headless & API Gateway (Completata)

L'architettura è stata trasformata in un'infrastruttura accessibile ovunque come middleware.

- **FastAPI Gateway (HTTP Bridge)**: Implementato con successo per superare le limitazioni di Docker (OpenClaw).
- **Agnosticismo dell'Interfaccia**: Mnemosyne ora parla via JSON, permettendo l'integrazione di OpenClaw, Open WebUI e altri client.
- **Portabilità**: Spostamento delle integrazioni nella cartella dedicata `integrations/`.

## 🟠 Fase 7: Intenzionalità e Pianificazione Strategica (LA PRIORITÀ)

Passare dalla risposta reattiva al supporto decisionale attivo. Mnemosyne smetterà di essere solo un archivio e diventerà un partner di pensiero, usando The Butler come suo portavoce.

- **Goal & Task Intelligence**: Introduzione di nodi `Goal` (obiettivi) e `Task` (azioni). Mnemosyne identificherà quando un discorso riguarda un impegno preso.
- **Scomposizione Piani d'Azione**: Se Mnemosyne rileva un obiettivo complesso (es. "Lanciare l'app"), incaricherà The Butler di suggerire: *"Ho notato che vuoi lanciare l'app. Vuoi che proviamo a scomporre il piano in task basandoci su quanto ci siamo detti in precedenza?"*.
- **Time Consciousness**: Implementazione della consapevolezza temporale profonda. Il grafo saprà che un'informazione di tre anni fa è potenzialmente obsoleta rispetto a una di ieri, applicando un **Decadimento Differenziale** basato sull'età del dato.
- **Time Monitoring**: Mnemosyne monitorerà gli impegni e userà The Butler per informarti: *"Avevamo detto di finire X entro oggi, a che punto siamo?"* o segnalarti scadenze passate da riprogrammare.
- **Parametro "Pedanteria" (Anti-Procrastinazione)**: Possibilità di marcare un nodo come "Imperativo". Mnemosyne ignorerà il decadimento per questo nodo e aumenterà la frequenza delle sollecitazioni (tramite The Butler) finché l'obiettivo non sarà dichiarato concluso.
- **Ragionamento in Sandbox (Simulazione)**: Analisi d'impatto cognitiva. Potrai chiedere a The Butler di simulare un cambiamento e Mnemosyne analizzerà la rete di dipendenze nel grafo.

## 🟡 Fase 8: Analisi Longitudinale e Briefing (L'Insight)

Sfruttare la memoria a lungo termine per generare consapevolezza e visione d'insieme.

- **Pattern Recognition**: Identificare temi che ricorrono ciclicamente o progetti che sono finiti nel "dimenticatoio" nonostante fossero dichiarati come priorità.
- **Briefing Longitudinali**: Mnemosyne genererà riassunti periodici (presentati da The Butler) che non dicono solo *cosa* hai fatto, ma *come* si sta evolvendo la tua rete di pensieri.
- **Evoluzione dei Concetti**: Strumenti per visualizzare la "linea del tempo" di un'idea, da una semplice citazione casuale alla sua trasformazione in un progetto strutturato.

## 🔵 Fase 9: Ingestione Documentale (Knowledge Feeding)

Alimentare il grafo con grandi volumi di dati esterni per una comprensione profonda dei progetti.

- **Massive Ingestion**: Caricamento di PDF, documentazioni tecniche e interi repository di codice.
- **Semantic Chunking**: Scomposizione dei file in `Observations` collegate, mantenendo il contesto del documento originale e collegandolo ai concetti già presenti nel grafo.
- **AnythingLLM Integration**: Sfruttare AnythingLLM come motore di ingestione e RAG esterno, sincronizzando i documenti caricati con i nodi del grafo di Mnemosyne tramite API.

## 🟣 Fase 10: Orchestrazione Ibrida (Routing Asimmetrico Interno, Agnosticismo dei Backend)

Ottimizzare l'uso delle risorse delegando i compiti cognitivi *interni al middleware* a diversi livelli (Tier) di intelligenza, indipendentemente dalla loro collocazione fisica.

- **Cognitive Tiering**: Mnemosyne agirà come uno smistatore intelligente di task. L'utente potrà configurare diversi "Tier" (es. *Fast/Light* per operazioni di routine e *Deep/Heavy* per ragionamento complesso).
- **Backend Agnosticism**: Questi Tier possono essere mappati liberamente su backend locali (es. modelli Ollama di diversa taglia), backend remoti (API diverse per costo/potenza), o configurazioni miste, a seconda delle necessità di privacy, costo e performance dell'utente.
- **Separation of Concerns**: Mnemosyne ottimizza i propri processi interni di Knowledge Management (riassunti, estrazione, analisi proattiva) tramite questi Tier, lasciando l'applicazione client libera di definire la propria logica per la risposta finale all'utente.
- **Model Orchestration**: Implementazione di una gerarchia dinamica che il middleware interroga in base alla complessità dell'operazione di arricchimento del contesto richiesta.

## ⚪ Fase 11: Percezione Multimodale (Oltre la Chat)

Mnemosyne inizierà a osservare il tuo ambiente di lavoro in modo passivo per eliminare l'attrito dell'input manuale.

- **OS & Filesystem Watchers**: Monitoraggio silente delle cartelle di lavoro (locali e online). Se modifichi un file relativo al "Progetto X", Mnemosyne "scalda" automaticamente i nodi corrispondenti nel grafo.

---

**Visione Finale**: Mnemosyne non è più solo un archivio, ma un **partner strategico** onnipresente che ti aiuta a pianificare, ti ricorda le scadenze e ti offre una prospettiva storica profonda sulla tua evoluzione intellettuale.
