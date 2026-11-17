# chatroom 1.0

This is a draft of the release notes. I will read it again before it goes out.

## Why this release

Version 0.19.9 had a good test room behind it, and then I ran one research room for 28 hours. It had three agents, about 850 messages and 22 runs out of the 40 I had planned. I wrote down every place where the harness got in the way, cost me time or told me something wrong. That list had 72 items. Almost all of them are fixed in 1.0. A few could not be fixed on the machine where I worked, and I list those at the end.

Nothing in 1.0 changes how you start a room. The commands you know still work. What changes is what happens when a room runs for hours without you.

## Research rooms

- **A wrong evaluator can be fixed.** After the baseline there used to be no way to correct an evaluator that was wrong. Now `research reseal --reason "..."` reopens the drafting with the history kept, and the auditor passes the new evaluator again. `research promote` brings a corrected harness into the shared worktree, and the kernel marks the sealed files as text so the line endings stay the same.
- **A moving reference is said out loud.** The kernel records the absolute value of the evaluator for each arm. When the reference drifts, the run line says so. A challenger close to the best is measured next to the best's program in the same run, so a drifting reference no longer turns a real gain into a discard.
- **A run that dies with the machine is not a crash.** It is marked invalid, it does not count in the budget or in the round, and its replica is accepted. A queued run that the precheck refuses stays in the queue and tries again.
- **The board line of a failed run says why.** Every guard is judged before the verdict, so one violated guard does not hide the others. `--guard` can be given more than once, can be an absolute limit (`abs=X`), and the seal checks that the evaluator printed each guard.
- **A recon in phase 1.** Ideas can be proposed as drafts in phase 1, a worker can be assigned from the base, and the lead opens a gate (`research gate --accept` or `--reject`) before the seal, so you see the ideas before any run starts.
- **Runs outside the count.** `--kind probe` takes an environment (`--env K=V`), is registered, and never counts as an attempt. It also works through the MCP tool.
- **Smaller things.** A soft budget warning before the hard one. A silent replica is now announced. The advice to repeat the baseline appears only when the noise is not known. Runs have a class and a level. Shelved ideas live in a register. `research dry-eval` tries the evaluator outside the kernel. `research final --dry` rehearses the final evaluator, and `--artifacts` keeps each run's output.
- **Batches.** `research wait --runs N` wakes the lead after N closed runs. The kernel says when a queued list is finished, and it tells the auditor about a new best.
- **Several things I had to learn by being refused** are now printed in `research status`, and `init` repeats the budget rule and the round size back to you.

## Waiting, holds and the relay

- The shared device has a line. `research hold` takes a place instead of being refused, and `research hold --for NAME` reserves the next turn. A hold whose owner fell is released at once, and the board tells the lead. Stray processes are shown with an owner and an age, and the text names the resource of the contract instead of always saying GPU.
- An agent that holds the device is no longer asked to end its turn or to hand in its report.
- `wait --until-cmd "..."` ends when a shell command exits 0, for work that waits on something outside the room.
- The relay hands over a message once, when it is really handed over. It no longer wakes the lead for a message already read, it keeps its place across a restart, and it prints the whole text of a message that tags the lead. `alerts --follow --heartbeat N` wakes the lead on a quiet room. Messages of a second lead reach the relay too.
- A tag to an agent that ended its run warns the lead at once, with the command to start it again.
- A room can be paused and resumed. While it is paused it raises no CHECK, counts no fall, hands out no task and keeps its agents held. `resume` names who to start again.
- States are right more often: finishing or going idle with nothing in hand is not a fall, any command clears "gone", and a held agent shows as held and not as waiting. Agents that left hours ago drop out of the roster.

## Messages and noise

- Idle lines that repeat the last report are cut to the first line and the number. A long message (over 3000 characters) goes whole into a note, and the chat keeps its start, its tags and a hash. Board lines are cut at a word, not in the middle of one.
- A held draft is no longer lost when another post goes through. A typed post such as a status can no longer let you miss a tag: what it went through without reading comes again at your next command.
- `read --last N` and `read --since #n` bring messages back after a compaction.
- The post answer carries the number and the hour of the message, so agents stop guessing them.
- A status has two percentages, the work and the runs, each with its own name.
- When a task on the board changes, its line names the new version and the files it had before.
- The lead gets a CHECK when an agent is close to a compaction and its notebook state is old or missing, with the hour it was written and the messages since. A task title longer than 200 characters keeps its end as a first note.

## What the room learns

- **Topic profiles.** A room can join a topic, and then what it learns stays for the next room on that topic: the lessons, the sources it read and the skills each role used (`lessons topic skills ROLE a,b`). The profile is versioned, so `lessons topic back SLUG` goes back one step. The lead asks you which topic the room joins and does not choose it alone.
- A cause that keeps firing in a room (the same refusal, the same fix by hand) asks the lead for a lesson, with the command ready. At the closing, the room lists the lessons of its topic with what each of them promised.
- The room's events file now records refusals, kernel actions and the lead's fixes, not only the checks.
- `alerts --from NAME` follows one agent. `spawn consult` asks one question to every host that is available. Each room keeps a register of the sources it read.
- `brief permissions="..."` carries what you allowed into every prompt, signed by the lead. A permission that is only mentioned in the chat does not count for the agents.

## Free models

Models of a provider with a daily quota (xKiro, the Z.ai flash models) were thrown away as not free. They are free while the usage shows an open quota. The line before a big round now names the providers that were skipped for lack of a key, and those whose quota is over.

## The viewer and the update

- The settings panel saves how long an unwatched viewer lives, so you do not need to edit `settings.json`.
- The lock that protects a merge in your copy of the plugin is kept while the merge that holds it is still running.
- `marketplace.json` follows the plugin version, and `doctor` complains when it does not.
- The guides tell the lead about an agent that does not answer, about work in batches and lists, and about the user's own way of working (data, smoke, web, hypothesis, test, web, maybe another round) set against the kernel's phases.

## What I did not do

- I did not run `/chatroom:update` from the real GitHub repository. That needs a push, and I will do it only after I read these notes.
- The automatic roster is not tried in the app with real subagents, and nothing here was tried on Linux or macOS.
- The mouse filter and the toolbar are not tried on a real phone.
- A seed profile of research on a given hardware is not written.
- The old files of 0.18.0 are still not in the repository.
- Some of the new checks read the agent's transcript, so they stay silent where that transcript is not on the machine.
