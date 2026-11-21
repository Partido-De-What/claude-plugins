---
name: close
description: Close the running agent group chat - ask every agent for its final vote and report, export the transcript, and summarize the outcome for the user. Use when the user wants to end a /chatroom:start discussion.
argument-hint: "[optional closing instruction]"
---

# Close the chat room

Extra instruction from the user, if any: $ARGUMENTS (in Codex this stays as written: the request is the user's message)

CHAT is `${CLAUDE_PLUGIN_ROOT}/scripts/chat.py`. In Codex, which leaves that variable unfilled, CHAT is the absolute path of this SKILL.md with `skills/close/SKILL.md` replaced by `scripts/chat.py`. In PowerShell, pipe the text to `post` with `$OutputEncoding = [System.Text.UTF8Encoding]::new($false); @'` ... `'@ | python "CHAT" post ...` instead of the heredoc.

1. Find the room of the chat running in this session (ROOM) and read `ROOM/roster.json`.
2. Post the closing notice as the lead:

```bash
python "CHAT" post --room "ROOM" --as LEAD <<'EOF'
CLOSING: the user is closing the chat. Post your final vote on the latest plan or conclusion, with any reservation, then stop and return your final report.
EOF
```

   Add the user's extra instruction, if there is one, to that message.
3. Look at `python "CHAT" status --room "ROOM"`: `closing.missing` are the agents that have not answered yet, `closing.gone`
   the ones whose run already ended. In Claude Code the room hands the CLOSING to the agents it holds: do not SendMessage
   them (an agent that already finished starts again and reports twice). SendMessage only the `gone` ones that still owe a
   vote, and tell the user which ones closed without one. In Codex send the notice with send_message, or followup_task if
   an agent's turn has ended.
4. Wait for the agents' final reports (in Claude Code they arrive as notifications; in Codex use `wait_agent`; no separate close call is needed), then run the
   fixed closing steps, the one list of the plugin (`task close-all`, `transcript`, `cost`, `lessons close`, `procs close`):

```bash
python "CHAT" close-steps --run --room "ROOM" --as LEAD
```

   When a CLOSED ended the room, your relay already ran them and handed you their output: do not run them twice, read it.
   The output ends with what to tell the user, the topic question (3.2) and the line on the plugin's bugs (3.4): do them.

5. Summarize for the user from the transcript and the reports only: the key moments, the outcome (the closed or latest plan with its votes), the disagreements still open, and the number of messages per agent, and what each agent and you cost (the `cost` table: tokens, cache rewrites, the protocol's share). Mention where the transcript file is.
   Then give the user the "chat improvement" that `lessons close` printed, in its parts and as it printed them: a. the auto-harness (what the harness learned and applied by itself, with local and general apart), then, only when it printed them, b. the improvements and bugs of the session still to decide and c. the bugs of the plugin. Do not add parts it did not print: for a user who is not the plugin's creator there is only a, and a line saying that scores 1 to 3 and the plugin's bugs are not kept: give it to the user as it is (the creator is a file named `creator` in the chatroom folder of their Claude config, or CHATROOM_CREATOR=1; nobody creates it by itself). A 4 or 5 the gate refused is listed under a as not applied, with its reason: give it too.
6. About `procs close` (one of the steps above): it ends the test viewers of the room (a room in the temporary folder) and the test ones left without a starter, and prints each one it ended. The user's viewer stays so they can scroll back: if it printed a line for it (port and number of clients), give that line to the user and stop it only if they ask (`procs stop PID`). With nobody looking at it a viewer of a closed room ends by itself after `viewer_idle_min` minutes (30; in the user's settings.json, 0 = never). `procs sweep` lists what is left over on the machine and `procs sweep --yes` ends it: ask the user first.
