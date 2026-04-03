# Il Butler

## Cosa è il Butler e perché è separato da Mnemosyne

Il Butler non è un componente di Mnemosyne. È un'entità distinta che si appoggia a Mnemosyne come fonte di verità, osservando il suo stato interno e traducendo i cambiamenti in azioni concrete nel mondo dell'utente.

La distinzione è importante. Mnemosyne è il cervello silente — accumula, connette, dimentica, ricorda. Il Butler è il layer che trasforma questi stati interni in qualcosa di percepibile: una notifica, un'azione su un device, un contesto iniettato al momento giusto. Senza il Butler, Mnemosyne sa molte cose ma non le porta mai da nessuna parte da sola. Senza Mnemosyne, il Butler non ha nulla da dire.

La separazione permette anche flessibilità: ogni utente può istanziare il proprio Butler con comportamenti calibrati sul proprio contesto, senza toccare il kernel. Mnemosyne è condivisa e stabile. Il Butler è personale e configurabile.

---

## La differenza tra rispondere e agire

Tutti gli strumenti AI che conosciamo rispondono. Aspettano una domanda, elaborano, restituiscono. Il Butler fa qualcosa di diverso: **osserva e agisce**, indipendentemente da qualsiasi richiesta esplicita.

Questo non significa che il Butler sia autonomo in senso pieno. Significa che ha un contratto con Mnemosyne: quando certi stati interni del grafo si verificano, il Butler reagisce in modo predefinito. È un'automazione contestuale — non intelligenza autonoma.

La distinzione è sottile ma necessaria. Il Butler non decide cosa è importante. Lo decide il modello di attenzione di Mnemosyne, attraverso il calore dei nodi. Il Butler decide solo *cosa fare* quando qualcosa diventa importante.

---

## Il contratto di osservazione

Il Butler si iscrive agli eventi pubblicati dall'Event Bus del Gateway. Non tutti gli eventi sono rilevanti — il contratto di osservazione definisce quali stati del grafo attivano il Butler e con quale priorità.

### Eventi principali

| Evento | Condizione | Priorità tipica |
|---|---|---|
| `NODE_ENERGIZED` | Un nodo supera la soglia di attivazione configurata | Alta |
| `DEADLINE_APPROACHING` | Un Task o Goal ha una scadenza entro N giorni | Alta |
| `DEADLINE_OVERDUE` | Una scadenza è stata superata senza completamento | Urgente |
| `PROJECT_DORMANT` | Un Project o Goal era caldo ma è inattivo da M giorni | Bassa |
| `MAYBE_SAME_AS_PENDING` | Esistono ambiguità semantiche irrisolte su nodi caldi | Media |
| `ORPHAN_TASK_DETECTED` | Un Task senza contesto è stato rilevato dal Gardener | Bassa |

Le soglie — temperatura minima, giorni alla scadenza, giorni di inattività — sono configurabili per ogni istanza di Butler. Un Butler calibrato su un utente con molti progetti attivi avrà soglie più alte per evitare rumore. Uno calibrato su un utente con pochi progetti ma scadenze critiche avrà soglie più basse.

### Due meccanismi di attivazione

Il Butler opera attraverso due meccanismi distinti, con logiche e responsabilità diverse.

**Eventi**: attivazioni reattive generate dal grafo quando qualcosa cambia — un nodo si scalda, un task viene salvato, una scadenza si avvicina. Alcune operazioni del Gardener si prestano naturalmente a questo modello: deduplicazione dopo la creazione di un nuovo nodo, rilevamento task orfani dopo un salvataggio. Per queste, l'event-driven è più efficiente di un loop continuo.

**Cron**: attivazioni periodiche a orari o frequenze predefinite, indipendenti dallo stato del grafo. Sono il meccanismo giusto per il briefing periodico, il decadimento temporale, l'analisi longitudinale — lavori che devono avvenire a prescindere da cosa sia successo nel frattempo. La configurazione segue la sintassi standard di cron e può essere delegata al cron di sistema.

> **Nota aperta — Gardener: loop continuo o event-driven?** Alcune operazioni del Gardener non hanno un trigger naturale oltre al passare del tempo — il decadimento temporale, per esempio. La scelta tra un loop continuo leggero e un approccio puramente event-driven dipende dall'hardware disponibile e dal carico reale del sistema. L'approccio ibrido — event-driven per il lavoro reattivo, cron per il lavoro temporale — è probabilmente il più equilibrato, ma rimane una decisione implementativa aperta.

Quando un evento supera la soglia configurata, il Butler sceglie un'azione dal proprio vocabolario. Il vocabolario è il punto di contatto tra Mnemosyne e il mondo fisico o digitale dell'utente.

### Azioni di notifica

Il livello più semplice — il Butler porta qualcosa all'attenzione dell'utente senza agire sul mondo:

- Notifica su device (push notification, sistema operativo)
- Messaggio via canale configurato (Telegram, email, Slack)
- Generazione di un briefing testuale disponibile al prossimo accesso

### Azioni su strumenti

Il Butler può interagire con strumenti esterni se questi espongono un'API o sono configurati come destinatari:

- Aggiornare lo stato di un task in un gestionale di progetto
- Creare un evento in calendario
- Aprire un documento o una URL specifica
- Avviare un processo o uno script predefinito

### Azioni su Mnemosyne

