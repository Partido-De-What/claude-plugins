"""1.0 P3b: the MCP tools bring again what a typed post missed, as the shell commands do (chat_wait, board, task, notebook).
Run: python -X utf8 smoke_10_t26.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10t26_'))
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


def miss(tag):
    r.append('B', f'@A answer {tag}')
    n = max(m['n'] for m in r.messages())
    (room / 'missed_A.json').write_text(json.dumps([n]))


def call(tool, **args):
    return chat.mcp_call(r, 'A', tool, {'room': str(room), 'as': 'A', **args})[0]


for tool, args in (('board', {}), ('task', {'action': 'add', 'text': 'x'}), ('notebook', {})):
    miss('MARK' + tool.upper())
    ok(f'P3b {tool} brings the missed tag again', 'MARK' + tool.upper() in call(tool, **args))
    ok(f'P3b and only once', 'MARK' + tool.upper() not in call(tool, **args))
miss('MARKWAIT')
t0 = time.time()
o = call('chat_wait', timeout=60)
ok('P3b chat_wait returns at once with the missed tag', 'MARKWAIT' in o and time.time() - t0 < 20, (time.time() - t0, o))
print('fails', fails)
sys.exit(1 if fails else 0)
