# Fase 7: Intenzionalità e Pianificazione Strategica — Analisi Implementativa

Questa fase trasforma Mnemosyne da "memoria statica" a "partner proattivo", introducendo la gestione degli obiettivi, la consapevolezza del tempo e la simulazione degli impatti.

---

## 1. Goal & Task Intelligence: Lo Schema Cognitivo

Perché Mnemosyne comprenda l'intenzione, i nodi `Goal` e `Task` devono avere un ciclo di vita e proprietà specifiche.

### Schema dei Nodi

- **`Goal`**: Rappresenta un obiettivo ad alto livello (es. "Lanciare Mnemosyne").
  - Proprietà: `status` (active, completed, discarded), `priority`, `deadline`, `success_criteria`.
- **`Task`**: Azione concreta per raggiungere un Goal.
  - Proprietà: `status` (todo, in_progress, done), `due_date`, `estimated_effort`.

### Relazioni

- `(Goal)-[:REQUIRES]->(Task)`: Decomposizione strutturale.
- `(Task)-[:DEPENDS_ON]->(Task)`: Sequenzialità.
- `(Goal)-[:SUB_GOAL_OF]->(Goal)`: Gerarchia di obiettivi.

---

## 2. Action Plan Decomposition (Il ruolo di The Butler)

L'attuale `InitiativeEngine` rileva `Goal` senza `Task`. L'evoluzione prevede:

1. **Trigger**: Quando un `Goal` è attivo (high heat), The Butler interviene.
2. **Decomposizione assistita**: Mnemosyne interroga l'LLM passando il contesto del `Goal` e dei nodi correlati nel grafo.
3. **Integrazione**: I task suggeriti dall'LLM vengono creati come nodi e collegati al `Goal` nel Connectome.

### Esempio di Iniziativa (The Butler)
>
> *"Ho visto che il tuo obiettivo 'Lancio Mnemosyne' è molto caldo. Vuoi che proviamo ad abbozzare i primi task tecnici basandoci sul Whitepaper che abbiamo analizzato ieri?"*
chiamo della memoria.

### Decadimento Differenziale

L'attivazione (`heat`) non decade in modo uniforme:

- **Nodi "Imperativi" (Pedanteria)**: Se un nodo ha `persistence: high` o è un `Goal` attivo con scadenza imminente, il decadimento è **zero** o rallentato.
- **Nodi "Effimeri" (Chiacchiere)**: Observations senza entità rilevanti decadono più velocemente.
- **Fattore Età**: Il peso delle relazioni può essere influenzato dalla data di creazione (le informazioni recenti hanno un moltiplicatore di importanza).

---

## 4. Time Monitoring & Reminders

Un nuovo `TimeWatcher` (in affiancamento al `Gardener`) effettua scansioni periodiche:

- Se un `Task` ha una `due_date` superata, riceve un **Activation Boost** massiccio (0.9+).
- Questo "accende" il nodo nel grafo, portandolo all'attenzione dell'`InitiativeEngine`, che genererà un'iniziativa per The Butler: *"Ehi, avevamo detto di finire {task} entro oggi"*.

---

## 5. Sandbox Reasoning: Analisi d'Impatto

Permette di simulare cambiamenti nel grafo senza renderli permanenti.

- **Simulazione**: Si crea una "proiezione" temporale del grafo.
- **Propagation Test**: Cosa succede se un nodo `Task` fallisce? Quali `Goal` vengono messi a rischio?
- **Output per l'utente**: *"Se non finiamo questo task, i progetti A e B subiranno un ritardo"*.

---

## Architettura dei Moduli da Evolvere

| Modulo | Evoluzione Richiesta |
|---|---|
| **`graph_manager.py`** | Metodi per query temporali (scadenze, età dei dati) e gestione cicli di vita Task/Goal. |
| **`attention.py`** | Logica di decadimento differenziale basata sul tipo di nodo e priorità. |
| **`initiative.py`** | Strategie di "Planning Suggestion" e analisi dei nodi in ritardo. |
| **`llm.py`** | Prompt specializzati per la scomposizione gerarchica degli obiettivi. |

---

## Conclusione

Fase 7 sposta il baricentro di Mnemosyne dall'**Archivio** alla **Pianificazione**. Il sistema non si limita a ricordare il passato, ma usa il passato per monitorare il presente e suggerire il futuro.
