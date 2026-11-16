"""1.0 S3: right states. An agent that left with nothing in hand (finished, or idle with nothing new) is not a fall; one that comes back
(any command, or its tools moving the transcript) is no longer gone or closed; a hold is `held`, not `waiting`.
Run: python -X utf8 smoke_10_s3.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10s3_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0
AID = 'a1b2c3d4e5f6'


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def run(*args, who='LEAD'):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *args, '--as', who, '--room', str(room)], capture_output=True, timeout=100)
    return (r.stdout + r.stderr).decode('utf-8', errors='replace')


def turn():
    return json.loads(run('status'))['turn']['A']


def gone(**kw):
    (room / 'gone.json').write_text(json.dumps({'A': {'n': last, 'why': '', 'tasks': [], 'procs': [], **kw}}))


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('A', 'working on it')
r.append('B', 'ok')
last = max(m['n'] for m in r.messages() if m['from'] == 'A')
r.update_roster(lambda ro: ro.update({'A': AID}))
d = BASE / 'claude' / 'projects' / 'p' / 's' / 'subagents'
d.mkdir(parents=True)
log = d / f'agent-{AID}.jsonl'
log.write_text(json.dumps({'type': 'assistant', 'message': {'role': 'assistant', 'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'done'}]}}) + '\n')
past = time.time() - 600
os.utime(log, (past, past))

gone(why='')
ok('S3 an agent that finished with nothing in hand is not a fall', 'ended its run' not in run('check'), run('check'))
gone(why='idle')
ok('S3 nor one that waited in idle with nothing new', 'ended its run' not in run('check'))
gone(why='task', tasks=['T6'])
ok('S3 but one that left holding a task still is', 'T6' in run('check'))
gone(why='')
ok('S3 status: gone and silent = closed', turn() == 'closed', turn())
os.utime(log, None)
ok('S3 its tools moved the transcript after it went: not closed', turn() != 'closed', turn())
os.utime(log, (past, past))
run('read', '--focus', who='A')
ok('S3 any command of it clears its gone.json entry', 'A' not in json.loads((room / 'gone.json').read_text()), (room / 'gone.json').read_text())
ok('S3 and it is not closed', turn() != 'closed', turn())
(room / 'waiting_A.txt').write_text(f'{time.time() + 300:.0f} {os.getpid()}')
ok('S3 its run ended and a hold keeps it: held, not waiting', turn() == 'held', turn())
print('fails', fails)
sys.exit(1 if fails else 0)
