"""PostToolUse hook of the chatroom: a room agent's shell command that printed more than LIMIT characters (a pytest run, a
build log, a render) gives back its head, the lines that look like errors and its tail; the whole output goes to
ROOM/outputs/, named in the answer, for a Read with offset and limit. Every output stays in the agent's context and is
read again at every turn, so a 200 KB log costs at every turn after it. The lead, the user's own sessions and short
outputs pass untouched; any fault lets the output through as it is. Standard library only."""
import json
import os
import re
import sys
import time
from pathlib import Path

LIMIT = 32_000                 # characters, about 8k tokens
HEAD, TAIL, ERRORS = 30, 60, 40
ERROR = re.compile(r'error|fail|traceback|exception|assert|fatal|panic|denied|not found', re.IGNORECASE)


def short(text, saved):
    lines = text.splitlines()
    if len(text) <= LIMIT or len(lines) <= HEAD + TAIL:
        return text
    middle = [l for l in lines[HEAD:-TAIL] if ERROR.search(l)][:ERRORS]
    cut = len(lines) - HEAD - TAIL
    return '\n'.join(lines[:HEAD] + [f'[... {cut} lines cut, {len(middle)} of them shown below because they look like errors;'
                                     f' the whole output: {saved} (Read it with offset and limit) ...]'] + middle
                     + ['[... tail ...]'] + lines[-TAIL:])[:LIMIT]


def room_of(aid):
    registry = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'chatroom' / 'rooms.json'
    rooms = json.loads(registry.read_text(encoding='utf-8'))
    return next((k for k, v in rooms.items() if aid in v.get('ids', []) and time.time() - float(v.get('ts', 0)) < 60), None)


def answer(ev):
    """the hook's JSON answer, or None to leave the output as it is"""
    aid = str(ev.get('agent_id') or '')
    out = ev.get('tool_response')
    if ev.get('tool_name') != 'Bash' or not aid or not isinstance(out, dict):
        return None
    texts = {k: out[k] for k in ('stdout', 'stderr') if isinstance(out.get(k), str)}
    if sum(map(len, texts.values())) <= LIMIT:
        return None
    room = room_of(aid)
    if not room:
        return None
    d = Path(room) / 'outputs'
    d.mkdir(exist_ok=True)
    saved = d / f"{aid[:12]}-{time.strftime('%H%M%S')}-{os.getpid()}.txt"
    saved.write_text('\n'.join(f'--- {k}\n{v}' for k, v in texts.items()), encoding='utf-8')
    new = dict(out, **{k: short(v, saved.as_posix()) for k, v in texts.items()})   # the tool's own shape, or Claude Code ignores it
    return {'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'updatedToolOutput': new}}


def main():
    raw = sys.stdin.buffer.read()
    if len(raw) <= LIMIT:                             # nearly every call: out before any parsing
        return 0
    try:
        got = answer(json.loads(raw.decode('utf-8', errors='replace')))
    except Exception:                                 # a fault here never hides an output
        return 0
    if got:
        sys.stdout.reconfigure(encoding='utf-8')
        print(json.dumps(got, ensure_ascii=False))
    return 0


def _prova():
    import tempfile
    base = Path(tempfile.mkdtemp(prefix='squeeze_'))
    os.environ['CLAUDE_CONFIG_DIR'] = str(base / 'c')
    (base / 'c' / 'chatroom').mkdir(parents=True)
    room = base / 'room'
    room.mkdir()
    (base / 'c' / 'chatroom' / 'rooms.json').write_text(json.dumps({str(room): {'ts': time.time(), 'ids': ['a1b2c3d4e5']}}))
    log = '\n'.join([f'line {i} ok' for i in range(3000)] + ['E   AssertionError: 2 != 3'] + [f'line {i} ok' for i in range(3000, 6000)])
    ev = {'tool_name': 'Bash', 'agent_id': 'a1b2c3d4e5', 'tool_response': {'stdout': log, 'stderr': '', 'interrupted': False, 'isImage': False}}
    got = answer(ev)['hookSpecificOutput']['updatedToolOutput']
    assert len(got['stdout']) < LIMIT and 'AssertionError' in got['stdout'] and 'line 5999 ok' in got['stdout'], got['stdout'][-300:]
    assert got['interrupted'] is False and got['isImage'] is False and set(got) == set(ev['tool_response'])
    assert (room / 'outputs').is_dir() and log in next((room / 'outputs').iterdir()).read_text(encoding='utf-8')
    assert answer({**ev, 'agent_id': 'other'}) is None                       # not a room agent
    assert answer({**ev, 'tool_response': {'stdout': 'short'}}) is None      # short
    print('squeeze prova ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
        sys.exit(0)
    sys.exit(main())
