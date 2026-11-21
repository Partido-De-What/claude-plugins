"""1.1: the room fixes from "Blocchi puliti" (21/11): one closing list run by itself, the auto-harness that collects, the task
cycle, the relay's reading, rotate and roster. Synthetic rooms only. Run: python -X utf8 smoke_11_room.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
BASE = Path(tempfile.mkdtemp(prefix='smoke11room_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
CHAT = str(SCRIPTS / 'chat.py')
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


def events(room):
    try:
        return [json.loads(x) for x in (room / 'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    except OSError:
        return []


# ---- closing: one list, printed or run
room = new_room('close')
run(room, 'task', 'add', 'a task', '--as', 'LEAD')
c, o = run(room, 'close-steps', '--as', 'LEAD')
ok('15 close-steps prints the five fixed steps', c == 0 and all(s in o for s in ('task close-all', 'transcript', ' cost', 'lessons close', 'procs close')), o)
c, o = run(room, 'close-steps', '--run', '--as', 'LEAD')
ok('16 --run runs them: the transcript is written, the task closed', c == 0 and (room / 'transcript.md').is_file()
   and all(t['state'] != 'open' for t in json.loads((room / 'board.json').read_text(encoding='utf-8'))['tasks']), o[-800:])
ok('3.2 without a topic it says how to keep what the room learnt', 'lessons topic use' in o, o[-600:])
ok('3.4 it asks the plugin bugs with --kind plugin', '--kind plugin' in o, o[-600:])
(room / 'closing_done.json').write_text('{}', encoding='utf-8')
run(room, 'post', '--as', 'LEAD', stdin='CLOSED v1')
run(room, 'reopen', '--as', 'LEAD', '--reason', 'one more thing')
ok('16 a reopened room runs its closing again next time', not (room / 'closing_done.json').exists())
skills = (SCRIPTS.parent / 'skills')
start, close = (skills / 'start' / 'SKILL.md').read_text(encoding='utf-8'), (skills / 'close' / 'SKILL.md').read_text(encoding='utf-8')
ok('15 start and close point to the same list', 'close-steps --run' in start and 'close-steps --run' in close)

# ---- auto-harness
room = new_room('learn')
with (room / 'events.jsonl').open('a', encoding='utf-8') as f:
    for i in range(10):
        f.write(json.dumps({'kind': 'refusal', 'key': 'task:done', 'name': 'AB'[i % 2], 'detail': 'held once', 'ts': time.time()}) + '\n')
    for i in range(4):
        f.write(json.dumps({'kind': 'check', 'key': 'oldstate', 'name': 'A', 'detail': 'state 20 min old', 'ts': time.time()}) + '\n')
c, o = run(room, 'lessons', 'close', '--as', 'LEAD')
ok('3.3 lessons close lists the room\'s repeated causes, a first room too', 'refusal:task:done x10' in o and 'check:oldstate x4' in o, o[-900:])
(BASE / 'claude' / 'chatroom' / 'creator').write_text('', encoding='utf-8')
run(room, 'check', '--as', 'LEAD')
props = json.loads((room / 'proposals.json').read_text(encoding='utf-8')) if (room / 'proposals.json').exists() else []
ok('3.1 a cause fired 10 times becomes a proposal by itself, score 3', any(p['note'].startswith('auto:refusal:task:done') and p['score'] == 3 for p in props), props)
run(room, 'check', '--as', 'LEAD')
props2 = json.loads((room / 'proposals.json').read_text(encoding='utf-8'))
ok('3.1 only once', len(props2) == len(props), props2)
sys.path.insert(0, str(SCRIPTS))
import lessons  # noqa: E402
ok('TOPIC_CAP is 12', lessons.TOPIC_CAP == 12)

# ---- tasks
room = new_room('tasks')
run(room, 'brief', 'goal=g', 'ground=1', 'max=20')
run(room, 'task', 'add', 't1', '--as', 'A'); run(room, 'task', 'take', 'T1', '--as', 'A')
c, o = run(room, 'task', 'done', 'T1', '--proof', 'pytest: 3 passed, exit 0; checked the callers of parse() in app.py:40 and the tests that read it', '--as', 'A')
ok('7 a first proof that shows the check against the existing code is not held', c == 0 and 'done by A' in o, o)
run(room, 'task', 'add', 't2', '--as', 'A'); run(room, 'task', 'take', 'T2', '--as', 'A')
work = BASE / 'work'
work.mkdir(exist_ok=True)
run(room, 'task', 'add', 't3 verified', '--verify', f'"{sys.executable}" -c "print(1)"', '--cwd', str(work), '--as', 'LEAD')
run(room, 'task', 'take', 'T3', '--as', 'B')
c, o = run(room, 'task', 'done', 'T3', '--proof', 'did it', '--as', 'B')
ok('7 the hold comes before the verify runs', c != 0 and 'held once' in o and 'verify' not in o.split('held once')[0].lower(), o)
lock = BASE / 'claude' / 'chatroom' / 'machine.lock'
lock.write_text(json.dumps({'pid': os.getpid(), 'label': 'docling of hours', 'since': time.time() - 1500}), encoding='utf-8')
c, o = run(room, 'task', 'done', 'T3', '--proof', 'did it, checked caller in app.py:12', '--as', 'B')
lock.unlink()
ok('6 a verify runs beside a heavy job, saying who holds it and since when', c == 0 and 'docling of hours' in o and '25 min' in o, o)
c, o = run(room, 'task', 'done', 'T2', '--proof', 'reviewed by me: app.py:3 and its callers', '--as', 'LEAD')
ok('10 the lead closes a stopped agent\'s task with its own proof', c == 0 and 'done' in o, o)
run(room, 'task', 'add', 't4', '--as', 'LEAD')
c, o = run(room, 'task', 'cancel', 'T4', '--note', 'not needed', '--as', 'A')
ok('11 an agent cannot cancel', c != 0 and 'lead' in o, o)
c, o = run(room, 'task', 'cancel', 'T4', '--note', 'not needed', '--as', 'LEAD')
t4 = next(t for t in json.loads((room / 'board.json').read_text(encoding='utf-8'))['tasks'] if t['id'] == 'T4')
ok('11 the lead cancels: dropped, never offered', c == 0 and t4['state'] == 'dropped' and 'cancelled' in o, (o, t4))

# ---- reading
room = new_room('read')
run(room, 'task', 'add', 'board line', '--as', 'LEAD')
long_text = 'x ' * 300
run(room, 'post', '--as', 'A', stdin='short one')
run(room, 'post', '--as', 'A', stdin=long_text)
run(room, 'post', '--as', 'B', stdin='another short')
c, o = run(room, 'read', '--all', '--as', 'LEAD')
ok('2 the lead sees no lead banner on its own messages nor on board lines', 'MESSAGE FROM THE LEAD' not in o.upper() or o.upper().count('MESSAGE FROM THE LEAD') == 0, o[:600])
c, o = run(room, 'read', '--all', '--as', 'A')
ok('2 an agent still sees the lead banner on the lead\'s message', 'LEAD' in o and o.count('#1 ') == 1, o[:400])
c, o = run(room, 'read', '--ids', '1,3', '--as', 'B')
ok('3 read --ids shows those messages only', '#1 ' in o and '#3 ' in o and '#2 ' not in o, o)
c, o = run(room, 'read', '--ids', 'x', '--as', 'B')
ok('3 a wrong --ids is said', c != 0 and '20-23' in o, o)
top = max(json.loads(x)['n'] for x in (room / 'chat.jsonl').read_text(encoding='utf-8').splitlines() if x.strip())
run(room, 'read', '--as', 'LEAD')
run(room, 'post', '--as', 'A', stdin='short after')
run(room, 'post', '--as', 'A', stdin=long_text + ' cut by the relay')
run(room, 'delivered', '--upto', str(top + 2), '--as', 'LEAD')
c, o = run(room, 'read', '--as', 'LEAD')
ok('4 a lead\'s read shows again what the relay showed cut, not what it showed whole', 'cut by the relay' in o and 'short after' not in o, o[-500:])

# ---- post without pings
c, o = run(room, 'post', '--as', 'LEAD', '--no-ping', stdin='for your information only')
ok('12 post --no-ping prints no ALERT', c == 0 and 'ALERT' not in o and 'no-ping' in o, o)

# ---- roster and rotate
room = new_room('rot', 'ALFA,BETA')
run(room, 'roster', 'ALFA~1=abc123')
ok('8 roster ALFA~1 is ALFA', json.loads((room / 'roster.json').read_text(encoding='utf-8')).get('ALFA') == 'abc123')
run(room, 'post', '--as', 'ALFA', stdin='working on it')
time.sleep(1.2)
(room / 'notes').mkdir(exist_ok=True)
(room / 'notes' / 'ALFA.state.md').write_text('goal: x; next: y', encoding='utf-8')
run(room, 'post', '--as', 'ALFA', stdin='state ready')
c, o = run(room, 'rotate', 'ALFA', '--as', 'LEAD')
ok('13 rotate goes straight on when the state is newer than the last work', c == 0 and 'without asking again' in o and 'not written its state' not in o, o)
ok('8 the rotate text says the chat name stays ALFA', 'it is still ALFA' in o, o)

# ---- the closing from a Codex relay (alerts without --follow)
room = new_room('codexclose')
run(room, 'post', '--as', 'LEAD', stdin='CLOSED v1')
c, o = run(room, 'alerts', '--messages', '--as', 'LEAD')
ok('16 a relay without --follow (Codex) runs the closing steps on a closed room', 'CLOSING of' in o and (room / 'closing_done.json').exists(), o[-600:])
c, o = run(room, 'alerts', '--messages', '--as', 'LEAD')
ok('16 only once', 'CLOSING of' not in o, o[-300:])
codex = json.loads((SCRIPTS.parent / '.codex-plugin' / 'plugin.json').read_text(encoding='utf-8'))
ok('Codex is pointed to an empty hooks file', codex.get('hooks') == './hooks/codex.json'
   and json.loads((SCRIPTS.parent / 'hooks' / 'codex.json').read_text(encoding='utf-8'))['hooks'] == {})

# ---- 3.6: a 4 or 5 on trial where it was born; it passes (accept) or is refused and deleted (retire)
home = BASE / 'claude' / 'chatroom'
(home / 'lessons.json').unlink(missing_ok=True)
r1 = new_room('trial1')
run(r1, 'lessons', 'topic', 'use', 'kernels', '--confirmed', '--as', 'LEAD')
c, o = run(r1, 'lessons', 'propose', 'Measure both arms in one run', '--score', '4', '--reach', 'general', '--scope', 'ratio metrics', '--as', 'LEAD')
les = json.loads((home / 'lessons.json').read_text(encoding='utf-8'))['lessons']
ok('3.6 a 4 general enters on trial, born in the topic', c == 0 and les[0]['status'] == 'trial' and les[0]['origin']['topic'] == 'kernels' and 'on trial' in o, (o, les))
def prompt_of(room):
    c, o = run(room, 'prompt', 'A', '--tools', 'shell', '--out', str(room / 'A.md'))
    return (room / 'A.md').read_text(encoding='utf-8') if c == 0 else o
r2 = new_room('trial2'); run(r2, 'lessons', 'topic', 'use', 'kernels', '--confirmed', '--as', 'LEAD')
r3 = new_room('trial3'); run(r3, 'lessons', 'topic', 'use', 'webapps', '--confirmed', '--as', 'LEAD')
ok('3.6 a room of the same topic carries it', 'Measure both arms in one run' in prompt_of(r2))
ok('3.6 a room of another topic does not', 'Measure both arms in one run' not in prompt_of(r3))
c, o = run(r1, 'lessons', 'trial', '--as', 'LEAD')
ok('3.6 lessons trial lists it on trial, with where it was born and its rooms', 'L1' in o and 'kernels' in o and '2 room' in o, o)
c, o = run(r1, 'lessons', 'accept', 'L1', '--as', 'LEAD')
les = json.loads((home / 'lessons.json').read_text(encoding='utf-8'))['lessons']
ok('3.6 after a second room it passes: active, for every room', c == 0 and les[0]['status'] == 'active' and 'Measure both arms in one run' in prompt_of(r3), (o, les))
c, o = run(r1, 'lessons', 'propose', 'Name the bench in every status', '--score', '5', '--reach', 'general', '--scope', 'shared benches', '--as', 'LEAD')
c, o = run(r1, 'lessons', 'retire', 'L2', '--as', 'LEAD')
les = json.loads((home / 'lessons.json').read_text(encoding='utf-8'))
ok('3.6 refused on trial: deleted, not only retired', c == 0 and all(x['id'] != 'L2' for x in les['lessons']) and 'deleted' in o, (o, les))
c, o = run(r1, 'lessons', 'trial', '--as', 'LEAD')
ok('3.6 lessons trial shows what passed and what was refused', o.index('PASSED') < o.index('L1', o.index('PASSED')) and 'Name the bench' in o[o.index('REFUSED'):], o)
ok('3.6 a refused lesson is in no prompt', 'Name the bench in every status' not in prompt_of(r2))

# ---- 3.7: task done --lesson
r4 = new_room('donelesson')
run(r4, 'task', 'add', 'parse dates', '--as', 'A'); run(r4, 'task', 'take', 'T1', '--as', 'A')
c, o = run(r4, 'task', 'done', 'T1', '--proof', 'pytest: 4 passed, exit 0', '--lesson', 'Parse dates with the locale of the file', '--as', 'A')
ok('3.7 a lesson without a score is refused before anything closes', c != 0 and '--score' in o, o)
c, o = run(r4, 'task', 'done', 'T1', '--proof', 'pytest: 4 passed, exit 0', '--lesson', 'Parse dates with the locale of the file', '--score', '4', '--as', 'A')
les = json.loads((home / 'lessons.json').read_text(encoding='utf-8'))['lessons']
ok('3.7 task done --lesson closes the task and proposes the lesson, with the task as its case', c == 0 and 'done by A' in o
   and any(x['text'] == 'Parse dates with the locale of the file' and x['status'] == 'trial' and 'T1' in x.get('evidence', '') for x in les), (o, les[-1:]))

print(f'fails {fails}')
sys.exit(1 if fails else 0)
