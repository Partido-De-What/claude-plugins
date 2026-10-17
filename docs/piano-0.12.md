# Piano chatroom 0.12: laboratorio research, ufficio corretto, visualizzazioni

Registrato il 17/10/2026 con le decisioni dell'utente. Branch `office-lab`, worktree `E:\claudecode pesante\claude-plugins-dev`.
Niente merge su main, push o installazione senza ok esplicito dell'utente.

## Decisioni dell'utente

- D1: la porta davanti all'arcade si toglie: resta solo il vano, senza anta (e senza il suo box di collisione).
- D2: sì, reset una tantum dei volumi salvati ai nuovi default bassi (chiave `chatroom.mix.v2`).
- D3: il tema laboratorio è automatico per le stanze research (`mode == research`); le stanze normali restano ufficio.
- D4: l'inventario delle funzioni da visualizzare non passa dall'utente: si procede da soli.
- D5: 3 agenti Sonnet e un occhio Haiku (effort max). Stanza di lavoro normale, non research.
- Fase 3 e fase 4: confermate per intero.

## 0. Due binari: si lavora con la chatroom senza installare la versione nuova

- Stanza di lavoro: chatroom installata 0.11.2 (CLI, porta 8770). Gli agenti discutono e si coordinano lì.
- Codice nuovo: solo nel worktree `claude-plugins-dev`, branch `office-lab`.
- Anteprima dev: `python <worktree>/plugins/chatroom/scripts/chat.py serve --room <stanza-test> --port 8775` (stanza normale
  di prova) e `--port 8776` (stanza research di prova). Porta diversa = origine diversa: volumi e preferenze separati.
