# Architettura Hybrid File-First (Il Manifesto)

Questo documento definisce il paradigma architetturale introdotto con Mnemosyne v0.3, ispirato al modello "LLM Wiki" di Andrej Karpathy. L'obiettivo è superare l'opacità dei database server-side (Neo4j) e restituire sovranità e visibilità totale all'utente tramite file Markdown, garantendo al tempo stesso performance per l'elaborazione termico-cognitiva del sistema.

## 1. Obiettivo: Dalla Server-Side alla Hybrid-Local
Spostare il baricentro del sistema da un'architettura **Server-Side e Opaca** a una **Ibrida e Trasparente**, dove:
- I **File Testuali Locali** gestiscono la conoscenza statica (Human-Readable).
- I **Database Embedded** gestiscono le transazioni cognitive e la velocità di recupero (AI-Readable).

## 2. Architettura a "Doppio Strato"

L'architettura separa rigorosamente la conoscenza persistente dal suo stato epistemico (calore dinamico).

### Strato A: Lo Stato Statico (Source of Truth - Markdown)
La directory `knowledge/` è l'unica e vera sorgente della conoscenza.
- **Interfaccia**: Progettata per essere esplorata con **Obsidian**.
- **Metadati**: Il Frontmatter YAML contiene ID univoci, tipi (`Project`, `Topic`, `Task`, `Goal`) e tag.
- **Relazioni**: I Wikilinks `[[Nome]]` definiscono la struttura del grafo.

### Strato B: La RAM Cognitiva Dinamica (KùzuDB + ChromaDB)
Database embedded che fungono da indici in tempo reale della directory `knowledge/`.
- **KùzuDB (Motore Termico & Relazionale)**: Mantiene l'ombra dinamica dei file. Traccia i pesi delle relazioni e i metadati volatili: `Activation_Level` (Heat), `Last_Accessed`, `Interaction_Count`.
- **ChromaDB (Motore Semantico)**: Database vettoriale per il retrieval intelligente basato sul significato.

## 3. Il Ciclo di Vita Cognitivo

1. **I/O File Watcher**: Quando editi un file, un demone se ne accorge, parseggia i wikilink e aggiorna Kùzu e Chroma. Contemporaneamente regala un "picco di calore" al nodo.
2. **Agente in Lettura**: L'Agente chiede il contesto. Il sistema interroga ChromaDB per la semantica e ordina i risultati in KùzuDB in base al calore attuale. L'Agente riceve il contenuto puro dei file Markdown.
3. **Il Sonno (Decadimento)**: Un task programmato abbassa l'energia di tutti i nodi. Questo calcolo passa solo da KùzuDB, salvando il disco da inutili riscritture dei file Markdown.

## 4. Resilience (Hydration Protocol)

L'intero strato "B" (Kùzu e Chroma) è **sacrificabile**. Qualora i database vengano eliminati, una procedura di "Cold Boot" scansiona la directory `knowledge/` e ricostruisce gli indici in pochi secondi, partendo dai metadati YAML. Tu non perdi mai i tuoi dati, perdi solo la "cache" della loro temperatura.

## 5. Tassonomia e Compartimentazione

- **Ordine Fisico**: Le cartelle (es. `knowledge/giodalab/`) servono per l'ordine umano e non creano muri per l'AI.
- **Silos Semantici "Morbidi"**: Il vero confinamento avviene nello YAML (`projects: [progetto_A]`), permettendo all'Agente di filtrare i dati con precisione chirurgica pur mantenendo la capacità di trovare connessioni trasversali se richiesto.

---

*Documento 7 di 7 — Approfondimento Architetturale*
*Progetto Mnemosyne — GiodaLab*
