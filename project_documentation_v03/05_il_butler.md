# Il Butler

## L'anima proattiva di Mnemosyne

Il Butler non è un database, né un archivio. È l'entità che trasforma Mnemosyne da "deposito di file" in un **partner cognitivo**. Se Mnemosyne è la memoria, il Butler è il sistema nervoso autonomo che segnala quando qualcosa richiede attenzione.

Dalla versione 0.3, il Butler si è evoluto per adattarsi all'architettura **File-First**. Non è più un demone centralizzato obbligatorio, ma una **capacità distribuita** che può manifestarsi tramite diversi canali: strumenti CLI, briefing periodici o suggerimenti iniettati direttamente nelle tue conversazioni con l'AI.

---

## La differenza tra trovare e ricordare

Mentre la ricerca semantica (Cerchio 3) serve a *trovare* qualcosa che sai di aver dimenticato, il Butler serve a *ricordarti* qualcosa che non sapevi di aver bisogno in quel momento.

Il Butler non aspetta che tu faccia una domanda. Osserva costantemente il "calore" dei tuoi concetti in KùzuDB. Se nota che un argomento è diventato molto caldo (perché ne stai parlando o scrivendo) e che esistono connessioni importanti ma "fredde" (dormienti), interviene per portarle alla tua attenzione.

---

## L'Initiative Engine: Il cuore della proattività

Il motore del Butler è l'**Initiative Engine**. La sua logica si basa su tre pilastri:

1. **Toposthesia (Rilevamento di picchi)**: Quando un'entità supera una soglia di attivazione (heat > 0.7), il motore scansiona i suoi vicini nel grafo.
2. **Dormanacy Check**: Se un vicino è rilevante ma ha un'energia molto bassa, viene considerato un "potenziale insight dimenticato".
3. **Generazione di Initiative**: Il motore formula un suggerimento. Ad esempio: *"Dato che stiamo parlando del Progetto Ganaghello, mi viene in mente che mesi fa avevi preso una nota sulla 'stabilità delle fondamenta' che ora è sepolta."*

---

## Manifestazioni del Butler

Nella nuova architettura, puoi interagire con il Butler in diversi modi:

### 1. Il Briefing Proattivo (CLI / Tool)
Puoi invocare il Butler in qualsiasi momento per avere un riepilogo dello stato della tua mente digitale:
- **CLI**: Eseguendo `python workers/briefing_worker.py`.
- **MCP**: Gli Agenti AI possono chiamare il tool `get_memory_briefing` per ricevere un'iniezione di "pensieri caldi" prima di iniziare a lavorare con te.

### 2. Suggerimenti contestuali in chat
Se usi Mnemosyne tramite un'interfaccia come Open WebUI o Claude via Desktop App, il Butler inietta silenziosamente le sue osservazioni nel contesto dell'Agente. L'Agente non le vede come file letti, ma come "intuizioni" o "memorie di background" che arricchiscono la risposta.

### 3. Allerta Scadenze (Time Watcher)
Il Butler monitora i metadati `deadline` e `due_date` nei file Markdown. Se una scadenza si avvicina, il calore di quel file sale artificialmente in KùzuDB, costringendo il sistema (e te) a notarlo tra i primi risultati.

---

## Il Contratto di Azione

Il Butler può agire sui file in risposta a comandi dell'AI o necessità di sistema:
- **Aggiornamento Status**: Può modificare lo YAML Frontmatter di un Task per passarlo da `todo` a `done`.
- **Linkaggio**: Può suggerire l'inserimento di un Wikilink tra due file che sembrano semanticamente identici ma non sono ancora collegati.
- **Deduplicazione**: Identifica file "doppioni" e suggerisce un merge testuale per mantenere la wiki pulita.

---

## Filosofia del servizio: Invisibile finché non serve

Il Butler segue una regola ferrea: **mai interrompere il flusso**.
I suoi suggerimenti sono pensati per essere marginali, pronti per essere ignorati se non pertinenti. Il feedback che dai (anche solo ignorando un suggerimento) viene registrato dal sistema per tarare meglio le future soglie di attivazione, imparando cosa è davvero importante per te.

---

*Documento 5 di 7 — Il Butler*
*Progetto Mnemosyne — GiodaLab*
