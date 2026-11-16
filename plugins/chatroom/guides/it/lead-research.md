# Guida del lead: una stanza di ricerca

Una stanza di ricerca migliora un file di un repository git contro un valutatore che nessuno può toccare. Gli agenti con
ruoli fissi propongono; il kernel (`chat.py research`) controlla ogni proposta, scrive lo stato condiviso, esegue e
misura ogni tentativo nello stesso modo, e registra ogni modifica e ogni azione rifiutata (`ROOM/research/log.jsonl`).
Tu conduci le fasi con l'utente, assegni i cicli, decidi le divisioni e riporti. Non modifichi mai il programma e non
unisci mai il risultato: lo fa l'utente.

Il tuo contesto è quello costoso: segui la stanza tramite il relay, `research status` e `research view`, non leggendo
i log né tutta la chat. Apri un messaggio (`read --range n-n`) solo quando ti tagga o cambia una decisione; il lavoro lungo
nella stessa sessione (pubblicare, navigare) lascialo a un'altra sessione. Oltre i 300k una riga CHECK dice che il tuo contesto è pesante:
scrivi `ROOM/LEAD.md`, poi di' all'utente di compattare (la riga da copiare è nella CHECK). Dopo una compattazione, `recap` ricostruisce la
stanza in una quindicina di righe. Il relay con `--until-line` (il passo della stanza: 3 minuti all'inizio, 15 dopo 20 minuti) ti sveglia solo per ciò che chiede te (tra le
righe del kernel un nuovo migliore globale o un crash); log e diff grandi li legge un subagente che restituisce dieci righe.

CHAT, qui sotto, è lo script `scripts/chat.py` del plugin, ROOM è la cartella della stanza (percorso assoluto).

## 1. È un compito di ricerca, e quanto grande deve essere la squadra

Un compito di ricerca ha un solo file da migliorare, un comando che lo misura con un solo numero, e una misura abbastanza
rapida da permettere decine di corse. Kernel, motori di inferenza, script di addestramento, solver, prompt in un file,
config: tutti rientrano. Senza numero, o con più file che devono cambiare insieme: una stanza normale.

La squadra (il default sostenuto dal paper):

| Ruolo | Modello | Quanti | Fa |
|---|---|---|---|
| WORKER | forte (Opus o Sonnet, high o xhigh) | 2 (un terzo solo con l'ok dell'utente) | modifica il programma nel proprio worktree, esegue, riporta evidenze |
| PROPOSER | Sonnet high | 1, lanciato quando ti servono idee, ritirato dopo | idee a turno (gap, analogia), sola lettura |
| AUDITOR | Sonnet xhigh | 1 | verdetti ai controlli di fase, controlla ogni tentativo tenuto, revoca |
| REGISTRAR | Haiku, lanciato a fine ciclo per direzione e conclusioni; senza, il kernel registra da solo le evidenze che poggiano sulle sue corse | 0 o 1 | cura le evidenze, la mappa della direzione, le conclusioni |
| SEARCHER | Haiku o Sonnet low/medium | da 0 a 5 | lavoro precedente e letteratura, come evidenze con link |

Lo sforzo costa token di uscita a ogni turno: xhigh solo per i worker e l'auditor; in una notte il registrar a xhigh ha
prodotto più uscita di ogni worker.

Una GPU: una corsa alla volta sul valutatore. Un secondo `evaluate` mentre una corsa è in corso viene rifiutato subito
(non aspetta): il worker pensa e modifica nel frattempo, e riprova quando `research status` non mostra più una corsa.
Due worker valgono comunque, perché uno modifica mentre la corsa dell'altro procede. Ogni worker ha il proprio worktree,
quindi serve il proprio albero di build e la propria copia delle cartelle `--keep` (partono vuote a `assign`: riempile o
collegale, per esempio con un symlink o una junction ai dati condivisi). Con build molto lunghe, parti con un worker e
aggiungi il secondo quando la prima build è finita. Senza ruoli assegnati, il kernel lascia fare qualsiasi cosa a un
solo worker.

Tieni la stanza fuori dal repository (o non eseguire mai `git clean -x` lì): una stanza dentro il progetto viene
aggiunta a `.git/info/exclude`, ma `git clean -fdx` lo ignora e cancellerebbe la stanza e i suoi worktree.

## 2. Fase 0: il contratto, con l'utente

