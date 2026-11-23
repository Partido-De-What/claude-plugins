# chatroom 1.3

## Why this release

I read how two other teams build the layer around their agents: DeepSeek Harness, where every part is a plugin and the session log is the only truth, and Qwen Code, which ships something new every week. Seven of their ideas fit a room of agents well, and each one removes a wake, a loop or a lost piece of work.

## What changed

- **A wake only when something happened.** `alerts --heartbeat N --wake-gate "cmd"` runs a small check at each timed wake and wakes the lead only when it prints something. A quiet hour costs nothing.
- **Final reports the closing can read.** Every final report starts with one line, `END: completed|partial|blocked|error; files: ...; gaps: ...`. The room keeps it, and `close-steps` lists each agent's line, so the summary does not depend on reading free text.
- **A nudge to conclude.** An agent that reads fifteen files in a row without changing anything or writing a message is told to conclude: write what it found, change what it meant to change, or ask.
- **Nothing held by an agent that left.** An agent that leaves the room releases its locks, its places in the queues and its device hold, and the room says so.
- **Loops reach the lead.** The same refusal three times in a row to one agent becomes a check for the lead, with where to read the last attempt.
- **A rotation that keeps the thread.** `rotate` gives the fresh agent the last eight messages that concern it, not only its notes.
- **What was tried, not only why it failed.** A refused post keeps its text in the room's events, so the harness learns from the attempt.

## What I did not do

- The gate runs only on the timed wakes of the relay; messages that need the lead still wake it at once.
- The END line is asked in the prompt: an agent that skips it simply has no line in the closing, nothing is invented.
