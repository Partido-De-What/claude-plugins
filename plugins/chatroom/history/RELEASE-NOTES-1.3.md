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

## 1.3.2, also

- **The mode chosen in the conversation.** The init skill says how to make the user's choice when they answer in the
  conversation, and a post by the user that is only a quick command (`/normale`) runs it instead of leaving it as text.
- **Topics without a room.** `lessons topic list` works without `--room`.
- **Help for one command.** `chat.py init --help` shows init and its options, not every option of every command.

## 1.3.3

Fixes from a night research room that ran heavy GPU jobs for hours.

- **Two heavy jobs at once, never again.** The machine lock was a file created empty and written a moment later: a waiter
  that read it in between took it for free, and two jobs ran together twice. The lock is now the operating system's own,
  released when its process dies.
- **A real queue for heavy jobs.** Jobs wait in one queue, first come first served. `heavy list` shows what runs, who
  waits and the last exits; `heavy pause`, `resume` and `move` change the order; `--key` skips a job that already ended
  well. A heavy job of the room that fails comes to the lead as a CHECK, and the WAKE line says what the machine runs.
  A word with spaces in the command stays one word.
- **The start of an agent.** An agent that ends its first turn before its brief (a style to load, a confirmation) is
  let go at once: the stop hook held it nine minutes, and the brief sent to it waited all that time.
- **Whole messages for who is tagged.** A long message that tags the reader comes whole in `read`, and the hook line
  to the lead keeps up to 4000 characters, so no `expand` is needed for what concerns you.
- **The closing of a rotated agent** lists the report of its live identity, and the output of the closing steps keeps
  its accents on a Windows console.
- **No double wake.** Lines the lead already read from the relay's output (with Read, not a chat.py command) are no
  longer handed to it again.
- **A tag for an agent that ended** prints the SendMessage to send, ready to copy.
- **The relay that stays alive** (`--stream` under Monitor) is explained as the choice for a long night, against the
  relay that is restarted at every wake.

## 1.3.4

- **The chat beside the office on a wide screen.** The chat's side margin centred a 980 pixel column on the whole
  window: beside the office on a 1920 screen that was 488 pixels a side, and the buttons went one per line. The margin
  now comes from the chat's own column. 1.3.1 had fixed only columns under 700 pixels, which is why it still broke at times.
- **Silent by default.** Every page of the office opens with the sound off, also after you turned it on last time: your
  levels stay, and the sound comes back from the mixer.

## 1.3.5

- **Lending an agent to a friend works.** The lend button never lent: a name in the viewer's code shadowed the lend
  function and every lend ended in an error the panel did not show. Now the panel says why a share action fails, a
  lend can last up to three hours, and lend requests survive a restart of the viewer (kept in `common/share.json`),
  so a second helper no longer gets the name AIUTO1 again and writes over the first one's prompt. A helper's folder is
  named after the helper (`common/help-aiuto2`).
- **When the host closes the viewer.** The friend's panel says the host's viewer looks closed instead of a socket
  error, and it asks less and less often (one call every 10 s at most, it was three a second). A line the host
  refuses for good is dropped and said, instead of blocking the queue forever. A helper that posts in `common/` is told
  when the room's viewer is off.
- **`post --common`** refuses `--status`, `--idle` and `--finding` (a helper's status reached the friend's chat as raw
  JSON), keeps `--reply N`, sends the words beside `--file` as a line of their own, and says when a long text is cut.
  Documents in `.mjs`, `.html` and `.css` keep their extension.
- **The user never waits for the room's pace.** A message of the user wakes the lead at once (friends and other leads
  keep the pace).
- **A relay that is down** is said in a last short line after every post of the lead, so `post | tail -1` shows it too.
- **`heavy -- "the whole command"`** works again as before 1.3.3.
- **Updated with the session open.** `init` from an old copy of the plugin says that skills, agent types and hooks
  stay old until Claude Code restarts, and the update skill says not to open rooms before the restart.
- **Claude not logged in.** The searchers, the reflect of the closing and the Claude arm of `spawn consult` check
  `claude auth status` first and say it, instead of a job that dies in its log; the doctor has a line for it.
- **Previews: lens and frame studio.** Each tile has a lens (wheel to zoom) and a studio: 31 frames around the moment
  of a video, the picture itself, or two seconds of a page filmed through the browser's tab capture. Pick one or more
  frames, make one sharper, draw with a pen or a highlighter, and send them to the chat as attachments. Preview videos
  can be sought (the server answers byte ranges).
- **Microphone.** A button beside Attach dictates into the message box through the browser's speech recognition;
  where there is none (the desktop app's pane) it puts the cursor in the box and says to use Windows dictation, Win+H.
- **Small ones.** `inbox.py --help` and unknown options behave; the lead's guide says `--until-tag` belongs to
  `inbox.py`; the doctor names the module missing for the spawn keys; `read --since #N` with nothing new says so.

## What I did not do

- The gate runs only on the timed wakes of the relay; messages that need the lead still wake it at once.
- The END line is asked in the prompt and once more at the hand-back: an agent that still skips it has no line in the closing, nothing is invented.
- The update check needs the network: offline, the room starts as before.
