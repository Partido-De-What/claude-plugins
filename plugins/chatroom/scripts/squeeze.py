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
TAIL_C, HEAD_C, LINE_C = 16_000, 6_000, 2_000   # the budget goes to the tail first (the result), then the head, then errors
ERROR = re.compile(r'error|fail|traceback|exception|assert|fatal|panic|denied|not found', re.IGNORECASE)


def _clip(line, cap):
    """a line longer than cap (minified JSON, HTML) keeps its start and its end"""
    return line if len(line) <= cap else f'{line[:cap // 2]} [... {len(line) - cap} characters ...] {line[-cap // 2:]}'


def _fit(lines, budget, reverse=False):
    out, size = [], 0
    for line in (reversed(lines) if reverse else lines):
        if size + len(line) + 1 > budget:
            break
        out.append(line)
        size += len(line) + 1
    return out[::-1] if reverse else out


def short(text, saved):
    """at most LIMIT characters: the tail whole, the head, then the lines that look like errors; never the end cut"""
    if len(text) <= LIMIT:
        return text
    raw = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')                            # \r: progress bars
    cap = max(LINE_C, (TAIL_C - 200) // len(raw))     # one huge line (a JSON answer) may fill the tail alone
    lines = [_clip(l, cap) for l in raw]
    tail = _fit(lines, TAIL_C, reverse=True)
    rest = lines[:len(lines) - len(tail)]
    head = _fit(rest, HEAD_C)
    middle = rest[len(head):]
    errors = _fit([l for l in middle if ERROR.search(l)], LIMIT - TAIL_C - HEAD_C - 600)
    note = (f'[... {len(middle)} lines cut, {len(errors)} of them shown below because they look like errors;'
            f' the whole output: {saved} (Read it with offset and limit) ...]')
    return '\n'.join(head + [note] + errors + ['[... tail ...]'] + tail)


def room_of(aid):
    """the room whose roster has this agent, among the served rooms and the ones chat.py met lately"""
    base = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'chatroom'
    for f in ('rooms.json', 'known_rooms.json'):
        try:
            for k in json.loads((base / f).read_text(encoding='utf-8')):
                if aid in (Path(k) / 'roster.json').read_text(encoding='utf-8'):
                    return k
        except (OSError, ValueError):
            continue
    return None


def picture_note(ev):
    """after a Read of a picture the room shrank: tell the agent it saw a copy, and how to get the original"""
    path = str((ev.get('tool_input') or {}).get('file_path') or '')
    if '/thumbs/' not in path.replace(os.sep, '/'):
        return None
    room = room_of(str(ev.get('agent_id') or ''))
    if not room:
        return None
    import thumbs
    n = thumbs.note_of(room, path)
    if not n:
        return None
    text = thumbs.note_text(n)
    try:                                              # many pictures in a row, and the room allows it: a verdict instead of pixels
        look_on = str(json.loads((Path(room) / 'config.json').read_text(encoding='utf-8')).get('vision', 0)) == '1'
    except (OSError, ValueError):
        look_on = False
    recent = sum(1 for v in thumbs._served(room).values() if time.time() - v['ts'] < 600)
    if look_on and recent >= 5:
        text += (f' You have read {recent} pictures in ten minutes: chat.py vision FILE --ask "..." has a free vision model '
                 f'answer in a few lines, and keeps the pixels out of your context.')
    return {'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': text}}


def answer(ev):
    """the hook's JSON answer, or None to leave the output as it is"""
    aid = str(ev.get('agent_id') or '')
    out = ev.get('tool_response')
    if ev.get('tool_name') == 'Read' and aid:
        return picture_note(ev)
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
    if len(raw) <= LIMIT and b'thumbs' not in raw:   # nearly every call: out before any parsing (a shrunk picture's path has /thumbs/)
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
    (room / 'roster.json').write_text('{"A": "a1b2c3d4e5"}')
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