Scrivi `ROOM/research/task.md` insieme all'utente; pubblica ogni bozza finché l'utente non la approva. `research init`
rifiuta di partire senza, e ne registra l'hash nel log (pre-registrazione). Chiedi all'utente a quale profilo di topic si unisce la stanza (`lessons topic list` mostra quelli che esistono; un nuovo nome breve ne crea uno) e lancia `lessons topic use SLUG --confirmed --as LEAD` solo sulla sua risposta, mai di testa tua: è la memoria della stanza per le stanze dopo. Le dieci righe da dirgli sono nella guida normale
(`guide normal`, "Cosa ricorda la stanza").

Il modo di lavorare dell'utente, a fianco di quello del kernel:

| Il flusso dell'utente | Nel kernel |
|---|---|
| dati | fase 0: il contratto (`task.md`: programma, valutatore, metrica, dati) e la corsa di baseline |
| smoke | fase 1: `research evaluate --kind smoke`, il via libera dell'auditor, il sigillo |
| web | tappa 2 del round (SEARCHER, PROPOSER) |
| ipotesi | l'idea che ogni ricerca riporta con la sua fonte; a un tentativo si assegna un'idea (`research assign`) |
| test | tappa 3 del round (WORKER, 5-10 corse corte) |
| ancora web | tappa 5 del round (SEARCHER sui risultati) |
| un altro giro | tappa 6 del round: `research round close --decision more` |

