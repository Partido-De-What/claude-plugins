"""1.0 S7+S8: an agent that left with nothing in hand and is silent for hours leaves the roster (it returns with its next command); read_by
does not wait for it; the status says the call budget is per agent. Run: python -X utf8 smoke_10_s7.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10s7_'))
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


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('A', 'hello')
r.append('B', 'hello')
r.append('LEAD', 'a message for all')
r.update_roster(lambda ro: ro.update({'A': 'aaaa1111', 'B': 'bbbb2222'}))
# A said its last word 4 hours ago and left with nothing in hand
lines = [json.loads(x) for x in (room / 'chat.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
for m in lines:
    if m['from'] == 'A':
        m['ts'] -= 4 * 3600
(room / 'chat.jsonl').write_text(''.join(json.dumps(m) + '\n' for m in lines), encoding='utf-8')
(room / 'gone.json').write_text(json.dumps({'A': {'n': 1, 'why': '', 'tasks': [], 'procs': []}}))
st = json.loads(subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'status', '--as', 'LEAD', '--room', str(room)], capture_output=True).stdout.decode('utf-8'))
ok('S8 the status names the budget as per agent', 'budget_calls_per_agent' in st and 'budget_calls' not in st, list(st))
last = [n for n, v in st['read_by'].items()][-1]
ok('S7 read_by does not wait for the one that left', 'A' in st['read_by'][last]['left'] and 'A' not in st['read_by'][last]['not_yet'], st['read_by'])
ok('S7 the roster has it until the sweep', 'A' in r.roster())
gone = chat.sweep_left(r)
ok('S7 sweep takes it out of the roster and keeps its address', gone == ['A'] and 'A' not in r.roster() and 'B' in r.roster()
   and json.loads((room / 'roster.left.json').read_text())['A'] == 'aaaa1111', (gone, r.roster()))
(room / 'gone.json').write_text(json.dumps({'B': {'n': 2, 'why': 'task', 'tasks': ['T1'], 'procs': []}}))
ok('S7 one that left holding a task stays', chat.sweep_left(r) == [] and 'B' in r.roster())
print('fails', fails)
sys.exit(1 if fails else 0)
