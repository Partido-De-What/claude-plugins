# Sintesi dello sciame del 29/10/2026: cosa fare dopo la 0.15

Quattro agenti Sonnet 5.5. I report completi sono nei file 1-4 di questa cartella. Le opzioni di Claude Code citate
(`subagentPromptCacheTtl`, `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`, `autoCompactWindow`, `omitClaudeMd`,
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, `asyncRewake`) le ho trovate nel binario installato qui (claude.exe di npm); la loro
semantica viene dalla documentazione letta dall'agente, non provata da me.

## Il punto comune dei quattro report

Il costo è turni x contesto riletto (2608.16801: 10,5M token a run di 8 agenti, quasi tutti riletture dalla cache;
2607.12161: scrittura e lettura della cache sono l'80% della bolletta). Comprimere il testo della chat o gli output dei
comandi tocca poco: Headroom come proxy su Claude Code è stato misurato +48% di costo, RTK circa zero. Le leve sono tre:
contesti più piccoli, meno turni, cache che non scade tra un turno e l'altro.

## Proposte, dalla più redditizia

| # | proposta | evidenza | dove | costo | rischio |
|---|---|---|---|---|---|
| P1 | Agenti della stanza come agent type del plugin (`agents/room-agent.md`), con `autoCompactWindow: 200000` e la cache a 1 h (`experimental.cacheTtl: 1h`); il lead lancia quel tipo con il modello e l'effort scelti dall'utente | default ~967k sui modelli da 1M = i nostri 300-850k mai compattati; [calc] da 600k a 200k il costo per richiesta si divide per 3; risveglio a freddo 25x una lettura calda | entrambe | basso | medio: il riassunto perde dettagli; la scrittura a 1 h costa 2x |
| P2 | Con la cache a 1 h: idle senza giro di wait da 270 s; l'agente chiude il turno e riparte al tag (ping o hook), invece di 13 richieste a vuoto all'ora | doc cache; nessun harness fa polling per tenere la cache (Codex, LangGraph, OpenHands) | entrambe | medio | medio: dipende da P1 |
| P3 | Tetto al dibattito: PIANO/VOTO al massimo 2-3 giri, stop se la maggioranza non cambia per 2 giri; il kernel lo segnala | 2609.27150: -76/-78% token a pari accuratezza | entrambe | basso | basso |
| P4 | Immagini ridimensionate prima della lettura (lato ~1000 px): uno script `chat.py thumb` o una regola nel prompt, foglio di miniature | costo = ceil(w/28) x ceil(h/28): 1920x1080 = 2.691 token, 1000x1000 = 1.296; 60-80 immagini per agente nella fucina | normale (render, video) | basso | basso |
| P5 | Lavoro parallelo coordinato via bacheca/file, post solo per decisioni e blocchi; niente giro di presentazioni né broadcast; rapporto di ritorno di 1 riga | 2608.16801: -25/-42% output; Anthropic: 1000-2000 token a rapporto | entrambe (non per pipeline a catena: lì +10/+17%) | basso | basso-medio |
| P6 | Quaderno per tipi: regole e contratto fissi letterali, ricaricati dopo una compattazione; solo il diario si riassume | 2608.22752: /compact tiene il 53% delle regole dopo 1 giro, il 10% dopo 5; 2608.16370 | entrambe | basso-medio | basso |
| P7 | Hook PostToolUse con `updatedToolOutput` solo sugli output enormi (>8k token: pytest, log, render): fallimenti e coda, l'intero su file; per la research, l'output di evaluate con handle e testa/coda | 2609.20519 SoL-Pi -45/-49% token; output del terminale = 11% dell'input (Quesma) | entrambe | medio | medio: riletture in più |
| P8 | Headroom: tolto dalla chat (0 misurato, costa fino a 5 s a lettura) oppure lasciato spento di default; mai come proxy | 2607.12161, tokbench, README | entrambe | basso | nullo |
| P9 | Research: rumore misurato (sigma da 2 seed allo smoke), margine in sigma del best nel report, rivalutazione a seed freschi prima della chiusura; solo report, nessun gate | 2606.20394, 2610.09239 (winner's curse: +13/20 punti sulla selezione), 2606.08106 | research | medio | basso |
| P10 | Research: libro dei costi (token o $ per tentativo, ruolo e ciclo nel report); tetto nel contratto | Sakana Fig.16, SwarmResearch +7,7% di overhead | research | medio | basso |
| P11 | Research: modello di contratto per kernel (timer fuori processo, input freschi, niente stream laterali, tetto di plausibilità sugli speedup; soglie di rumore 0,30% / 1,58% / 3,90%) | 2608.12004, 2608.14560, 2609.30057 | research | basso | basso |
| P12 | Research: task canary con scorciatoia piantata per tarare auditor e detector; precheck su dati e passi dichiarati | 2608.30724 (57% di corse con hack), 2608.26753 | research | basso | nullo |
| P13 | Hook SubagentStop che porta i tag all'agente al posto di SendMessage | solo documentazione | entrambe | medio | alto: prima un esperimento |
| P14 | Stato del lead ricostruito dalla bacheca e risveglio a evento | 2610.15224: 6x meno token in simulazione | entrambe | alto | alto: ultimo |

Da non fare: agent teams sperimentali (riscrittura, ~7x token), Headroom proxy, topologie di comunicazione apprese
(2609.27150: non servono), SAGE/PACE come gate di keep (cambiano il comportamento della research).

## Da tenere a mente

Molti paper sono v1 non revisionati, su benchmark diversi dalle nostre stanze. Le stime [calc] sono aritmetica, non misure:
dopo ogni proposta va misurata una stanza vera (lo script di analisi della fucina c'è già).