Il Butler può anche modificare lo stato del grafo in risposta a eventi:

- Applicare un boost di attivazione a nodi correlati
- Marcare un Task come `allow_orphan` se l'utente lo conferma
- Eseguire un merge dopo conferma dell'utente su un `MAYBE_SAME_AS`
- Promuovere un nodo a uno scope più ampio via `/share`

---

## La soglia di intervento

Un Butler che agisce troppo spesso è rumore. Uno che agisce troppo poco è invisibile. La soglia di intervento è il parametro più delicato della configurazione.

Il sistema gestisce questo problema su due livelli:

**Priorità degli eventi**: non tutti gli eventi hanno lo stesso peso. Una scadenza superata ha priorità urgente e bypassa qualsiasi filtro. Un progetto dormiente ha priorità bassa e viene aggregato nel briefing periodico invece di generare una notifica immediata.

**Cooldown per evento**: dopo che il Butler ha segnalato un nodo, quel nodo viene marcato come "già notificato" e non genera nuove notifiche finché non scende sotto la soglia e risale. L'intervento avviene una volta per ogni "salita", non continuamente finché il nodo rimane caldo. Questo evita che un nodo persistentemente caldo — che l'utente non ha ancora gestito — generi rumore continuo.

**Feedback come apprendimento**: ogni azione del Butler può ricevere un feedback implicito o esplicito dall'utente. Se una notifica viene ignorata sistematicamente, il Butler abbassa la priorità di quel tipo di evento. Se viene seguita con un'azione, la priorità sale. Nel tempo, il Butler si calibra sul comportamento reale dell'utente — non su soglie fisse.

Questo meccanismo è già presente in Mnemosyne tramite `feedback.py`, che aggiorna i pesi delle relazioni in base alle interazioni. Il Butler lo estende al proprio livello: non solo le relazioni del grafo imparano, ma anche le soglie di intervento.

---

## Personalità e tono

Il Butler è prima di tutto un layer di servizio. La sua responsabilità è portare il contesto giusto al momento giusto — non intrattenere, non costruire una relazione.

Detto questo, il modo in cui il Butler comunica influenza l'esperienza dell'utente. Un tono troppo meccanico rende le notifiche fastidiose. Un tono troppo informale può sembrare fuori luogo in contesti professionali.

La configurazione della personalità è quindi limitata a pochi parametri di superficie: tono delle notifiche (formale, neutro, diretto), livello di verbosità (conciso, dettagliato), lingua di output. La profondità relazionale — empatia, adattamento emotivo, gestione delle conversazioni — è delegata agli LLM che operano sopra il Butler, non al Butler stesso.

Ogni utente che istanzia il proprio Butler definisce questi parametri in base al proprio contesto. Il kernel di Mnemosyne non ne è influenzato.

---

## Come istanziare un Butler

Il Butler è configurabile tramite un file dedicato che definisce il contratto di osservazione, il vocabolario delle azioni attive, e i parametri di personalità.

```yaml
# config/butler.yaml

observation:
  node_energized_threshold: 0.75      # Soglia di attivazione per NODE_ENERGIZED
  deadline_approaching_days: 3        # Giorni alla scadenza per DEADLINE_APPROACHING
  dormant_project_days: 30            # Giorni di inattività per PROJECT_DORMANT
  cooldown_hours: 24                  # Ore di silenzio dopo una notifica sullo stesso nodo

cron:
  - "0 8,17 * * mon-fri"   briefing       # Briefing alle 8 e alle 17, lun-ven
  - "30 15 * * sat,sun"    briefing       # Briefing alle 15:30 nel weekend
  - "0 3 * * *"            decay          # Decadimento temporale ogni notte
  - "0 9 * * mon"          longitudinal   # Analisi longitudinale ogni lunedì

actions:
  notification_channel: "telegram"    # Canale di notifica principale
  telegram_chat_id: "<chat_id>"
  enable_calendar: false              # Integrazione calendario
  enable_task_sync: true              # Sincronizzazione task con strumenti esterni

personality:
  tone: "neutral"                     # formale | neutro | diretto
  verbosity: "concise"                # conciso | dettagliato
  language: "it"
```

Ogni voce cron è una riga autonoma: espressione temporale standard seguita dal tipo di job. Lo stesso tipo può comparire più volte con orari diversi — il Butler li esegue tutti indipendentemente. La configurazione può essere delegata al cron di sistema operativo invece di gestire uno scheduler interno.

---

## Il Butler nel flusso quotidiano

Il Butler non ha un momento dedicato nella giornata dell'utente — è presente nei margini di quello che l'utente già fa.

Durante una conversazione con un LLM, il Butler può segnalare ambiguità semantiche irrisolte sui nodi attivi. Negli slot di briefing configurati, aggrega gli eventi a bassa priorità accumulati nel periodo precedente — il momento e la frequenza sono una scelta dell'utente: un solo slot al giorno, più slot in orari diversi, o una cadenza settimanale. Quando una scadenza si avvicina, interviene direttamente sul canale configurato senza aspettare il prossimo slot di briefing.

L'obiettivo è che l'utente percepisca il Butler non come uno strumento da usare, ma come qualcosa che c'è — silenzioso la maggior parte del tempo, presente quando conta.

---

*Documento 5 di 6 — Il Butler*
*Progetto Mnemosyne — GiodaLab*
