# Implementazione: modifiche all'API Mnemosyne

**Data:** 2026-06-11  
**Stato:** Completato (Fase 1, 2, 3)

Questo documento documenta l'implementazione della richiesta di evoluzione API descritta in `modifiche-mnemosyne.md`. Tutte le richieste bloccanti (R1, R3, R4, C1) sono implementate, testate e integrate; le rifiniture (R2, R5, R6, C2-C4) sono completate.

---

## Stato di implementazione per richiesta

### Bloccanti per l'integrazione

| Richiesta | Stato | Implementazione |
|---|---|---|
| **R1** Campo `relations` su `/tasks`, `/goals` | ✅ Completo | Entrambi gli endpoint REST accettano `relations: "Target:TYPE,Other:TYPE"` e li scrivono nel frontmatter come `relations:` list con `source: user` |
| **R3** Upsert per nome su `/tasks`, `/goals` | ✅ Completo | Helper `_upsert_node_file()` centralizzato: una seconda POST con lo stesso name aggiorna in place, preservando `created_at`/`enriched_at`. Ricerca ricorsiva nei subfolder |
| **R4** Risposte con nome canonico | ✅ Completo | Nuovo schema `NodeWriteResponse`: tutte le POST `/goals`, `/tasks`, `/nodes` restituiscono `{status, action, name, type, scope}` dove `name` è lo slug effettivamente scritto |
| **C1** Target relazione inesistente | ✅ Completo | Stub creato automaticamente eredita `scope` e `project` dal nodo sorgente, mai defaulting a `Public` (risolto il leak di scope) |

### Non bloccanti ma critici

| Richiesta | Stato | Implementazione |
|---|---|---|
| **R2** `goal_name` senza archi spuri | ✅ Completo | `goal_name` su `/tasks` e MCP `create_task` ora crea una relazione `CONTRIBUTES_TO` nel frontmatter, non un wikilink `[[...]]` → `LINKED_TO` |
| **Riconciliazione archi** (Fase 2) | ✅ Completo | `get_outgoing_edges()` + `delete_edge()` in KuzuManager; file_watcher riconcilia: cancella i file-derived edge non più dichiarati, crea i nuovi, preserva `SEMANTICALLY_RELATED` del Gardener |

### Non bloccanti (rifiniture)

| Richiesta | Stato | Implementazione |
|---|---|---|
| **R5** Tipo `Journal` con decay ~40gg | ✅ Già presente | `node_type="Journal"` con decay_rate 0.0007 (half-life ~40gg), days_journal: 45 in config. Documentato nello schema |
| **R6** Scope privato + coerenza nomenclatura | ✅ Completo | Campo singolare `scope` su `/goals`, `/tasks` ha priorità sul legacy `scopes`; helper `_resolve_scope()` usa il primo di `scopes` se `scope` assente; default `Private` esplicito (mai `Public`) |
| **C2** Schema `GET /briefing/{project}` | ✅ Completo | Nuovo schema `BriefingResponse` (`hot_topics: List[str]`, `dormant: List[DormantItem]`) applicato a `/briefing` e `/briefing/{project}` |
| **C3** Formato `deadline` | ✅ Documentato | ISO `YYYY-MM-DD`, opzionale (omesso se assente). Documentato nei Field description. |
| **C4** `DELETE /nodes/{name}` per ogni tipo | ✅ Documentato | Cancella un nodo di qualunque tipo in qualunque subfolder; il param `scopes` è accettato ma non filtra |

---

## Modifiche ai file

### gateway/http_server.py
- Nuovo helper `_upsert_node_file()`: find-or-create per nome ricorsivo, merge conservativo del frontmatter, restituisce lo slug canonico.
- Nuovo helper `_resolve_scope()`: unifica scope vs scopes con default `Private`.
- `_parse_relations_str()` con parametro `source` per taggare relazioni come `source: user`.
- Modelli Pydantic aggiornati:
  - `Goal`, `Task`: nuovi campi `scope` (singolare), `relations`.
  - Nuovi: `NodeWriteResponse` (schema `/goals`, `/tasks`, `/nodes`), `DormantItem`, `BriefingResponse` (schema `/briefing`).
- Endpoint REST con `response_model` dichiarato e docstring esteso.

### gateway/mcp_app.py
- `write_markdown()` preserva `created_at`/`enriched_at` in upsert.
- `_parse_relations()` con parametro `source`.
- `create_goal()` e `create_task()` MCP: goal_name → `CONTRIBUTES_TO` (non wikilink), relazioni taggate `source: user`.

