# Guida: Upgrade Ontologico e Relazioni Semantiche in Mnemosyne Gateway

## Stato: Implementato (Aggiornato Marzo 2026)

Questo documento illustra il contesto, le motivazioni e le istruzioni per l'implementazione di una nuova architettura di estrazione delle relazioni all'interno di `mnemosyne-gateway`.

## 1. Contesto e Problema Attuale

Il Connectome di Mnemosyne attualmente soffre di un effetto "grafo piatto e disconnesso". Quando un utente fornisce informazioni complesse (es. *"Il GiodaLab gestisce il progetto Echo e il Team Alpha"*), il sistema:

1. **Estrae solo Nodi:** L'Intelligenza Artificiale isola correttamente le entità (GiodaLab, Echo, Team Alpha).
2. **Ignora la Struttura:** L'IA non viene istruita a estrarre la relazione logica tra queste entità (chi gestisce cosa).
3. **Applica un Fallback Cieco:** Il modulo [PerceptionModule](file:///home/giorgio/Projects/mnemosyne-gateway/butler/perception.py#8-79) prende tutte le entità citate nella stessa frase e le collega tra loro usando un generico arco `LINKED_TO`.

Il risultato è un database a grafo privo di reale semantica organizzativa, in cui è impossibile distinguere gerarchie (es. Lab -> Team) o tipologie di relazioni (es. congruenza tra due concetti). Inoltre, il [GraphManager](file:///home/giorgio/Projects/mnemosyne-gateway/core/graph_manager.py#7-624) è hardcoded per rifiutare qualsiasi arco che non faccia parte di una sua stretta e limitata whitelist.

## 2. Obiettivo dell'Architettura

Vogliamo trasformare la pipeline di ingestione da "estrattore di entità" a vero e proprio **"estrattore di tripli di conoscenza"** (Soggetto -> Relazione -> Oggetto), permettendo al grafo Neo4j di riflettere accuratamente l'impalcatura logica e aziendale.

Per fare ciò, dobbiamo:

1. **Espandere l'Ontologia Base:** Insegnare al database ad accettare costrutti aziendali (es. `MANAGES`, `PART_OF`, `RELATED_TO`).
2. **Ampliare i Payload dell'IA:** Chiedere ai modelli (OpenAI/Ollama) un JSON contenente sia le [entities](file:///home/giorgio/Projects/Mnemosyne/core/llm.py#109-156) che l'array di `relationships`.
3. **Iniezione Diretta:** Bypassare il raggruppamento generico in [PerceptionModule](file:///home/giorgio/Projects/mnemosyne-gateway/butler/perception.py#8-79) e usare la mappatura esplicita dell'IA per creare i nodi e i relativi archi in Neo4j.

---

## 3. Istruzioni di Implementazione per gli Sviluppatori

> **ATTENZIONE:** Le seguenti modifiche devono essere applicate al codice sorgente del repository `mnemosyne-gateway`.

### Fase 1: Espansione dell'Ontologia ([core/graph_manager.py](file:///home/giorgio/Projects/mnemosyne-gateway/core/graph_manager.py))

**File:** [core/graph_manager.py](file:///home/giorgio/Projects/mnemosyne-gateway/core/graph_manager.py) > Metodo: [add_edge()](file:///home/giorgio/Projects/mnemosyne-gateway/core/graph_manager.py#94-119)

Il dizionario `valid_relations` agisce da scudo contro le inserzioni non autorizzate. Se l'IA inventa una relazione, questa viene bloccata e declassata a `LINKED_TO`. Dobbiamo inserire in questa whitelist i verbi strutturali di cui abbiamo bisogno.

**Modifica richiesta:**
Aggiungere le nuove relazioni organizzative con il rispettivo "peso" (utilizzato dagli algoritmi di pagerank interni).

```python
valid_relations = {
    # Relazioni Base Esistenti
    "LINKED_TO": 0.3, "DEPENDS_ON": 0.9, "EVOKES": 0.6,
    "IS_A": 1.0, "MENTIONED_IN": 0.1, "MAYBE_SAME_AS": 0.0,
    
    # NUOVE Relazioni Organizzative/Strutturali
    "PART_OF": 0.8,      # Es. Team X -> PART_OF -> GiodaLab
    "MANAGES": 0.8,      # Es. GiodaLab -> MANAGES -> Progetto Y
    "HAS_MEMBER": 0.7,   # Es. Team X -> HAS_MEMBER -> Mario Rossi
    "REQUIRES": 0.9,     # Es. Task -> REQUIRES -> Tool
    "RELATED_TO": 0.4    # Relazione strutturale per entità/lab congruenti e simili
}
```

### Fase 2: Prompt Engineering ([butler/llm.py](file:///home/giorgio/Projects/mnemosyne-gateway/butler/llm.py))

**File:** [butler/llm.py](file:///home/giorgio/Projects/mnemosyne-gateway/butler/llm.py) > Metodi: [extract_entities](file:///home/giorgio/Projects/Mnemosyne/core/llm.py#109-156) (nelle classi [OpenAILLM](file:///home/giorgio/Projects/mnemosyne-gateway/butler/llm.py#71-189) e [OllamaLLM](file:///home/giorgio/Projects/Mnemosyne/core/llm.py#170-285))

Attualmente il prompt chiede lo schema JSON con una sola chiave ([entities](file:///home/giorgio/Projects/Mnemosyne/core/llm.py#109-156)). Il prompt deve essere aggiornato per imporre rigorosamente la generazione di un secondo array (`relationships`), obbligando il modello a usare ESCLUSIVAMENTE i verbi definiti nella Fase 1.

**Modifica richiesta:**
All'interno del prompt, aggiungere:

```text
Structure your response as a JSON object with two keys:
1. "entities": a list of objects, each with 'name' (the label) and 'type' (Entity, Topic, Resource, Goal, or Task).
2. "relationships": a list of objects, each representing an explicit link between two extracted entities. Each must have 'source', 'target', and 'type' (a screaming snake case verb EXCLUSIVELY from this list: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A).

CRITICAL INSTRUCTION:
Extract clear, direct relationships. If A is a project of B, the relationship is A -> PART_OF -> B. If two concepts are similar/congruent, map A -> RELATED_TO -> B.
```

Inoltre, il corpo Python della funzione deve spacchettare il nuovo array dal payload JSON:

```python
# ... parsing del JSON ...
entities = data.get("entities", [])
relationships = data.get("relationships", [])
return entities, relationships # IMPORTANTE: Ritornare una tupla!
```

*(Nota: Aggiornare anche il file [workers/llm_worker.py](file:///home/giorgio/Projects/mnemosyne-gateway/workers/llm_worker.py) affinché riceva questa tupla e inserisca sia [entities](file:///home/giorgio/Projects/Mnemosyne/core/llm.py#109-156) che `relationships` nel dizionario inviato via RPC come `ENRICHMENT_RESULT`.)*

### Fase 3: Riconoscimento Relazionale ([butler/perception.py](file:///home/giorgio/Projects/mnemosyne-gateway/butler/perception.py))

**File:** [butler/perception.py](file:///home/giorgio/Projects/mnemosyne-gateway/butler/perception.py) > Metodo: [integrate_entities](file:///home/giorgio/Projects/mnemosyne-gateway/butler/perception.py#47-79)

Il [PerceptionModule](file:///home/giorgio/Projects/mnemosyne-gateway/butler/perception.py#8-79) deve abbandonare la generazione cieca dei `LINKED_TO`. Dovrà ricevere il payload `relationships` elaborato nella Fase 2 e convertirlo in chiamate architetturali a database tramite `self.gm.add_edge()`.

**Modifica richiesta:**

1. Aggiornare la firma del metodo per accettare `relationships: list[dict] = None`.
2. Conservare una mappa `node_map` durante la creazione dei nodi per recuperare i nomi esatti salvati su Neo4j.
3. Ciclare l'array `relationships` per creare i collegamenti specifici.
4. **Resilienza (Anti-Allucinazione):** Prevedere un controllo per cui, se l'LLM ha citato un nodo come `source` o `target` ma si è dimenticato di inserirlo nell'array [entities](file:///home/giorgio/Projects/Mnemosyne/core/llm.py#109-156), il [PerceptionModule](file:///home/giorgio/Projects/mnemosyne-gateway/butler/perception.py#8-79) provvederà a istanziarlo dinamicamente come "Topic" di base prima di connetterlo.

```python
# Pseudo-codice di riferimento
for rel in relationships:
    source = rel.get('source')
    target = rel.get('target')
    edge_type = rel.get('type')
    
    # (Logica per assicurarsi che source e target esistano nella node_map...)
    
    # Creazione sicura dell'arco direzionale
    self.gm.add_edge(actual_source, actual_target, edge_type)
```

---

## 4. Aggiornamento "Graph Hygiene" (Metà Marzo 2026)

A seguito dell'osservazione del comportamento in produzione, l'ontologia è stata ulteriormente semplificata per ridurre la frammentazione e i nodi vuoti.

### 4.1 Semplificazione dei Tipi (Merge Concept)

Per evitare che l'LLM si confonda tra categorie simili, i tipi `Entity` e `Resource` sono stati fusi nel tipo universale **`Topic`**.

- **Topic**: Rappresenta qualsiasi concetto, persona, strumento, luogo o risorsa digitale.
- **Project**: Mantenuto come categoria isolata per agire da macro-contenitore strutturale.

### 4.2 Lotta ai "Nodi Vuoti" (Mandatory Description)

Il prompt di estrazione ora impone all'AI di generare sempre una proprietà `description` per ogni nuovo nodo.

- Il modulo `PerceptionModule` è stato aggiornato per catturare questa descrizione e salvarla nel database Neo4j.
- Questo garantisce che ogni nodo abbia un contesto minimo fin dalla sua nascita.

### 4.3 Gestione Task Orfani

I Task non sono più vincolati ai Goal, ma il sistema (tramite prompt e tramite il worker `Gardener`) cerca di connetterli a un `Project` o a un `Topic` di riferimento. Se un Task rimane isolato, il sistema lo segnala nei "Briefing" per consentire all'utente di contestualizzarlo o di marcarlo esplicitamente come "libero" (`allow_orphan`).
