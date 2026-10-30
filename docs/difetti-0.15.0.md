# Chatroom 0.15.0 (0da4131): difetti trovati e 5 migliorie

Revisione del 30/10/2026 su tutto il commit 0da4131 (45 file, +1551/-206), da main a 5d05acc in poi. Righe di riferimento
su 0da4131. Ogni difetto ha la prova, la correzione proposta e il test da aggiungere alla suite (t014 o una nuova t015).

## Cosa è già verificato (non serve rifarlo)

- **Cache a 1 h degli agenti della stanza.** È attiva davvero. Un agente `chatroom:room-agent` su Haiku ha mandato tutte
  le richieste con `cacheControl ... "ttl": "1h"`, e l'uso riporta `ephemeral_1h_input_tokens` (transcript
  `subagents/agent-a5de784f8d0eba262.jsonl` della sessione dfbf87aa, 29/10 23:32).
- **`autoCompactWindow` e `experimental.cacheTtl`.** Sono campi del frontmatter degli agenti nel binario installato
  (`claude.exe` npm, loader degli agent). L'effetto della compattazione a 200k NON è misurato.
- **Avviso di RTK.** `RTK_SUPPRESS_HOOK_WARNING=1` lo toglie davvero (rtk 1.1.0).
- **`chat_for_agents()`.** Dal sorgente risolve in
  `C:\Users\Administrator\.claude\plugins\cache\artyomita-plugins\chatroom\0.15.0\scripts\chat.py`.
- **Prove dei moduli.** `hold.py --prova`, `squeeze.py --prova` e `thumbs.py` passano. `import chat` funziona col Python
  3.12 di sistema, quello usato dagli hook.
- **`/thumb`.** È protetto da `trusted()` (`chat.py:3764`).

## Difetti

### A. squeeze lascia passare intero un output enorme su poche righe (alto)

- **Dove.** `scripts/squeeze.py:18-21`. `short()` restituisce il testo com'è se `len(lines) <= HEAD + TAIL` (90 righe).
- **Prova.** Un JSON di 657.790 caratteri su una riga esce di 657.790 caratteri:
  ```python
  one = '{"data":[' + ','.join('{"id":%d,"name":"model-%d"}' % (i,i) for i in range(20000)) + ']}'
  len(squeeze.short(one, 'X'))  # 657790
  ```
  È il caso più comune della fucina: le risposte JSON delle API di Hugging Face e YouTube (categoria `bash.web/api`,
  2,8 M equivalenti). Lo stesso vale per i log di ffmpeg con `\r` e per l'HTML minificato.
- **Correzione.** Lavorare a caratteri oltre che a righe:
  - ogni riga oltre 2.000 caratteri si tronca con `[... N caratteri ...]`;
  - con poche righe e testo oltre LIMIT si tengono i primi ~6k caratteri, i pezzi che sembrano errori e gli ultimi ~16k;
  - l'output intero resta comunque in `ROOM/outputs/`.
- **Test.** JSON su una riga da 600k: uscita al massimo LIMIT, e contiene l'inizio, la fine e il percorso del file
  salvato.

### B. squeeze taglia la coda, cioè il risultato finale (alto)

- **Dove.** `scripts/squeeze.py:26`. Il `[:LIMIT]` finale taglia dalla fine: con righe lunghe, testa (30) + errori (40)
  + coda (60) superano i 32k caratteri e la parte persa è la coda.
- **Prova.** 300 righe da 500 caratteri più `FINAL RESULT: 42` in fondo: l'uscita è di 32.000 caratteri e senza
  `FINAL RESULT`.
- **Correzione.** Il budget si assegna dalla coda:
  1. prima la coda, fino a ~16k caratteri;
  2. poi la testa, fino a ~6k;
  3. poi gli errori, nel resto.

  Non si taglia mai la fine del testo composto.
- **Test.** Il caso sopra deve contenere `FINAL RESULT: 42` e stare in LIMIT.

### C. L'arresto anticipato del kernel può scartare una corsa che sarebbe stata tenuta (medio, tocca i risultati)

