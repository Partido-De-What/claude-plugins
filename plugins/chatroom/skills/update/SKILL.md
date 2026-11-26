---
name: update
description: Update the chatroom plugin and keep what the user changed - say what will be kept, run the update, merge the user's own copies with the new version, and go through every point that needs a merge with the user, one at a time. Use when the user asks to update the chatroom plugin or runs /chatroom:update.
argument-hint: "[optional instruction, for example: only check]"
---

# Update the chatroom plugin

Extra instruction from the user, if any: $ARGUMENTS (in Codex this stays as written: the request is the user's message)

OLD is `${CLAUDE_PLUGIN_ROOT}` (in Codex, the folder two levels above this SKILL.md's `skills/update/`): the version running now.
`<claude dir>` is `~/.claude`, or the folder in `CLAUDE_CONFIG_DIR`. The user's own copies are in `<claude dir>/chatroom/user/`
(`templates/`, `guides/`, `locales/`), which an update never touches. The scripts below need only Python and are run as they
are written, not through `chat.py`. Nothing here is decided for the user: a merge is applied only after their yes.

## 1. Before: what is theirs

1. Read the version in `OLD/.claude-plugin/plugin.json`.
2. List the files under `<claude dir>/chatroom/user/templates`, `guides` and `locales` (not the folders that start with a dot):
   these are kept whatever happens.
3. `python "OLD/scripts/manifest.py" manifest --verify "OLD"` lists the files of the installed copy that were edited by hand
   (a version before 0.19.9 has no list: say that the new version looks for them itself).
4. If a room of this session is running, say that it keeps running the old version until Claude Code restarts, and ask
   whether to update now or after the room closes.
5. Tell the user in three lines: the version now, how many copies of theirs are kept, how many hand edits will be looked
   for. With "only check" in the instruction, stop here.

## 2. The update

```bash
claude plugin marketplace update artyomita-plugins && claude plugin update chatroom@artyomita-plugins
```

In Codex: `codex plugin marketplace update artyomita-plugins`, then `codex plugin add chatroom@artyomita-plugins`.

NEW is the `installPath` of `chatroom@artyomita-plugins` in `<claude dir>/plugins/installed_plugins.json` after the command.
If its version is the one of step 1, the plugin was already the latest: say so and stop. If the command failed, show its
last lines and stop: nothing was changed.

## 3. Right away: recover and merge

Do not wait for the restart: the new scripts are already on disk.

```bash
python "NEW/scripts/manifest.py" recover
python "NEW/scripts/merge.py"
python "NEW/scripts/manifest.py" recover --list
```

- `Merged: <file>` and `Updated: <file>`: done, the user's change and the new version are both in. Count them.
- `Needs a merge: <file>`: go to step 4 for that file.
- What `recover --list` prints: go to step 5 for each file.
- `Nothing of yours needs a merge.` and an empty list: go to step 6.

## 4. Each file that needs a merge, one at a time

For `<file>` (a path like `templates/agent_prompt.md`) there are, under `<claude dir>/chatroom/user/`: the user's copy
`<file>`, the file it started from `.base/<file>` (it may be missing, coming from 0.18 or before), and the draft
`<file>.merged` with the conflict markers. The new version's file is `NEW/<file>`.

1. Read them. Say in one or two sentences what the user changed and what the new version changed at the same place.
2. Show only the part in conflict, and the text you propose for it: both changes when they can live together, otherwise
   the two choices, and which one you would take and why.
3. Wait for the user's answer.
   - Yes: write the whole resolved file to `<file>.merged` (no `<<<<<<<`, `=======`, `>>>>>>>` line left), then
     `python "NEW/scripts/merge.py" --accept <file>`.
   - No, or later: change nothing. Their copy stays in use and `doctor` will list it again.
4. A locale file (`locales/<lang>.json`) names the keys in conflict: for each key show the user's text, the old default
   and the new one, and on a yes write the chosen text for that key in their `locales/<lang>.json`, then `--accept`.

## 5. Each hand edit that was recovered

`recover --list` prints, under each file, the command that compares the user's edit with the new version's file. Run it and
read the difference.

- A template, a guide or a locale key: propose to put the user's change into their copy in
  `<claude dir>/chatroom/user/<same path>`. That is where the next update merges from.
- Anything else (`hooks`, `agents`, `skills`, `scripts`): these are read from the plugin folder, so the change can only go
  into `NEW/<file>` itself, and the next update will recover it again. Say this before proposing it.

Apply only on a yes, then `python "NEW/scripts/manifest.py" recover --done VERSION:file` with the pair the list printed.
On a no, leave it: the edit stays in `<claude dir>/chatroom/user/recovered/` and nothing is lost.

## 6. The MCP server and the end

1. `python "NEW/scripts/doctor.py"`: if a line says the MCP server points at an older copy or at the path of one version,
   show the fix it prints and run it only on the user's yes.
2. Close with three lines: updated from X to Y; N changes of theirs kept (merged by the plugin or with them now); M still
   need a merge, by name, or none.
3. Tell the user to restart Claude Code: the hooks, the agents and the skills of the new version start with the next
   session. Until then this session keeps the old ones (its skills even carry the old copy's path to chat.py, and the
   new agent types are missing), so say plainly: do not open new rooms in this session, open them after the restart.
   A room started from the old copy anyway gets a warning from `init`.
