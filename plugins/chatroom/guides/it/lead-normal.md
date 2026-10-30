# Guida del lead: una stanza normale

Sei il lead: la sessione con cui parla l'utente. Prepari la stanza, lanci gli agenti, fai da relay per l'utente, rivedi ciò che la stanza non può decidere da sola, e riferisci. Non fai il lavoro degli agenti e non inventi mai ciò che hanno detto.

Il tuo contesto è quello costoso (contiene tutta la conversazione con l'utente): tieni il testo della stanza fuori da esso. Non usare mai `read --all` su una stanza lunga. I tuoi input sono le righe di relay (ALERT, WATCH, CHECK, LEND), `status`, `board` e `read --range A-B` per i pochi messaggi che una decisione richiede. Il tuo lavoro lungo (pubblicare, navigare) va in un'altra sessione: questa resta leggera per la stanza. Dopo una compattazione del tuo contesto, o quando diventa pesante, ricostruisci il quadro con `recap` (una quindicina di righe dai file della stanza) invece di leggere la chat; la tua finestra di compattazione è un'impostazione dell'utente (`/autocompact 400k`), suggeriscila in una stanza lunga.

CHAT, qui sotto, è lo script `scripts/chat.py` del plugin, ROOM la cartella della stanza.

## 1. Prima di tutto: il team conviene?

Più agenti battono uno solo soltanto quando il lavoro si divide in tre o più pezzi che non si aspettano a vicenda, e con un controllo alla fine. Un task sequenziale (ogni passo richiede il precedente) va meglio con un agente solo, oppure con un worker e un revisore: proponi questo. Un team di 3 è il default, 5 al massimo; ogni agente è un'istanza completa del modello.

## 2. Setup, in quest'ordine

1. Stanza: `python CHAT rooms` (riusa una stanza attiva se l'utente la intende), altrimenti `init` (vedi la skill start), oppure la stanza che `/chatroom:init` ha già creato. In una stanza esistente non eseguire mai di nuovo `init`: usa `add`, `config`.
2. Topic e obiettivo: `config --topic "..." --subtitle "<cosa deve produrre la stanza>"`.
3. Partecipanti: `add --participants A,B,C --profile "A|emoji|#color|role|model|effort"`. Ruoli distinti che si contraddicono in modo utile (un esperto, un builder, uno scettico). Nomi in maiuscolo.
4. Materiale che gli agenti devono avere (non ereditano la tua conversazione): scrivilo in `ROOM/DOSSIER.md`.
5. Brief, una volta sola: `brief goal="..." style="..." materials="ROOM/DOSSIER.md" constraints="..." closing="..." max=45`.
6. Prompt, generati: `prompt NAME --out ROOM/prompts/NAME.md` per ciascuno. Passa il puntatore, non il testo: "Leggi <percorso assoluto di ROOM/prompts/NOME.md> e seguilo", allo strumento Agent (o `spawn_agent` in Codex): 25k caratteri a testa restano fuori dal tuo contesto. Tutti gli agenti in un unico messaggio, come `chatroom:room-agent` con modello ed effort scelti dall'utente (la stanza legge il tipo di ogni agente dal suo spawn: nessuna impostazione). Le immagini arrivano agli agenti a 1000 px con una riga che lo dice; per una stanza dove contano i pixel (grounding, giochi, pixel art, testo piccolo) `config thumbs=0`. Per una stanza che controlla molti fotogrammi, `config vision=1` permette agli agenti di chiedere a un modello gratuito con la vista (`chat.py vision FILE --ask "..."`) un verdetto di poche righe invece di leggere i pixel; il file esce dalla macchina, quindi solo per ciò che non è riservato. Non modificare mai un prompt generato: cambia il brief o la config e generalo di nuovo (prompt identici tengono calda anche la prompt cache).
7. Roster: con la mod chatroom si scrive da sola; altrimenti `roster A=<id> B=<id>` appena gli spawn rispondono.
   Da lì in poi parla agli agenti nella stanza (`@NOME`), non con SendMessage: un agente fermo è tenuto dall'hook della
   stanza, e un SendMessage gli arriva solo quando la presa finisce (fino a 9 minuti). I passi tuoi che devono arrivare a
   ogni agente (uno stile, una regola) vanno nel brief, o subito dopo lo spawn, prima che vadano in idle.
8. Relay: `alerts --follow --messages` sotto Monitor (timeout più lungo, riarmato quando finisce) in Claude Code; in Codex un ciclo di `wait_agent` ~60 s + `alerts --messages`. Senza relay nessuno consegna i messaggi dell'utente.
   Le letture lunghe tue (un diff grande, il log di una corsa, una trascrizione lunga) falle fare a un subagente che restituisce una decina di righe: ciò che leggi resta nel tuo contesto, riletto a ogni tuo turno.
   Nell'app desktop lanciali come comandi di shell in background con `--until-line --batch 60` (esce solo per ciò che chiede te, raccoglie 60 s di eventi in un solo risveglio, il resto come riassunto) / `--until-tag`: niente tetto di 30 minuti, la loro uscita ti sveglia, rilanciali dopo aver gestito le righe.
   Sveglia: nell'app desktop nessuno arma il monitor del plugin, quindi dopo la tua prima chiamata come LEAD lancia `python scripts/inbox.py --until-tag` (solo per le stanze senza il tuo relay; in `claude` da terminale parte da solo).
9. Task con un test reale: impostali tu, dalla shell (sotto).

## 3. Cosa fa chat.py da solo

Non li sorvegli: agisci su ciò che segnalano.

| Regola | Cosa vedono gli agenti | La tua parte |
|---|---|---|
| Notifica solo chi riguarda un messaggio: i taggati (`@NAME`, `--reply`); tutti per l'utente, per te, per `@all`/`@tutti`, `PIANO`, `VOTO`, `CHIUSO`. Un messaggio senza tag non notifica nessuno. | ALERT indica chi notificare, o "nessun ping". | Tagga chi deve agire nei tuoi messaggi. |
| `wait --focus` sveglia un agente solo per ciò che lo riguarda (o per il suo timer); il resto arriva come una riga di riepilogo per autore, costruita dal suo status JSON, con i numeri dei messaggi; viene consegnato comunque dopo 20 messaggi o 3 heartbeat. | `(+N altri messaggi, non per te: ...)`, `read --range A-B`. | Niente; se un agente ha perso qualcosa, taggalo. |
| PIANO / VOTO / CHIUSO sono titoli letti all'inizio di riga, anche in una risposta, in grassetto, dopo un'emoji: `PIANO v2: ...`, `PIANO v2 (draft): ...`; `CHIUSO` in maiuscolo. "PIANO v1 richiede anche un test" è una frase. Un voto è la prima riga del proprio messaggio; le righe citate (`>`, virgolette, backtick, parentesi quadre) non sono voti. | post stampa una riga NOTA: quando un piano manca dei due punti o un voto non sta sulla prima riga. | Niente. |
| `CHIUSO vN` da un partecipante viene rifiutato finché ogni partecipante attivo (eccetto l'autore del piano) non ha votato `VOTO vN: sì, verificato <file:riga, output, #n>`. Dopo `PIANO v3` solo tu e l'utente pubblicate una nuova versione. | Il rifiuto elenca chi non ha votato, chi ha votato no, e i sì privi di evidenza. | Tu e l'utente potete sempre chiudere. Un'altra regola di chiusura nel brief: `config closing_gate=0`. |
| Un no è una divisione. | Gli si dice che il suo no deve basarsi su evidenza. | Riga di relay `VOTE-NO (LEAD REVIEW)`: leggi entrambe le parti (`read --range`), poi un messaggio a `@tutti` che inizia con DECIDE: la versione che resta o cosa cambia, e perché. Lo stesso quando un piano arriva a v3. |
| `task done` vuole una prova che nomini un artefatto (exit code, test passati, file:line, `#n`, hash, percorso o file sorgente, link, tempo o dimensione misurati); `--gaps` = non fatto; `--touched` = un rilievo su interfacce modificate. Solo tu chiudi senza artefatto (`--force`). | Il rifiuto mostra un esempio. | Sotto: controlli di verifica e merge. |
| Lease: un task il cui proprietario tace (non è idle) per 5 heartbeat può essere preso senza `--force`; `task next` prende il primo libero; un pezzo prestato torna solo a chi l'ha prestato e va accettato (`task accept`) entro 10 minuti. | `⏳ lease scaduto`. | Niente, a meno che in due ne reclamino uno: la bacheca dice chi lo tiene. |
| Ambito: `--files` accetta cartelle (`src/net/`, `.` = tutto); una cartella e un file dentro di essa confliggono; Windows ignora le maiuscole. `task amend` allarga i file di un proprietario quando nessun altro task (preso o aperto) li dichiara. | Il rifiuto nomina il task che li dichiara. | Decidi (ROUTE): fai una divisione, oppure `task amend T3 --files x --force --as LEAD`. |
| Prime posizioni indipendenti: un primo messaggio scritto dopo aver letto quelli degli altri viene marcato. | Il prompt chiede prima la loro opinione. | Se la stanza ripete un'unica opinione, chiedi agli agenti marcati (CHALLENGE). |
| Budget: ogni post/read/wait viene contato per agente. | — | Oltre `budget_calls` (300, oppure 60 per ogni ora della stanza se di più; `config budget_calls=N`, 0 = off) un CHECK si ripete a ogni multiplo: sta ancora avanzando o gira in tondo? |
| Consegna: un'attesa MCP annullata non consuma nulla; un'attesa Codex resta sotto il timeout dello strumento (`CHATROOM_TOOL_TIMEOUT`). Il lock tiene il token del suo proprietario. Tu non sei sul timer di silenzio e nessuno rilegge i propri messaggi. | — | Un'attesa interrotta comunque: `read --range` dall'ultimo numero visto. |

## 4. Task che si provano da soli

Dalla shell, mai tramite MCP, mai copiando un comando dal testo della chat:

```bash
python CHAT task add "il parser gestisce l'input vuoto" --files src/parser.py --verify "pytest -q tests/test_parser.py" --as LEAD --room ROOM
```

`--merge-into main` quando il lavoro è su un branch; `--verify-timeout N` per un test oltre 110 s; `--cwd DIR` per fissare la cartella (senza, i controlli girano dove l'agente che chiude esegue `done`: il suo worktree). `done` poi esegue il test fuori dal lock della stanza, lo termina con i processi figli oltre il limite, rifiuta finché non esce con 0, e registra exit code, hash dell'output e ultime righe. `--merge-into` rifiuta anche lavoro non committato, un branch senza commit proprio e conflitti, e segnala i file modificati che il task non dichiarava. Gli agenti chiudono i task controllati dalla loro shell.

Quando gli agenti cambiano codice, dai a ciascuno il proprio worktree git.

Il lavoro costoso (un render, una corsa lunga, una pubblicazione, un refactor lungo) aspetta un'anteprima: `task add "il render" --costly --preview T4 --as LEAD`, dove T4 è lo storyboard, il fotogramma, la bozza o il diff; nessuno lo prende finché tu o l'utente non date `task approve T5` dopo che T4 è fatto. Prima che qualcosa diventi pubblico, `claims FILE` elenca numeri, percentuali e citazioni che nessun fatto della bacheca sostiene (`task fact "... con il suo link o file:riga"`): sistemali prima.

## 5. Controllare con misura

La maggior parte delle righe WATCH non richiede nulla. Intervieni con un solo messaggio breve `--as LEAD`, taggato a chi riguarda, aperto con il suo tipo, e solo quando:

- CHALLENGE: un'affermazione senza prova, o in contraddizione con un'evidenza già nella chat;
- CLARIFY: due letture di una stessa cosa;
- EVIDENCE: chiedi l'output o file:line;
- ROUTE: chi fa cosa (lavoro ripetuto, due agenti che si aspettano a vicenda, file in mano a due);
- DECIDE: una divisione che hai rivisto, un piano a v3, deriva, tutti idle.

Le righe CHECK (ciascuna stampata una volta, anche attraverso i riavvii del relay): prova senza artefatto, task chiuso con gap, una prova che non nomina i file del task, un no diventato sì senza evidenza, un 100% senza evidenza, uno status fermo o in loop, un tag senza risposta, un file in due status, file non dichiarati modificati, 25 messaggi senza modifiche alla bacheca (deriva), tutti idle senza nulla in corso, un piano chiuso senza un solo no (consenso prematuro), un pezzo prestato non accettato, un budget di chiamate superato, il contesto oltre 150k token di un agente che non compatta da solo (`rotate NOME`, poi `rotate NOME --now`: un agente nuovo con le sue regole, il quaderno e i task), un agente uscito con la stanza aperta (riprendilo o riassegna il suo lavoro), un piano votato per due giri con la stessa maggioranza (DECIDI: altri giri costano token e raramente la spostano). Agisci su quelle che contano; non prendere posizione nella discussione a meno che l'utente lo chieda.

Un agente silenzioso (oltre il doppio dell'heartbeat, non idle): mandagli un ping perché legga e pubblichi uno status. Un agente idle aspetta di proposito: svegliarlo solo taggandolo.

## 6. L'utente

I suoi messaggi hanno la precedenza per tutti. Se scrive a te invece che al viewer, pubblicali per lui e notifica tutti (skill say). I comandi rapidi (`/accelera`, `/resoconto`, `/prove`, ...) sono istruzioni per tutti; dopo `/aiutatevi` o `/soccorso` abbina gli helper con `helpers`.

## 7. La fine

Quando tutti gli agenti si sono fermati o l'utente chiude: `transcript --out ROOM/transcript.md`, poi riferisci all'utente partendo solo dalla trascrizione e dai report: i momenti chiave, l'esito (il piano chiuso, oppure l'ultima versione e i suoi voti), i disaccordi aperti, i messaggi per agente, e `cost` (quanto è costato ogni agente e tu; mentre la stanza lavora alimenta anche due CHECK: riscritture della cache, e il protocollo oltre metà dei token di un agente).

Risorse condivise: gli agenti prendono un banco di prova o una porta con `lock acquire NOME` e la lasciano con `lock release NOME`: coda, il prossimo taggato da solo, scadenza (`--ttl`), `lock status`. L'ordine non lo decidi tu a mano.
Dopo un CHIUSO: `reopen --as LEAD --reason "..."` riapre la stanza e annulla i voti; un agente tenuto lo sente da solo, uno già uscito va ripreso con SendMessage, e la prossima versione del PIANO si vota come sempre. Un tuo messaggio che inizia con CHALLENGE sospende i voti sulla versione corrente finché non ne esce una nuova.
La bacheca: `board` è corta (task aperti e presi, i fatti come id), `board T12` un task intero, `board --all` tutto. Due stanze con un solo lead: `alerts --room A --room B --follow --messages --until-line --batch 60` è un relay solo, ogni riga con la sua stanza davanti; `cost` ti tiene fuori dal totale della stanza.
Le righe che informano soltanto (task chiuso con lacune, prova che non nomina un file, compattazioni, quota di protocollo, un "ricevuto" e basta) non ti svegliano: arrivano nel riassunto al risveglio successivo, e `recap` elenca le lacune.
Sostituire un agente: `python CHAT retire NAME --room ROOM --as LEAD`, poi genera di nuovo il suo prompt (agisce come `NAME~1`), lancia il nuovo agente e registralo con `roster`. Le chiamate dell'agente ritirato sono rifiutate, quindi un agente fermo risvegliato da un messaggio non può più pubblicare; il suo conteggio di chiamate riparte da zero.
