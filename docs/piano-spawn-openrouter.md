# Piano: modalità Spawn (chatroom 0.13.0), versione 2

Stato: proposta, niente implementato. Si parte solo dopo l'ok di Adrian sulle decisioni della sezione 14.
Sostituisce la versione 1 (solo OpenRouter). Elenco completo di adapter e modelli in `docs/adapter-modelli.md`.

## 0. In una riga

`/spawn` fa entrare in una stanza agenti che girano su modelli esterni (tutti i modelli free di tutti i provider insieme; le chiavi si inseriscono una volta, al primo `/spawn`). Prima li scegli guardando punteggi, grafici e punti forti; poi lavorano come **ruoli** che sopravvivono al cambio di modello. Quando un ruolo resta senza token lampeggia, ci clicchi e scegli il sostituto dalla stessa vetrina di benchmark.

## 1. Tre modi di usarlo

| Modo | Come parte | Agenti | Motore | Headroom e RTK |
|---|---|---|---|---|
| **A. Stanza spawn nuova** | `/spawn` da zero o tasto "Nuova stanza spawn" | modelli di **tutti** i provider free insieme (sezione 5); agenti Claude solo su tua richiesta esplicita | motore completo adattato da free-claude-code | **obbligatori**, uso pieno |
| **B. Evocato in una chatroom normale** | `/spawn` dentro una stanza esistente | si aggiungono ai partecipanti attuali | stesso motore | integrati nella chatroom stessa (sezione 3.1), per tutti gli agenti, prima di caveman |
| **C. Evocato in una stanza research** | `/spawn` dentro una research | come B, rispettando contratto e ruoli research | stesso motore | come B |

In B e C Headroom e RTK non restano chiusi nei ruoli spawnati: diventano parte della chatroom e servono a tutti gli agenti della stanza, Claude compresi (sezione 3.1). Le parti pesanti di Headroom (proxy, wrap, memoria condivisa, `learn`) restano fuori.

## 2. Il motore: free-claude-code adattato

free-claude-code (FCC) non si installa. Il suo codice si copia e si modifica dove serve, e FCC si cita nel README in fondo.

**Licenza (punto da decidere, vedi D-LIC).** FCC è AGPL-3.0-only, il plugin è MIT. Copiare codice AGPL dentro un programma MIT lo farebbe diventare AGPL. Soluzione proposta: il motore spawn è **un programma separato** dentro il repo, in `plugins/chatroom/spawn/`, con il suo file LICENSE AGPL-3.0, gli avvisi di copyright di FCC e un `NOTICE` che dice cosa è stato preso e cosa cambiato. Il resto della chatroom resta MIT e parla col motore solo via processo e HTTP locale (come già fa il viewer), quindi resta un'opera separata. Non è un parere legale: è lo schema che la licenza stessa prevede per programmi distinti.

