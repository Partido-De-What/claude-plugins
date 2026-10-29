# Sciame 29/10/2026, filone 1: efficienza token e coordinamento multi-agente

Agente Sonnet 5.5, paper aperti su arXiv. Finestra 1/8-29/10/2026; (EXT) = esteso a giugno 2026. Molti sono v1 non
revisionati, su benchmark QA/robot/coding e non su chat multi-agente come la nostra: la trasferibilità è un'inferenza.

| ID | data | titolo | risultato misurato | idea per noi | dove | costo | rischio |
|---|---|---|---|---|---|---|---|
| 2608.16801 | 17/8 | When Agents Coordinate: Measuring Coordination in Multi-Agent AI Coding | 1902 run. File condivisi obbligatori al posto dei messaggi 1-a-1: output -25% (4 agenti), -42% (8 agenti) su lavoro ricco di messaggi; su task a catena +17%/+10% (peggio). Messaggi/run 6,1 (2 ag), 28,5 (4), 71,3 (8). Coordinatore nominato: nessun guadagno di successo. Gran parte dei token = contesto in cache riletto a ogni turno (10,5M/run a 8 ag; 6,6M con file) | coordinare via bacheca/file per lavoro parallelo, non per pipeline | entrambe (research di più) | basso | basso-medio |
| 2609.27150 | 22/9 | Distinct-Peer Random Routing, Sparse MAD | Topologia complessa non serve (57,3-57,6k token/domanda per tutti). Stop a round 3: -78,5% token, accuratezza 77,33 vs 76,87. Stop a maggioranza stabile: -75,9% | tetto ai giri di PIANO/VOTO, stop se la maggioranza non cambia per 2 giri | entrambe | basso | basso |
| 2610.16343 | 12/10 | Confidence-Guided Adaptive Debate (LASE) | Leader da solo, un pari solo se incerto: token 1,0-1,8x di un agente, 8,9-14,3x meno del dibattito fisso; accuratezza +3,8 di media | secondo parere solo su dubbio dichiarato | research | medio | medio |
| 2609.23790 | 20/9 | Total Cost of Agency | memoria iniettata 12% del costo, fino a 27,6%; finestra di recupero 32 a 2 voci: -28,7% token a pari accuratezza | ridurre ciò che `read --focus` inietta | entrambe | basso | basso |
| 2608.16370 | 17/8 | What Does Context Compression Cost an Agent? | compressione 5x: completamento uguale ma chiamate di recupero da 21,0 a 63,9 (p=.002) | il quaderno tiene fatti, non riassunti generici | entrambe | basso | basso |
| 2608.22752 | 24/8 | The Compaction Cliff | /compact di Claude Code tiene il 53% delle regole dopo 1 giro, il 10% dopo 5; triage per tipo: recall 96% | regole e contratto fissi fuori dal riassunto, ricaricati dopo la compattazione | entrambe | basso-medio | basso |
| 2608.17188 | 17/8 | Token Optimization in Multi-Agent Workflows | solo stime (-60/70%), non misure | handoff come schema fisso | entrambe | basso | basso |
| 2610.15224 | 10/10 | Persistent LLM Orchestration of Robot Teams | orchestratore con stato ricostruito a ogni invocazione: 6x meno token, 98% vs 89% | stato del LEAD ricostruito da bacheca e quaderno, risveglio a evento | entrambe (LEAD) | alto | alto |
| 2606.05304 (EXT) | 3/6 | Action-state Communication (PACT) | record compatto azione+stato: OpenHands -10% token per risolto, SWE-agent -50% input | status come record corto strutturato (quasi già fatto) | entrambe | basso | basso |
| 2606.10662 (EXT) | 9/6 | DeLM: shared context, no main agent | +17,5 punti, 2,49x più veloce; costo non riportato | conferma la bacheca come centro | research | alto | alto |

Scartati: 2608.12921 (nessun numero sulla pagina), 2609.35427 (concettuale).

## Prime 5 proposte dell'agente

1. Tetto al dibattito e stop anticipato (2609.27150): PIANO/VOTO al massimo 2-3 giri, stop se la maggioranza non cambia per 2 giri.
2. Bacheca e file al posto dei post per il lavoro distribuito (2608.16801): solo per lavori paralleli, non per pipeline.
3. Verifica o secondo parere solo su dubbio dichiarato (2610.16343).
4. Quaderno per tipi, con regole fisse non riassunte (2608.22752, 2608.16370).
5. Stato del LEAD ricostruito dalla bacheca, risveglio a evento (2610.15224): ultimo, come esperimento.

## Non trovato

Nessun paper misura il costo di polling, heartbeat o wait, né il TTL di 5 minuti della cache in multi-agente; niente
di diretto sulla rotazione degli agenti in chat; broadcast contro indirizzato solo descrittivo (2608.16801).
