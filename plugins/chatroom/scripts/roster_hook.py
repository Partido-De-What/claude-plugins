"""PreToolUse hook of the chatroom: writes the roster by itself where the mod does not run (the Claude desktop app). A room
agent's first call to the chat (an MCP tool with `room` and `as`, or a chat.py command with --room and --as) says its
name and, in the hook's input, its agent id: that is the roster line (name = id), so the lead's first post pings it and
the SubagentStop hold finds it. Only a name the room lists as a participant, and only when the name and the id are both
still free; a call of the lead (no agent id) or of another room is left alone. Any fault passes silently."""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
AGENT_ID = re.compile(r'a[0-9a-f]{8,40}\Z')                   # a Claude Code agent id (as activity.py)
CALL_AS = re.compile(r'--as[ =]+["\']?([A-Za-z][\w-]{0,39})')
CALL_ROOM = re.compile(r'--room[ =]+(?:"([^"]+)"|\'([^\']+)\'|(\S+))')


def call_of(ev):
    """(room folder, name) the tool call names, or (None, None)"""
    inp = ev.get('tool_input') or {}
    if ev.get('tool_name') == 'Bash':
        cmd = str(inp.get('command') or '')
        got, who = CALL_ROOM.search(cmd), CALL_AS.search(cmd)
        room, name = (next(g for g in got.groups() if g) if got else None), (who.group(1) if who else None)
    else:
        room, name = inp.get('room'), inp.get('as')
    if not room or not name:
        return None, None
    room = str(room)
    if os.name == 'nt' and re.match(r'/[a-zA-Z]/', room):      # Git Bash writes E:/x as /e/x
        room = room[1].upper() + ':' + room[2:]
    return room, str(name).partition('~')[0]


def main():
    ev = json.load(sys.stdin)
    aid = str(ev.get('agent_id') or '')
    room, name = call_of(ev)
    if not (room and AGENT_ID.match(aid)):
        return
    d = Path(room)
    roster = d / 'roster.json'
    kind = str(ev.get('agent_type') or '')[:60]                 # B1: the desktop app sends no spawn event: the type comes with the call, when the hook has it
    if roster.is_file() and aid in roster.read_text(encoding='utf-8'):
        if kind:                                                # D2: written by the lead (`roster`) before its first call: its type still counts
            note_type(d, aid, kind)
        return                                                  # cheap first: most calls come from an agent already written
    if name not in json.loads((d / 'config.json').read_text(encoding='utf-8')).get('participants', []):
        return
    import chat
    chat.Room(d).update_roster(lambda ro: ro.setdefault(name, aid))
    if kind:
        note_type(d, aid, kind)


def note_type(d, aid, kind):
    """agent_types.json: the type of the roster name of this agent id (its cache life and its waits come with it). Written
    only when it changes: chat is imported only then"""
    try:
        types = json.loads((d / 'agent_types.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        types = {}
    name = next((k for k, v in json.loads((d / 'roster.json').read_text(encoding='utf-8')).items() if v == aid), None)
    if not name or types.get(name) == kind:
        return
    import chat
    chat.write_atomic(d / 'agent_types.json', json.dumps({**types, name: kind}))


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # fail open: a fault here never blocks a tool call
        pass
