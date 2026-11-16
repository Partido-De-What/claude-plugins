"""1.0 S4: `pause` / `resume`: a paused room says no CHECK, counts no fall, hands no task, and resume forgets the gone marks.
Run: python -X utf8 smoke_10_s4.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10s4_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def sh(*a):
    p = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *a, '--room', str(room)], capture_output=True, timeout=90)
    return p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('A', 'working on T1')
r.append('B', 'ok')
r.update_roster(lambda ro: ro.update({'A': 'aaaa1111', 'B': 'bbbb2222'}))
(room / 'gone.json').write_text(json.dumps({'A': {'n': 1, 'why': '', 'tasks': ['T1'], 'procs': ['serve']}}))
before = [k for k, _ in chat.failures(r)]
ok('before the pause a gone agent with a task is a CHECK', any(k.startswith('gone') for k in before), before)
out = sh('pause', '--as', 'A')
ok('an agent cannot pause the room', not chat.is_paused(r) and ('lead' in out.lower() or 'lead' in out), out)
out = sh('pause', '--as', 'LEAD', 'the machine goes off')
ok('the lead pauses it', chat.is_paused(r) is True and chat.pause_info(r)['why'] == 'the machine goes off', out)
ok('a paused room says no CHECK', chat.failures(r) == [], chat.failures(r))
st = json.loads(sh('status', '--as', 'LEAD'))
ok('status shows the pause', (st.get('paused') or {}).get('by') == 'LEAD', st.get('paused'))
ok('wake_summary says it', 'paused' in chat.wake_summary(r).lower(), chat.wake_summary(r))
ok('sweep_left leaves the roster alone', chat.sweep_left(r, now=time.time() + 10 * 3600) == [])
ok('pausing twice says so', 'already' in sh('pause', '--as', 'LEAD'))
out = sh('resume', '--as', 'LEAD')
ok('resume ends the pause', not chat.is_paused(r) and (room / 'resumed.json').exists(), out)
ok('and forgets the gone marks', json.loads((room / 'gone.json').read_text()) == {})
ok('the CHECK for the gone agent does not come back', not any(k.startswith('gone') for k, _ in chat.failures(r)), chat.failures(r))
ok('the lead remedies are counted as events', {json.loads(x)['key'] for x in (room / 'events.jsonl').read_text().splitlines()} >= {'pause', 'resume'})
# a run that ended while the room stood still is named at resume
sh('pause', '--as', 'LEAD')
import cost  # noqa: E402
ended = []
chat.agent_ended = lambda aid: aid == 'bbbb2222'
ok('is_paused is a bool', chat.is_paused(r) is True)
import io, contextlib  # noqa: E402
buf = io.StringIO()
class NS: name = 'LEAD'; pairs = []
with contextlib.redirect_stdout(buf):
    chat.cmd_resume(r, NS)
ok('resume names who to start again, with prompt and state', 'B' in buf.getvalue() and 'B.state.md' in buf.getvalue() and 'A.state.md' not in buf.getvalue(), buf.getvalue())
print('FAILS', fails)
sys.exit(1 if fails else 0)
