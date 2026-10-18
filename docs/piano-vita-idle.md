# Piano: vita in idle (combinazione C, con l'interruttore)

Dal documento `docs/idee-idle-vista.md`, combinazione C scelta dall'utente il 18/10/2026, con due aggiunte sue: l'agente
può decidere dove andare, e la mappa ASCII mostra zone e posti di tutti, utente compreso.

## Regole

- Interruttore per utente in `~/.claude/chatroom/settings.json` (`idle_life`), spento di default. Si accende dal pannello
  🛋 del viewer. Mai nelle stanze research, mai nelle visite agli amici.
- Nessun risveglio in più: il modello vede e decide solo nei risvegli che avvengono comunque.
- Uno scrittore solo: il server (chat.py). Il viewer legge e disegna.

## Pezzi

1. `office-layout.js`: `idleSpots(layout, placed, floor)` elenca i posti per le pause (sedute e posti in piedi della
   caffetteria e della lounge, `coffee`; la sala comune, `common`, solo per chi ci può andare; niente posti dei giochi),
   con id stabili, zona e raggiungibilità dalla piazza; più una griglia 24x14 delle zone. Usata dal tool node e
   dall'ufficio, così server e viewer hanno la stessa lista.
2. `tools/idle_spots.mjs`: genera `scripts/idle_spots.json` dalla pianta di default. Il viewer, quando l'interruttore è
   acceso, pubblica la lista del suo ufficio (mobili dell'utente) in `~/.claude/chatroom/idle_spots.json`; chat.py usa
   quella se c'è, altrimenti quella di default.
3. `chat.py`:
   - `idle_places(room, t)`: per ogni agente in idle, il posto della fascia di 20 minuti. Funzione pura di
     (stanza, nome, fascia) con un carattere fisso per agente (zona preferita); due agenti mai sullo stesso posto. Se
     l'agente ha scelto (`go`), vale la sua scelta per 40 minuti.
   - `go POSTO --as NOME`: l'agente sceglie (numero del posto o nome della zona); il server controlla interruttore,
     posto esistente e libero.
   - `look --as NOME [--map]`: una riga (dove sei, chi è vicino, dove sono gli altri e l'utente, posti liberi); con
     `--map` la mappa 24x14 con zone, posti liberi, persone e l'utente (`@`).
   - Diario al risveglio: in `read` e `wait`, una riga "mentre dormivi: ..." la prima volta dopo una pausa di almeno
     10 minuti, ricostruita rigiocando le fasce.
   - `GET /idle.json` (posti per l'ufficio), `POST /idle_me` (posizione dell'utente, al massimo ogni 5 s, solo quando si
     muove), `POST /idle_spots` (lista dei posti dell'ufficio dell'utente), azione `idle_life` nel pannello 🛋.
4. `office.js` / `office-ui.js`: con l'interruttore acceso, gli agenti in idle vanno al posto deciso dal server
   (`/idle.json` ogni 10 s) invece che al posto a caso; interruttore nel pannello 🛋; posizione dell'utente inviata.
5. Testi nel catalogo (it/en); test python (determinismo, go, look, mappa, diario, interruttore spento, research spenta)
   e node (lista dei posti raggiungibili, stessa lista in office e tool).

## Fuori

- Misura A/B: si fa a mano dopo, prima di consigliarla ad altri.
- Memoria da compagno (idea 14): più avanti.
