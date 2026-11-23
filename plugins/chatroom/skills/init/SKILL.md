---
name: init
description: Start the chat room in one step - create the room, open the live viewer on the chat, and let the user choose in the chat between a normal room (the lead sets it up with them) and a research room (contract first, then fixed research roles). Use when the user runs /chatroom:init or wants to start the chat room and decide its mode from the viewer.
argument-hint: "[optional: topic or title]"
---

# Start the chat room and let the user choose its mode

The user asked for: $ARGUMENTS (in Codex this stays as written: the request is the user's message)

You are the lead. CHAT is `${CLAUDE_PLUGIN_ROOT}/scripts/chat.py`. In Codex, which leaves that variable unfilled, CHAT is the absolute path of this SKILL.md with `skills/init/SKILL.md` replaced by `scripts/chat.py`. In PowerShell, pipe the text to `post` with `$OutputEncoding = [System.Text.UTF8Encoding]::new($false); @'` ... `'@ | python "CHAT" post ...` instead of the heredoc.

Every text the room shows for the choice, and every agent prompt, is written by chat.py: you never rewrite them. Once agents work in the room, read section 6b of the chatroom start skill ("The lead's guide"): what chat.py enforces by itself (pings, focus, closing with evidence, proof of done, leases, checks, budget) and what is left to you, mainly reviewing a split vote (`VOTE-NO (LEAD REVIEW)`) and acting on CHECK lines without reading the whole chat into your context. You only fill the data they read (the config with `chat.py config`/`add`, the brief with `chat.py brief`).

## 1. Create the room, asking for the mode

Run `python "CHAT" rooms` first: if the user means a room that is already live, use it instead: open its viewer if it is not running (step 2), then go on from step 4a or 4b by its config (`mode` is `normal` or `research`; in a room opened without the choice ask the user in the room which one).

Put the room in your scratchpad directory when you have one, otherwise in `.chatroom/<short-slug>` under the project. For a research room, prefer a folder outside the repository: inside it, `git clean -fdx` would delete the room and its worktrees. Use the user's language for `--lang` (`it` or `en`); a title from the request if there is one, otherwise a neutral one you can change later.

```bash
# If init stops with UPDATE AVAILABLE: ask the user, update (the chatroom update skill, then a new session) or continue (the same init with --skip-update).
python "CHAT" init --room "ROOM" --ask-mode --lang <it|en> --topic "<the topic in the user's words, or a placeholder>" --title "<title>" --icon "🧪" \
  --user-name <USER or the user's word for it> --profile "LEAD|👓|#6c5ce7|<your role>|<your model>|<your effort>"
```

`--ask-mode` posts the choice card in the chat: two buttons, **Normal** and **Research**; the user can also type `/normale` (`/normal`) or `/research`. The choice is taken once: chat.py refuses a second one.

## 2. Open the viewer on the chat

Start the viewer as in the chatroom start skill (step 3: a preview or launch configuration if one exists, otherwise a background process, never in the foreground):

```bash
python "CHAT" serve --room "ROOM" --port 8765
```

Give the user the address with the chat view: `http://127.0.0.1:<port>/?view=chat`. The office is one click away (the 🏢 and ◫ buttons).

## 3. Wait for the choice

Tell the user in one line that the room is open and waits for their choice in the chat. Then listen: repeatedly run `python "CHAT" wait --room "ROOM" --as LEAD --timeout 100` and read what arrives. A timeout with no message is not the end. The choice arrives as a message of the user that starts with `@LEAD MODALITÀ:` / `@LEAD MODE:`. chat.py hands you, with it, the command of the guide for that mode (`python "CHAT" guide normal` or `guide research`): run it and follow it before anything else. Answer any other message of the user in the room (`post --as LEAD`) while you wait.

## 4a. Normal

The lead's guide for this mode: `python "CHAT" guide normal`.

Keep the room as it is and set it up with the user, in the room: ask the topic, the goal, the participants (roles, models, effort) and the look; wait for their answer before spawning anyone. Then follow the chatroom start skill from "Decide the setup" with these differences:

- the topic profile, only on the user's answer: ask which one the room joins (`python "CHAT" lessons topic list --room "ROOM"`, or a new short name) and bind it with `python "CHAT" lessons topic use SLUG --confirmed --room "ROOM" --as LEAD`; the guide has the ten lines to tell them (`guide normal`, "What the room remembers").
- the room exists: never run `init` again (it would rewrite the config); set the real topic first if init had a placeholder (`python "CHAT" config --room "ROOM" --topic "..." --subtitle "<the goal>"`: the prompts read it); add the participants with `python "CHAT" add --room "ROOM" --participants A,B,C --profile "A|<emoji>|#rrggbb|<role>|<model>|<effort>" ...` and change the look with `python "CHAT" config --room "ROOM" --title ... --subtitle ...`;
- write the brief once: `python "CHAT" brief --room "ROOM" goal="..." style="..." materials="ROOM/DOSSIER.md" constraints="..." closing="..." max=45` (left out: the room's defaults). What the user allowed goes in `permissions="..." --as LEAD`, in the user's words and signed: a permission you only name in the chat is not the agents'.
- each prompt is `python "CHAT" prompt NAME --room "ROOM" --tools mcp --out "ROOM/prompts/NAME.md"` (`--tools shell` in Codex): pass the Agent tool (or spawn_agent) the pointer "Read <absolute path of that file> and follow it", not its text. If something in it is wrong, change the brief or the config and generate it again; do not edit the prompt.

## 4b. Research

Run `python "CHAT" guide research` and follow it: it is the only source of the research procedure (the contract template, `research init`, the team and its efforts, preparing and compacting before the spawn, phases 1 to 6 with their gates, the cycles you assign, the detectors, the report and the cleaning up). Nothing of it is copied here, so a copy loaded in a long session cannot go stale: run the command again when a phase changes and whenever you are unsure of a step.

## 5. When it ends

As in the chatroom start skill (step 7) and the chatroom close skill.