- **Dove.**
  - `scripts/research.py:775`:
    `if enough and 2 <= len(values) < c.get('repeats', 1) and enough(statistics.median(values))`;
  - il predicato è a `research.py:1055-1056`.
- **Problema.** Con 2 valori `statistics.median` è la media. Con `repeats=3` la mediana finale è il valore centrale, e
  la media dei primi due non la decide.
- **Esempio.** Direzione min, migliore di linea 1,0, valori 0,9 e 1,2: la media è 1,05, "perde", e la corsa si ferma.
  Con 0,95 come terzo valore la mediana sarebbe stata 0,95, cioè un keep.
- **Correzione.** Fermarsi solo quando almeno `repeats // 2 + 1` valori, presi uno per uno, perdono: allora la mediana
  perde per forza (vale anche con repeats pari, perché sono perdenti entrambi i valori centrali). Il predicato va passato
  per valore singolo, non sulla mediana.
- **Test.**
  - repeats=3 con [0.9, 1.2, 0.95]: nessuno stop dopo 2, keep;
  - [1.1, 1.2]: stop dopo 2;
  - repeats=5: stop solo con 3 perdenti.

### D. L'hold dipende dal viewer acceso, ma il prompt dice che chiudere il turno non costa nulla (medio)

- **Dove.**
  - `scripts/hold.py:26-29`: `find()` vuole il registro dei viewer aggiornato da meno di 60 s;
  - `_hold` lascia andare l'agente se il viewer sparisce;
  - il prompt è a `templates/agent_prompt.md:83` e `templates/it/agent_prompt.md:117` ("ending your turn while idle
    costs nothing").
- **Problema.** A viewer chiuso (dall'utente, per un crash o in una sessione senza viewer), un agente che segue il
  prompt e chiude il turno in idle si ferma per sempre. Il lead se ne accorge solo dai silenzi.
- **Correzione.**
  - Trovare la stanza senza il viewer: un registro scritto da `chat.py` stesso a ogni roster/post (per esempio
    `~/.claude/chatroom/live_rooms.json` con cartella e id), considerato vivo finché la chat non è chiusa e `chat.jsonl`
    è cambiato nelle ultime N ore. Oppure cercare l'id nei `roster.json` delle stanze note.
  - In alternativa, minima: rendere condizionale la frase del prompt ("se il viewer della stanza è acceso").
- **Test.** Registro dei viewer vecchio di 10 minuti, stanza viva, un messaggio taggato all'agente: l'hold lo
  consegna.

### E. Regole in contrasto su attesa e fine turno (medio, costa turni e confonde gli agenti)

- **Dove.**
  - `templates/agent_prompt.md:83`: "ending your turn while idle costs nothing";
  - `:84`, regola 9: "Then loop on wait --timeout {{IDLE_WAIT}}";
  - `templates/research_*.md`, worker:72, auditor:46, proposer:35, registrar:34, searcher:28, e le versioni `it/`:
    "do not end your turn".
- **Problema.** Tre politiche diverse.
  - Con `cache_ttl=1h` il giro di wait a 540 s costa circa 6-7 turni l'ora per agente fermo.
  - L'hold costa 1 turno ogni 50 minuti, più i risvegli veri.
  - L'agente non sa quale seguire.
- **Correzione.** Una sola politica:
  - idle = `post --idle` e poi fine turno (l'hold consegna);
  - `wait` solo per attese brevi (meno di 110 s, risultato atteso a momenti);
  - per i worker research: `research queue` e poi fine turno, con il risultato della corsa come board line che li tagga
    (vedi miglioria 2).
  - Allineare EN/IT, README (`README.md:66`, `:130`), guide del lead e la skill start (Known pitfalls).
- **Test.** Un test di testo che fallisce se nei template compaiono insieme "loop on wait" e "costs nothing".

### F. Coda research: scritture senza lock, due runner in gara, corse perse (medio)

- **Dove.** `scripts/research.py:1602-1655` (`queue`, `_queue_runner`, `run_queue`).
- **Problemi.**
  1. **Scrittura senza lock.** `queue.json` si legge e si riscrive senza lock (`:1615`, `:1649`): due worker in coda
     nello stesso istante, una delle due voci si perde.
  2. **Due runner.** `_queue_runner` controlla il pid, fa Popen e solo dopo scrive `queue.pid` (`:1632`): due `queue`
     contemporanei possono avviare due runner, che leggono la stessa voce pronta. Il secondo `evaluate` viene rifiutato
     e posta una riga "rifiutata" falsa.
  3. **Corse perse.** `run_queue` toglie la voce prima di `evaluate` e prende solo ValueError (`:1652`): un OSError o un
     KeyError uccide il runner e la corsa è persa senza traccia.
  4. **Runner eterno.** Una voce con `after=att-N` che non arriverà mai (budget finito) tiene vivo il runner per sempre,
     con un giro ogni 15 s.
- **Correzione.**
  - Coda modificata sotto `_locked(room, ...)` o un lock a file.
  - Runner con un lock esclusivo (`queue.lock` creato con O_EXCL, pid dentro, stantio se il pid è morto).
  - `except Exception` che posta la riga e continua.
  - Voci con `after` irraggiungibile (N oltre `max_evals`, o fase non più 2) tolte con una riga.
- **Test.**
  - 2 `queue` in parallelo (thread): 2 voci;
  - 2 `_queue_runner` in parallelo: un solo processo;
  - `evaluate` che lancia OSError: riga sulla bacheca e runner vivo.

### G. `cache_ttl=1h` è un passo a mano del lead (medio, può riportare il bug della fucina)

- **Dove.**
  - `scripts/chat.py:769-771`: `idle_wait_max()` legge solo la config della stanza;
  - `:2232`: soglia del contesto;
  - `skills/start/SKILL.md`: passo a mano.
- **Problema.**
  - Se il lead mette `cache_ttl=1h` ma lancia agenti general-purpose (cache a 5 minuti), le attese da 540 s tornano a
    riscrivere tutto il contesto: è il 37% di spreco della fucina.
  - Se lo dimentica con i room-agent, si perde solo metà del vantaggio.
  - Una stanza mista (un room-agent e un agente di tipo diverso) non si può esprimere.
- **Correzione.**
  - TTL per agente, non per stanza. Il mod vede il tipo allo spawn (`hooks/register.ts:292`, `subagentType`, già salvato
    da `activity.py:403`): scriverlo nel profilo dell'agente.
  - `idle_wait_max(name)` dà 540 solo se quell'agente è `chatroom:room-agent*`; la stessa logica vale per la soglia del
    contesto (CHECK).
  - `config cache_ttl` resta come forzatura.
- **Test.** Stanza con un room-agent e un general-purpose: 540 al primo, 270 al secondo.

### H. Gli hook nuovi girano in tutte le sessioni (basso, ma si paga a ogni comando)

- **Dove.** `hooks/hooks.json:9-11`: PostToolUse su ogni Bash di ogni sessione, SubagentStop su ogni sotto-agente.
- **Misura (30/10, questa macchina).**
  - `squeeze.py` con un output corto: 89 ms a chiamata Bash, più il wrapper `command -v`;
  - `hold.py` con un agente fuori stanza: 137 ms a ogni fine di sotto-agente.
- **Correzione.**
  - Spostare il filtro nel mod (`register.ts` sa già se l'agente è di una stanza, `roomOf(e.agentId)`) se l'API del mod
    permette di riscrivere il risultato di un tool.
  - Altrimenti uscire prima di avviare Python: un controllo in bash sulla dimensione dello stdin, e per hold un test sul
    file `rooms.json` che non contiene l'id.
- **Test.** Il tempo medio di 100 Bash con e senza plugin.

### I. Documentazione dell'attesa idle non aggiornata (basso)

- **Dove.** `README.md:66` e `:130`, la skill start (Known pitfalls) e `templates/room_agents.md`.
- **Problema.** Dicono "270 s" senza nominare i 540 con la cache a 1 h, né la politica dell'hold (vedi E).

### J. Le immagini ridotte non hanno via d'uscita (basso)

- **Dove.** `hooks/register.ts`, la funzione `thumb()` e il ramo Read in `tool.call`; `scripts/thumbs.py:MAX`.
- **Problema.** Un agente che deve leggere un testo piccolo in un fotogramma 1080x1920 lo riceve a 562x1000 (la scritta
  da 46 px diventa 24 px) e non può chiedere l'originale.
- **Correzione.** Lasciare intatto un percorso con un suffisso (`#full`), oppure `config thumb_px=N`. Va detto nel
  prompt.

### K. L'hold consegna un'anteprima e poi fa rileggere tutto (basso, un turno a risveglio)

- **Dove.** `scripts/hold.py:reason()` e la chiave `chat.say.hold.new_for_you`: 4 messaggi da 300 caratteri, poi "Leggi
  la stanza (read --focus)".
- **Problema.** A ogni risveglio l'agente fa una `read` in più per avere quello che l'hook aveva già letto.
- **Correzione.**
  - Mettere nel `reason` l'uscita di `room.read(name, focus=True)`, già limitata a ciò che lo riguarda, e far avanzare
    il cursore.
  - Rinviare a `read` solo se il testo supera una soglia (per esempio 6k caratteri), con `expand N` per i messaggi
    lunghi.

## 5 migliorie per renderlo davvero di prima fascia

Nella fucina, e lo dicono anche le note del 29/10, il costo è turni x contesto riletto. La 0.15 ha abbassato il
contesto e tolto le riscritture della cache. Il passo dopo è far consumare un turno a un agente solo quando c'è qualcosa
per lui, misurare ogni stanza, e smettere di rifare il lavoro.

### 1. Contatore dei costi dentro la stanza

**Cosa.** `chat.py cost`, un pannello del viewer e un report alla chiusura. Per ogni agente e per il lead mostrano:
- richieste, letture e scritture della cache, output;
- token equivalenti (pesi input 1, scrittura 1,25 o 2 a 1 h, lettura 0,1, output 5);
- riscritture della cache (scrittura sopra il 50% del contesto dopo una pausa più lunga del TTL);
- quota del protocollo (wait, read, status, idle, ping) contro il lavoro.

**Come.**
- `agent_context()` legge già l'uso dai transcript: va esteso a tutte le richieste.
- La classificazione dei tool c'è già negli script dell'analisi della fucina (`token.py`, `gap.py` nella cartella
  scratchpad della sessione dfbf87aa, `analisi_stanza/`).
- Due CHECK nuovi: "riscritture della cache" (quella che nella fucina costava il 37%) e "protocollo oltre il 50%".
- Un banco di regressione: una stanza registrata (fixture) rigiocata a ogni release, che fallisce se il costo per
  messaggio cresce oltre una soglia.

**Perché.** Oggi ogni risparmio è una stima [calc] e si scopre solo con un'analisi a mano. Con il contatore ogni stanza
si misura da sola, e l'utente vede in diretta chi costa e perché. È anche il libro dei costi chiesto per la research
(P10).

**Costo e rischio.** Medio, rischio basso: legge solo i transcript locali, e senza transcript (Codex) mostra "n/d".

### 2. Postino unico: niente polling, niente SendMessage tra agenti

**Cosa.** Un solo strato di consegna che sceglie da sé, in base allo stato dell'agente:
- **in wait:** il file della chat (già oggi);
- **al lavoro:** il tag a metà lavoro via hook `additionalContext` (0.14);
- **a turno chiuso:** l'hold, reso indipendente dal viewer (D).

**Come.**
- L'ALERT degli agenti diventa solo informativo: un agente non manda mai SendMessage. Nella fucina erano 228 chiamate
  e 242 code.
- La regola idle diventa `post --idle` e fine turno (E).
- I worker research mettono la corsa in coda e chiudono il turno: la riga del kernel che chiude la corsa li tagga e li
  risveglia.
- TTL per agente dal tipo (G).

**Perché.** Nella fucina il protocollo era il 67% del costo degli agenti. Con il postino un agente consuma un turno
solo quando c'è un messaggio per lui o un suo risultato, e mai per controllare se c'è qualcosa.

**Costo e rischio.** Medio, rischio medio: tocca prompt, hold, mod e kernel insieme. Va provato con una stanza di 3
agenti finta (messaggi scritti da script) e misurato con la miglioria 1.

### 3. Rotazione automatica del contesto, regole intatte

**Cosa.** `chat.py rotate NAME`:
1. tramite l'hold, chiede all'agente di scrivere il quaderno (stato, prossimi passi, riferimenti #n e file:riga);
2. costruisce il prompt nuovo: template + regole `--rule` parola per parola + quaderno + il pezzo di bacheca dei suoi
   task;
3. il lead lancia l'agente fresco con lo stesso nome (la generazione `NAME~2` esiste già).

**Quando.** Al CHECK del contesto, o dopo la seconda compattazione: dopo 5 compattazioni resta il 10% delle regole
(2608.22752).

**Insieme.** Un PreToolUse leggero per gli agenti della stanza:
- un Read di un file di testo oltre 50 KB senza offset/limit riceve un limit e una nota;
- un Write che riscrive un file esistente oltre 20 KB riceve l'avviso "usa Edit".

Nella fucina erano circa 120k token per agente di file riscritti con heredoc.

**Perché.** Un agente fresco riparte da circa 30k token, contro i 200k di uno compattato, e non perde regole né
decisioni.

**Costo e rischio.** Basso-medio, rischio basso: il quaderno c'è già, manca solo l'automatismo.

### 4. Occhio esterno: le letture pesanti fuori da Claude

**Cosa.** `chat.py look FILE --ask "..."` manda un'immagine, un log lungo o una pagina web a un modello gratuito con la
vista, tra gli host di spawn (il catalogo ha già i metadati di vision). Restituisce un verdetto di 3-5 righe, in cache
per hash del file.

**Esempio.** "Nei fotogrammi 0-3 s il testo esce dai margini? La keyword si legge?"

**Il mod.** Può proporlo al posto del Read quando un agente legge più di N immagini di fila.

**Perché.** Nella fucina 141 fotogrammi letti come immagini erano circa l'8% del costo, e restavano nel contesto per
sempre. Un verdetto di 5 righe costa cento volte meno e non si porta dietro i pixel.

**Costo e rischio.** Medio.
- Rischi: qualità dei modelli gratuiti e file che escono dalla macchina.
- Solo per contenuti non riservati, attivabile per stanza.
- Mai sui dati sigillati della research.
- Se l'host non risponde, si torna al thumbnail.

### 5. Cancelli prima del lavoro caro e registro dei fatti con fonte

**Cosa.**
- **Task costosi.** Un task segnato `--costly` (render, corsa lunga, pubblicazione) non si può prendere finché il suo
  task `preview` (storyboard, fotogramma, copione, diff) non ha l'ok del lead o dell'utente (`task approve`).
- **Registro dei fatti.** I fatti della bacheca portano la fonte (URL, file:riga). `chat.py claims FILE` estrae da un
  testo da pubblicare numeri, percentuali e nomi propri e li confronta con i fatti: quelli senza fonte diventano CHECK.

**Perché.** Lo spreco più grosso della fucina che non si vedeva nei token era il rifare:
- il framing 0/2304, "94% invented", "I serve", "sent a file", tutti presi da Adrian a video finito, ognuno con un
  render in più e i giri di verifica;
- i due agenti, nei rapporti finali, chiedono proprio "fonte primaria prima del copione" e "storyboard approvato prima
  del codice".

Lo stesso cancello serve nelle stanze di codice (diff prima di un refactor lungo) e completa la pre-registrazione della
research.

**Costo e rischio.** Basso-medio, rischio basso: è la bacheca con due stati in più e un estrattore di affermazioni.

## Ordine consigliato per la sessione di fix

1. A, B, C: si correggono in fretta, con un test ciascuno.
2. D, E, G: vanno insieme, perché sono la base della miglioria 2.
3. F, K.
4. H, I, J.
5. Poi la miglioria 1, così ogni passo dopo si misura.
6. Infine 2, 3, 5, 4.
