# Guida all'Integrazione: Mnemosyne come Cognitive Memory Layer

Questa guida è destinata agli sviluppatori che desiderano utilizzare **Mnemosyne** come motore di memoria semantica e base di conoscenza per applicazioni web, mantenendo i dati strutturati (es. utenti, permessi, sessioni) su un database SQL tradizionale (PostgreSQL, MySQL, ecc.).

## 🏗️ Architettura Ibrida Consigliata

L'approccio "Best Practice" prevede una separazione netta delle responsabilità:

1. **Database Relazionale (SQL)**: Gestisce entità strutturate, relazioni fisse e dati transazionali.
    * *Esempi*: Tabella `Users`, `Organizations`, `SubscriptionPlans`, `AuditLogs`.
2. **Mnemosyne (Graph Memory)**: Gestisce la conoscenza non strutturata, le intuizioni dell'AI e le connessioni semantiche.
    * *Esempi*: Concetti estratti dai documenti, note dell'utente, obiettivi strategici, suggerimenti proattivi ("The Butler").

### Mapping tra i due mondi

Per collegare i due sistemi, salva l'ID dell'utente o dell'organizzazione SQL come proprietà o label all'interno dei nodi di Mnemosyne utilizzando il sistema degli **Scopes**.

---

## 🔌 Collegamento API

Mnemosyne espone un'interfaccia REST (default porta `4002`) che funge da bridge verso il grafo Neo4j e i modelli di linguaggio.

### 1. Autenticazione e Scoping

Ogni chiamata deve includere l'header `X-API-Key` (se configurata).
Usa il parametro `scope` per isolare i dati:

* `Public`: Conoscenza condivisa da tutti.
* `Internal`: Conoscenza aziendale.
* `Private`: Conoscenza specifica per un singolo `user_id` (mappa l'ID SQL qui).

### 2. Endpoint Chiave per il Frontend

#### A. Inserire Conoscenza (Add Observation)

Invece di salvare solo una "nota" su SQL, inviala a Mnemosyne affinché venga analizzata:

```http
POST /add?scope=user_123
Content-Type: application/json

{
  "content": "Sto lavorando al progetto 'Alpha' e abbiamo deciso di usare React per il frontend."
}
```

*Cosa succede*: Mnemosyne estrae "Progetto Alpha" e "React", li collega e aumenta la loro "attenzione" (calore).

#### B. Ricerca Semantica (Search)

Per recuperare informazioni correlate senza usare query SQL complesse:

```http
GET /search?q=progetti frontend&scopes=user_123,Public
```

#### C. Briefing Proattivo (The Butler)

Per mostrare all'utente cosa è rilevante *adesso* nella sua area di lavoro:

```http
GET /briefing?scopes=user_123
```

---

## 🛠️ Pattern di Implementazione (Esempio Node.js/Python)

### Middleware di Sincronizzazione

Quando un utente crea un documento nel tuo database SQL, invia un segnale a Mnemosyne:

```javascript
// Esempio logica backend
async function handleUserNote(note) {
  // 1. Salva su SQL per record storico/testuale
  const sqlNote = await db.notes.create(note);
  
  // 2. Invia a Mnemosyne per arricchimento cognitivo
  await axios.post(`${MNEMOSYNE_URL}/add`, {
    content: note.text
  }, {
    headers: { 'X-API-Key': process.env.MNEMOSYNE_KEY },
    params: { scope: `user_${note.userId}` }
  });
}
```

---

## 💡 Best Practices

1. **Non duplicare i dati**: Non salvare l'email o la password dell'utente in Mnemosyne. Salva solo l'ID univoco come riferimento nello scope.
2. **Usa gli Scopes per la Privacy**: Assicurati che il tuo backend filtri sempre gli scope corretti basandosi sulla sessione dell'utente SQL.
3. **Sfrutta l'Attention Model**: Invece di mostrare liste cronologiche, usa l'endpoint `/briefing` per mostrare i concetti "più caldi" che Mnemosyne ha rilevato.
4. **Gestione Documenti**: Usa l'endpoint `/ingest` per caricare PDF/Markdown. Mnemosyne gestirà lo chunking e l'indicizzazione automaticamente.

## 🚀 Prossimi Passi

* Consulta `gateway/http_server.py` per tutti gli endpoint disponibili.
* Usa lo strumento **MCP** se la tua applicazione è un agente AI moderno (es. basata su Vercel AI SDK o LangChain).
