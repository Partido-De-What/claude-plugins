# Agenti in idle che scelgono dove andare (con o senza "vista")

Idee raccolte nella stanza Officina 0.12 (T9), 17/10/2026: note di FABBRO, ALCHIMISTA, ASTRONOMO, OCCHIO, poi un giro
di critica. Niente è implementato. Vincoli di Adrian: funzione sperimentale, interruttore per utente, spento di default,
solo stanza normale (mai research), solo azioni non interattive (sedie, caffè, divano, camminare; niente giochi), e
nessun costo che intasi il contesto o rallenti gli agenti.

## Il fatto che decide quasi tutto

Un agente in idle è fermo in `chat_wait`: in quel momento non c'è nessun modello che gira. Ogni "scelta" fatta dal
modello vuol dire svegliarlo, e svegliarlo costa la rilettura del suo contesto (migliaia di token), non i 40-50 token
della domanda. Quindi:

- le scelte mentre dorme le fa il codice (deterministico), non il modello;
- il modello vede qualcosa solo nel risveglio che avviene comunque (un tag, un messaggio dell'utente o del lead), mai
  con un risveglio in più fatto apposta.

## Le idee

| # | Idea | Costo in token | Pro | Contro |
|---|------|----------------|-----|--------|
| 1 | Scelta deterministica: la figura sceglie da una tabella pesata di posti non interattivi (caffè, divano, finestra, guardare il biliardo, TV) | 0 | Nessun modello, nessun costo, sempre attiva | Non è "libero arbitrio" del modello: è carattere scritto nel codice |
| 2 | Diario al risveglio: "mentre dormivi: 20 min al caffè con ALFA, poi divano" (3-5 voci) | ~40, solo al risveglio | Continuità e base per una memoria da compagno | Se l'agente lo prende per un suo ricordo, può citarlo come fatto |
| 3 | Vista in testo: una riga generata dalla pianta vera ("sei sul divano; vicino: TV accesa, ALFA parla, biliardo libero"), solo se è cambiato qualcosa | ~50, solo al risveglio | 10-30 volte meno di un'immagine, deterministica, testabile | Dice poco dello spazio |
| 4 | Mappa ASCII dall'alto (24x14 caratteri) con persone come lettere | 150-200 | Spaziale: si vedono i posti liberi | Costa più della riga; il modello deve interpretarla |
| 5 | Immagine piccola dall'alto a fine azione (192x120 px, agente cerchiato) | ~30 per immagine (640x400 = ~340) | "Vede" davvero | Il costo vero è che resta nel contesto per tutti i turni dopo; a 192x120 si vede poco; si rompe in silenzio se il canvas non disegna (vista nera) |
| 6 | Frequenza: solo su evento, o con backoff 3, 5, 10, 20 min; tetto di N azioni all'ora; zero azioni se il viewer è chiuso | riduce tutto il resto | Il costo da periodico diventa quasi nullo | Con il viewer chiuso la "vita" si ferma (vedi 11) |
| 7 | Seme e casualità a tre livelli: seme fisso = personalità (preferenze), seme del giorno = variazione, caso solo sul 10% delle scelte | 0 | Ogni agente ha un carattere riconoscibile, ma non è sempre uguale | Il 10% di caso puro rompe la ripetibilità: anche quello va preso dal seme (vedi critica) |
| 8 | Modello come arbitro raro (Haiku, ~120 token in) che sceglie fra 4-6 opzioni ogni 15-20 min | ~130 per scelta | Scelte più sensate | RITIRATA: svegliare un agente in idle rilegge tutto il suo contesto |
| 8b | Menu a risveglio: ogni 30 min l'agente riceve 4 opzioni numerate e risponde con una cifra | ~40 in, 2 out (sulla carta) | Scelta "vera" del modello | RITIRATA per lo stesso motivo: il risveglio costa il contesto intero |
| 9 | Stato scritto solo dal server (lock e scrittura atomica come il kernel research), ricostruibile da (seme, fascia di 20 min) | 0 | Niente duplicati, niente stato perso | Serve un pezzo di server in più |
| 10 | Vista solo con render attivo: niente immagini in idle | 0 | Evita la vista nera e il costo | Nessuna immagine automatica |
| 11 | Funzione pura `f(seme, fascia)`: il posto di ogni fascia si calcola, non si salva; il diario al risveglio si ricostruisce rigiocando le fasce dormite | 0 | Uguale con 0, 1 o 2 viewer aperti; nessuna scrittura doppia | I posti devono essere quelli fissi della pianta |
| 12 | `chat.py look`: un comando che l'agente usa al risveglio per avere la riga dell'idea 3 | ~50 a chiamata | Nessun polling dell'agente; la vista la chiede lui | Un comando in più nel prompt |
| 13 | `idle_spots.json`: un tool node genera dai posti della pianta (`resolve()`) la lista dei posti raggiungibili dalla piazza, e un test la ricontrolla; viewer e chat.py leggono la stessa lista | 0 | Python non può eseguire il codice della pianta: così entrambi sanno quali posti sono validi | Va rigenerata se cambia la pianta |
| 14 | Memoria da compagno: un file per agente di ~200 byte (ultimi 5 posti, umore 0-1, incontri), mai in chat.jsonl, separato dai log del kernel | 0, finché l'agente non lo apre | Base per lo "stato come memoria" di un companion | Va deciso chi lo legge e quando |

## Critiche emerse (tutte accolte)

1. Non deve scrivere il viewer. Con due viewer aperti si scriverebbe due volte (è lo stesso difetto del messaggio
   doppio, misurato: 42 righe contro 41), con nessun viewer non si scriverebbe niente. Scrittore unico: il server,
   oppure nessuno (idea 11).
2. Il seme deve includere la stanza: `hash(stanza + nome)`. Nella stessa sessione "OPERAIO1" esiste in due stanze e
   farebbe le stesse scelte alla stessa ora.
3. Il posto si sceglie tra quelli raggiungibili adesso: una scrivania aggiunta dopo può chiudere la strada a un posto
   scelto un'ora prima (è successo davvero in questo cantiere).
4. La riga dell'idea 3 al massimo una per risveglio, solo se è cambiato qualcosa e se l'agente dormiva da più di N
   minuti; strettamente fattuale e marcata come generata dal viewer, altrimenti l'agente la scambia per un suo ricordo.
5. Le immagini: default no. Il costo non è il singolo file ma il contesto che si porta dietro; e una vista che dipende
   dal disegno si rompe in silenzio (in questo cantiere il canvas è rimasto nero più volte con il pannello nascosto).
6. Interruttore per utente, non per stanza: in `settings.json` (esiste già), spento di default, mai in research, mai
   nelle visite agli amici.
7. Misurare prima di accendere: A/B su 5 compiti uguali con e senza la riga, contando token e tempo.

## Seme e casualità: cosa cambiano davvero sullo stesso agente

- Il seme di queste idee decide solo dove va la figura. Non tocca il campionamento del modello: Claude Code non espone un
  seme per il modello, e lo stesso agente con lo stesso prompt dà già risposte diverse da una volta all'altra.
- Un seme fisso per agente dà alla figura un carattere stabile (ALFA va sempre volentieri alla finestra), e rende tutto
  ripetibile e testabile: stessa stanza, stesso nome, stessa ora = stesso posto.
- L'effetto sul modello arriva solo se gli si fa leggere qualcosa (diario, riga, mappa, immagine). Quello che legge entra
  nel suo contesto e cambia ciò che scrive dopo: un agente che "sa" di aver passato un'ora al caffè con BETA può
  nominarlo, o dare più peso a BETA. È qui che serve la misura A/B (critica 7): se la riga peggiora token, tempo o
  qualità dei compiti, resta spenta.
- Per un companion questo è proprio l'effetto voluto (continuità, ricordi). Per un agente di lavoro è rumore. Per questo
  l'interruttore è per utente e spento di default.

## Combinazioni

| Combinazione | Cosa contiene | Costo | Per chi |
|---|---|---|---|
| A | 1 + 2 + 7 + 11 (scelta deterministica pura, diario ricostruito, carattere dal seme) | ~40 token solo al risveglio | Default della funzione sperimentale |
| B | A + 3 + 12 (riga di vista al risveglio, `chat.py look`) | ~50-90 token solo al risveglio | Chi vuole che l'agente "sappia dove si trova" |
| C | B + 4 su richiesta (mappa ASCII con un comando "guarda") | +150-200 quando la chiede | Prove, debug, curiosità |
| D | C + 14 (memoria da compagno) | 0 finché non la legge | Il companion di cui parlerete dopo |
| E | D + 5 su richiesta esplicita dell'utente (immagine) | ~30-340 per immagine | Solo a mano, mai automatica |

Raccomandazione della stanza (concorde): A + B con la funzione pura (11), lo stato solo dal server (9),
`idle_spots.json` (13), seme con la stanza; interruttore per utente, spento di default, solo stanza normale; prima di
renderlo attivabile, la misura A/B.
