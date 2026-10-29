# Sciame 29/10/2026, filone 3: harness multi-agente e uso migliore con Claude

Agente Sonnet 5.5. Documentazione code.claude.com letta il 29/10 (pagine senza data). I calcoli sono dell'agente, segnati [calc].

| # | fonte | meccanismo | evidenza | modifica proposta | dove | costo | rischio |
|---|---|---|---|---|---|---|---|
| 1 | doc prompt caching (Claude Code e piattaforma) | TTL della cache dei subagenti: 5 min di default; `subagentPromptCacheTtl=1h` nelle impostazioni, env `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`, o `experimental.cacheTtl: 1h` nel frontmatter (2.1.248+). Scrittura 5 min 1,25x, 1 h 2x, lettura 0,05x | [calc] agente a 600k: lettura calda 30k equivalenti, risveglio a cache scaduta 750k (25x); l'ora conviene da circa 2 risvegli sparsi all'ora | TTL di 1 h per gli agenti delle stanze; attese lunghe senza perdere la cache invece del tetto a 270 s | entrambe | 1 riga | basso |
| 2 | doc sub-agents (auto-compaction), model-config | i subagenti compattano da soli; `autoCompactWindow` 100000-1000000 nel frontmatter; `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` vale anche per loro; il default sul modello da 1M è ~967k, ed è per questo che i nostri restano a 300-850k | [calc] contesto da 600k a 200k = costo per richiesta diviso 3 | `autoCompactWindow: 200000` per gli agenti, `/autocompact 400k` per il lead | entrambe | 1 riga per agente | medio: il riassunto perde dettagli |
| 3 | doc plugin (monitors) | monitor di plugin persistente per la sessione; il tool Monitor scade (5 min default, 30 max) | 51 riarmi in una notte | relay del lead dal monitor di plugin, con digest | entrambe | basso | NOTA NOSTRA: nell'app desktop i monitor di plugin non partono (verificato prima in questa sessione) |
| 4 | doc hooks (SubagentStop) | `decision: block` + `reason` tiene vivo il subagente e gli passa `reason` come istruzione successiva | ipotesi da documentazione, non misurata | un hook SubagentStop che legge la chat: tag per l'agente → block con il tag (niente SendMessage, niente rapporto di ritorno); altrimenti attende nello script | entrambe | medio | alto se non provato: loop, timeout, Windows |
| 5 | doc hooks (async/asyncRewake) | hook in background, exit 2 sveglia la sessione | sezione letta solo in parte | relay one-shot senza tetto di 30 min | normale | basso | non verificato su sessione idle |
| 6 | doc agent-teams (sperimentale) | mailbox nativa, task list con lock, hook TeammateIdle/TaskCreated/TaskCompleted; ~7x token in plan mode | limiti: niente resume in-process, un team per sessione | non migrare; prenderne solo il design | research (prova) | alto | alto |
| 7 | doc cross-session-messaging | SendMessage consegna tra due tool call; `notify_when_idle` solo per sessioni, non per subagenti | | solo lead verso sessioni esterne | normale | basso | basso |
| 8 | blog Claude, 22/10/2026: when to fold subagents into your main agent loop | subagenti solo se il contesto degrada, per lavori paralleli con contesto scartabile, o per tool in conflitto; dividere per contesto, non per tipo di problema; un cliente: loop singolo ~2x più veloce; la scelta dei tool cala oltre 30-50 definizioni | dichiarato da Anthropic | meno ruoli fissi; agenti solo per parallelismo vero | normale soprattutto | basso | serve un eval |
| 9 | arXiv 2608.16801, 2606.00953 Co-Coder, 2609.19759 SAIGE | file condivisi al posto dei messaggi 1-a-1: -42% output a 8 agenti; giro di presentazioni costoso; coordinatore dedicato senza guadagno; partizione per dipendenze: +14% pass, -35% costo | | niente giro di presentazioni né broadcast; discussione nel file con riferimenti; partizione per file | entrambe | basso | basso |
| 10 | Anthropic engineering: multi-agent research system; effective context engineering | multi-agente ~15x token della chat; l'80% della varianza viene dal numero di token; rapporto del subagente 1000-2000 token; non usarlo per molte dipendenze e quasi tutto il coding | | rapporto di ritorno di 1 riga con puntatore; 3-5 agenti in parallelo al massimo | entrambe | prompt | basso |
| 11 | Codex, Gemini CLI, OpenHands, LangGraph | padre bloccato in attesa, oppure checkpoint e resume su evento; nessuno fa polling con timeout per tenere la cache | | l'agente chiude il turno e riparte su evento (SendMessage con cache a 1 h) invece del giro da 270 s | entrambe | basso | basso |

Limiti dalla documentazione: profondità dei subagenti 3, concorrenza 20, `additionalContext` fino a 10.000 caratteri,
Bash in background 30 min (fino a 2 h), `omitClaudeMd: true` nei subagenti (2.1.271), cambiare modello, effort o
plugin MCP invalida la cache.

## Prime 5 proposte dell'agente

1. `subagentPromptCacheTtl=1h` e risveglio su evento invece delle attese da 270 s.
2. `autoCompactWindow: 200000` per gli agenti e `/autocompact 400k` per il lead.
3. Digest degli eventi e relay persistente (nell'app desktop serve un'altra strada: il monitor di plugin non parte).
4. Hook SubagentStop che porta i tag: da provare prima.
5. Meno agenti, niente broadcast, rapporto di 1 riga.

## Non verificato

Costo degli agent teams oltre "~7x"; scadenza reale del monitor di plugin; un hook Stop lungo 50 minuti su Windows;
parti di hooks.md non lette (pagina troncata).
