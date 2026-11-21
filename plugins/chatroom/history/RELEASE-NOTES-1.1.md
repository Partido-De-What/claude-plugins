# chatroom 1.1

## Why this release

Two rooms gave me this list. In one of them, which cleaned up the structure of a long technical document overnight, the agents closed tasks, voted and wrote their notes as they should, and still the room ended with half of its closing forgotten and an empty topic profile. In the other, I sent one long question to 47 free models: 117 tries, 32 answers, six reruns by hand, and the fifth script of mine written around `spawn consult` because the plugin cut the answers I wanted.

## The closing runs itself

When a plan is closed, the lead's relay runs the closing steps by itself, once: open tasks closed, the transcript written, the cost of every agent, what the harness learned, the test viewers shut. Its output ends with what to tell the user, the question about which rules are worth keeping for the next rooms of the topic, and a reminder to file the plugin's own bugs where I see them. The same list is `chat.py close-steps`, and the start skill, the close skill and the lead's guide all point to it. It works from a Codex relay too.

## A harness that collects

- A cause that keeps firing in a room (the same refusal, the same fix by hand) becomes a proposal by itself after ten times, and the closing lists every cause that fired three times or more, even in a first room.
- A lesson scored 4 or 5 is applied at once, but on trial, only in the rooms of the topic where it was born. When a second room has carried it, `lessons accept` makes it general; if it proves wrong, `lessons retire` deletes it. `lessons trial` shows what is on trial, what passed and what was refused.
- Agents propose a lesson at the end of a task, with the case still in front of them: `task done T4 --lesson "what to do" --score 4`.
- A topic keeps up to twelve live lessons instead of eight.

## Tasks, reading and rotation

- The first `task done` of a room that writes code is held before its verify runs, not after, and not at all when the proof already shows the check against the existing code. The agent prompt says so from the start.
- A verify no longer waits hours behind another room's heavy job: it runs beside it and says who holds the machine and since when.
- The lead can close the task of an agent that stopped, with its own proof, and cancel a task that is no longer needed (`task cancel`): it is never offered again.
- `read --ids 15,18,20-23` reads some messages by number. A message the relay showed cut comes back whole at the lead's next read, and reading by number counts as having read, so the relay stops repeating itself.
- `post --no-ping` writes without waking anyone. The lead no longer sees its own banner, nor one on every board line.
- `rotate` goes straight on when the agent has just written its state, and the rotated agent keeps its name in the chat, the roster and the checks.

## One question, every free model

`spawn consult` has no budget of its own any more: the most output each host takes, no deadline unless you give one, an hour of patience for a model that thinks before it writes. A truncated answer, an empty one or a tool call written as text is never saved as an answer: it is asked again, and if it still fails, the outcome says why. Routes that ask for money leave the free list and no longer block the free models of the same host; the limiter says until when a host is blocked (`spawn blocks`, `--clear`); a question too big for a route is not sent. `--web` gives the models web and arXiv search and page reading, `--attach` adds files, `--per-host 5 --stealth --new-since DATE` picks the way I pick, `--claude MODEL` asks `claude -p` beside them, and the same command again asks only the models that fell. While it runs, `stato.json` shows who is thinking and how much.

`spawn council "your situation"` asks the ten smartest free models (or as many as you say) for improvements, a constructive fact-check and brilliant ideas on what you wrote, and gives a fallen model's place to the next one until the number is reached.

## Codex and the rest

Codex runs plugin hooks now, and it would have run the ones I wrote for Claude Code: the Codex manifest points to an empty hooks file, so nothing asks to be trusted. cloudflared is downloaded only when you press its button in the common room's panel, never at the start of a session.

## What I did not do

- In the VS Code extension the plugin's skills are sometimes missing from the `/` menu, an issue of the extension that I cannot fix here; the closing no longer depends on them.
- `spawn consult --web` searches through DuckDuckGo's page and arXiv; I tried it with fake pages in the tests and with real models only without the web.
- A Codex user has not tried this release yet.
