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
    if roster.is_file() and aid in roster.read_text(encoding='utf-8'):
        return                                                  # cheap first: most calls come from an agent already written
    if name not in json.loads((d / 'config.json').read_text(encoding='utf-8')).get('participants', []):
        return
    import chat
    chat.Room(d).update_roster(lambda ro: ro.setdefault(name, aid))
    kind = str(ev.get('agent_type') or '')[:60]                 # B1: the desktop app sends no spawn event: the type comes with the call, when the hook has it
    if kind:
        types = chat.read_json(d / 'agent_types.json', {})
        if types.get(name) != kind:
            chat.write_atomic(d / 'agent_types.json', json.dumps({**types, name: kind}))


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # fail open: a fault here never blocks a tool call
        pass
