"""1.0 R9: a tag, or a task, for an agent that ended its run: nobody told the lead (a task unread for 11 minutes, an order that never
arrived). Now the ALERT of the post and a CHECK of the relay say it, with the command to resume the agent.
Run: python -X utf8 smoke_10_r9.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r9_'))
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


def alert(room, author, text):
    n = room.append(author, text)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        chat.print_alert(room, author, n, text)
    return n, buf.getvalue()


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B', 'C'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
(room / 'roster.json').write_text(json.dumps({'A': 'aaaaaaaa1', 'B': 'bbbbbbbb2', 'C': 'cccccccc3'}), encoding='utf-8')
r = chat.Room(room)
r.append('A', 'start')
r.append('B', 'my last message')
(room / 'gone.json').write_text(json.dumps({'B': {'n': 2, 'why': 'idle', 'tasks': [], 'procs': []}}), encoding='utf-8')

n, o = alert(r, 'LEAD', '@B take the T3 task')
ok('R9 a tag to an agent that ended says GONE with its id to resume', 'GONE B' in o and 'bbbbbbbb2' in o, o)
n2, o = alert(r, 'LEAD', '@C and what about you')
ok('R9 a tag to a live agent says nothing of the kind', 'GONE' not in o, o)
keys = [k for k, _ in chat.failures(r)]
ok('R9 the relay has a CHECK for the unread tag', any(k == f'gonetag:B:{n}' for k in keys), keys)
r.append('B', 'I am back')
(room / 'gone.json').write_text(json.dumps({'B': {'n': 2}}), encoding='utf-8')
n3, o = alert(r, 'LEAD', '@B thanks')
ok('R9 an agent that wrote again is no longer gone', 'GONE' not in o and not any(k.startswith('gonetag:B') for k, _ in chat.failures(r)), o)
print('fails', fails)
sys.exit(1 if fails else 0)
