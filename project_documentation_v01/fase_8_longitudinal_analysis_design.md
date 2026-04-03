# Fase 8: Analisi Longitudinale e Briefing — Analisi Implementativa

Questa fase trasforma Mnemosyne da un sistema di "memoria di lavoro" a un sistema di "saggezza storica", capace di estrarre trend, cicli e intuizioni su archi temporali lunghi.

---

## 1. Pattern Recognition (L'Occhio del Grafo)

Invece di reagire solo a ciò che è "caldo", Mnemosyne analizza la struttura "oscura" del grafo.

### Identificazione dei Temi Ricorrenti

- **Analisi di Co-occorrenza**: Identificare cluster di entità che appaiono spesso insieme in diverse `Observation` in un periodo di 3-6 mesi.
- **Topological Clustering**: Identificare "isole" di conoscenza molto dense ma isolate dal Connectome principale.

### Rilevamento Progetti "Dimenticati"

- **Query di Abbandono**: Ricerca di nodi con label `Project` o `Goal` che:
  1. Hanno avuto un'attivazione media altissima in passato.
  2. Non sono stati toccati/nominati negli ultimi 30 giorni.
  3. Non sono marcati come `completed`.
- **Iniziativa**: The Butler potrebbe suggerire: *"Ho notato che il progetto 'Mnemosyne' era molto presente a Gennaio, ma non ne parliamo più da tre settimane. È in standby o ci sono blocchi?"*.

---

## 2. Briefing Longitudinali (La Voce di The Butler)

A differenza dei briefing istantanei, questi sono sintesi "panoramiche".

### Pipeline di Generazione

1. **Temporal Query**: Estrazione di tutte le `Observation` e `Entity` toccate in un intervallo (es. l'ultima settimana).
2. **Clustering Semantico**: Raggruppamento delle attività per "Filo Conduttore".
3. **LLM Synthesis**: The Butler non riassume solo i fatti, ma descrive l'**evoluzione**: *"Questa settimana la tua attenzione si è spostata dal design tecnico alla pianificazione strategica. Il nodo 'Fase 9' è diventato il centro del grafo"*.

---

## 3. Evoluzione dei Concetti (Timeline Cognitiva)

Tracciare come un'idea nasce, si espande e si trasforma.

### Meccanismo di Tracciamento

- **Sincronia Temporale**: Ogni nodo `Entity` mantiene un piccolo audit-trail (o query dinamica) dei momenti in cui è stato "attivato" massicciamente.
- **Visualizzazione via The Butler**: Potrai chiedere: *"Com'è nata l'idea del Semantic Firewall?"* e The Butler ricostruirà la catena: `Obs_A -> Topic_X -> Maybe_Same_As -> Semantic Firewall`.

---

## 4. Architettura dei Moduli da Evolvere

| Modulo | Evoluzione Richiesta |
|---|---|
| **`graph_manager.py`** | Nuovi metodi `get_nodes_by_activity_period(start, end)` e query di clustering via Cypher. |
| **`initiative.py`** | Strategie "Longitudinal": rileva non la mancanza di calore attuale, ma il calo di calore storico. |
| **`gardener.py`** | Il Gardener diventa lo "Scansore di Trend", calcolando una volta al giorno le statistiche di crescita dei nodi. |
| **`http_server.py`** | Endpoint `/briefing/longitudinal` per richiamare report settimanali/mensili. |

---

## Conclusione

Fase 8 è il momento in cui Mnemosyne smette di essere solo "reattiva" e inizia ad avere una **visione d'insieme**. Aiuta l'utente a vedere la foresta, non solo gli alberi, fornendo una prospettiva che solo una memoria digitale persistente può garantire.
