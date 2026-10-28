# Piano: idee da pixel-agents e concord-mcp per la chatroom

Analisi del 28/10/2026. Repo lette (clone in `D:\ref-repos`):
- pixel-agents-hq/pixel-agents, commit b1bafd0 (16/10), licenza MIT: ufficio pixel-art degli agenti Claude Code, estensione VS Code e CLI standalone.
- get-concord-ai/concord-mcp, commit 37d48f7 (28/10), licenza MIT: strato MCP locale per far parlare agenti di harness diversi e coordinare il lavoro.

Lette per intero: entrambi i README, il glossario `CONTEXT.md` e `docs/design/standalone-terminal.md` di pixel-agents, `docs/claude-code.md`, `docs/codex.md`, `docs/messaging-v2.md` e il plugin `concord-relay` (hooks, monitors, `watch-inbox.sh`) di concord. Il codice l'ho guardato nei punti che servono al confronto (gestore degli eventi hook, indicatore del contesto, guardia sulle modifiche, terminale integrato).

Le licenze sono MIT e la chatroom è AGPL-3.0-only: il codice copiato o adattato si può portare dentro, con l'attribuzione nel file (come già fatto con free-claude-code).

## Cosa la chatroom ha già (non lo rifaccio)

| Idea delle due repo | Nella chatroom |
| --- | --- |
| Un personaggio per agente, animato da quello che fa | Ufficio 3D, `activity.py` e mod `register.ts` |
| Bolla "attende permesso" | `activity.py` (waiting), toast nel /stanza |
| Indicatore del contesto (istantanea, la finestra si allarga se superata) | `activity.py` ctx/window, stesso metodo |
| Sotto-agenti come personaggi | `activity.py` + `office.js` |
| Rivendicare file prima di lavorare, avviso di sovrapposizione | board/task con `files`, `files_overlap` in `chat.py` |
| Claim scaduti (proprietario sparito) | lease dei task (`lapsed`, 5 heartbeat) |
| Editor dell'ufficio | `office-edit.js` |
| Accesso da un altro dispositivo con segreto | `share.py` (PIN, token, tunnel) |
| Pannello nel terminale | `/stanza` |
| Suoni a fine turno | beep della chat |

## Da portare dentro (in ordine di valore)

### 1. Sveglia immediata delle sessioni ferme (concord, monitor del plugin)
Problema oggi: una sessione Claude ferma al prompt (il LEAD, o tu che hai aperto la stanza) non sa di essere stata taggata finché non legge da sola. Per questo il LEAD ha un cron ogni 15 minuti.
Come lo fa concord: il plugin dichiara un `monitor` (`experimental.monitors` in `plugin.json`); è uno script che gira per tutta la sessione e ogni riga che stampa diventa una notifica che sveglia la sessione anche quando è ferma.
Adattamento: `monitors/monitors.json` nella chatroom con `chat.py inbox --monitor`. Lo script trova la stanza della sessione da `CLAUDE_CODE_SESSION_ID` (già in `rooms.json`, campo `ids`), stampa una riga per ogni messaggio che tagga quella sessione o le chiede qualcosa, poi aspetta di nuovo. Esce subito se la sessione non è in nessuna stanza (zero costo nei progetti senza chatroom) e si ferma se il processo di Claude Code muore (controllo del processo genitore, come `watch-inbox.sh`).
Effetto: il cron del LEAD non serve più; tag a te o al LEAD arrivano in pochi secondi.
Da verificare prima: che la versione di Claude Code installata accetti `monitors` nei plugin e come si comporta su Windows (lo script di concord è bash).

### 2. Messaggi consegnati a metà lavoro (concord, hook PostToolUse e Stop)
Problema: un agente che lavora a lungo (molti tool di fila) vede un tag solo alla sua prossima `chat_read`.
Come lo fa concord: a ogni PostToolUse e a ogni Stop un hook svuota la casella e restituisce i messaggi nuovi come contesto aggiuntivo.
Adattamento: nel mod `register.ts` (che vede già ogni tool di ogni agente della stanza) aggiungere, dopo il tool, una riga breve "📨 #N da X: …" quando quell'agente ha un tag non letto. Solo tag e messaggi dell'utente, mai tutta la chat, per non gonfiare il contesto.
Da verificare: se il contesto aggiunto in un hook di un sotto-agente arriva al sotto-agente e non alla sessione principale.

### 3. Ricevute dei messaggi (concord, spunte stile WhatsApp)
Stati: ✓ inviato, ✓✓ consegnato (preso dalla sessione), letto (il cursore del destinatario è oltre quel messaggio), ↩ risposto. La chatroom ha già i cursori di lettura per agente, quindi "letto" costa poco.
Nel viewer: spunte accanto a ogni tag, per destinatario. Per chi scrive: se il destinatario sta aspettando un tuo permesso, `chat_post` lo dice ("FETTE non lo leggerà finché Adrian non risponde").
Più una chiave di idempotenza facoltativa su `chat_post`: un nuovo tentativo dopo un errore di rete non duplica il messaggio.

### 4. Guardia sulle modifiche (concord, PreToolUse con blocco)
Oggi una sovrapposizione di file tra task è solo un avviso. Concord blocca davvero: un hook PreToolUse su Edit/Write risponde "nega" quando il file è rivendicato da un task attivo di un altro agente.
Adattamento: nel mod, su Edit/Write/NotebookEdit di un agente della stanza, se il file è nei `files` di un task preso da un altro agente e il lease non è scaduto, nega con il motivo ("prova.py è di T3 di FETTE: chiedi in chat o prendi il task"). Usa `files_overlap` e `lapsed` che già esistono. Interruttore per stanza, acceso di default nelle stanze research.

