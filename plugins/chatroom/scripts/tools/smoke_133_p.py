"""1.3.3: the faults P1-P7 of room 37 and its double wake. Synthetic rooms, nothing goes out.
Run: python -X utf8 smoke_133_p.py"""
import io
import json
import contextlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
BASE = Path(tempfile.mkdtemp(prefix='smoke133_'))
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
    cmd = [sys.executable, CHAT, *args] + (['--room', str(room)] if room else [])
    r = subprocess.run(cmd, input=stdin.encode('utf-8'), capture_output=True, timeout=300, env=dict(os.environ), cwd=str(BASE))
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def new_room(name, parts='A,B'):
    room = BASE / name
    run(room, 'init', '--participants', parts, '--lang', 'en')
    run(room, 'post', '--as', 'LEAD', stdin='hello, I lead')
    return room


import chat  # noqa: E402
import hold  # noqa: E402
import machine  # noqa: E402

# P1: an agent before its brief is not held by the stop hook
room = new_room('p1')
r = chat.Room(room)
r.update_roster(lambda ro: ro.update(A='a1111111111'))
t0 = time.time()
ok('P1 an agent that never read the room stops at once', hold.decide({'agent_id': 'a1111111111'}, wait=5, poll=0.2) is None and time.time() - t0 < 2)
r.set_cursor('A', 1)
r.append('A', '40%: waiting for @B', 'idle')
got = hold.decide({'agent_id': 'a1111111111'}, wait=1, poll=0.2)
ok('P1 once it works in the room, the hold applies again', got and got.get('decision') == 'block', got)

# P2, P3: the machine
p = subprocess.run([sys.executable, str(SCRIPTS / 'machine.py')], capture_output=True, timeout=120, env=dict(os.environ))
ok('P2 the lock self-test: an empty file or a dead holder is no lock, the queue keeps its order', p.returncode == 0 and b'prova ok' in p.stdout, p.stdout + p.stderr)
c, o = run(None, 'heavy', '--key', 'job1', '--', sys.executable, '-c', 'print(42)')
ok('P3 heavy runs the command', c == 0 and '42' in o, o)
c, o = run(None, 'heavy', '--key', 'job1', '--', sys.executable, '-c', 'print(42)')
ok('P3 the same key after a success is skipped', c == 0 and 'already done' in o and '42' not in o, o)
room = new_room('p3')
c, o = run(None, 'heavy', '--room', str(room), '--as', 'A', '--', sys.executable, '-c', 'raise SystemExit(5)')
ok('P3 a failing job keeps its exit code', c == 5, (c, o))
checks = chat.failures(chat.Room(room))
ok('P3 the lead gets a CHECK for it', any(k.startswith('heavy:') and 'exit 5' in t for k, t in checks), checks)
c, o = run(None, 'heavy', 'list')
ok('P3 heavy list shows the last exits', c == 0 and 'exit 5' in o and 'exit 0' in o, o)
slow = subprocess.Popen([sys.executable, CHAT, 'heavy', '--', sys.executable, '-c', 'import time; time.sleep(4)'], env=dict(os.environ), cwd=str(BASE))
time.sleep(1.5)
waiter = subprocess.Popen([sys.executable, CHAT, 'heavy', '--', sys.executable, '-c', 'print(1)'], env=dict(os.environ), cwd=str(BASE),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(1.5)
q = machine.queue()
c, o = run(None, 'heavy', 'pause', q[0]['id'] if q else 'x')
ok('P3 a waiter can be paused', q and c == 0 and machine.queue()[0].get('paused'), (q, o))
line = chat.heavy_line()
ok('P3 the wake line says what the machine runs and who waits', 'sleep' in line and '1 waiting' in line, line)
run(None, 'heavy', 'resume', q[0]['id'] if q else 'x')
slow.wait(timeout=60), waiter.wait(timeout=60)
ok('P3 resumed, it runs after the holder', waiter.returncode == 0, waiter.stdout.read())

# P4: a long message that tags the reader comes whole
room = new_room('p4')
r = chat.Room(room)
import compress  # noqa: E402
long = '@A ' + ' '.join(f'word{i}' for i in range(compress.CHARS // 4))
r.append('B', long)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    r.show([m for m in r.messages() if m['from'] == 'B'], reader='A')
ok('P4 the tagged reader reads it whole', long in buf.getvalue(), buf.getvalue()[-300:])
import inbox  # noqa: E402
ok('P4 the hook line to the lead keeps long messages', inbox.LEAD_TEXT >= 4000)

# P5: the report of the live identity of a rotated agent
room = new_room('p5')
(room / 'reports').mkdir()
(room / 'reports' / 'A.json').write_text(json.dumps({'end': 'partial', 'at': 100}), encoding='utf-8')
(room / 'reports' / 'A~2.json').write_text(json.dumps({'end': 'completed', 'at': 200}), encoding='utf-8')
reps = chat.final_reports(chat.Room(room))
ok('P5 one line per role, the last report', list(reps) == ['A'] and reps['A']['end'] == 'completed', reps)
ok('P5 output in the console code page is not broken', chat.console_text('è'.encode(chat.console_encoding())) == 'è', chat.console_encoding())

# P7: a tag for an agent that ended prints the ping ready to send
chat.use('en')
ok('P7 the GONE line carries the SendMessage to send', 'SendMessage to=a99' in chat.say('chat.say.print_alert.gone_tagged', k='A', n=7, aid='a99'))

# the double wake: lines the lead read from the relay's output are not handed again
room = new_room('wake')
r = chat.Room(room)
proj = BASE / 'claude' / 'projects' / 'p'
proj.mkdir(parents=True)
(room / 'sessions.json').write_text(json.dumps({'sid-lead-1': 'LEAD'}), encoding='utf-8')
(proj / 'sid-lead-1.jsonl').write_text(json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': 'WATCH #9 MSG A: @LEAD the run on the GPU ended'}]}}) + '\n', encoding='utf-8')
chat.relay_handover(r, 'LEAD', 9, ['WATCH #9 MSG A: @LEAD the run on the GPU ended'])
rec = json.loads((room / 'relay_sent_LEAD.json').read_text(encoding='utf-8'))
rec['ts'] = time.time() - 400
(room / 'relay_sent_LEAD.json').write_text(json.dumps(rec), encoding='utf-8')
ok('double wake: seen in the transcript, not handed again', chat.relay_redeliver(r, 'LEAD') == '' and not (room / 'relay_sent_LEAD.json').exists())
chat.relay_handover(r, 'LEAD', 10, ['WATCH #10 MSG B: @LEAD something never read'])
rec = json.loads((room / 'relay_sent_LEAD.json').read_text(encoding='utf-8'))
rec['ts'] = time.time() - 400
(room / 'relay_sent_LEAD.json').write_text(json.dumps(rec), encoding='utf-8')
ok('double wake: lines it never saw still come again', 'never read' in chat.relay_redeliver(r, 'LEAD'))

print(f'fails {fails}')
sys.exit(1 if fails else 0)