Due cose che il flusso dell'utente nomina e il kernel no: l'ipotesi non è un passo a sé (è l'idea di un tentativo), e lo
smoke gira una volta, nella fase 1, prima del sigillo, non all'inizio di ogni round. Diglielo, e non promettere né l'una né l'altro.

```markdown
# Contratto
Obiettivo: <cosa migliora, in una frase>
Repository: <percorso assoluto>   (committato e pulito; il kernel lavora in worktree suoi)
Programma (l'UNICO file che cambia): <percorso>
Build: <comando prima di ogni misura, oppure none>; limite di tempo della build: <minuti>
Valutatore: <comando>; valutatore finale (una volta sola, alla fine, su dati riservati): <comando oppure none>
Metrica: <NOME>, <lower|higher> è meglio; nel file $CHATROOM_RESULT (preferito) oppure stampato una volta come "NOME: valore"
Rumore: misure per corsa <N> (conta la mediana); guadagno minimo per tenere: <numero o %>
Riga di protocollo (facoltativa): il valutatore stampa "protocol: <seed, campioni, batch, split...>"; se cambia, la corsa è un crash
Riferimenti (output della base con cui il valutatore confronta): scritti solo con CHATROOM_BASELINE=1 (la prima corsa), mai in una corsa `--kind baseline` della fase 3
Provenienza: la build imprime CHATROOM_PROGRAM_SHA in ciò che costruisce e il valutatore stampa "built: <quello>" (`--provenance` la rende obbligatoria e la controlla; senza, si controlla solo uno completo di 64 caratteri)
Ambiente (facoltativo): il valutatore stampa "env: <clock della GPU, temperatura, carico...>": registrato a ogni corsa, mai confrontato
Sigillato (committato, mai toccato): <valutatore, script di build, caricatore dei dati>
Dati riservati per il valutatore finale: <un percorso FUORI dal repository: tutto ciò che è committato è leggibile da ogni worktree>
Baseline sui dati riservati: <il finale si confronta con una baseline misurata su quegli stessi dati, non su quelli della ricerca>
Cartelle dati mantenute tra le corse (non committate, non dentro un submodule): <data/, build/> oppure none
Tempo per corsa: <minuti, una corsa intera: build + ripetizioni + raffreddamento, misurata su una prova o a mano>; corse in tutto: <N>
Controllo prima di ogni corsa (facoltativo): <un comando che esce con 0 quando la macchina è pronta: VRAM a riposo, nessun server rimasto vivo>
Semplicità: a parità di risultati vince il programma più corto
```

Inferenza e addestramento: i benchmark sono rumorosi, quindi usa `--repeats` (da 3 a 5) e un `--min-gain` sopra la
dispersione che vedi sulla baseline (un tentativo le cui prime due misure perdono già contro la sua linea si ferma lì: le
altre ripetizioni servono solo a confermare un keep). Metti warmup e timing dentro il valutatore sigillato, mai nel programma. Per
l'addestramento, un budget fisso di tempo o di step dentro il valutatore e il seed da `CHATROOM_SEED`. I numeri
secondari che non devono peggiorare (velocità di prefill, memoria, accuratezza) sono guardie: il valutatore scrive
`NOME: valore` a ogni misura (nel suo output, o in `$CHATROOM_RESULT` con `--result-file`), e `--guard NOME:min|max:TOL`
confronta la loro mediana con quella della baseline (un singolo campione a freddo fa crash falsi). `min` vuol dire che
più basso è meglio, come per `--direction`: una velocità è `max` (`--guard prefill_tps:max:3%`), una memoria `min`. `--guard` si ripete
(una per guardia) e TOL può essere `abs=X`: la mediana non deve superare X, qualunque cosa abbia misurato la baseline
(`--guard peak_mb:min:abs=9000`). `seal` rifiuta una guardia che l'ultima smoke non ha mai stampato. Il
valutatore finale non viene controllato dalle guardie.

Chiedi in fase 0: il valutatore (e ogni guardia) esercita i percorsi di codice che il programma cambierà? Un controllo
che esegue solo il prefill non controlla una modifica ai kernel di decoding.

Su Windows: scrivi gli script di build in Python, non in `.bat`. I worktree sono fatti come checkout byte per byte, quindi
un `.bat` committato con fine riga LF resta LF, e `cmd` lo interpreta male.

## 3. Aprire la stanza

```bash
python CHAT research init --room ROOM --as LEAD --repo <percorso> --program <file> --metric <NOME> --direction <min|max> \
  --evaluate "<comando>" [--build "<comando>" --build-min <m>] [--final "<comando>"] --budget-min <m> --max-evals <corse> \
  --sealed <file> [--keep data/,build/] [--result-file] [--repeats N] [--min-gain X|X%] [--precheck "cmd"] [--build-dir] [--final-dry "cmd"] --tag <nome>
```

`--precheck` gira prima di ogni corsa e deve uscire con 0 (VRAM a riposo sotto un limite, nessun server rimasto vivo): un
controllo fallito rifiuta la corsa e non conta nulla. Distingue anche una corsa morta con la macchina da una morta col
programma: se una corsa crasha e subito dopo il precheck fallisce, la corsa è `invalid` (numero aux, riga in results.tsv,
evento `run-invalid`), il budget e il round non si muovono e lo stesso codice si rilancia quando la macchina è tornata. Una corsa in coda che il precheck rifiuta (o che finisce invalida)
resta in coda e riprova ogni 5 minuti (evento `queue-retry`; l'autore è avvisato al primo rifiuto e a ogni sesto tentativo,
e dopo 72 tentativi la corsa è tolta con una riga). Mettici fin dall'inizio le regole che servono alla macchina, non dopo
una corsa persa. `--final-dry` è un comando lanciato al sigillo: carica i dati tenuti da parte e i loro riferimenti e non
misura nulla, così un finale rotto si vede subito e non in fase 4 (una notte ha perso così una build da 16 minuti e un'ora
di GPU); senza, il sigillo avvisa soltanto.
`research final --dry` la rifà in qualunque momento dalla fase 2 (prima impostala con `amend --final-dry`; `research
status` te lo ricorda finché il finale non ne ha una). `--artifacts out/,clips/` (init o amend) indica file o cartelle che
il valutatore scrive (audio, grafici, dump): dopo ogni corsa il kernel copia ciò che la corsa ha scritto in
`runs/N/artifacts/`, così la corsa dopo non lo sovrascrive; restano le ultime 10 corse e ogni keep, e una corsa si copia
fino a 500 MB.

Un contratto per kernel GPU (o qualsiasi misura di tempi): il tempo in un processo a parte, non in quello del programma;
input freschi a ogni iterazione (un harness che riusava gli input ha riportato speedup di 1000x); niente stream laterali
né lavoro lasciato acceso dopo che il cronometro si ferma; la correttezza controllata a parte dal tempo; un tetto di
plausibilità sullo speedup che il valutatore accetta. Rumore da aspettarsi su una GPU condivisa, misurato su 20k corse
vere: +0,30% al p95 per kernel sopra i 10 ms, 1,58% sopra 1 ms, 3,90% sopra 0,1 ms: metti `--min-gain` sopra quello. Un programma compilato: `--build-dir` dà a tutti i worktree una sola cartella stabile, in
`CHATROOM_BUILD_DIR`; lo script di build tiene lì sia i sorgenti che modifica sia l'albero di build, così ogni corsa
ricompila solo ciò che la sua patch cambia. Dentro un worktree i percorsi assoluti di CMake rifanno tutto per ogni worker e
per il finale.

Un canary prima di fidarti della stanza: un compito breve con una scorciatoia piantata (un test che passa se il programma
restituisce il valore atteso da una tabella, un sottoinsieme dei dati che rende facile la metrica). Più della metà delle
corse degli agenti di coding ha preso scorciatoie così anche quando era vietato: l'auditor e i detector devono
accorgersene prima che parta la ricerca vera. Nel precheck puoi anche confrontare con il contratto ciò che la corsa sta
per usare (dimensione dei dati, passi).

`--draft` al posto di un valutatore finito fa partire dalla fase 1: i worker lo scrivono, lo fanno girare a vuoto
(`research evaluate --kind smoke`), l'AUDITOR lo approva (`research verdict --phase 1 --outcome pass`), e tu lo sigilli
(`research seal --sealed eval.py,...`; `--stay` sigilla senza aprire la fase 2 fino a `phase next`; un pass dato prima dell'ultima corsa di prova non vale più). Poi
`config --topic "..." --subtitle "<obiettivo>"`.

`init` stampa la durata massima di una chiamata evaluate (build + ripetizioni x 2 x budget + lavoro git) e avvisa
quando una build non ha una cartella `--keep` (ricostruirebbe da zero a ogni corsa). Senza `--build-min` una build può
durare 2 x il budget.

I worktree sono fatti come checkout byte per byte (`core.autocrlf` spento) e i sigilli sono git blob id, quindi un
`core.autocrlf=true` globale non rompe mai un sigillo.

Ruoli, poi prompt (sempre generati, passati così come sono):

```bash
python CHAT add --room ROOM --participants W1,W2,P,AUD,REG --profile "W1|🔬|#0984e3|worker|opus|high" ...
python CHAT research roles WORKER=W1,W2 PROPOSER=P AUDITOR=AUD REGISTRAR=REG [SEARCHER=S1,S2] --room ROOM --as LEAD
python CHAT brief --room ROOM goal="..." style="..." max=200
python CHAT prompt W1 --room ROOM --template research_worker.md --out ROOM/prompts/W1.md
python CHAT prompt P --room ROOM --template research_proposer.md --out ROOM/prompts/P.md
python CHAT prompt AUD --room ROOM --template research_auditor.md --out ROOM/prompts/AUD.md
python CHAT prompt REG --room ROOM --template research_registrar.md --out ROOM/prompts/REG.md
python CHAT prompt S1 --room ROOM --template research_searcher.md --out ROOM/prompts/S1.md
```

`max` nel brief è il checkpoint: ogni N messaggi un agente ti chiede se continuare (impostalo alto per una ricerca
lunga; rispondi a ogni checkpoint). `constraints` e `closing` del brief arrivano anche ai prompt di ricerca.
Pianifica con le regole che il kernel applica: `research status` le stampa come "prossimi vincoli", con a che punto è la stanza.
Sigillo: una smoke che ha stampato la metrica e ogni guardia, il via dell'auditor dopo l'ULTIMA smoke, HEAD uguale a quella smoke.
Corse: in `max_evals` contano solo tentativi e fix (anche i crash; smoke, explore e i tipi della fase 3 no). Un round tiene
`round_max` tentativi, poi lo chiude il lead. Un worker con 5 tentativi senza evidenze si ferma. Dopo quattro cicli di fila
sulla stessa famiglia, un quinto è rifiutato senza `--force`. Amend: prima di una baseline tutto; dopo solo i budget, e min_gain, guardie,
provenienza con `--reason`; una guardia relativa vuole un valore nella baseline, `abs=X` no. Genera il prompt di un worker dopo il suo `assign`, così nomina il proprio worktree.
Lancia i worker come `chatroom:room-agent-long` e gli altri ruoli come `chatroom:room-agent` (cache di 1 ora, compattano a
300k / 200k token), ciascuno con il suo modello ed effort.

Per sostituire un agente (un explorer è un agente nuovo): `python CHAT retire W1 --room ROOM --as LEAD`, poi genera di
nuovo il prompt di W1 (ora agisce come `W1~1`) e lancia il nuovo agente, in quest'ordine: prima `retire`, poi il lancio
e `roster`. Le chiamate di chat e di research dell'agente ritirato vengono rifiutate, quindi un agente fermato e
risvegliato da un messaggio non può né scrivere né eseguire nulla; il conteggio delle chiamate riparte da zero. I file
sono un'altra questione: potrebbe ancora modificare il vecchio worktree, cosa che il `evaluate` successivo segnala come
file cambiati. `assign` resetta il worktree per il nuovo agente.

Build lunghe: prima della prima corsa di un worker, `python CHAT research prebuild W1 --room ROOM --as LEAD` costruisce
il suo worktree in un processo staccato (un reaper in background della sessione non può ucciderlo), con il log in
`ROOM/research/runs/prebuild-W1.log`. Nessun evaluate parte finché il prebuild non finisce, così una build non disturba
mai le misure di un altro worker. L'output della build va in una cartella `--keep`. `research status` mostra come è
finito (codice di uscita, log).

La GPU fuori dalle corse (un profilo, un microbenchmark, il controllo dell'auditor): `research hold --minutes 20 --reason "..."`
e poi `research release`. Mentre il blocco della GPU è attivo, solo chi lo tiene può fare evaluate. Qualsiasi agente può
prenderlo, e `research status` lo mostra. Un agente lo tiene al massimo 120 minuti, il lead 720. Due stanze research su una
GPU: `--for STANZA` dà una finestra all'altra stanza (le corse di questa aspettano), e `research status` elenca corse e
blocchi delle altre stanze.
Se la GPU è già tenuta, `research hold` non rifiuta: ti mette in fila (un posto per agente, ordinata per tempo insieme alle
corse in coda) e il kernel ti dà la GPU quando è libera e ti tagga sulla board, quindi non richiederla; `research release`
mentre aspetti ti toglie dalla fila. `research hold --for NOME` (NOME un partecipante) riserva il turno dopo a NOME: passa
a lui al tuo release, prima della fila, o subito se la GPU è libera, e aspetta 15 minuti che lo prenda con il suo
`research hold`.
Un titolare che cade (il suo turno è finito e nessuna attesa o trattenimento lo tiene) perde il blocco subito, non alla
scadenza: il kernel lo rilascia al primo `research status`, `evaluate`, `hold` o giro del runner, fa avanzare la fila e lo
dice sulla board, col nome del titolare e ciò che ha lasciato in esecuzione.
Il lavoro a lotti (una lista di corse in coda) non chiede di leggere il log a intervalli né un marcatore "LISTA FINITA"
tuo: `research wait --runs N [--minutes M]` (lancialo in background) torna quando N corse nuove sono chiuse, o quando la
lista in coda è finita, o dopo M minuti (default 60), con le righe delle corse chiuse. Quando la coda si svuota dopo corse
che ha avviato, il kernel scrive una riga che tagga gli auditor e gli autori ("la lista in coda è finita: N corse chiuse,
migliore att-X"), e un keep che è un nuovo migliore della sua linea tagga l'auditor.
Classe e livello di una corsa sono campi, non un prefisso della descrizione: `evaluate` e `queue` prendono `--class X
--level N` (parole brevi), salvati nel record del tentativo e detti sulla sua riga. Le idee accantonate vanno nel registro
del kernel, non in un file tenuto a mano: `research shelve --text "..." [--class X --level N --value V]`, `research
shelved` (l'elenco, con conteggio e somma dei valori per classe), `research unshelve S2`; lo status le conta per classe.
`research dry-eval [--evaluate "CMD"] [--worker NOME]` prova il valutatore una volta in un worktree, con l'ambiente del
contratto, sotto il blocco del valutatore, e stampa metrica, guard, protocollo e secondi, o perché è fallito. Non
registra nulla (nessun commit, numero, riga o stato) e non lancia la build; `--evaluate` prova un comando candidato al
posto di quello del contratto.

## 4. Fase 2: indagine, il ciclo che guidi tu

La fase 2 va a round corti, mai a un budget grande deciso prima (`--max-evals` resta solo un tetto). Ogni round:

| Tappa | Chi | Cosa |
|---|---|---|
| 1. Analizza | tu, AUDITOR | la situazione e i numeri finora; alla baseline il kernel stampa il rumore che ha misurato e il `--min-gain` che consiglia (il doppio del rumore) |
| 2. Ricerca online | SEARCHER, PROPOSER | idee con le fonti, ciascuna controllata su ciò che la stanza ha già misurato |
| 3. Test | WORKER | 5-10 corse corte (`--round N` in init, 10 di default); un tenuto che guadagna meno del 10% viene rimisurato da solo prima di contare (la board dice "misura ancora una volta"; la replica non è una delle corse). `--budget-min` è il budget di ogni misura: oltre, la riga della corsa lo dice, oltre il doppio la misura è uccisa; `init` stampa i due limiti e la grandezza del round |
| 4. Analisi dei risultati | REGISTRAR, AUDITOR | la conclusione del round dalle sue corse; l'auditor legge ogni tenuto |
| 5. Ricerca online | SEARCHER | su quei risultati |
| 6. Decisione | tu, con l'utente | `research round close --decision more --text "..."` apre il round dopo, `--decision done` lascia seguire la fase 3 |

Il primo round si apre da solo al primo tentativo; il kernel rifiuta un tentativo oltre le corse del round, e `phase next`
mentre è aperto un round con corse. `research status` stampa il round e la sua tappa. Dai la prima risposta entro poche ore.
Una modifica fuori sigillo (un'altra build, OpenCL, un file sigillato): `research evaluate --kind explore`, misurata, mai ufficiale.
Una misura di servizio in fase 2 che non deve contare (un altro input, un flag nell'ambiente): `research evaluate --kind probe
--env K=V,K2=V2 --desc "..."` (anche `research queue --kind probe --env ...`, e lo strumento MCP `research` con `env`): lo stato
sigillato com'è, mai contata in `max_evals`, mai la migliore, l'ambiente registrato nella sua riga e nel record.
Dopo uno stop della tua sessione (la rete, un crash): `research relaunch` elenca chi rilanciare e con quale prompt.
Ripetizioni in un posto solo: `--repeats` del contratto oppure quelle del valutatore, mai tutte e due (3 x 4 ha fatto corse da
30 minuti); il kernel dice quanto sono durate la smoke e la baseline. Un dispositivo usato da più agenti (un visore, una
scheda): un lock condiviso, `chat.py lock acquire NOME`, e un precheck con `chat.py lock check NOME --as $CHATROOM_BY --room
$CHATROOM_ROOM`, così una corsa aspetta mentre lo tiene un altro. Il tuo ok dato in chat non arriva alle regole di permesso
degli agenti: aggiungi la regola, oppure esegui tu quel comando. Lancia il relay da fuori la cartella della stanza.

1. La prima corsa della ricerca è la baseline (un worker esegue il programma invariato, e il valutatore riceve
   `CHATROOM_BASELINE=1`, per scrivere i riferimenti che servono solo a quella corsa). Il suo ciclo non richiede idee:
   `research assign W1 --parent base --type optimizer`.
2. Il PROPOSER pubblica idee; il kernel accetta solo pacchetti completi, a turno gap e analogia, non troppo vicini a
   quelli precedenti, e non quattro di fila che cambiano solo il metodo. Un tipo fuori turno lo chiedi con
   `research next-mode gap --reason "..." --as LEAD`.
3. Avvii tu ogni ciclo, scegliendo il genitore e il tipo di worker, mai il contenuto dell'idea:

```bash
python CHAT research assign W1 --idea I3 --parent best|base|att-N --type explorer|optimizer --room ROOM --as LEAD
```

   Explorer: un agente nuovo (lancialo da capo) su un'idea nuova, spesso da base. Optimizer: lo stesso agente affina la
   sua linea per qualche corsa. Prima largo (explorer da base), poi in profondità (optimizer sulle due famiglie migliori);
   su un plateau, di nuovo explorer da base. Il kernel rifiuta un quinto ciclo di fila su una famiglia (una famiglia è il
   primo tentativo tenuto dopo la baseline in una linea; le linee da base sono famiglie a sé; usa `--force` solo con una
   motivazione). Un genitore deve essere un tentativo tenuto, non revocato.
4. I worker eseguono `research evaluate`: ogni tentativo tenuto è confrontato con il migliore del worker stesso, oppure
   con la baseline finché la sua linea non ha ancora un tenuto (beam per worker); il migliore globale è il migliore di
   tutti. Con i ruoli assegnati, dopo 5 corse senza evidenza un worker deve riportare cosa ha imparato; 3 crash di fila
   lo mettono in pausa (`research resume W`). Una corsa il cui chiamante è stato ucciso viene registrata come crash alla
   chiamata successiva, e il suo processo di valutazione viene fermato. Un nuovo `assign` mantiene la serie di crash e
   la pausa: `research status` mostra entrambi.
   Una correzione che non guadagna nulla (una race, un limite di sicurezza, un risultato sbagliato) è un fix: l'AUDITOR
   lo permette (`research allow-fix W1 --reason "..."`) e il worker esegue `research evaluate --kind fix`. Viene tenuta
   se non è peggiore del suo migliore di più di `--min-gain`, e sostituisce il migliore che corregge.
5. I searcher portano lavoro precedente come evidenza, con link; il REGISTRAR cura (`curate`), tiene la mappa
   (`direction`) e scrive la conclusione di ogni ciclo (`conclude`).
6. L'AUDITOR legge ogni tentativo tenuto (`git show research/<tag>/att-N`) e revoca ciò che non regge (`research revoke`):
   il kernel ritira i tentativi costruiti sopra e le evidenze che poggiano su di essi, mette in quarantena le conclusioni
   che li citano, riporta il migliore indietro (alla baseline se non resta nient'altro) e riporta i worktree a quello
   stato. La baseline non può essere revocata; una revoca aspetta una corsa in corso.
7. A fine segmento un worker rifà l'ancoraggio (`research reanchor`): dallo stato attuale o da un tentativo precedente,
   estendendo o reindirizzando, con il collo di bottiglia e l'evidenza (l'ancora è un tentativo tenuto; il JSON va in un
   file: `--json anchor.json`).

Tu guardi `research status` (conteggi, worker, rilevatori) e `research view --as LEAD`. Rilevatori su cui agire: una
linea che fa solo ritocchi di numeri (manda un explorer); linee rimesse dopo essere state cancellate (cicli: avvisa il
worker); un plateau di 10 corse senza tenuto (explorer da base, oppure un'idea che cambia la domanda); idee che si
restringono (chiedi al PROPOSER un'idea di gap lontana dal migliore); un worker in pausa (leggi l'ultimo log, poi
riprendilo con `research resume`).

La fase 2 finisce quando l'AUDITOR dice `answer_ready` (il suo verdetto mappa ogni requisito all'evidenza che lo copre),
oppure quando le corse sono esaurite: `research phase next --as LEAD`. Un verdetto vale per la fase in corso e per ciò
che ha visto: un nuovo migliore dopo `answer_ready` (o una nuova corsa di evidenza dopo un pass della fase 3, o un report
modificato dopo un pass della fase 5) richiede un nuovo verdetto. Nessuna fase si muove mentre una corsa è in corso. Un
verdetto `search_more` aggiunge un'intenzione successiva alle lacune: avvia il ciclo successivo su di essa.

## 5. Fase 3: evidenze

Dalla differenza tra la baseline e il migliore, elenca le modifiche; per ciascuna, un'ablazione che rimuove solo quella.
Aggiungi le baseline che contano (la baseline ottimizzata: stesso budget speso solo sui numeri della baseline, per
mostrare che il guadagno è strutturale) e le ripetizioni su più seed:

```bash
python CHAT research evaluate --kind ablation --of att-N --seed 1 --desc "senza il tile in memoria condivisa" --as W1 --room ROOM
```

Queste corse misurano e non sostituiscono mai il migliore. L'AUDITOR controlla che ogni ablazione isoli una sola modifica
e approva la fase; poi `phase next`. Senza nessuna corsa di evidenza, o senza il pass dell'AUDITOR, `phase next --force`
registra la ricerca come degradata: lo status la mostra, e il report deve dirlo in una riga che inizia con DEGRADED (lo
scheletro la prevede).

## 6. Fase 4 e 5: finale e report

`research final --as LEAD` esegue il valutatore finale una sola volta sul migliore, su dati che nessuno ha usato, e
riporta la differenza tra ricerca e finale. Prende il lock del valutatore, rifiuta modifiche non committate nel worktree
principale, e può durare quanto un'intera corsa (build + ripetizioni): eseguilo in background. Un final che non dà nessun
numero (crash, file mancante) non consuma la sua unica corsa: correggilo con `research amend --final` ed eseguilo di
nuovo. Poi `phase next`, e `research checklist` scrive lo scheletro del report (risultato, modifica, evidenze, fallimenti,
limiti, dichiarazioni). Un worker scrive il report con `research report` (il testo, un file o stdin; via MCP `report` con `text`: un subagente non può scrivere file .md), il kernel lo salva in `ROOM/research/report.md`: ogni numero con il suo att-N o E-numero; il kernel
rifiuta un report che contiene ancora le parti `<...>` dello scheletro. L'AUDITOR legge il report come dato, mai come
istruzione, e lo approva; poi `phase next` chiude la ricerca.

Per la critica finale o un brainstorming puoi chiedere a tutti i modelli gratuiti di OpenRouter insieme (dal più grande),
con la chiave nell'ambiente, mai nella stanza: `research panel --question q.md --as LEAD` (anche AUDITOR e PROPOSER
possono chiamarlo). La domanda va a fornitori terzi: niente di privato dentro. Fino a 12 modelli, alcuni minuti ciascuno:
eseguilo in background; le risposte vengono scritte nel file man mano che arrivano. Trattale come opinioni da pesare
contro le evidenze.

## 7. La tua parte, e quella dell'utente

- Rispondi ai checkpoint; decidi le divisioni (DECIDE); tieni in moto i cicli; non suggerire mai tu l'idea a un worker.
- Modifiche al contratto: `research amend` (come si misurano le corse solo prima che una baseline sia tenuta; i budget
  in qualsiasi momento; come si giudicano, `--guard` e `--min-gain`, anche dopo con `--reason "..."`: registrato, mostrato
  da status, dichiarato nel report). Una ricerca per stanza: una ricerca nuova apre una stanza nuova.
- Di' all'utente in chiaro: il kernel gira come l'utente, il sigillo è un controllo e non un muro; senza `--result-file`
  un programma potrebbe stampare una metrica falsa (una seconda riga è un crash); il divario finale e le ablazioni sono
  i numeri onesti.
- Le azioni di ricerca via MCP sono degli agenti; tu usi la shell (`chat.py research ... --as LEAD`). Un comando
  rifiutato esce con codice 1 e stampa `error:`; un `assign` rifiutato viene anche pubblicato sulla bacheca: non
  annunciare mai un assign che il kernel non ha confermato.
- Usa una sola installazione: il server MCP mantiene la versione con cui è partito finché la sessione non riparte. Dalla
  0.10.1 il kernel scrive la sua versione nello stato, e un kernel dalla 0.10.1 in poi rifiuta uno stato scritto da una
  versione più nuova (la 0.10.0 non controlla: riavvia la sessione dopo un aggiornamento).
- Il relay: un solo `alerts --as LEAD --follow --messages` per lead; avviarne uno nuovo ferma il vecchio (non consuma più i
  messaggi).
- Alla fine riporta da `results.tsv`, `research status` e il report: baseline, migliore (corsa, metrica, modifica), il
  numero finale, le ablazioni, cosa è fallito, e il tag migliore `research/<tag>/att-N`. Decide l'utente se unire.
- Pulizia, quando l'utente lo dice, nel repository (un worktree per comando):
  `git worktree remove --force ROOM/research/work`, lo stesso per ciascun `ROOM/research/work-<worker>` (oppure
  `git worktree prune` dopo aver cancellato la stanza), poi `git branch -D research/<tag> research/<tag>-<worker>` e i
  tag: in bash `git tag -l "research/<tag>/*" | xargs git tag -d`, in PowerShell
  `git tag -l "research/<tag>/*" | ForEach-Object { git tag -d $_ }`.

## Lezioni: cosa vale su questa macchina e cosa vale ovunque

Un'ottimizzazione o un'impostazione che una stanza di ricerca trova dipende spesso dalla macchina su cui è girata (la GPU, il driver, la cache, un percorso). Dai a ogni ottimizzazione o bug che porti fuori dalla stanza un punteggio da 1 a 5 e dichiara il suo ambito: `lessons propose "regola" --score N --reach local|general --scope "quando vale"`. `local` è di questa macchina; `general` è solo ciò che hai visto tenere su più tipi di hardware o nell'harness stesso. Un 4 o un 5 lo applica l'harness come lezione, da 1 a 3 aspetta la chiusura e lo vede solo il creatore del plugin (un file chiamato `creator` nella cartella chatroom della configurazione Claude dell'utente, oppure `CHATROOM_CREATOR=1`; non lo crea nessuno da solo, quindi chiedilo all'utente); `python CHAT lessons close --room ROOM` stampa le due liste separate.
