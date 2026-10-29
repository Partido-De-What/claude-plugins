# Sciame 29/10/2026, filone 2: compressione del contesto, Headroom e alternative

Agente Sonnet 5.5. Finestra 1/8-29/10/2026; dove serve, fonti precedenti segnate.

## Verdetto

- Headroom come proxy su Claude Code è stato misurato peggio: +48,4% di costo (712 run per braccio, v0.27.0 in token
  mode; arXiv 2607.12161). Non va messo sul proxy.
- Il nostro risultato (prosa della chat, risparmio 0) coincide con il README di Headroom: su prosa e scambi corti dà
  poco o niente.
- Il costo sta nella scrittura della cache (44,3%) e nella lettura (35,4%), circa l'80% della bolletta (2607.12161).
  Comprimere gli output dei tool tocca poco. Le leve vere: meno token che entrano e restano, meno turni, meno contesto
  riletto.

## Headroom oggi

Repo headroomlabs-ai/headroom; PyPI headroom-ai 0.42.0 del 26/10/2026.

- Router per tipo: SmartCrusher (JSON), CodeCompressor (AST: Py, JS, TS, Go, Rust, Java, C, C#, PHP), Kompress-v2-base
  (prosa: ModernBERT 150M + LoRA, ONNX int8 da 274 MB). Kompress toglie circa il 13% dei subword a soglia 0,5 (recall
  0,989) e il 25% a 0,7 (recall 0,953); solo inglese, estrattivo.
- Proxy, `headroom wrap claude`, MCP (compress/retrieve/stats), CCR reversibile, `--mode cache` (default su Anthropic,
  prefisso stabile) o `token`; immagini "40-90%" solo dichiarato nel README.
- Novità: 0.39 hook di veto per messaggio; 0.40 diagnostica per messaggio; 0.42 risparmio per richiesta;
  `frozen_message_count`, `--protect-tool-results`.
- Benchmark del README: ricerca nel codice 21%, triage GitHub 30%, codebase 42%, incidente SRE 57%.

## Tabella

| fonte | data | cosa | risultato misurato | uso da noi | dove | costo | rischio |
|---|---|---|---|---|---|---|---|
| arXiv 2607.12161 | v5 12/8 | A/B su Claude Code: RTK, RTK-ML, Headroom 0.27 token mode | Headroom +48,4% costo; RTK -2,7% (holdout non significativo); correlazione riduzione token/costo 0,15 | prova per non usare il proxy; RTK conferma di valere poco | entrambe | zero | cache mode non testato |
| tokbench (GitHub) | giugno | headroom, rtk, lean-ctx su un caso reale | N=1: tutti peggio del nativo | conferma | entrambe | zero | N=1 |
| blog Quesma | 11/9 | RTK su Terminal-Bench 2.1, 1.740 tentativi | costo -5%/+5% secondo il modello; output del terminale = 11% dei token di input; `rtk gain` conta output tolto, non soldi | spiega i nostri 127k su 1.627 comandi | entrambe | zero | |
| arXiv 2609.22114 | agosto | gateway Paritok | filtrare gli schemi dei tool: -21k/-57k token a turno (l'unica leva sempre positiva); comprimere i contenuti ~2% | tagliare schemi tool/MCP inutili | entrambe | basso | |
| arXiv 2608.16370 | 17/8 | costo nascosto della compressione | recuperi da 21,0 a 63,9 | cautela | research | zero | ambiente sintetico |
| arXiv 2508.21433 (2025) | | observation masking vs riassunto | masking circa metà costo, pari al riassunto | cancellare i vecchi tool result | entrambe | basso | |
| arXiv 2610.10590 | 6/10 | l'agente sostituisce i vecchi tool result con note, originali archiviati | ~-50% token in un caso, 0 in un altro, +17% tempo | come i quaderni e `expand` | entrambe | basso | |
| arXiv 2606.17016 | v2 28/8 | TokenPilot: compattazione che stabilizza il prefisso | costo -56/-87% | principio: non toccare il prefisso | research | alto | |
| arXiv 2608.24188, 2609.08318, 2609.29875, 2610.28577 | ago-ott | modelli o serving propri | -20/-34% | non applicabili via API | research | alto | |
| doc Anthropic: context editing | 29/10 | `clear_tool_uses_20250919`, `compact_20260112` | nessun numero pubblicato | solo controllando la chiamata API | | | |
| doc Claude Code: hook | 29/10 | PostToolUse `updatedToolOutput` (il modello vede solo la versione sostituita) | | il punto d'ingresso giusto | entrambe | basso | forma sbagliata ignorata |

## Cache Anthropic

Ordine del prefisso: tools, system, messages; un cambio invalida quel livello e i successivi. Cambiare le definizioni dei
tool invalida tutto. Comprimere contenuto nuovo prima del primo invio non rompe la cache, se deterministico (il nostro
caso). Riscrivere risultati vecchi rompe la cache da lì in poi. Prezzi Sonnet/Opus 5.5: scrittura 1,25x (5 min) o 2x
(1 h), lettura 0,05x. Il contenuto che resta costa soprattutto in lettura: conviene non farlo entrare, o farlo uscire presto.

## Prime 5 proposte dell'agente

1. Ridimensionare le immagini prima che l'agente le legga: costo = ceil(w/28) x ceil(h/28), 1920x1080 = 2.691 token,
   1000x1000 = 1.296. Con 60-80 immagini per agente è probabilmente la leva più grossa.
2. Hook PostToolUse con `updatedToolOutput` solo sugli output enormi (>~8k token: pytest, log, render): fallimenti e
   coda, l'intero su file con il percorso. Soglia alta.
3. Riavvio dell'agente a soglia con passaggio dal quaderno (2610.10590, 2508.21433).
4. Tagliare gli schemi tool/MCP non usati (2609.22114).
5. Edit invece di riscrivere file interi con heredoc; letture con offset/limit.

Headroom: lasciarlo sulla chat (non fa danni, non rende) o toglierlo per semplicità; se si prova, solo come libreria
dentro l'hook del punto 2, su JSON e log, mai come proxy.

## Non trovato

Nessun A/B indipendente di Headroom `--mode cache` su Claude Code; parametri di `compress()` verificati solo su fonti
terze; nessun numero sulla compressione delle immagini di Headroom né sul context editing.