### workers/file_watcher.py
- Costante `EPHEMERAL_EDGE_TYPES = {"SEMANTICALLY_RELATED"}` per escludere archi non derivati da file.
- Riconciliazione completa: costruisce set desiderato (wikilink + relations), cancella file-derived edges non più dichiarati, crea i nuovi, preserva ephemeral.
- Stub eredita scope/project del sorgente via `_ensure_stub()`.

### core/kuzu_manager.py
- `get_outgoing_edges(name)`: archi `RELATES` uscenti diretti (target, type).
- `delete_edge(source, target, type)`: rimozione tipizzata di arco.

### CLAUDE.md
- Documentazione aggiornata: upsert, relations, riconciliazione archi, scope, briefing schema, deadline formato.
- Nota su `EPHEMERAL_EDGE_TYPES` per futuri archi calcolati.

### tests/test_api_upsert.py (nuovo)
- 10 test coprenti:
  - TestUpsertEndpoints (5 test): relations, goal_name→CONTRIBUTES_TO, upsert idempotente, preservazione created_at/enriched_at, scope singular.
  - TestStubScopeInheritance (5 test): stub eredita scope, riconciliazione archi (rimozione, cambio tipo), preservazione SEMANTICALLY_RELATED.

---

## Comportamenti attesi (esempi di chiamata)

### Creare/aggiornare un task con relazioni tipizzate

```
POST /tasks
{
  "name": "task-figlio-001",
  "description": "Implementazione feature X",
  "deadline": "2026-09-30",
  "folder": "progetto",
  "scope": "Private",
  "goal_name": "goal-001",
  "relations": "task-padre-001:PART_OF,area-001:LOCATED_IN"
}

→ 200 {
  "status": "success",
  "action": "created",
  "name": "task-figlio-001",
  "type": "Task",
  "scope": "Private"
}
```

Il file markdown salvato contiene:
```yaml
---
type: Task
status: todo
scope: Private
deadline: 2026-09-30
relations:
  - target: goal-001
    type: CONTRIBUTES_TO
    source: user
  - target: task-padre-001
    type: PART_OF
    source: user
  - target: area-001
    type: LOCATED_IN
    source: user
created_at: 2026-06-11
---
# task-figlio-001

Implementazione feature X
```

Una seconda POST con lo stesso `name` aggiorna il file in place (action="updated"), preservando il created_at.

### Briefing filtrato per progetto

```
GET /briefing/progetto

→ 200 {
  "hot_topics": ["task-attivo-001", "goal-recente"],
  "dormant": [
    {
      "name": "nota-dimenticata",
      "type": "Journal",
      "days_inactive": 47
    },
    {
      "name": "task-vecchio",
      "type": "Task",
      "days_inactive": 35
    }
  ],
  "timestamp": "2026-06-11T00:43:00.123456"
}
```

---

## Coerenza con la filosofia file-first

Tutte le modifiche mantengono il principio che **i database KuzuDB e ChromaDB sono stato derivato dai file markdown**.
- Nessun endpoint scrive direttamente nel DB: tutto passa per frontmatter e il file watcher sincronizza.
- Relazioni tipizzate nel frontmatter (`relations:`) sopravvivono a un reset del DB.
- L'enrichment LLM non tocca le relazioni taggate `source: user`.
- Archi computati (Gardener) sono espliciti come `SEMANTICALLY_RELATED` ed escclusi dalla riconciliazione.

---

## Test

Suite: `tests/test_api_upsert.py` (10 test, 100% pass rate).

Lanciare con:
```bash
python3 -m unittest tests.test_api_upsert -v
```

I test usano DB isolati temporanei (Kuzu/ChromaDB) e non toccano il DB di produzione.

---

## Prossimi passi consigliati

1. **Deploy**: aggiornare l'istanza di produzione con i nuovi file. MCP `/mcp/` è retrocompatibile.
2. **Monitoraggio**: osservare i log del file watcher per eventuali archi riconciliati durante il primo ciclo di sincronizzazione con file vecchi.
3. **Stub orfani (opzionale)**: aggiungere un ciclo del Gardener che pulifisce i stub senza file né archi (al momento sono solo ignorati).
4. **Validazione deadline**: se necessario, aggiungere una validazione strita del formato ISO `YYYY-MM-DD` (oggi è accettato come-è).

---

## Riferimenti

- **Specifica originale**: `modifiche-mnemosyne.md`
- **CLAUDE.md**: documentazione dell'architettura e comportamenti
- **OpenAPI**: `GET /openapi.json` espone gli schemi e field descriptions