**Ambiente.** FCC richiede Python 3.14.9. Il motore gira in un ambiente suo creato con uv (cartella configurabile: per Adrian `D:\chatroom-spawn\spawn-env`, di default `~/.claude/chatroom/spawn-env`), separato dal Python della chatroom (che resta solo libreria standard). Dipendenze: openai, httpx, pydantic, tiktoken, loguru, jsonschema, headroom-ai. Python, cache di uv e binario RTK (`rtk-oss` 1.1.0) stanno in `D:\chatroom-spawn\`.

**Cosa prendiamo da FCC** (copiato e adattato):

| Modulo FCC | Da noi diventa | Modifiche |
|---|---|---|
| `config/provider_catalog.py` | catalogo provider | togliamo abbonamenti personali di default, aggiungiamo campi "free", "limiti", "ping gratis" |
| `providers/openai_chat/*` (profili, transport, stream, tool_calls, reasoning_details, usage) | adapter generico OpenAI-compatibile | input dai nostri ruoli invece che da Claude Code; niente conversione Anthropic in ingresso |
| adapter speciali: open_router, nvidia_nim, groq (tpm), mistral, deepseek, kilo, opencode, gemini, vertex, cloudflare, anthropic, alibaba, lmstudio | adapter speciali | OpenRouter esteso con `/key`, `/endpoints`, `/benchmarks`, `session_id`, `provider{data_collection, require_parameters}`, header di attribuzione |
| `providers/admission*.py` | limitatore centrale | uno solo nel server del viewer, condiviso da tutti i ruoli e le stanze, per chiave e per modello |
| `providers/failure_policy.py`, `request_recovery.py`, `stream_recovery.py`, `continuation.py` | classificazione errori, ripresa stream | uguale |
| `api/tool_call_buffer.py`, passo TOOL_REPAIR | riparazione tool call | uguale, con i nostri schemi |
| `core/history_replay.py`, `providers/history_replay.py` | replay della storia | usato anche per il cambio di host |
| `application/routing.py` (fallback ordinati) | catena di strade del ruolo | stesso modello su altri host prima di un modello diverso |
| `providers/model_listing.py`, `runtime/discovery.py`, `model_cache.py` | updater del catalogo | più ping, coda benchmark, identità comune |
| `core/token_estimation.py`, tiktoken | stima contesto | uguale |

**Cosa lasciamo fuori:** launcher degli harness (claude, codex, pi...), integrazioni IDE e desktop, Admin UI (diventa le nostre card), bot Telegram e Discord, voce, sessioni Codex nel browser, provider ad abbonamento personale (ChatGPT, Copilot, Kimi Code, piani coding Qwen e Z.ai, ClinePass, OpenCode Go, Wafer, Featherless) per i loro termini d'uso: restano disattivati e attivabili solo a mano per uso tuo interattivo.

## 3. Headroom e RTK obbligatori

Installazione (cambia il sistema, la faccio solo col tuo ok al momento):
- Headroom: `uv pip install "headroom-ai[proxy,code]"` dentro `spawn-env`. Senza `[ml]` all'inizio: niente modello Kompress da Hugging Face (connessione lenta); JSON e codice compressi, la prosa no. Il modello si aggiunge dopo con un tasto.
- RTK: `winget install rtk-ai.rtk` scegliendo l'edizione `rtk-oss` (solo Apache-2.0). Niente `rtk-proxy` (licenza BUSL).
- Telemetria: `HEADROOM_TELEMETRY=off` sempre nell'ambiente del motore; RTK è già spento di default.
- Controllo all'avvio dello spawn: se mancano, la card "Prepara spawn" li mostra in rosso con il tasto "Installa" (che chiede conferma). Senza di loro la modalità A non parte, come per caveman.

Uso per modo:

| | Stanza spawn (A) | Compatibile (B e C) |
|---|---|---|
| Headroom `compress()` su chat, board, risultati tool | sì | sì |
| CCR: tool `recupera` per rileggere l'originale | sì | sì |
| Compressione della sola parte nuova (cache del provider salva) | sì | sì |
| `SharedContext` per i passaggi di consegne tra ruoli | sì | no (passaggio solo in chiaro) |
| Output shaper (risposte più asciutte), insieme a caveman | sì | no |
| RTK sui comandi shell dei ruoli che hanno la shell | sì | sì, solo per i ruoli spawnati |
| Contatore dei token risparmiati in card | sì | sì |

### 3.1 Headroom e RTK dentro la chatroom (tutti gli agenti, modi B e C e stanze normali)

Tre strade possibili, scelta la prima:

| Strada | Come | Giudizio |
|---|---|---|
| **Alla fonte (scelta)** | La chatroom comprime da sola ciò che restituisce agli agenti: `chat_read`, `chat_wait`, board, notebook, risultati research, export. Lo fa chiamando un piccolo servizio di compressione locale (Headroom, nell'ambiente `spawn-env`). Per RTK il plugin ha già i suoi hook: si aggiunge un `PreToolUse` sul Bash che passa i comandi da `rtk rewrite` **solo per gli agenti di una stanza** | Tocca solo la chatroom; nessuna impostazione globale cambiata; se Headroom o RTK mancano tutto funziona come oggi |
| Proxy (`headroom wrap claude`) | Tutto il traffico di Claude Code passa dal proxy di Headroom | Cambia `ANTHROPIC_BASE_URL` per tutte le sessioni, anche fuori dalla chatroom; un proxy fermo blocca il lavoro. Scartato |
| Patcher dopo l'installazione (`rtk init -g`, modifica delle impostazioni globali) | Riscrive la configurazione di Claude Code | Agisce su tutte le sessioni e si rompe agli aggiornamenti. Scartato |

Regole della strada scelta:
- **Ordine:** Headroom lavora su ciò che l'agente **legge**, caveman su ciò che l'agente **scrive**. Quindi Headroom viene prima di caveman e non si pestano i piedi. L'output shaper di Headroom resta spento quando caveman è attivo (farebbero lo stesso lavoro).
- **Cosa si comprime:** solo i contenuti grandi e ripetitivi (log, JSON, tabelle della board, risultati, codice, messaggi lunghi oltre una soglia, es. 1.500 token). I messaggi brevi della chat e **tutti i messaggi di Adrian** passano intatti.
- **Recupero:** ogni blocco compresso porta un segno `⟨compresso: id⟩` e la chatroom ha un tool `chat_expand(id)` che restituisce l'originale (CCR di Headroom).
- **Cache:** si comprime solo il nuovo; ciò che l'agente ha già letto non cambia, così la cache del provider resta valida.
- **Interruttore:** in ogni stanza, nel pannello 🛋 (acceso di default in B e C, obbligatorio in A), con contatore dei token risparmiati.
- **RTK:** il hook riconosce gli agenti della stanza dal registro che `register.ts` scrive già; per tutte le altre sessioni il comando passa senza modifiche.

## 4. Chiavi e provider

- OpenRouter: OAuth PKCE dal browser come nella versione 1 (callback sul viewer, `state`, chiave cifrata con DPAPI in `~/.claude/chatroom/secrets/`, mai in stanza, chat, log o URL, card con limite e quota free da `GET /key`).
- Altri provider: campo password inviato solo a localhost, stessa cifratura. Più chiavi numerate per provider come in FCC.

### 4.1 Prima inizializzazione (obbligatoria, al primo `/spawn`)

La card "Prepara spawn" elenca **tutti i provider con modelli free**, uno per riga: logo, cosa offre gratis, **link esatto della pagina dove registrarsi e creare la chiave**, campo per la chiave, tasto "Verifica" (prova la chiave con la lista modelli, mai con una completion), stato verde o rosso. Lo spawn parte solo quando la lista è completa (vedi D8 per i provider dove non riesci a registrarti).

| Provider | Dove registrarsi e prendere la chiave | Cosa c'è di gratis |
|---|---|---|
| OpenRouter | login dal browser (PKCE), oppure https://openrouter.ai/keys | 20 modelli `:free` |
| NVIDIA NIM | https://build.nvidia.com/settings/api-keys | tutto il catalogo con limite di frequenza |
| Groq | https://console.groq.com/keys | free tier su tutti i modelli |
| Google AI Studio (Gemini) | https://aistudio.google.com/apikey | free tier |
| Mistral La Plateforme | https://console.mistral.ai/ | piano Experiment |
| Mistral Codestral | https://console.mistral.ai/ (chiave separata) | codestral, devstral |
| Cerebras | https://cloud.cerebras.ai | free tier |
| SambaNova | https://cloud.sambanova.ai/apis | free tier |
| Cohere | https://dashboard.cohere.com/api-keys | chiave trial |
| Cloudflare Workers AI | https://dash.cloudflare.com/profile/api-tokens (serve anche l'account ID) | neuron gratis ogni giorno |
| Hugging Face | https://huggingface.co/settings/tokens | crediti mensili |
| SiliconFlow | https://cloud.siliconflow.com/account/ak | modelli piccoli gratis |
| Ollama Cloud | https://ollama.com/settings/keys | quota gratis |
| Kilo | https://app.kilo.ai | 17 modelli free |
| OpenCode Zen | https://opencode.ai/auth | 46 modelli free |
| Vercel AI Gateway | https://vercel.com/docs/ai-gateway | crediti e 5 modelli free |
| ZenMux | https://zenmux.ai/platform/pay-as-you-go | 2 modelli free |
| OrcaRouter | https://www.orcarouter.ai/console | 5 modelli free |
| TokenRouter | https://www.tokenrouter.com/ | glm-5.3 free |
| NaraRoute | https://router.bynara.id/keys | modelli free |
| xKiro | https://xkiro.com/dashboard/api/keys | modelli `:free` |
| LLM7 | https://dash.llm7.io/ | gratis |
| Z.ai API | https://z.ai/manage-apikey/apikey-list | glm flash free |
| Agnes AI | https://agnes-ai.com/ | 3 modelli flash free |
| Poolside | https://platform.poolside.ai/ | laguna free |
| Novita | https://novita.ai/settings/key-management | 1 modello free |

I link vengono dal catalogo di FCC e si ricontrollano all'implementazione; l'elenco si aggiorna da solo quando il catalogo trova un provider nuovo con modelli free.
- Test anti-fuga in ogni run della suite: nessun `sk-or-v1-` e nessuna chiave nota in stanza, log, transcript, export.

## 5. Catalogo: ping, coda benchmark, lista

```
scoperta → identità comune → ping → coda benchmark (timeout) → lista con AA → aree migliori → scelta → analisi
```

0. **Tutti i free insieme**: la vista di default unisce i modelli free di tutti i provider della sezione 4.1 in una sola lista (non solo OpenRouter). Filtro "anche a pagamento" disponibile ma spento.
1. **Scoperta** per ogni provider configurato: liste pubbliche (OpenRouter, Kilo, OpenCode Zen, NIM, Hugging Face) o con chiave, più models.dev come riserva. Record unico `{adapter, model_id, canonical_id, nome, tools, ctx, free, prezzo, limiti}`.
2. **Identità comune**: lo stesso modello visto da più provider diventa una scheda sola con più strade (es. nemotron-3-ultra gratis su OpenRouter, Kilo, Zen, NIM).
3. **Ping** solo sui candidati (gratis o scelti), timeout 20 s, una volta ogni 12 ore per strada, passando dal limitatore. Dove esiste un segnale gratuito si usa quello: per OpenRouter `/endpoints` (uptime e latenza) e `/key`, ping vero solo allo spawn. Locali: solo `/v1/models`, mai una completion (il llama-server di altre sessioni non si tocca).
4. **Coda benchmark**: chi risponde entra in coda. Fonti veloci 30 s; ricercatore Haiku per i benchmark di nicchia 10 min. Allo scadere mostra ciò che ha trovato con l'etichetta "parziale".
5. **Lista**: il modello compare subito con valore AA (o "n.d."), pallino della strada e latenza. La riga "aree migliori" si riempie quando arriva la ricerca.

## 6. Schede benchmark

Come nella versione 1, invariato: quattro strati di fonti (OpenRouter, Artificial Analysis, fonti pubbliche, ricercatore Haiku), ogni punteggio con fonte, data, indipendente o dichiarato, posizione rispetto alla frontiera; glossario con una riga semplice per benchmark; **10 punti forti** per modello (al massimo 3 per ambito, pesati per indipendenza, badge 🏆); tutti i benchmark sceglibili per i grafici, ognuno con la sua descrizione; confronto tra modelli.

## 7. Ruoli al posto di agenti

- Un ruolo è: nome, missione, tool permessi, stato (task, decisioni, punti aperti), note di passaggio. Il modello è la sua **strada attuale** e può cambiare.
- Caveman ultra obbligatorio nel prompt di sistema di ogni ruolo.
- Prefisso di sistema identico byte per byte e `session_id` fisso per strada, così la cache lavora.
- Tool di base: leggere e scrivere in chat, board, notebook, `recupera` (Headroom). Shell e file solo per i ruoli a cui li dai tu, sempre con RTK.
- Il motore conserva e rimanda intatti i `reasoning_details` (mancava nella versione 1), mette sempre `max_tokens` e controlla i token visibili, ripara le tool call rotte, ritenta senza `reasoning` se il provider lo rifiuta.

**Passaggio di contesto e cambio di strada**, in quest'ordine:
1. Contesto oltre l'80% (stimato con tiktoken) o errore `context_window_exceeded`: il ruolo scrive le consegne (compresse con Headroom, SharedContext in modalità A).
2. Stesso modello su un altro host della sua scheda (per 429, quota finita, provider giù).
3. Modello diverso: **solo scelto da te** (sezione 8).

Al cambio di host la cache si perde (la card lo dice) e il reasoning non passa: passa solo il riassunto in testo, come nel replay di FCC.

## 8. Ruolo senza token: sostituzione

- Quando un ruolo ha esaurito tutte le strade del suo modello, lo stato diventa "senza token".
- Nella lista dei partecipanti il nome prende un'icona che lampeggia a intermittenza (📟 con impulso). Nell'ufficio 3D la sua figura lampeggia uguale. Suono: spento di default (l'audio delle stanze resta muto); se lo vuoi, un beep breve attivabile nelle impostazioni.
- Clic sul nome o sulla figura: si apre la scheda "Sostituisci". Mostra tutti i modelli disponibili ordinati per adatti al ruolo: prima chi ha tool e contesto sufficiente, poi per punteggio nelle aree del ruolo (gli ambiti del suo task confrontati con i punti forti), con grafici dei benchmark, 10 punti forti, prezzo o free, latenza.
- Scegli, il nuovo modello riceve le consegne e il ruolo riprende. La chat mostra "ROLE ora gira su X".

## 9. Card in chat

Stesso sistema della versione 1 (messaggio `card` con testo di riserva, registro dei renderer, `POST /card_action`, stato in `ROOM/cards.json`). Card: Prepara spawn (Headroom, RTK, chiavi), Collega OpenRouter, Aggiungi provider, Catalogo, Grafico AA, Studio, Scheda modello, Confronto, Crea ruolo e assegna, Stato ruolo (strada, token, costo, risparmio Headroom e RTK, quota free), Sostituisci.
La riscrittura del render chat richiede tutti i test retroattivi (sezione 12).

## 9.1 Tema della stanza multi-agenti: "l'Hangar delle Porte"

La stanza spawn (modo A) diventa **la stanza multi-agenti** e ha un ambiente suo, automatico come il laboratorio per le research (`mode == spawn`). Le stanze normali restano ufficio, le research restano laboratorio.

Idea: un hangar notturno dove gli agenti arrivano da altri mondi attraverso porte, una per provider.

- **Porte dei provider:** un arco luminoso per ogni provider collegato, col suo colore e logo. Un ruolo che entra esce dalla porta del suo provider con un lampo; quando cambia host entra in una porta ed esce dall'altra. Porta rossa = provider senza quota.
- **Tabellone partenze:** grande display a palette che girano, come in aeroporto: ruolo, modello attuale, host, stato ("in servizio", "cambio porta", "senza token" lampeggiante).
- **Tavolo olografico dei benchmark:** al centro, mostra in 3D il grafico AA e i punti forti dei modelli scelti (riusa `office-viz.js`).
- **Serbatoi di quota:** un serbatoio per provider che si svuota con la quota free del giorno.
- **Pressa di Headroom e imbuto di RTK:** macchine che lavorano quando comprimono, con il contatore dei token risparmiati.
- **Ruolo senza token:** la figura si ferma, sopra la testa un 📟 che lampeggia a impulsi (come nella lista partecipanti); clic per la scheda Sostituisci.
- **Luci:** blu notte e acciaio, neon colorati per provider, strisce di sicurezza gialle e nere sulle piste.

Texture nuove, procedurali in canvas come `office-floor.js` e `office-lab.js`, niente download: lamiera a rombi del pavimento, strisce di sicurezza, piste d'atterraggio luminose, pareti in pannelli rivettati, fibra di carbonio per i banconi, griglia neon, alone delle porte, palette del tabellone, vetro olografico.

**Easter egg** (tutti muti; il suono resta spento come nel resto della chatroom):
1. Codice Konami davanti al tabellone: tutte le palette girano e scrivono i crediti ("ADRIAN CIPRIAN IANCU · ArtyomITA").
2. Sette clic su una porta qualsiasi: ne esce un lama che attraversa l'hangar (omaggio a llama.cpp).
3. Pittura rupestre di caveman su una parete: al clic mostra quanti token ha risparmiato caveman in questa stanza.
4. Quando un ruolo usa un modello primo in un benchmark 🏆, sulla sua scrivania cade un piccolo trofeo con il nome del benchmark.
5. Tra mezzanotte e l'una il tabellone mostra "tutte le porte dormono" per qualche secondo, poi riprende.
6. Porta misteriosa `openrouter/free`: ogni tanto ne esce una sagoma col punto di domanda e il nome del modello che il router ha scelto.

File: `office-hangar.js` nuovo (tema, texture, oggetti, easter egg); `office.js` cambia solo dove sceglie il tema. Stesse regole di prestazioni della 0.12: frame time e draw call misurati prima e dopo, prova a 375 px.

## 10. Limitatore centrale e costi

- Uno solo, nel server del viewer, per chiave e per modello, logica di FCC (finestra, concorrenza, una sonda di recupero mentre gli altri aspettano, 10 tentativi da 2 a 60 s, `Retry-After`).
- Rispetta i limiti free (OpenRouter 20 rpm e quota giornaliera da `/key`, NIM circa 40 rpm, Groq RPM e TPM con correzione di `max_tokens`).
- Modalità solo free: nessuna strada a pagamento entra nella catena. A pagamento: tetto in dollari per ruolo e per stanza, somma di `usage.cost`.
- Errori 402 e 403 fermano il ruolo con card che spiega.

## 11. README

In fondo al README del plugin: "La modalità spawn adatta codice di free-claude-code (Alishahryar1, AGPL-3.0) e usa Headroom (Apache-2.0) e RTK (Apache-2.0)", con link.

## 12. Test

- Tutti quelli della versione 1 (PKCE, DPAPI, anti-fuga, catalogo su fixture, 10 punti forti, validatore schede, server finto con 429, 402, 403 e stream interrotti, viewer su 8775 e 8776, 375 px).
- Nuovi: cambio di host con passaggio di contesto; stima contesto e soglia 80%; riparazione tool call; replay di `reasoning_details`; limitatore condiviso con 3 ruoli sulla stessa chiave (nessun 429 provocato da noi); Headroom acceso e spento dà la stessa risposta su casi noti; RTK solo sui ruoli con shell; modalità B e C non toccano gli altri agenti; icona lampeggiante e scheda Sostituisci.
- Test portati da FCC per i moduli copiati (adattati).
- Suite completa `run_all.sh` più test del motore prima di ogni commit.

## 13. Fasi

| Fase | Contenuto | Peso |
|---|---|---|
| F0 | Ambiente `spawn-env`, Headroom, RTK, scheletro del motore AGPL separato | 5% |
| F1 | Chiavi (PKCE, provider), card Prepara spawn | 8% |
| F2 | Adapter da FCC, limitatore centrale, errori, stream | 20% |
| F3 | Catalogo, identità, ping, coda benchmark | 12% |
| F4 | Card in chat e test retroattivi | 15% |
| F5 | Schede benchmark, glossario, 10 punti forti, grafici | 15% |
| F6 | Ruoli, passaggio di contesto, cambio host, sostituzione con icona lampeggiante | 15% |
| F7 | Hangar delle Porte: tema, texture, oggetti vivi, easter egg | 7% |
| F8 | Modi B e C, rifinitura estetica, i18n, test finali, release 0.13.0 | 3% |

Costruzione: stanza cantiere 0.13, io LEAD.

| Ruolo | Modello | Lavoro |
|---|---|---|
| PORTE | Opus 5.5 high | adapter da FCC, limitatore centrale, errori, stream |
| CATALOGO | Opus 5.5 high | updater, identità, ping, coda benchmark, schede, glossario |
| VETRINA | Opus 5.5 high | card in chat, riscrittura del render, test retroattivi |
| REGIA | Opus 5.5 high | ruoli, passaggio di contesto, cambio host, sostituzione, Headroom e RTK nella chatroom |
| ALLESTITORE | Opus 5.5 high | Hangar delle Porte: `office-hangar.js`, texture procedurali, oggetti legati ai dati, easter egg |
| OCCHIO | Sonnet 5.5 xhigh | verifica grafica nel browser (8775, 8776, 375 px, tema chiaro e scuro) |
| CERCATORI | Sonnet 5.5 xhigh, solo se servono | link di registrazione, limiti free reali, benchmark di nicchia per il glossario |

Questa scelta di modelli vale per la stanza 0.13 (eccezione alla regola generale "agenti su Sonnet"). Worktree separato, MCP fermo sulla 0.12.1, regole git della 0.12, audio muto, chiavi mai in stanza.

## 14. Decisioni di Adrian (26/10/2026)

- **D-LIC** Motore spawn come programma separato AGPL-3.0 in `plugins/chatroom/spawn/` (LICENSE AGPL, NOTICE di FCC); il resto della chatroom resta MIT e parla col motore solo via processo e HTTP locale.
- **D1** Shell e file solo ai ruoli che sceglie Adrian, sempre con RTK.
- **D2** Sì alla chiave Artificial Analysis (gratuita, 100 richieste al giorno), inserita nella prima inizializzazione come gli altri provider.
- **D3** No allo screenshot del sito AA: solo i nostri grafici.
- **D4** `data_collection: deny` sempre.
- **D5** Ambiente del motore (Python 3.14 e pacchetti), Headroom e RTK scaricati subito, su D:.
- **D6** Il ricercatore Haiku studia una volta tutti i modelli; poi, a ogni nuovo "Studia", solo i modelli nuovi.
- **D7** Nessun suono: beep **luminoso** (icona che lampeggia) più una notifica in chat che nomina il ruolo e il modello da cambiare.
- **D8** Un provider si può saltare, ma resta sempre configurabile in seguito (card Prepara spawn, riga in rosso con "configura").
- **D9** Soglia di compressione Headroom: 1.500 token.
- **D10** Tema: Hangar delle Porte.

### 14.1 Regole della stanza cantiere 0.13

- Gli agenti Opus devono leggere **obbligatoriamente tutto il codice tranne la grafica** prima di scrivere una riga: `chat.py`, `research.py`, `share.py`, `activity.py`, `i18n.py`, `idle_life.py`, `github_data.py`, gli altri script Python, hook (`hooks.json`, `register.ts`), skill, template, guide, test della suite.
- OCCHIO (Sonnet xhigh) legge **solo la parte grafica**, com'è fatta a codice: `viewer.html`, tutti gli `office*.js` (ufficio, laboratorio, giochi dell'arcade, arena, paintball, zombie, pannelli, insegne, tv, timeline, viz, research), `i18n.js`, asset.
- VETRINA e ALLESTITORE, oltre alla lettura obbligatoria, leggono anche i file grafici che devono cambiare.
