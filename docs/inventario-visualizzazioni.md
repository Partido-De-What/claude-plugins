# Inventario delle funzioni da visualizzare (chatroom 0.8.18 - 0.12)

Fase 3 del piano 0.12. Fonte: i messaggi dei commit da 0.8.18 a 0.11.2 e il codice del worktree `office-lab`. Colonne:
"Oggi nel 3D" dice se la stanza normale (ufficio voxel) lo mostra già, con il file e la riga che lo prova; "Proposta" è la
visualizzazione; "Stato" dice se si costruisce in 0.12 (modulo `office-viz.js`, agganciato da `office.js`) o perché no.
Le funzioni della CLI senza niente di visivo (help, MCP, migrazioni, prestazioni) sono in fondo.

## Già visibili oggi (nessun lavoro)

| Versione | Funzione | Dove si vede |
|---|---|---|
| 0.8.19, 0.8.22, 0.8.25 | armi voxel e zombie del paintball | modalità paintball (`office-paintball.js`, `office-zombies.js`) |
| 0.8.20, 0.8.24, 0.8.27 | cabinato arcade, giochi NES per due, invito | cabinato in sala comune, riga d'invito (`office-arcade.js`) |
| 0.8.26 | due blocchi di scrivanie, sala regia | pianta (`office-layout.js`) |
| 0.8.28 | arena, finestra GitHub, movimenti con un senso (PLAN alla lavagna, tag alla scrivania) | `office-arena.js`, `office-github.js`, `office.js` (visite) |
| 0.8.29 | timeline sopra ogni testa, rack dei processi, insegne neon | `office-timeline.js`, `office-rack.js`, `office-signs.js` |
| 0.8.14, 0.8.35, 0.8.36 | TV con telecomando, cinema, mixer dei volumi | `office-tv.js` |
| 0.8.18 | percentuale dello status | etichetta sopra la testa (`office.js` tag, `pct`) |
| 0.8.37 | prestito di un pezzo (task help): 🤝 su lavagna e sull'aiutante | `office.js:1287`, `office.js:1744` |
| 0.8.37 | il lead non è l'utente (occhiali, colore, ruolo) | etichette e figure |
| 0.8.39 | fino a tre stanze nello stesso ufficio (tre tavoli dei lead) | `office.js`, `office-layout.js` (LEAD3_ITEMS) |
| 0.8.37 | comandi rapidi dalla scrivania | palette (`commands.json`) |
| 0.9.0 | bacheca dei task: da fare, in corso, fatto, ultimo fatto | lavagna (`drawBoards`, `office.js`) |
| stati | attesa, stallo, in pausa, voto, "taggato" | bandierine sull'etichetta (`office.js:1738-1747`) |

## Da costruire (stanza normale)

| Versione | Funzione | Oggi nel 3D | Proposta | Stato |
|---|---|---|---|---|
| 0.8.17, 0.10.1, 0.11.1 | CHECK: stallo, tutti fermi, tag senza risposta, 100% senza prove, task chiusi senza artefatto, budget | no (solo CLI `check` e avvisi del relay) | pannello sulla parete della sala controllo con i CHECK attivi, colorati per gravità (rosso errore, ambra attenzione, grigio informazione), clic = apre il messaggio | 0.12, serve `/check.json` (da `failures()`) |
| 0.11.1 | `post` avvisa dei messaggi per te non letti | no | badge `!!! #N` sull'etichetta dell'agente che ha postato senza leggere un messaggio per lui | 0.12, serve il campo `missed` nel messaggio (`cmd_post`) |
| 0.8.21 | tag e risposte | solo nel viewer 2D | linea luminosa tra chi tagga e il taggato; verde quando il taggato risponde (messaggio, status, riga di bacheca) | 0.12, dati già nel client |
| 0.11.1 | CHECK "tutti fermi" (una volta per episodio) | no | lampada sul tavolo della sala regia, accesa finché tutti gli agenti sono in pausa | 0.12, dati già nel client |
| 0.10.1 | budget di chiamate per agente (`budget_calls`) | no | barra sulla scrivania di ogni agente: verde sotto il 60%, ambra fino al 100%, rossa oltre | 0.12, serve `calls` in `/check.json` |
| 0.8.37 | pacchetti (task help), restituzione, soccorso tra stanze | solo 🤝 | un pacco che viaggia dalla scrivania di chi presta a quella di chi aiuta, finché non è accettato; ambra se non accettato, verde se accettato | 0.12, dati nella bacheca (`lender`, `owner`, `accepted`) |
| 0.11.0 | lingua della stanza (it/en) | solo nei testi | bandierina sull'insegna e clic per cambiare lingua (POST `config` come il viewer) | 0.12 |
| 0.8.21 | scoperte (`--finding`) | solo viewer 2D (pillola gialla) | 💡 sull'etichetta per 60 s | 0.12, dati nel client |

## Candidati scartati o rimandati

| Funzione | Perché no |
|---|---|
| decisioni (`task decide`) sulla lavagna | la lavagna ha già l'ultimo fatto; una riga in più la affolla. Rimandato. |
| quaderno (`notebook`) | file dell'agente, nessuna dimensione spaziale |
| prestazioni 0.8.40/0.8.41, MCP, AGENTS.md, migrazioni, i18n degli strumenti | niente di visivo |
| `read --focus`, relay, alerts | è lettura, non stato dell'ufficio |
| risposte (`--reply`) | già mostrate nel viewer 2D; il collegamento dei tag copre il caso 3D |

## Regole di costruzione

- Un modulo, `office-viz.js`, con `install(ctx)` e `update(dt, t)`; nessuna allocazione per frame, texture e geometrie create una
  volta, `CanvasTexture.needsUpdate` solo al cambio del contenuto, niente lavoro con la pagina nascosta.
- Dove si può, istanze (`InstancedMesh`) e colori condivisi: tutte le barre del budget in una draw call, i pacchi in una.
- Colori degli stati come nel resto del plugin: OK verde `#43a047`, errore rosso `#e53935`, attenzione ambra `#ffb74d`,
  in corso ciano `#4dd0e1`, scartato grigio `#90a4ae`.
- Testi nel catalogo (`office.viz.*` in `locales/en.json` e `it.json`), mai nel codice.
