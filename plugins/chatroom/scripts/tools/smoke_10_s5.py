"""1.0 S5: an agent that takes or closes a task while its notebook state is old or missing is told to rewrite it (the state is what a
compaction or a rotation leaves it). Run: python -X utf8 smoke_10_s5.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10s5_'))
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
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('A', 'first')


def call(who, **args):
    return chat.mcp_call(r, who, 'task', {'room': str(room), 'as': who, **args})[0]


state = room / 'notes' / 'A.state.md'
ok('S5 no state at all: take says to write it', 'no notebook state' in call('A', action='add', text='t1') + call('A', action='take', id='T1'))
call('A', action='note', id='T1', text='plain')
state.parent.mkdir(exist_ok=True)
state.write_text('10:00 goal\n')
ok('S5 a fresh state: nothing said', 'notebook state' not in call('A', action='handoff', id='T1', to='B', note='x'), 'fresh')
old = time.time() - 45 * 60
os.utime(state, (old, old))
o = call('A', action='accept', id='T1') + call('A', action='take', id='T1')
ok('S5 a state 45 minutes old: the age is said', '45 minutes old' in o, o)
ok('S5 a note or an add is not a decision: nothing said', 'notebook state' not in call('A', action='note', id='T1', text='n') + call('A', action='add', text='t2'))
ok('S5 the lead is never asked', 'notebook state' not in call('LEAD', action='decide', text='rule one'))
print('fails', fails)
sys.exit(1 if fails else 0)
