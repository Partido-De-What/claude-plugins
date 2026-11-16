"""1.0 P3: a typed post (status, finding) goes through with the numbers it `missed`: an agent that posts only statuses and then waits or
works never read the tag (wait said "no new messages", the tag stayed unread). Now the next command of the author brings them again, once.
Run: python -X utf8 smoke_10_p3.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10p3_'))
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


def run(*args, stdin=b''):
    t0 = time.time()
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *args, '--as', 'A', '--room', str(room)], input=stdin, capture_output=True, timeout=200)
    return (r.stdout + r.stderr).decode('utf-8', errors='replace'), time.time() - t0


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
run('post', stdin=b'first position')
r.append('B', '@A please answer MARKQ1')
o, _ = run('post', '--status', stdin=b'step one, 10%')
ok('R P3 the status itself shows what it missed', 'MARKQ1' in o, o)
o, _ = run('board')
ok('R P3 the next command of the author brings the missed tag again', 'MARKQ1' in o and 'TASKS' in o, o)
o, _ = run('board')
ok('R P3 once: the command after that is quiet', 'MARKQ1' not in o, o)
r.append('B', '@A and now MARKQ2')
run('post', '--status', stdin=b'step two, 30%')
o, took = run('wait', '--timeout', '60')
ok('R P3 a wait with a missed tag returns at once with it', 'MARKQ2' in o and took < 40, (took, o))
print('fails', fails)
sys.exit(1 if fails else 0)
