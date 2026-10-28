"""PreToolUse hook of the chatroom: an agent of a room may not change a file another agent holds through a task (chat.py guard_reason).
Reads the hook event on stdin; exit 2 with the reason on stderr denies, anything else lets the tool run (fail open).
The agent is found by its agent id in the registry of served rooms, as the mod does; the lead and the main thread are never stopped.
Standard library only."""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TOOLS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')


def agent_of(ev):
    """the sub-agent id of the event: the field Claude Code sets inside a sub-agent, else the one of its transcript's name"""
    aid = str(ev.get('agent_id') or '')
    if not aid:
        m = re.search(r'agent-(a[0-9a-f]{8,40})\.jsonl', str(ev.get('transcript_path') or ''))
        aid = m.group(1) if m else ''
    return aid


def decide(ev):
    """the reason to deny, or ''"""
    tool, inp = ev.get('tool_name'), ev.get('tool_input') or {}
    aid = agent_of(ev)
    target = inp.get('file_path') or inp.get('notebook_path')
    if tool not in TOOLS or not aid or not target:
        return ''
    registry = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'chatroom' / 'rooms.json'
    try:                                              # cheap first: most sessions have no room, and they must not pay for importing chat.py
        rooms = {k: v for k, v in json.loads(registry.read_text(encoding='utf-8')).items() if time.time() - float(v.get('ts', 0)) < 60}
    except (OSError, ValueError):
        return ''
    for key, info in rooms.items():
        if aid in info.get('ids', []):
            import chat
            room = chat.Room(key)
            name = next((n for n, v in room.roster().items() if v == aid), None)
            chat.use(room.config().get('lang'))
            return chat.guard_reason(room, name, tool, target) if name else ''
    return ''


def main():
    sys.stderr.reconfigure(encoding='utf-8')          # Claude Code reads the reason as UTF-8; Windows' default would garble è
    try:
        why = decide(json.load(sys.stdin))
    except Exception:                                 # a fault here never blocks an agent
        return 0
    if why:
        print(why, file=sys.stderr)
        return 2
    return 0


def _prova():
    """self-check: the agent id from the event or from the transcript's name, and which files a task claims"""
    assert agent_of({'agent_id': 'a1b2c3d4e5f6'}) == 'a1b2c3d4e5f6'
    assert agent_of({'transcript_path': 'C:/x/subagents/agent-a1b2c3d4e5f6.jsonl'}) == 'a1b2c3d4e5f6'
    assert agent_of({'transcript_path': 'C:/x/main.jsonl'}) == ''
    import chat
    assert chat.file_claimed('/w/src/x.py', ['src/x.py']) and chat.file_claimed('/w/lib/a/b.py', ['lib/'])
    assert not chat.file_claimed('/w/src/y.py', ['src/x.py']) and not chat.file_claimed('/o/src/x.py', ['src/x.py'], '/w')
    print('guard: self-check ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
        sys.exit(0)
    sys.exit(main())
