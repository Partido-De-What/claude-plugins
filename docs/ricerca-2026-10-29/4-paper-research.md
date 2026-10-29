# Sciame 29/10/2026, filone 4: i paper della stanza research e quelli nuovi

Agente Sonnet 5.5. Pagine arXiv riaperte il 29/10; alcune HTML troncate a circa 100k caratteri (segnato "non letto").
(E) = finestra estesa a maggio-giugno 2026.

## Parte 1: paper già usati, cosa non abbiamo ancora preso

Mappa: A1/A2 = Sakana 2610.18933 + Harness-Search 2610.05382 + PatchBoard 2605.29313 + MemTX 2607.23929; A3 = Narrow
Exploration 2605.27905 + IdeaScientist 2610.04074; A4 = SwarmResearch 2607.02807; A5 = ScienceFlow 2608.14354; A6 =
Sakana + Evolutionary coding agents 2605.20086; A7 = ARAC-Bench 2608.12788 + verification gap 2608.05179; A8 = autoresearch.

| paper | già preso | non ancora preso e utile | rischio |
|---|---|---|---|
| Sakana 2610.18933 | A1, sigillo, rubric, cancelli, 2 worker | costo API per ciclo e per worker nel report (Fig.16); manifest delle figure; "guadagno per worker" (un secondo worker che non aggiunge nulla: avviso) | basso |
| Harness-Search 2610.05382 | ruoli, S_max, auditor | similarità del nuovo tentativo col PRIMO (deriva verso l'inizio); statistica "l'auditor rifiuta, si recupera?" (1 su 5); ultimi 5 azione-osservazione interi, il resto riassunto | basso |
| PatchBoard 2605.29313 | kernel, viste, contratti | self-test con fault injection (JSON invalido, path sbagliato, scrittura non autorizzata, falso claim, ciclo) come regressione del kernel; token per ruolo; il falso claim passa nel 43%: verificarlo contro l'artefatto grezzo | basso (test) |
| ScienceFlow 2608.14354 | tag, stati recuperabili | telemetria GPU (utilizzo medio 27,5%); consiglio del worker (continue/timebox/stop/replan) con decisione al kernel; stop su non convergenza su più finestre | basso report, medio consiglio |
| SwarmResearch 2607.02807 | explorer/optimizer, rami | tetto in $ o token nel contratto; overhead dell'orchestratore (+7,7% output) | basso |
| Narrow 2605.27905 | gap/analogia, Jaccard 0,5 | quota di proposte valide nello status; ampiezza e distanza dal seed nel tempo | basso |
| Evolutionary 2605.20086 | righe rimesse, sola taratura, soffitto taratura | etichette "dipendenza esterna" (odds 3,58) ed "efficienza" (1,61) dal diff; profondità del lignaggio; credito per tipo di modifica nel report | basso |
| ARAC 2608.12788 | rubric 0/1,5/3 | limiti omessi e sovra-estrapolazione come voce di checklist; confronto degli iperparametri con valori noti | basso |
| verification gap 2608.05179 | seed, tracce, novità, selezione | Table 10 non letta (pagina troncata) | nullo |

Da non rifare: righe rimesse, sola taratura, soffitto di taratura, sigillo, final una volta, Jaccard, quota 1/4, 4
famiglie uguali, rubric 0/1,5/3, checklist seed/tracce/selezione, viste da 1-2k.

## Parte 2: paper nuovi (1/8-29/10/2026)

| ID | data | titolo | risultato | idea per noi | costo | rischio |
|---|---|---|---|---|---|---|
| 2610.09239 | 7/10 | Winner's Curse in LLM Self-Improvement Loops | keep-if-better su un set piccolo: selezione sopra l'held-out di 13-20 punti (16 item), 1-5 (256); rivalutare su 64 item mai usati toglie il bias | nel report: scarto tra selezione e rivalutazione fresca del best | basso | basso |
| 2609.36043 | 28/9 | SAGE statistical acceptance gate | test binomiale appaiato per item; regressioni dal 36,5% a 0 | solo per valutatori con esito binario per item | medio | medio (cambia il keep) |
| 2606.08106 (E) | 6/6 | PACE anytime-valid acceptance | e-process appaiato, stop anticipato valido, -18% di valutazioni; greedy con 30-42% di commit falsi | versione con garanzia del nostro "stop a 2 se la mediana perde" | medio | medio |
| 2606.20394 (E) | 18/6 | Agentic AutoResearch for Space Autonomy | sigma da 2+ seed prima di credere; accetta solo oltre 2 sigma; seed freschi; potatura leave-one-out delle modifiche; tetto in $ | sigma misurato allo smoke e scritto nel contratto; nel report le modifiche portanti e quelle inerti | medio | basso solo report |
| 2610.00349 | 29/9 | Fault-Tolerant Budget Conservation | credito riservato prima del dispatch con chiave idempotente | una corsa reaped resta contata; chiave idempotente per evaluate ripetuti | basso-medio | medio |
| 2609.30057 | 24/9 | KREX concurrent kernel benchmarking | esclusività solo nelle regioni critiche: 3,4x throughput; inflazione p95 0,30% (>10 ms), 1,58% (>1 ms), 3,90% (>0,1 ms) | lucchetto GPU solo sul cronometro (alto rischio); le soglie di rumore subito | alto | alto |
| 2608.12004 | 12/8 | RealisticTritonBench | hack con stream laterale; timing e accuratezza in processi separati; 3 corse, ~1% | modello di contratto per kernel: timer fuori processo | basso | basso |
| 2608.14560 | ? (data incongruente) | Agentic Kernel Optimization | speedup >1000x da un harness che riusava gli input | input freschi a ogni iterazione; tetto di plausibilità sugli speedup | basso | basso |
| 2609.20519 | 17/9 | SoL-Pi | -44,7/-49% token, -1/3 costo, 93,7% del punteggio; output >10 KiB archiviati con handle + testa/coda; log >= 4 KiB ridotti con verificatore deterministico; compattazione solo se il risparmio supera il costo della riscrittura della cache | output di evaluate limitato con handle; regola costo-beneficio nel rilevatore >150k | basso-medio | medio |
| 2606.14945 (E) | 12/6 | Remember, Don't Re-read | stato fuori contesto: token da 24.465 a 2.492 (iperparametri), da 1,28M a 0,63M (codice) | vista del worker: best + ultimi 5 | basso | basso |
| 2609.17846 | 15/9 | PrimeScientist | albero di piani + MCTS: +10,3% con il 50,6% di tentativi in meno | solo come suggerimento al lead | alto | alto |
| 2608.30724 | 31/8 | BAITBENCH | 57,1% delle corse con hack, oltre il 50% anche se vietato | task canary con scorciatoia piantata per tarare auditor e detector | basso | nullo |
| 2608.26753 | 27/8 | Beyond Execution (ABE-Ralph) | dataset o budget ridotti in silenzio, componenti sostituiti da lookup | precheck: dati e passi dichiarati contro il contratto; tabelle letterali grosse nel diff | medio | basso |
| 2608.14905 | 14/8 | AutoResearchEval (ARFT) | 45 pattern di fallimento; leakage trovato solo ricalcolando | checklist dell'auditor (lista non letta) | basso | basso |
| 2610.12822 | 9/10 | Reward Hacking as Transmissible Strategy | l'hack si propaga via codice e memoria condivisi | controllo dei findings condivisi prima di passarli | basso | basso |
| 2608.22331 | 23/8 | Noise Floor Audit | rerun a temp 0 quasi deterministici; perturbazioni del prompt 11-58x più varianza | solo per valutatori con LLM | basso | basso |

Scartati: 2610.03055 (servono gli stati interni del modello), 2609.03335 (sovradimensionato).

## Prime 5 proposte dell'agente

1. Rumore misurato e margine: sigma da 2+ seed allo smoke nel contratto; margine in sigma del best nel report; rivalutazione a seed freschi prima della chiusura. All'inizio solo report.
2. Modello di contratto per i kernel: timer fuori processo, input freschi, niente stream laterali, tetto agli speedup; soglie di rumore KREX.
3. Libro dei costi: costo per tentativo, ruolo e ciclo nel report; tetto nel contratto; corsa incerta contata finché non è chiarita.
4. Efficienza token: output di evaluate con handle e testa/coda, ricevuta del log verificata, regola costo-beneficio per la rotazione, vista del worker best + ultimi 5.
5. Canary e detector metodologici: task con scorciatoia piantata; precheck di dati e passi; etichette di modifica dal diff.

Non letto per intero: Table 10 di 2608.05179, i 5 modi di 2608.26753, sezioni 7-8 di Sakana, PACE/SAGE oltre l'abstract.
