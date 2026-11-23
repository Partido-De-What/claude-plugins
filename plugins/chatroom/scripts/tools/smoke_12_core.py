"""1.2: the core fixes of the report of 23/11 (two rooms of deliveries in the desktop app). Synthetic rooms only.
Run: python -X utf8 smoke_12_core.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
BASE = Path(tempfile.mkdtemp(prefix='smoke12_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
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

# ---- B1/B6: no type recorded (desktop app): a participant is a room agent
room = new_room('types')
r = chat.Room(room)
ok('B1 a participant with no type recorded gets the room agent cache', r.long_cache('A'))
(room / 'agent_types.json').write_text(json.dumps({'A': 'general-purpose'}), encoding='utf-8')
ok('B1 a type recorded as another one still counts', not r.long_cache('A'))
ok('B1 a name outside the room does not', not r.long_cache('ZED'))
hook = subprocess.run([sys.executable, str(SCRIPTS / 'roster_hook.py')], input=json.dumps({
    'agent_id': 'abcdef0123456789', 'agent_type': 'chatroom:room-agent', 'tool_name': 'mcp__chatroom__chat_read',
    'tool_input': {'room': str(room), 'as': 'B'}}).encode(), capture_output=True, env=dict(os.environ))
types = json.loads((room / 'agent_types.json').read_text(encoding='utf-8'))
ok('B1 the roster hook records the type it is given', types.get('B') == 'chatroom:room-agent' and r.roster().get('B') == 'abcdef0123456789', (types, r.roster(), hook.stderr[-300:]))

# ---- B3: an agent that ends with nothing in hand is no event
room = new_room('left')
r = chat.Room(room)
hold.left(r, 'A', '')
ev = (room / 'events.jsonl').read_text(encoding='utf-8') if (room / 'events.jsonl').exists() else ''
ok('B3 an end with nothing in hand writes no hold:left event', '"left"' not in ev, ev[-300:])
run(room, 'task', 'add', 't1', '--as', 'A'); run(room, 'task', 'take', 'T1', '--as', 'A')
hold.left(r, 'A', 'task')
ev = (room / 'events.jsonl').read_text(encoding='utf-8')
ok('B3 an end with a task in hand is still one', '"left"' in ev and 'T1' in ev, ev[-300:])

# ---- B4: a wait said without a question mark keeps the agent
room = new_room('wait')
r = chat.Room(room)
run(room, 'post', '--as', 'A', stdin='@LEAD delivered out.mp4, I wait for your ok on the full render')
ok('B4 "I wait for your ok" to the lead is a wait', chat.waits_for_lead(r, only='A'), chat.waits_for_lead(r))
ok('B4 the stop hook keeps it: waits() says lead', hold.waits(r, 'A') == 'lead', hold.waits(r, 'A'))
run(room, 'post', '--as', 'LEAD', stdin='@A ok, go on')
ok('B4 the lead answered: it may go', hold.waits(r, 'A') == '', hold.waits(r, 'A'))
run(room, 'post', '--as', 'B', stdin='@LEAD report: the file is in out/, all checks pass')
ok('B4 a plain report is no wait', not chat.waits_for_lead(r, only='B'))

# ---- T4: the message and the wait in one call
run(room, 'read', '--as', 'B')
c, o = run(room, 'post', '--as', 'B', '--wait-for', 'LEAD', stdin='@LEAD second render ready in out/b.mp4')
ok('T4 post --wait-for posts the message and an idle that waits on LEAD', c == 0 and 'ALERT' in o and r.waits_on_of('B') == 'LEAD', (o, r.idle_entry('B')))
ok('T4 the stop hook holds it as idle', hold.waits(r, 'B') == 'idle')

# ---- B2: the cost table keeps the agents that left
import cost  # noqa: E402
(room / 'roster.json').write_text(json.dumps({'A': 'aaaaaaaa11111111'}), encoding='utf-8')
(room / 'roster.left.json').write_text(json.dumps({'B': 'bbbbbbbb22222222'}), encoding='utf-8')
ok('B2 room_costs lists an agent that left', set(cost.room_costs(chat.Room(room))) >= {'A', 'B'}, cost.room_costs(chat.Room(room)))

# ---- B7: --resend, and the lead is not held for agents' reports
room = new_room('cross')
run(room, 'post', '--as', 'A', stdin='my first position')
run(room, 'post', '--as', 'B', stdin='my first position too')
run(room, 'read', '--as', 'A'); run(room, 'read', '--as', 'B'); run(room, 'read', '--as', 'LEAD')
run(room, 'post', '--as', 'B', stdin='@A here is the table you asked for')
c, o = run(room, 'post', '--as', 'A', stdin='my long analysis that crossed')
ok('B7 a crossed agent post is held and names post --resend', c != 0 and '--resend' in o, o)
c, o = run(room, 'post', '--as', 'A', '--resend')
ok('B7 post --resend posts the held text', c == 0 and 'my long analysis that crossed' in (room / 'chat.jsonl').read_text(encoding='utf-8'), o)
run(room, 'read', '--as', 'LEAD')
run(room, 'read', '--as', 'A')
c0, o0 = run(room, 'post', '--as', 'A', stdin='@LEAD done with T1, proof in out/')
c, o = run(room, 'post', '--as', 'LEAD', stdin='@B start T2 now')
ok("B7 an order of the lead goes through an agent's crossed report, shown after", c0 == 0 and c == 0 and 'posted' in o and 'done with T1' in o, (o0, o))

# ---- B8: the confirmation is the last word about the post
c, o = run(room, 'post', '--as', 'LEAD', stdin='@A one more')
lines = [x for x in o.splitlines() if x.strip()]
ok('B8 the relay warning, when shown, comes before the confirmation', not any('relay' in x.lower() for x in lines[lines.index(next(x for x in lines if x.startswith('posted'))):][1:2]), o)

# ---- O1: prompt --stub
room = new_room('stub')
c, o = run(room, 'prompt', 'A', '--tools', 'mcp', '--out', str(room / 'prompts' / 'A.md'), '--stub')
ok('O1 prompt --stub writes the prompt and prints three lines to pass', c == 0 and 'follow it' in o and (room / 'prompts' / 'A.md').is_file() and len(o) < 600, o)

# ---- O4/B5: deliveries
room = new_room('deliv')
run(room, 'brief', 'goal=g', 'mode=deliveries', '--as', 'LEAD')
c, o = run(room, 'post', '--as', 'A', stdin='CLOSED')
ok('B5 a CLOSED in a room of deliveries is not refused', c == 0, o)
run(room, 'prompt', 'B', '--tools', 'mcp', '--out', str(room / 'B.md'))
p = (room / 'B.md').read_text(encoding='utf-8')
ok('O4 the prompt says deliver and end, and drops the rule on CHALLENGE', 'deliveries' in p and 'CHALLENGE suspends' not in p, p[:400])

# ---- T3: a JSON status keeps the notebook state
room = new_room('state')
(room / 'notes').mkdir(exist_ok=True)
(room / 'notes' / 'A.state.md').write_text('10:00 my own line\n', encoding='utf-8')
run(room, 'post', '--as', 'A', '--status', stdin=json.dumps({'task': 'T1', 'step': 'render', 'pct': 40, 'next': 'mix audio'}))
st = (room / 'notes' / 'A.state.md').read_text(encoding='utf-8')
ok('T3 the status writes its auto line and keeps the agent\'s own', 'my own line' in st and 'auto ' in st and 'mix audio' in st, st)
run(room, 'post', '--as', 'A', '--status', stdin=json.dumps({'task': 'T1', 'step': 'mix', 'pct': 70, 'next': 'deliver'}))
st = (room / 'notes' / 'A.state.md').read_text(encoding='utf-8')
ok('T3 one auto line, the newest', st.count('auto ') == 1 and 'deliver' in st, st)

# ---- T5: the lead gets a message that tags it whole
import inbox  # noqa: E402
room = new_room('inbox')
body = '@LEAD ' + 'word ' * 120
run(room, 'post', '--as', 'A', stdin=body)
lines, _ = inbox.lines(room, 'LEAD')
ok('T5 a message to the lead up to 800 characters reaches it whole', lines and '[expand' not in lines[-1] and lines[-1].count('word') >= 119, lines[-1:])

# ---- B11
room = new_room('long')
c, o = run(room, 'lessons', 'propose', 'x ' * 200, '--score', '4', '--reach', 'local', '--scope', 'always', '--as', 'LEAD')
ok('B11 a long lesson is refused with the text cut to fit', c != 0 and 'Cut to fit' in o, o[-300:])

print(f'fails {fails}')
sys.exit(1 if fails else 0)