### 5. Assegnazioni e passaggi di consegne espliciti (concord, transfer_work)
Oggi un task si prende o si lascia. Concord aggiunge:
- assegnare a qualcuno: il task resta "assegnato" finché quell'agente non accetta;
- offrire un passaggio di consegne: la proprietà resta a chi offre finché l'altro non accetta;
- numero di versione del task: due agenti che agiscono sulla stessa versione, vince il primo e l'altro riceve un errore chiaro;
- storico delle proprietà che si aggiunge e basta.
Adattamento: nuove azioni `assign`, `accept`, `decline`, `offer` nello strumento `task`, versione nel task, storico nel file della board. Le carte del viewer mostrano "assegnato a X, in attesa".

### 6. Pacchetto di revisione e consegne leggibili (concord, REVIEW_PACKET.md e HANDOFF.md)
Quando un task si chiude con la prova, la chatroom genera nella cartella della stanza `review/T3.md`: obiettivo, file toccati, comandi di test con esito, rischi, messaggi della chat collegati (#n), chi l'ha fatto. Con le consegne del 🧳 dei ruoli spawn fa lo stesso (`handoff/NOME.md`). Utile a te e al LEAD per verificare senza rileggere tutta la chat.

### 7. `chat.py doctor` (concord, doctor e adapters status)
Un solo comando che controlla: versione del plugin installata contro quella del sorgente, percorso dell'MCP `chatroom` (oggi va ripuntato a mano a ogni aggiornamento), ambiente Python 3.14, viewer in ascolto, hook attivi, Headroom e RTK, chiavi spawn salvate (solo sì/no). Stampa i comandi per sistemare quello che non va.

### 8. Codex svegliato dal vivo (concord, app-server di Codex)
Gli agenti Codex della stanza oggi ricevono i ping con `send_message` solo quando leggono. Concord usa l'app-server di Codex (`turn/steer` durante un turno, `turn/start` quando è fermo). Utile, ma legato alla versione del protocollo di Codex: da fare dopo i punti 1-7, con un controllo di versione che rinuncia in modo pulito se il protocollo cambia.

## Da valutare dopo (valore minore o costo alto)

9. **Lanciare agenti dal viewer, con terminale integrato** (pixel-agents): "+ Agente", scegli una cartella, parte Claude Code in un terminale lato server mostrato nel browser (xterm.js), anche dal telefono via share. Grosso: su Windows serve pywinpty, e lanciare processi dal browser va protetto col token di share.
10. **Ufficio in sola lettura** (pixel-agents): chi apre il viewer senza token vede tutto ma non scrive né lancia nulla. Da confrontare con quello che fa già il PIN di `share.py`.
11. **Ruoli spawn disegnati come "fantasmi"** (pixel-agents, Ghost): i ruoli spawn non hanno terminale; semitrasparenti nell'ufficio, a richiesta.
12. **Aree** (pixel-agents): zone dell'ufficio legate a cartelle o progetti; gli agenti di quel progetto si siedono lì.
13. **Esporta e importa la disposizione dell'ufficio in JSON**, più pacchetti di mobili e personaggi esterni (pixel-agents).
14. **Squadre** (pixel-agents, Lead e Teammate): disegnare chi ha generato chi, con i sotto-agenti attorno al genitore invece che seduti.
15. **Prima apertura guidata** (pixel-agents, Greeter): quattro passi che spiegano la stanza e chiedono il consenso per gli hook.

## Cosa non porto
- Telemetria di concord (manda dati a getconcord.ai): no.
- Concord Cloud e la sincronizzazione tra macchine: la chatroom ha già share e la sala comune.
- Scrittura automatica in `CLAUDE.md`, `AGENTS.md` e nelle config di altri client: troppo invasiva.
- Caselle private per agente (messaging v2 di concord): la stanza è pubblica per scelta.
- Ufficio 2D canvas di pixel-agents: abbiamo già il 3D.

## Suite di test (dopo l'implementazione)
- Ogni funzione nuova con il suo self-check nel file (stile `_prova` attuale): monitor (stanza giusta, uscita senza stanza, uscita a processo morto), guardia (nega solo con lease valido, permette al proprietario e con lease scaduto), ricevute (consegnato, letto da cursore, risposto, idempotenza), versioni dei task (doppia azione sulla stessa versione), pacchetto di revisione, doctor.
- Prove di integrazione nella suite `claude-plugins-dev-tools/t013/run_all.sh`: stanza vera in HOME temporanea con due agenti finti che si tagga, si bloccano sullo stesso file, si passano un task.
- Prova dal vivo con sessioni Claude vere: sessione ferma svegliata dal monitor, agente fermato dalla guardia, passaggio di consegne tra due agenti.
- Interfaccia: controllo nel browser integrato (spunte, carte "assegnato") come per le versioni precedenti. Pixel-agents usa Playwright per l'end-to-end: si può aggiungere, ma scarica i browser (circa 150 MB su D:), quindi solo se lo vuoi.

## Ordine proposto
1 e 2 insieme (la sveglia), poi 4 (la guardia), poi 3, 5, 6, 7, poi la suite completa. Il punto 8 e la lista "dopo" solo se li scegli tu.
