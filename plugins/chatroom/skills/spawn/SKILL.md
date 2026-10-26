---
name: spawn
description: Bring agents that run on external free models (OpenRouter, NVIDIA NIM, Groq, Gemini and the other free providers) into a chat room, as roles that survive a change of model. Use when the user runs /spawn, asks for agents on free or external models, or for a spawn room. Without a room it opens a spawn room (the Hangar); inside a normal or research room it adds the roles there.
argument-hint: "[what the roles should do]"
---

# Spawn: roles on external models

The user asked for: $ARGUMENTS (in Codex this stays as written: the request is the user's message)

CHAT is `${CLAUDE_PLUGIN_ROOT}/scripts/chat.py` (in Codex, this SKILL.md's path with `skills/spawn/SKILL.md` replaced by
`scripts/chat.py`). The spawn mode needs Python 3.14 and the packages of `uv.lock`: chat.py runs itself through `uv run`
when it is started by an older Python, so nothing changes in the commands below.

A role is a name, a mission and a model; the model can change, the role keeps its history and its notes. Roles run as
threads of the room's viewer (`serve`): keep the viewer running, they stop with it and start again with it. Every request
goes through one limiter that keeps to the free tiers' limits. Only free hosts are used.

## 1. Which mode

Run `python "CHAT" rooms`.

- **A, a spawn room** (no room, or the user wants a new one): `python "CHAT" init --spawn --room "ROOM" --topic "..."
  --title "..." --lang <it|en> --user-name <USER> --profile "LEAD|👓|#6c5ce7|<your role>|<your model>|<your effort>"`, then
  start the viewer as in the chatroom start skill (step 3). Its office is the Hangar of the Doors. Claude agents join it
  only when the user asks for them by name.
- **B, a normal room** or **C, a research room** that is already live: use that room. The roles join its participants; in
  a research room they get the kernel's `research` tool, and the kernel holds them to their research roles.

## 2. Prepare: keys, Headroom, RTK

`python "CHAT" spawn --room "ROOM"` posts the Prepara spawn card in the chat. The user fills it in the viewer: for each
free provider the link to sign up and create the key, a field for the key (sent only to this computer, kept encrypted,
never in the chat, a log or a URL), Verify, Skip (a skipped provider stays configurable). OpenRouter can log in from the
browser. Headroom and RTK show there too, with Install (it asks first). A spawn room (A) does not start without Headroom.

Never ask the user to paste a key in the chat or in this conversation, and never write one anywhere.

## 3. Create the roles

When the card is complete, `python "CHAT" spawn create --room "ROOM"` posts the Crea ruolo card: the user picks the model
from the catalog (scores, charts, ten strengths, free hosts, latency), names the role, writes its mission, and gives it the
shell only if they want to (the shell starts in the role's own folder, through RTK; the folder is where it starts, not a
wall: a role with the shell can reach what the user's account reaches, so say so when the user gives it). Suggest names and missions from the
request, but the user chooses the models.

## 4. While the roles work

Follow the room as in the chatroom start skill (relay, WATCH lines, CHECK lines). What the runner does by itself:

- context over 80% of the model's window: the role writes its handover, it goes to its notebook, the history starts again
  from it (a 🧳 line in the chat);
- a host out of quota or failing: the same model on another free host (a 🚪 line; the provider's cache is lost);
- no host left: the role is without tokens (📟, blinking in the viewer and in the Hangar) and a message tags the user, with
  the Sostituisci card. Only the user picks another model;
- 401, 402, 403: the role stops (⛔) and the message says why: the key or the account needs the user.

A role tags others in the chat like any agent, but it cannot ping a Claude agent: that agent sees it at its next read or
wait. To tell a role something, tag it in the chat.

## 5. The end

As in the chatroom close skill. To stop the roles, stop the viewer.
