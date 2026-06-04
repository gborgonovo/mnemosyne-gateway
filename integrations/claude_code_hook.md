# Integrazione Claude Code: Auto-Memory Hook

Questo documento descrive come Claude Code (il CLI di Anthropic) sincronizza automaticamente la propria memoria a lungo termine verso Mnemosyne tramite un hook `PostToolUse`.

---

## Come funziona

Claude Code mantiene una memoria locale per ogni progetto in:

```
~/.claude/projects/<progetto>/memory/
```

I file in questa cartella sono markdown con frontmatter YAML che Claude Code scrive al termine di ogni conversazione. Senza integrazione, questa memoria è isolata: visibile solo a Claude Code in quel progetto, non interrogabile da altri agenti, non arricchita dal grafo.

L'hook descritto qui risolve questo: ogni volta che Claude Code scrive un file di memoria, viene chiamato automaticamente `POST /nodes` sull'istanza Mnemosyne, sincronizzando il contenuto nella cartella `Sistema/Claude_Code` del knowledge graph.

---

## Architettura

```
Claude Code scrive ~/.claude/projects/.../memory/foo.md
        ↓
PostToolUse hook (settings.json) lancia lo script Python
        ↓
sync_memory_to_mnemosyne.py
  - filtra i path che non sono file di memoria
  - esclude MEMORY.md (indice, non un nodo)
  - stripping del frontmatter YAML
  - determina node_type (Reference se type=reference, Node altrimenti)
        ↓
POST /nodes → https://your-mnemosyne-host
  - upsert: crea o aggiorna il nodo
  - cartella: Sistema/Claude_Code, scope: Private
```

---

## File

### Script hook

Percorso: `~/.claude/hooks/sync_memory_to_mnemosyne.py`

Lo script:
- Legge il payload JSON da stdin (formato standard dei hook Claude Code)
- Agisce solo su tool `Write` verso path `.claude/projects/.*/memory/*.md`
- Esclude `MEMORY.md` (indice locale, non da sincronizzare)
- Chiama `POST /nodes` con timeout 6s, esce sempre con codice 0 (non blocca mai Claude)
- Legge `MNEMOSYNE_URL` e `MNEMOSYNE_API_KEY` da variabili d'ambiente

### Configurazione hook

In `~/.claude/settings.json`:

```json
{
  "env": {
    "MNEMOSYNE_API_KEY": "la-tua-chiave"
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/<utente>/.claude/hooks/sync_memory_to_mnemosyne.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

---

## Endpoint REST usato

L'hook chiama il nuovo endpoint `POST /nodes` della gateway (aggiunto insieme a questa integrazione):

```
POST /nodes
Content-Type: application/json
X-API-Key: <chiave>

{
  "name": "slug_del_file",
  "content": "corpo del nodo in markdown",
  "node_type": "Node",
  "scope": "Private",
  "folder": "Sistema/Claude_Code",
  "relations": ""
}
```

Il comportamento è **upsert**: se il nodo esiste già (ricerca ricorsiva per nome), il suo frontmatter viene preservato e aggiornato; se è nuovo, viene creato con `created_at` automatico.

---

## Struttura della memoria in Mnemosyne

Tutti i nodi di memoria di Claude Code finiscono in `knowledge/Sistema/Claude_Code/` con scope `Private`. I tipi di memoria mappano così:

| Tipo memory Claude Code | `node_type` Mnemosyne |
|---|---|
| `user`, `feedback`, `project` | `Node` |
| `reference` | `Reference` (non decade) |

---

## Setup su una nuova macchina

1. Copiare lo script in `~/.claude/hooks/sync_memory_to_mnemosyne.py`
2. Renderlo eseguibile: `chmod +x ~/.claude/hooks/sync_memory_to_mnemosyne.py`
3. Aggiungere hook e `MNEMOSYNE_API_KEY` a `~/.claude/settings.json` (vedi sopra)
4. Verificare con:
   ```bash
   echo '{"tool_name":"Write","tool_input":{"file_path":"/home/user/.claude/projects/test/memory/test.md","content":"---\nname: test\n---\n\nTest."}}' \
     | MNEMOSYNE_API_KEY=la-tua-chiave python3 ~/.claude/hooks/sync_memory_to_mnemosyne.py
   ```

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `MNEMOSYNE_URL` | `http://localhost:4001` | URL base della gateway |
| `MNEMOSYNE_API_KEY` | *(vuoto)* | API key per autenticazione |
