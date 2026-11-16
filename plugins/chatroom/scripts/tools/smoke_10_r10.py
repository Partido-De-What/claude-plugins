"""1.0 R10: after a compaction `read` said "no new messages" (the place had moved on): `read --last N` and `read --since #n` give
the messages back without moving anyone's place. Run: python -X utf8 smoke_10_r10.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r10_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'      # a fresh config dir has no uv environment yet: relaunching into it costs a minute
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def read(*args):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'read', *args, '--room', str(room)], capture_output=True, stdin=subprocess.DEVNULL, timeout=200)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
for i in range(1, 7):
    r.append('A' if i % 2 else 'B', f'message number {i} MARK{i}')
r.set_cursor('B', 6)                                    # B has read everything: a plain read says nothing is new
c, o = read('--as', 'B')
ok('R10 a plain read after the place moved says nothing new', 'MARK' not in o, o)
c, o = read('--last', '2', '--as', 'B')
ok('R10 read --last 2: the last two, in full', c == 0 and 'MARK5' in o and 'MARK6' in o and 'MARK4' not in o, (c, o))
c, o = read('--since', '#4')
ok('R10 read --since #4: what came after #4, no --as needed', c == 0 and 'MARK5' in o and 'MARK6' in o and 'MARK4' not in o, (c, o))
ok('R10 the place did not move back', r.cursor('B') == 6, r.cursor('B'))
c, o = read('--since', '9')
ok('R10 read --since past the end: says so', c == 0 and 'MARK' not in o, (c, o))
print('fails', fails)
sys.exit(1 if fails else 0)
