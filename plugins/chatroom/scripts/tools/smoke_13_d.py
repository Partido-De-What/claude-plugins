"""1.3.2: the faults D1-D9 of the demo room of 23/11. Synthetic rooms and fake providers, nothing goes out.
Run: python -X utf8 smoke_13_d.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
BASE = Path(tempfile.mkdtemp(prefix='smoke13d_'))
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

# D2: an agent the lead wrote in the roster still gets its type from its first call
room = new_room('types')
r = chat.Room(room)
r.update_roster(lambda ro: ro.update(A='a0123456789abcdef'))
ev = {'agent_id': 'a0123456789abcdef', 'agent_type': 'chatroom:room-agent-lean', 'tool_name': 'mcp__chatroom__chat_read',
      'tool_input': {'room': str(room), 'as': 'A'}}
p = subprocess.run([sys.executable, str(SCRIPTS / 'roster_hook.py')], input=json.dumps(ev).encode('utf-8'), capture_output=True, timeout=60)
types = chat.read_json(room / 'agent_types.json', {})
ok('D2 the type is written for an agent already in the roster', types.get('A') == 'chatroom:room-agent-lean', (types, p.stderr[-300:]))
ok('D2 a lean agent keeps the hour of cache, also after a rotation', r.long_cache('A') and r.long_cache('A~2'))

# D5: the skill panel's own line wakes only whom it tags
room = new_room('auto', 'A,B,SEARCHER')
r = chat.Room(room)
import skills  # noqa: E402
n = skills.post(r, 'SKILLSEARCH r1: pdf merge @SEARCHER pause what you are doing')
m = next(x for x in r.messages() if x['n'] == n)
ok('D5 the line is marked automatic', m.get('kind') == 'auto', m)
ok('D5 it wakes the searcher it tags, nobody else', r.wakes(m, 'SEARCHER') and not r.wakes(m, 'A') and not r.wakes(m, 'B'))
r.update_roster(lambda ro: ro.update(A='a1111111111', B='a2222222222', SEARCHER='a3333333333'))
lines = chat.alert_lines(r, [m], r.user_names())
ok('D5 the relay pings only the searcher', len(lines) == 1 and 'SEARCHER = a3333333333' in lines[0] and 'a1111111111' not in lines[0], lines)
user = r.append('USER', 'everyone, a real message')
ok('D5 a real message of the user still wakes everyone', r.wakes(next(x for x in r.messages() if x['n'] == user), 'A'))

# D6: --stub without --out writes the file and prints the three lines
room = new_room('stub')
c, o = run(room, 'prompt', 'A', '--tools', 'mcp', '--stub')
ok('D6 prompt --stub alone writes ROOM/prompts/A.md', c == 0 and (room / 'prompts' / 'A.md').is_file(), o[-300:])
ok('D6 and prints a few lines, not the prompt', len(o.strip().splitlines()) <= 4 and 'A.md' in o, o[-500:])

# D7: lines the hook already showed the lead are not handed again by the relay
room = new_room('relay')
r = chat.Room(room)
r.mark_delivered('LEAD', 13)
chat.relay_handover(r, 'LEAD', 13, ['#13 USER: hi'])
ok('D7 already shown: nothing to hand again', not (room / 'relay_sent_LEAD.json').exists() and chat.relay_redeliver(r, 'LEAD') == '')
chat.relay_handover(r, 'LEAD', 15, ['#15 USER: news'])
ok('D7 new lines still wait for a sign of reading', (room / 'relay_sent_LEAD.json').is_file())

# D1: demo=on keeps an idle agent while somebody looks at the viewer
room = new_room('demo')
r = chat.Room(room)
c, o = run(room, 'config', 'demo=on', '--as', 'LEAD')
ok('D1 config demo=on is accepted', c == 0 and r.config().get('demo') == 'on', o[-300:])
import procs  # noqa: E402
ok('D1 no viewer watched: the usual rules', not hold.demo_kept(r))
entry = procs.add('serve', os.getpid(), room.resolve(), 8799)
procs.touch(os.getpid(), clients=1)
ok('D1 a viewer with someone on it: the idle agents stay', hold.demo_kept(r))
procs.touch(os.getpid(), clients=0)
ok('D1 nobody on the viewer: they go as before', not hold.demo_kept(r))
(procs.home() / f'{os.getpid()}.json').unlink(missing_ok=True)

# D8, D9: refresh says each provider as it goes; a model only paid is listed as new, never as a route
from spawn.catalog import catalog  # noqa: E402
said = []
lists = {'groq': [{'id': 'old-free-7b', 'free': True}, {'id': 'old-paid-70b', 'free': False}],
         'nim': [{'id': 'other-free-8b', 'free': True}]}
cat = catalog.refresh({'providers': {}, 'models': []}, ['groq', 'nim', 'down'],
                      lambda pid: lists[pid] if pid in lists else (_ for _ in ()).throw(OSError('no route')), force=True, progress=said.append)
ok('D8 one line before and after each provider, the failure said', sum('groq' in x for x in said) == 2 and any('down: failed' in x for x in said), said)
ok('D9 the first read is the base: nothing paid is new', catalog.paid_new(cat) == [], catalog.paid_new(cat))
lists['groq'].append({'id': 'glm-9-coder', 'name': 'GLM 9 Coder', 'free': False})
cat = catalog.refresh(cat, ['groq'], lambda pid: lists[pid], force=True)
fresh = catalog.paid_new(cat)
ok('D9 a model out today only paid is listed', [m['name'] for m in fresh] == ['GLM 9 Coder'] and fresh[0]['adapter'] == 'groq', fresh)
ok('D9 and never offered as a route', all('glm' not in m['canonical'] for m in cat['models']), [m['canonical'] for m in cat['models']])
lists['nim'].append({'id': 'glm-9-coder', 'free': True})
cat = catalog.refresh(cat, ['nim'], lambda pid: lists[pid], force=True)
ok('D9 once free somewhere it leaves the list', catalog.paid_new(cat) == [], catalog.paid_new(cat))

# E2: a quick command posted as text by the user is run, not left as plain words
room = BASE / 'mode'
run(room, 'init', '--ask-mode', '--lang', 'it', '--user-name', 'ADRIAN', '--topic', 'x')
c, o = run(room, 'post', '--as', 'ADRIAN', stdin='/normale')
ok('E2 the user posting /normale chooses the mode', c == 0 and chat.Room(room).config().get('mode') == 'normal', (o[-300:], chat.Room(room).config().get('mode')))
room = new_room('cmdtext')
n0 = len(chat.Room(room).messages())
c, o = run(room, 'post', '--as', 'A', stdin='/accelera')
ok('E2 an agent writing the same word only posts it', c == 0 and chat.Room(room).messages()[-1]['text'] == '/accelera', o[-300:])
c, o = run(room, 'post', '--as', 'LEAD', stdin='/tmp/file is where I wrote it')
ok('E2 a sentence that starts with a slash stays a message', c == 0 and chat.Room(room).messages()[-1]['text'].startswith('/tmp/file'), o[-300:])

# E3: the topics are listed without a room
r3 = subprocess.run([sys.executable, CHAT, 'lessons', 'topic', 'list'], capture_output=True, timeout=120,
                    env={k: v for k, v in os.environ.items() if k != 'CHATROOM_DIR'}, cwd=str(BASE))
ok('E3 lessons topic list needs no room', r3.returncode == 0 and b'no room' not in r3.stdout + r3.stderr, (r3.stdout + r3.stderr)[-300:])

# E4: the help of one command
r4 = subprocess.run([sys.executable, CHAT, 'init', '--help'], capture_output=True, timeout=120, env=dict(os.environ), cwd=str(BASE))
h = r4.stdout.decode('utf-8', 'replace')
ok('E4 init --help shows init and its options only', 'chat.py init --room' in h and '--ask-mode' in h and '--evaluate' not in h and 'spawn consult' not in h
   and len(h.splitlines()) < 25, h[:600])

print(f'fails {fails}')
sys.exit(1 if fails else 0)