- Le stanze research di prova si creano e si usano solo con la CLI del worktree (il kernel dev può essere più nuovo
  dell'MCP installato, che le rifiuterebbe).
- Test: `E:\claudecode pesante\claude-plugins-dev-tools\run_all.sh` (la suite completa puntata al worktree).

## 1. Correzioni nella stanza di default

1a. Porta davanti all'arcade (arcade in `ARCADE_AT {x 1.2, z 5.52}`): l'anta della parete della sala comune si toglie,
    resta il vano (D1). Verifica camminando: l'arcade si raggiunge da ogni lato.
1b. La sensibilità della visuale cambia contro gli ostacoli. Prima riprodurre e misurare (radianti per pixel lontano e
    vicino a un muro), poi correggere la causa. Sospetti in ordine:
    1. `eyeLead` (office.js): vicino a un ostacolo l'occhio rientra da 0.32 a 0 m e torna avanti a 0.8 m/s: girando
       accanto a un muro l'occhio va avanti e indietro;
    2. l'occhio sta 0.32 m davanti al perno della testa e gira su un arco;
    3. il corpo che striscia lungo un ostacolo cambia `boss.rot`, che viene sottratto da `me.yaw` (`dr`).
    Correzione attesa: la visuale ruota attorno all'occhio; l'arretramento contro i muri non cambia il giro; lo
    strisciamento non tocca `yaw`. Test: gli stessi pixel di mouse danno lo stesso angolo vicino e lontano dai muri.
1c. Volume: la TV del lounge usa la dissolvenza lunga (si sente fino a 30 m) e il mixer parte da 1. Default nuovi:
    master 0.3, TV 0.5; la TV resta nella sua stanza (`reach` 4-5 m come radio e lofi); arcade allo stesso livello.
    Reset una tantum dei volumi salvati (D2).

## 2. Ambiente laboratorio per le stanze research (automatico, D3)

- Stessa pianta, stesse posizioni, tutte le funzioni: arcade e giochi NES, TV, radio, lofi, arena, paintball e zombie,
  rack, finestra GitHub, insegne, timeline, ufficio del boss, ponte verso gli amici.
- Cambiano palette e materiali (laboratorio pulito: bianco e acciaio, luci fredde, accenti ciano e ambra) e i mobili:
  scrivanie in banconi da laboratorio, armadi in rack server e frigo campioni, sala riunioni in camera bianca a vetri con
  cappa, lavagne bianche con i risultati, insegne a tema.
- Texture nuove, procedurali in canvas come `office-floor.js`, niente download: resina epossidica grigia a piastrelle,
  pavimento antistatico esagonale, griglia da camera bianca, circuito stampato per le pareti tecniche, lavagna
  blueprint, acciaio spazzolato, tessuto ESD dei banconi.
- File: `office-lab.js` nuovo (tema, texture, sostituzioni); `office.js` cambia solo dove sceglie il tema.

## 3. Visualizzare nella chatroom normale le funzioni introdotte

3a. Inventario in `docs/inventario-visualizzazioni.md`: funzioni dalla 0.8.18 alla 0.12, visibile oggi?,
    visualizzazione proposta. Si procede senza approvazione dell'utente (D4).
3b. Da costruire (più quelle che l'inventario trova):
    - pannello CHECK sulla parete della sala controllo: CHECK attivi (stallo, tutti fermi, tag senza risposta, 100%
      senza prove...), colorati per gravità, clic per aprire il messaggio;
    - badge "!!! #N" sopra l'agente che ha postato senza leggere un messaggio per lui;
    - tag: linea luminosa tra chi tagga e il taggato, verde quando ha risposto (anche con uno status o la bacheca);
    - lampada "tutti fermi", una volta per episodio;
    - indicatore del budget di chiamate sulla scrivania di ogni agente;
    - prestiti, pacchetti e relay tra stanze: pacchi che viaggiano lungo il ponte o tra le scrivanie;
    - lingua della stanza: bandierina sull'insegna e selettore it/en nel viewer.
    Fuori: ciò che non ha niente di visivo (help della CLI, MCP, migrazioni).

## 4. Visualizzazioni research

- Dati: endpoint in sola lettura `/research.json` nel viewer, da `state.json`, `results.tsv`, `log.jsonl`,
  `contract.json`; polling ogni 2-3 s; nessuna scrittura.
- Vista 3D nel laboratorio:
  - pipeline delle fasi 0-6 come striscia luminosa sul pavimento; il cancello che blocca la fase dopo è un portale
    rosso con il motivo;
  - muro dei risultati: metrica per corsa, punti KEEP/DISCARD/CRASH, linea del migliore, baseline tratteggiata, fascia
    di `min_gain`; passandoci sopra il dettaglio di `att-N`;
  - banconi dei worker: worktree, corsa in corso con barra del budget e luce pulsante, fumo nei crash, nastro giallo
    in pausa per crash;
  - lampade: GPU tenuta (prebuild), `eval.lock` occupato;
  - bacheca delle idee: schede con stato e autore, le confutate nel cestino;
  - muro dei verdetti: timbri PASS/FAIL dell'auditor per fase, revoche a cascata come catena;
  - provenienza: sigillo verde sulle corse con `built:` verificato, grigio senza; indicatori di clock e temperatura
    dalle righe `env:`;
  - registro delle modifiche al contratto dopo la baseline, con il motivo;
  - valutazione finale: trofeo, numero della ricerca e finale con la differenza;
  - cancello del report: checklist spuntata.
- Vista 2D: scheda "Research" nel viewer con lo stesso grafico e la pipeline (anche senza 3D e su telefono).
- File: `office-research.js` (3D), viewer (2D), endpoint in `chat.py`.

## 5. Organizzazione

| Agente | Modello | Lavoro | File suoi |
|---|---|---|---|
| FABBRO | Sonnet 5.5 xhigh | fase 1, poi fase 3 | `office.js`, `office-layout.js`, `office-tv.js`, `office-viz.js` nuovo, `docs/inventario-visualizzazioni.md` |
| ALCHIMISTA | Sonnet 5.5 xhigh | fase 2 | `office-lab.js` nuovo, `office-floor.js`, `office-voxel.js` se serve |
| ASTRONOMO | Sonnet 5.5 xhigh | fase 4 | `office-research.js` nuovo, `viewer.html`, endpoint in `chat.py`, fixture della stanza research di prova |
| OCCHIO | Haiku 5.5 max | controllo visivo continuo nell'anteprima dev | nessuno (solo screenshot e segnalazioni) |
| LEAD | Opus (sessione) | regia, revisione del codice, resoconto visivo a fine batch | punti di aggancio condivisi su richiesta |

- `office.js` è di FABBRO: ALCHIMISTA e ASTRONOMO espongono `install(ctx)` dai loro moduli e chiedono a FABBRO la riga
  di aggancio.
- Testi nuovi: chiavi in `locales/en.json` e `it.json`, `i18n_check` a 0 errori.
- Lavoro a batch: ogni batch si chiude con test verdi, controllo di OCCHIO e resoconto del lead.

## 6. Test e rilascio

- Suite completa più test nuovi: forma di `/research.json`, sensibilità costante, volumi di default, arcade raggiungibile.
- Prova visiva: screenshot di ufficio e laboratorio, anche a larghezza telefono; frame time e draw call misurati prima
  e dopo (`renderer.info`).
- Versione 0.12.0 sul branch `office-lab`. Merge, push e installazione solo con ok dell'utente.
