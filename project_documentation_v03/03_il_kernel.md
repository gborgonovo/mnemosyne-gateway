# Il kernel

## Cosa è il kernel e perché esiste

Il kernel è il cerchio più interno di Mnemosyne. È lo strato che nessun utente vede direttamente, ma da cui dipende tutto il resto. La sua funzione è una sola: mantenere la memoria in uno stato coerente, vivo e interrogabile.

A differenza della versione originale basata su un database server-side pesante (Neo4j), il kernel v0.3 adotta un'architettura **Hybrid File-First**. In questo modello, la vera memoria risiede nei file Markdown che crei e modifichi. Il kernel funge da "sistema nervoso" che indicizza, scalda e connette questi file in tempo reale.

---

## Architettura a Doppio Strato

L'architettura separa rigorosamente la conoscenza persistente dal suo stato epistemico (calore dinamico), garantendo che i tuoi file markdown rimangano puliti e leggibili.

### Strato A: Lo Stato Statico (Markdown)
La directory `knowledge/` è l'unica sorgente della verità. 
- **Formato**: File `.md` standard.
- **Frontmatter**: Ogni file contiene metadati YAML (`title`, `type`, `scope`, `tags`).
- **Relazioni**: I collegamenti tra concetti sono espressi tramite **Wikilinks** (`[[Nome Nodo]]`).

### Strato B: La RAM Cognitiva (KùzuDB + ChromaDB)
Poiché scansionare migliaia di file ad ogni domanda dell'AI sarebbe troppo lento, Mnemosyne mantiene due "ombre" digitali dei tuoi file:
1. **KùzuDB (Graph Database)**: Una replica embedded leggera che traccia la topologia (chi è collegato a chi) e, soprattutto, il **Activation Level** (il calore del nodo).
2. **ChromaDB (Vector Database)**: Un indice semantico che trasforma il contenuto dei file in vettori matematici per permettere ricerche basate sul significato, non solo sulle parole chiave.

---

## Il Ciclo di Vita Cognitivo (Event Loop)

### Il File Watcher: Il battito cardiaco
Il cuore del kernel è il `FileWatcher`. È un demone silenzioso che osserva la cartella `knowledge/`. 
- Quando crei o modifichi un file, il Watcher lo parseggia istantaneamente.
- Estrae i wikilink e aggiorna il grafo in KùzuDB.
- Aggiorna l'indice semantico in ChromaDB.
- Regala un "boost di calore" al nodo: se lo stai scrivendo, la tua attenzione è lì.

### Il Modello di Attenzione (AttentionModel)
Governa la "fisica" della memoria:
- **Stimolazione**: I nodi si scaldano con l'interazione umana o AI.
- **Propagazione**: Il calore fluisce lungo i Wikilinks. Se parli del "Progetto A", anche i task ad esso collegati si intiepidiscono, salendo in superficie.
- **Decadimento (Il Sonno)**: Periodicamente, il sistema applica un decadimento matematico globale. La memoria che non usi "si raffredda", scomparendo dal contesto immediato per fare spazio al presente. Questo calcolo avviene solo nei database interni, senza mai riscrivere i tuoi file Markdown.

---

## Il Gateway FastAPI (Thin Client)

Il Gateway è il punto di ingresso unico per le interazioni. Nella v0.3 è diventato un layer estremamente sottile ("Thin Gateway"):
- Non gestisce più transazioni database complesse.
- Serve principalmente come bridge per l'interfaccia MCP e per le API REST minime.
- Coordina l'autenticazione tramite `X-API-Key` per gestire gli **Scopes** (Privacy).

### Knowledge Scopes
Rimane la divisione della conoscenza in livelli di privacy, gestiti tramite il metadato `scope` nello YAML dei file:
- `Private`: Note personali.
- `Internal`: Progetti di team.
- `Public`: Conoscenza condivisa.

---

## I Worker

### Gardener (Il Sonno)
Applica il ciclo di decadimento termico. È il processo che permette al sistema di "dimenticare" il superfluo e mantenere solo le connessioni calde.

### Briefing Worker
Analizza i picchi di calore in KùzuDB e individua connessioni dormienti. Se un argomento diventa molto caldo e ha vicini freddi che potrebbero essere rilevanti, il Briefing Worker genera una segnalazione ("The Butler suggests...").

---

## Resilience (Hydration Protocol)

L'intero strato dei database embedded è sacrificabile. Se le cartelle `data/kuzu_db` o `data/chroma_db` vengono eliminate, al riavvio del kernel il `FileWatcher` eseguirà un **Cold Boot**: scansionerà l'intera directory `knowledge/` e ricostruirà l'intero Connectome in pochi secondi. La tua conoscenza è al sicuro nei file; gli indici sono solo strumenti di velocità.

---

*Documento 3 di 7 — Il kernel*
*Progetto Mnemosyne — GiodaLab*
