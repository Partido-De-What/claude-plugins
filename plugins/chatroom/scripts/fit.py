"""PreToolUse hook of the chatroom for the room's agents: what enters a context stays there, read again at every turn.
- A Read of a text file over READ_BIG bytes without offset or limit gets a limit of LINES lines and a note on the size:
  the agent reads the rest by offset, or greps.
- A Write that rewrites an existing file over WRITE_BIG bytes is refused once with "use Edit" (a night room carried about
  120k tokens per agent of files written whole with heredocs); the same Write again within AGAIN seconds goes through.
Agents outside a room and the lead pass untouched (hooks.json skips Python for them); any fault lets the tool run.
Standard library only."""
import json
import os
import sys
import time
from pathlib import Path

READ_BIG, WRITE_BIG, LINES, AGAIN = 50_000, 20_000, 800, 120
SKIP = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.ipynb', '.bmp', '.svg')


def room_of(aid):
    base = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'chatroom'
    for f in ('rooms.json', 'known_rooms.json'):
        try:
            for k in json.loads((base / f).read_text(encoding='utf-8')):
                if aid in (Path(k) / 'roster.json').read_text(encoding='utf-8'):
                    return Path(k)
        except (OSError, ValueError):
            continue
    return None


def answer(ev):
    tool, inp, aid = ev.get('tool_name'), ev.get('tool_input') or {}, str(ev.get('agent_id') or '')
    path = Path(str(inp.get('file_path') or ''))
    if not aid or not path.name or path.suffix.lower() in SKIP:
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if tool == 'Read' and size > READ_BIG and not inp.get('offset') and not inp.get('limit'):
        if not room_of(aid):
            return None
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'updatedInput': dict(inp, limit=LINES),
                                       'additionalContext': f'[chatroom: {path.name} is {size // 1000} KB; you get its first {LINES} '
                                                            f'lines. Read the rest with offset and limit, or grep for what you need: '
                                                            f'everything you read stays in your context.]'}}
    if tool == 'Write' and size > WRITE_BIG:
        room = room_of(aid)
        if not room:
            return None
        mark = room / 'fit_denied.json'
        try:
            denied = json.loads(mark.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            denied = {}
        key = f'{aid}|{path}'
        if time.time() - denied.get(key, 0) < AGAIN:      # it insists: a rewrite it means
            return None
        denied = {k: v for k, v in denied.items() if time.time() - v < AGAIN}
        denied[key] = time.time()
        mark.write_text(json.dumps(denied), encoding='utf-8')
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                       'permissionDecisionReason': f'[chatroom: {path.name} already exists ({size // 1000} KB): change it '
                                                                   f'with Edit, so only the change enters your context. If you mean '
                                                                   f'to rewrite it whole, send the same Write again.]'}}
    return None


def main():
    try:
        got = answer(json.load(sys.stdin))
    except Exception:
        return 0
    if got:
        sys.stdout.reconfigure(encoding='utf-8')
        print(json.dumps(got, ensure_ascii=False))
    return 0


def _prova():
    import tempfile
    base = Path(tempfile.mkdtemp(prefix='fit_'))
    os.environ['CLAUDE_CONFIG_DIR'] = str(base / 'c')
    (base / 'c' / 'chatroom').mkdir(parents=True)
    room = base / 'room'
    room.mkdir()
    (room / 'roster.json').write_text('{"A": "abcdef12345"}')
    (base / 'c' / 'chatroom' / 'known_rooms.json').write_text(json.dumps({str(room): {'ts': time.time(), 'ids': ['abcdef12345']}}))
    big = base / 'big.log'
    big.write_text('line\n' * 20000)
    got = answer({'tool_name': 'Read', 'agent_id': 'abcdef12345', 'tool_input': {'file_path': str(big)}})
    assert got['hookSpecificOutput']['updatedInput']['limit'] == LINES, got
    assert answer({'tool_name': 'Read', 'agent_id': 'abcdef12345', 'tool_input': {'file_path': str(big), 'limit': 50}}) is None
    assert answer({'tool_name': 'Read', 'agent_id': 'other', 'tool_input': {'file_path': str(big)}}) is None
    w = {'tool_name': 'Write', 'agent_id': 'abcdef12345', 'tool_input': {'file_path': str(big), 'content': 'x'}}
    assert answer(w)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert answer(w) is None                                                       # the same Write again: through
    print('fit prova ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
        sys.exit(0)
    sys.exit(main())
