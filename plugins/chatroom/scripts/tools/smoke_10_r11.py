"""1.0 R11: the WAKE line counts the agents at work from their true state: one whose run ended (gone, or stopped) is named, not counted.
Run: python -X utf8 smoke_10_r11.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r11_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B', 'C'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
for k in 'ABC':
    r.append(k, f'hello from {k}')
o = chat.wake_summary(r)
ok('R11 nobody gone: three at work, nothing away', '3 working' in o and 'Not at work' not in o, o)
(room / 'gone.json').write_text(json.dumps({'B': {'n': 2, 'why': '', 'tasks': [], 'procs': []}}))
o = chat.wake_summary(r)
ok('R11 B left: two at work, B named', '2 working' in o and 'Not at work (their run ended): B.' in o, o)
r.append('B', 'I am back')
o = chat.wake_summary(r)
ok('R11 B wrote again: at work', '3 working' in o and 'Not at work' not in o, o)
print('fails', fails)
sys.exit(1 if fails else 0)
