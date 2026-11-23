"""1.3: seven ideas from Pi and Hermes. Synthetic rooms, no network, no real model. Run: python -X utf8 smoke_13_pihermes.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
BASE = Path(tempfile.mkdtemp(prefix='smoke13ph_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
os.environ['CHATROOM_NO_UPDATE_CHECK'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
CHAT = str(SCRIPTS / 'chat.py')
sys.path.insert(0, str(SCRIPTS))
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def run(room, *args, stdin=''):
    r = subprocess.run([sys.executable, CHAT, *args, '--room', str(room)], input=stdin.encode('utf-8'), capture_output=True, timeout=300,
                       env=dict(os.environ), cwd=str(BASE))
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def new_room(name, parts='A,B'):
    room = BASE / name
    run(room, 'init', '--participants', parts, '--lang', 'en')
    run(room, 'post', '--as', 'LEAD', stdin='hello, I lead')
    return room


import chat  # noqa: E402
import hold  # noqa: E402
import skills_d6  # noqa: E402

# 1: the state format
room = new_room('state')
c, o = run(room, 'notebook', '--state', '--as', 'A')
ok('1 notebook --state alone prints the parts of a state', 'goal' in o and 'blocked' in o and 'critical' in o, o)
c, o = run(room, 'notebook', 'just some words', '--state', '--as', 'A')
ok('1 a state without its parts is kept, and the parts are shown', c == 0 and 'goal' in o and (room / 'notes' / 'A.state.md').is_file(), o)
c, o = run(room, 'notebook', 'goal: ship | next: mix audio', '--state', '--as', 'A')
ok('1 a state with its parts is kept quietly', c == 0 and 'blocked' not in o, o)

# 2, 3: the lessons budget and the lint
room = new_room('lessons')
c, o = run(room, 'lessons', 'propose', 'Check the render on 2026-11-21 before mixing', '--score', '4', '--reach', 'local', '--scope', 'renders', '--as', 'LEAD')
ok('3 a lesson with a date is refused as a log', c != 0 and 'not the story' in o, o)
c, o = run(room, 'lessons', 'propose', 'As the user said "we need to render it again at full size first" always', '--score', '4', '--reach', 'local', '--scope', 'renders', '--as', 'LEAD')
ok('3 a lesson with a long quote is refused', c != 0 and 'not the story' in o, o)
import lessons  # noqa: E402
data = {'lessons': [{'id': f'L{i}', 'text': 'x' * 290, 'status': 'trial'} for i in range(1, 10)]}
old_cap, lessons.CAP = lessons.CAP, 99
ok('2 a lesson over the character budget is refused with merge or shorten', 'budget' in (lessons.gate('Measure both arms in the same run', data) or ''), lessons.gate('Measure both arms in the same run', data))
lessons.CAP = old_cap

# 4: the reflection, with a fake model
room = new_room('reflect')
(BASE / 'claude' / 'chatroom' / 'creator').write_text('', encoding='utf-8')
seen = []
outs = []
chat.reflect(chat.Room(room), 'LEAD', out=outs.append, runner=lambda ask: seen.append(ask) or
             'LESSON | 3 | general | rooms of deliveries | Post the delivery with wait_for so the agent stays\nnoise line\nLESSON | 4 | topic | renders | Render a short preview before the full one')
props = json.loads((room / 'proposals.json').read_text(encoding='utf-8'))
ok('4 the reflection asks the model with the room and its causes', seen and 'TRANSCRIPT' in seen[0] and 'hello, I lead' in seen[0], seen[:1])
ok('4 its lessons become proposals to decide, never applied', len(props) == 2 and all(p['status'] == 'presented' and p['by'] == 'reflect' for p in props), props)
ok('4 the model is a Sonnet with high effort', chat.REFLECT_MODEL.startswith('claude-sonnet') and chat.REFLECT_EFFORT == 'high')
outs.clear()
chat.reflect(chat.Room(room), 'LEAD', out=outs.append, runner=lambda ask: 'nothing worth it')
ok('4 no lesson: said, nothing added', any('no lesson' in x for x in outs) and len(json.loads((room / 'proposals.json').read_text(encoding='utf-8'))) == 2, outs)

# 5: a report without END goes back once
room = new_room('end')
r = chat.Room(room)
r.update_roster(lambda ro: ro.update(A='abcdef0123456789'))
(BASE / 'claude' / 'chatroom' / 'known_rooms.json').write_text(json.dumps({str(room): {'ts': time.time(), 'ids': ['abcdef0123456789']}}), encoding='utf-8')
ev = {'tool_name': 'SubagentHandback', 'agent_id': 'abcdef0123456789', 'tool_input': {'result': 'I did it, all fine'}}
first = hold.handback(ev)
second = hold.handback(ev)
ok('5 a report without END is sent back once, asking for the line', first and 'END:' in json.dumps(first), first)
ok('5 the second time it passes', not (second or {}).get('hookSpecificOutput', {}).get('permissionDecisionReason', '').startswith('Before you hand back'), second)

# 6: candidate lifecycle
room = new_room('cands')
base = room / 'skills-candidates'
for name, days, pin in (('old-one', 40, False), ('mid-one', 20, False), ('new-one', 1, False), ('kept-one', 40, True)):
    d = base / name
    d.mkdir(parents=True)
    (d / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: x\n---\nbody\n', encoding='utf-8')
    (d / 'meta.json').write_text(json.dumps({'status': 'new', 'at': time.time() - days * 86400, 'pinned': pin}), encoding='utf-8')
moved = skills_d6.sweep(room)
ok('6 a candidate unused for 30 days goes to the archive, not deleted', (base / '.archive' / 'old-one' / 'SKILL.md').is_file() and not (base / 'old-one').exists(), moved)
ok('6 one unused for 14 days goes stale', json.loads((base / 'mid-one' / 'meta.json').read_text(encoding='utf-8'))['status'] == 'stale')
ok('6 a new one and a pinned one stay', (base / 'new-one').is_dir() and (base / 'kept-one').is_dir() and json.loads((base / 'new-one' / 'meta.json').read_text(encoding='utf-8'))['status'] == 'new')

# 7: ping-pong
room = new_room('pingpong')
r = chat.Room(room)
for i in range(6):
    r.append('AB'[i % 2], f'@{"BA"[i % 2]} no, {i}')
c, o = run(room, 'check', '--as', 'LEAD')
ok('7 two agents answering only each other: a CHECK', 'answered only each other' in o, o[-400:])
r.append('LEAD', '@A take T2')
ok('7 the lead steps in: no more loop', chat.ping_pong(r, r.messages()) is None)

# 8: init asks before starting when a newer chatroom is out
os.environ.pop('CHATROOM_NO_UPDATE_CHECK', None)
cache = BASE / 'claude' / 'chatroom' / 'update_check.json'
cache.unlink(missing_ok=True)
ok('8 a newer version is seen', chat.newer_version(fetch=lambda: '99.0.0') == (__import__('lessons').core_version(), '99.0.0'))
cache.unlink(missing_ok=True)
ok('8 the same or an older one is not', chat.newer_version(fetch=lambda: '0.1.0') is None)
cache.unlink(missing_ok=True)
ok('8 no network: the room is not held up', chat.newer_version(fetch=lambda: (_ for _ in ()).throw(OSError('offline'))) is None)
cache.write_text(json.dumps({'at': time.time(), 'latest': '99.0.0'}), encoding='utf-8')
c, o = run(BASE / 'upd', 'init', '--participants', 'A', '--lang', 'en')
ok('8 init stops and asks the user: update or continue', c != 0 and 'UPDATE AVAILABLE' in o and '--skip-update' in o and not (BASE / 'upd' / 'config.json').exists(), o)
c, o = run(BASE / 'upd', 'init', '--participants', 'A', '--lang', 'en', '--skip-update')
ok('8 --skip-update starts it with this version', c == 0 and (BASE / 'upd' / 'config.json').exists(), o)
os.environ['CHATROOM_NO_UPDATE_CHECK'] = '1'

print(f'fails {fails}')
sys.exit(1 if fails else 0)
