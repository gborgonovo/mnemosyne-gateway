# Le integrazioni

## Cosa sono i cerchi 2 e 3

Il kernel di Mnemosyne è silenzioso per design. Non sa nulla del mondo esterno finché qualcuno non gli porta informazioni, e non restituisce nulla finché qualcuno non lo interroga. I cerchi 2 e 3 sono i canali attraverso cui questo scambio avviene.

Nell'architettura **File-First**, questi cerchi sono diventati estremamente trasparenti:
- **Cerchio 2 (Sensi)**: Tutto ciò che scrive file Markdown nella directory `knowledge/`.
- **Cerchio 3 (Voce)**: Il modo in cui Mnemosyne espone il contenuto e la "temperatura" di questi file agli Agenti (MCP).

---

## Cerchio 2 — L'alimentazione

### Il modello: La scrittura come percezione

In Mnemosyne v0.3, alimentare il sistema significa produrre documenti. Non c'è più bisogno di una complessa procedura di "ingestione" in un database proprietario. Se un'informazione esiste come file `.md` nella cartella `knowledge/`, Mnemosyne la "sente" istantaneamente grazie al File Watcher.

Il pattern di integrazione ora è:
```
Utente o Suggeritore scrive un file .md
        ↓
Il File Watcher rileva il nuovo file/modifica
        ↓
Vengono estratti Wikilinks [[Relazioni]] e Metadati YAML
        ↓
Gli indici KùzuDB e ChromaDB si allineano in background
```

### Strumenti di Scrittura

#### Obsidian: L'interfaccia umana
Obsidian è il compagno ideale di Mnemosyne. Usandolo per gestire la tua conoscenza, Mnemosyne riceve automaticamente tutto il contesto di cui ha bisogno.
- **Wikilinks**: La navigazione che fai in Obsidian crea la topologia che Mnemosyne usa per propagare il calore.
- **Frontmatter**: Le proprietà YAML che definisci (es. `type: Project`) permettono a Mnemosyne di classificare la conoscenza.

#### Gateway API (Compatibilità)
Per mantenere la compatibilità con i sistemi esistenti, Mnemosyne espone ancora degli endpoint, ma ora sono dei semplici proxy verso il file system:
- **POST /process_input**: Prende del testo, genera un nome file univoco (es. `Obs_abc123.md`) e lo salva nella directory.
- **POST /ingest**: Salva un file caricato direttamente nella cartella `knowledge/`.

---

## Cerchio 3 — L'output via MCP

### MCP come protocollo standard

Il **Model Context Protocol (MCP)** è il ponte tra la tua cartella di file e l'intelligenza degli Agenti (come OpenClaw o Claude). Invece di far leggere all'AI migliaia di file grezzi, Mnemosyne fornisce all'AI dei "superpoteri" di ricerca:

1. **Ricerca Semantica**: L'Agente chiede "Cosa so sulla bioedilizia?" e Mnemosyne usa ChromaDB per trovare i file più pertinenti.
2. **Reranking Termico**: Tra i risultati semantici, Mnemosyne dà la precedenza a quelli "più caldi" in KùzuDB (quelli che hai toccato di recente o che sono collegati ad argomenti attivi).
3. **Lettura Diretta**: Una volta trovato il file giusto, Mnemosyne ne restituisce l'intero contenuto Markdown.

### Strumenti esposti via MCP

| Strumento | Descrizione | Effetto sui file |
|---|---|---|
| `query_knowledge` | Cerca file per significato + calore | Sola lettura (stimola il calore) |
| `add_observation` | Crea una nota rapida | Crea un nuovo file `.md` |
| `update_knowledge_frontmatter` | Cambia i metadati (es. status) | Modifica lo YAML del file |
| `create_goal` / `create_task` | Crea obiettivi o task | Crea file strutturati con Wikilinks |
| `forget_knowledge_node` | Elimina un concetto | Elimina fisicamente il file `.md` |

---

## Pattern di Integrazione per Sviluppatori

Se vuoi collegare un nuovo "senso" a Mnemosyne, hai due strade:

1. **Scrittura Diretta (Raccomandata)**: Fai in modo che il tuo strumento scriva semplicemente file Markdown nella directory monitorata. È la via più veloce, sicura e resiliente.
2. **Utilizzo dei Gateway**: Se il tuo strumento è remoto, usa l'endpoint `POST /process_input` per inviare frammenti di testo che Mnemosyne trasformerà in note.

### Best practice
- **YAML Frontmatter**: Includi sempre un blocco YAML iniziale per definire il `type` del contenuto.
- **Wikilinks**: Usa la sintassi `[[Nome]]` nel corpo del testo per creare connessioni grafiche. Mnemosyne le userà per costruire il Connectome liquido in KùzuDB.

---

*Documento 4 di 7 — Le integrazioni*
*Progetto Mnemosyne — GiodaLab*
