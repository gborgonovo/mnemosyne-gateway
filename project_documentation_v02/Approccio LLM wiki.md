# Architettura Hybrid File-First (Compromesso LLM-Wiki)

Questo documento definisce il nuovo paradigma architetturale di Mnemosyne, ispirato al modello "LLM Wiki" di Andrej Karpathy, nato per superare l'opacità dei database server-side (Neo4j) e restituire sovranità e visibilità totale all'utente tramite file Markdown, garantendo al tempo stesso performance per l'elaborazione termico-cognitiva del sistema ("Grafo Liquido").

## 1. Obiettivo della Migrazione
Spostare il baricentro del sistema da un'architettura **Server-Side e Opaca** (Neo4j) a una **Ibrida e Trasparente**, dove i file testuali locali gestiscono la conoscenza statica (Human-Readable) e database embedded gestiscono le transazioni cognitive (AI-Readable).

## 2. Architettura ibrida a "Doppio Strato"

L'architettura separa rigorosamente la conoscenza persistente dal suo stato epistemico / calore dinamico, evitando frizioni nel file system.

### Strato A: Lo Stato Statico (Source of Truth - Markdown)
La directory `/wiki` è l'unica e vera sorgente della conoscenza e delle sue interconnessioni esplicite. È progettata per essere utilizzata tramite **Obsidian** come interfaccia utente (WYSIWYG e navigazione). 
* I file Markdown **non contengono mai valori numerici dinamici** che mutano frequentemente (come il decadimento termico).
* Il **Frontmatter YAML** contiene solo metadati stabili: `UUID`, `Title`, `Type` (Entity, Topic, Observation, Goal), `Tags`, `Aliases`, e opzionalmente `Persistence: high`.
* **Vantaggi:** Trasparenza assoluta su cosa sa l'agente. Versioning nativo (Git). Zero conflitti durante la scrittura simultanea. Assenza di "opacità".

### Strato B: La RAM Cognitiva Dinamica (KùzuDB + ChromaDB/LanceDB)
Al posto di Neo4j, il calcolo della rilevanza semantica e dell'attenzione usa due DB embedded leggerissimi in locale, che fungono da indici in tempo reale della directory `/wiki`.
* **KùzuDB (Motore Termico & Relazionale):** Mantiene l'"ombra" dei file Markdown in locale. Traccia i Wikilinks creati estraendoli dai Markdown, ma a questi link assegna un *peso*. Soprattutto, tiene traccia dei metadati volatili legati ad un nodo: `Current_Heat`, `Last_Accessed_Agent`, `Interaction_Count`.
* **ChromaDB / LanceDB (Motore Semantico):** Database vettoriale per tradurre il testo dei Markdown in embeddings per il retrieval intelligente. 

## 3. Il Ciclo di Vita Cognitivo (Event Loop)

* **I/O File Watcher:** Quando l'utente edita un file `.md`, un demone (File Watcher) se ne accorge, parseggia il testo per estrarre i wikilink ed esegue un update in Kùzu per creare/aggiornare il nodo e le sue relazioni logiche. Contemporaneamente regala un "picco di calore" al nodo poiché l'utente ci ha interagito.
* **Agente in Lettura:** L'Agente chiede (tramite MCP/Tool) il contesto pertinente. Il sistema interroga prima semanticamente ChromaDB e filtra/ordina il risultato in KùzuDB in base all'Activation Level (`Current_Heat`). L'Agente riceve il contenuto puro dei file `.md`.
* **Il Decadimento e l'Energia Oscura:** Un task programmato autonomo abbassa l'energia (`Current_Heat`) di tutti i nodi di una percentuale "n" a cadenza regolare, e fa calcoli di propagazione (Spreading Activation) verso le informazioni connesse. **Tutto questo calcolo passa solo da KùzuDB**, non tocca mai i file Markdown, salvando il disco da inutili scritture.

## 4. Gestione Proliferazione File e Consolidamento (Linting)

Per non annegare in migliaia di frammenti di Markdown illeggibili (il problema tipico dei knowledge graph puri), si stabiliscono due difese:

1.  **Regola dell'Append-Over-Create:** Le direttive di sistema (System Prompt / Schema) obbligano l'agente a modificare/ampliare file "Topic" già esistenti invece che generare innumerevoli file piccoli dedicati a micro-dettagli, tranne per documenti primari ed entità isolate di rilievo.
2.  **Linting e Garbage Collection (Il Sonno):** L'Agente, durante i momenti di inattività del sistema, scansionerà l'indice alla ricerca di note "deboli" (orfane, fredde o misere per mole di testo), fondendole concettualmente all'interno di file macroscopici e distruggendo/svuotando l'origine debole.

## 5. Resilience (Hydration Protocol)
L'intero strato "B" (Database Embedded) è considerato **volontariamente sacrificabile e ricreabile (epimero per struttura, persistente per comodità)**. Qualora la directory di Kùzu o Chroma vanga distrutta o corrotta, una procedura di "Cold Boot" deve scansionare l'intera directory ed appaiarsi nuovamente, restituendo un indice Kùzu caldo il giusto partendo da termodinamiche di zero e dai metadati YAML.

## 6. Tassonomia e Compartimentazione
Per gestire progetti multipli senza creare barriere rigide per l'intelligenza dell'Agente, si usa un approccio ibrido (Fisico vs Semantico):

1. **Ordine Fisico (OS/Cartelle):** Le sottocartelle (es. `/wiki/giodalab`, `/wiki/personale`) servono esclusivamente per l'ordine visivo umano (per non avere listati infiniti) e non creano muri semantici per l'Agente.
2. **Silos Semantici "Morbidi" (Metadata YAML):** Il vero confinamento avviene nel Frontmatter dei file `.md` tramite tag espliciti (es. `projects: [giodalab, hr]`). Questo permette all'Agente di effettuare filtering vettoriali su Chroma/Kùzu, escludendo istantaneamente dal prompt dati non pertinenti se l'utente richiede "focus", ma preservando l'accessibilità trasversale se si cerca una connessione laterale.
3. **Pagine Hub (MOCs - Maps of Content):** Per dare un forte contesto a specifici temi, si creano pagine centrali (es. `Progetto_Alfa.md`). L'Attention Engine accenderà e valuterà i nodi nel raggio di 1 o 2 "salti" (hops logici in Kùzu) da quella pagina, stringendo il cerchio della rilevanza sulle note pertinenti a quel dominio.

---

*Stack raccomandato: Python, KùzuDB (Graph), ChromaDB o LanceDB (Vector), ed erogazione su file locali.*
