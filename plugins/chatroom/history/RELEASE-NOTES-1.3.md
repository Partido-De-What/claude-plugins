# chatroom 1.3

## Why this release

I read how four other teams build the layer around their agents: DeepSeek Harness, where every part is a plugin and the session log is the only truth; Qwen Code, which ships something new every week; Pi, which keeps its prompt under a thousand tokens on purpose; and Hermes, which learns from every session. Fourteen of their ideas fit a room of agents, and each one removes a wake, a loop or a lost piece of work.

## What changed

- **A wake only when something happened.** `alerts --heartbeat N --wake-gate "cmd"` runs a small check at each timed wake and wakes the lead only when it prints something. A quiet hour costs nothing.
- **Final reports the closing can read.** Every final report starts with one line, `END: completed|partial|blocked|error; files: ...; gaps: ...`. The room keeps it, and `close-steps` lists each agent's line, so the summary does not depend on reading free text.
- **A nudge to conclude.** An agent that reads fifteen files in a row without changing anything or writing a message is told to conclude: write what it found, change what it meant to change, or ask.
- **Nothing held by an agent that left.** An agent that leaves the room releases its locks, its places in the queues and its device hold, and the room says so.
- **Loops reach the lead.** The same refusal three times in a row to one agent becomes a check for the lead, with where to read the last attempt.
- **A rotation that keeps the thread.** `rotate` gives the fresh agent the last eight messages that concern it, not only its notes.
- **What was tried, not only why it failed.** A refused post keeps its text in the room's events, so the harness learns from the attempt.
- **A check for updates before the room starts.** If a newer chatroom is out, `init` stops and you choose: update now, or go on with the version you have.

## What I took from Pi and Hermes

- **One shape for an agent's state.** Goal, constraints, done, doing, blocked, decisions, files, next, what must not be lost: the parts a good compaction summary keeps, now the parts of the notebook.
- **Lessons with a budget.** The lessons that reach every prompt share a budget of characters: a new one past it asks to merge or shorten, never a silent cut. A lesson that reads like a log, with a date, a PR number or a quote, is refused: a lesson is a rule and one reason.
- **A second look at the end.** `close-steps --reflect` asks a Sonnet with high effort to read the room and propose lessons. They wait for your decision; none is applied by itself.
- **One correction for the final report.** A report without its END line is sent back once, with the line it needs.
- **Skill candidates that age.** A candidate nobody took goes stale after 14 days and to the archive after 30, never deleted; a pinned one stays, and every promotion is written down with the hashes before and after.
- **A loop between two agents.** Two agents that answer only each other for six messages, with nothing moving on the board, come to the lead as a check.

## 1.3.1

With the office open, the chat sits in a column of about 600 pixels, and it was laid out as on a wide screen: the toolbar wrapped one button per line and the messages were left 26 pixels. The chat now takes the compact layout whenever its own column is narrow. The Skill, Spawn and Previews screens say that Esc goes back to the chat.

## 1.3.2

Fixes from a demo room run in the desktop app.

- **The report after the exit.** When the room let an idle agent go, it asked for the report and then put it off again,
  so four agents of four went without one. Once the exit is decided, the report goes through, and the agent is not held
  another nine minutes first.
- **One exit, one event.** The exit was written twice per agent, and counted as a fault. An idle agent nobody needed
  is now one plain event, outside the lessons.
- **The agent type in the desktop app.** An agent the lead wrote in the roster before its first call never got its
  type recorded. It does now, and a rotated agent keeps the hour of cache of its role.
- **Demo rooms.** `config demo=on` keeps idle agents at their desks while someone has the viewer open.
- **Automatic lines wake nobody.** The line the skill panel writes for a search went out under the user's name and
  woke every agent. It now wakes only the agent it tags.
- **`prompt --stub` alone** writes the prompt to `ROOM/prompts/NAME.md` and prints the three lines, never the whole prompt.
- **No second delivery.** Lines the lead's hook had already shown it are no longer handed again by the relay.
- **`spawn refresh`** updates the catalog from the terminal with one line per provider, and lists the models that
  came out paid only and are not free anywhere yet.

## What I did not do

- The gate runs only on the timed wakes of the relay; messages that need the lead still wake it at once.
- The END line is asked in the prompt and once more at the hand-back: an agent that still skips it has no line in the closing, nothing is invented.
- The update check needs the network: offline, the room starts as before.
