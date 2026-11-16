"""1.0 P1: less noise. An idle that repeats the report of the author's last message is cut to its first line and the number of that message;
the queue's "run done" line for the agent is a pointer to the run's own line, not a copy of it. Run: python -X utf8 smoke_10_p1.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10p1_'))
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
REPORT = ('Done: the parser reads the three headers, the footer is skipped, the tests cover the empty file and the long line. '
          'The open point is the encoding of the second table, which I did not check against the sample from the dossier.\n'
          'Files: scripts/parse.py, tests/test_parse.py. Risks: the footer rule may eat a real row.')


def post(who, text, **kw):
    return chat.mcp_call(r, who, 'chat_post', {'room': str(room), 'as': who, 'text': text, **kw})


post('A', REPORT + ' 70%', status=True)
n = r.messages()[-1]['n']
post('A', 'waiting for B on the table\n' + REPORT, idle=True)
last = r.messages()[-1]
ok('P1 an idle that repeats the report is cut to its first line and the number', last['kind'] == 'idle' and f'#{n}' in last['text'] and len(last['text']) < len(REPORT) // 2, last)
post('B', 'ok, 30%', status=True)
post('B', 'waiting for A to answer the question about the second table: which encoding does the dossier give? ' * 2, idle=True)
ok('P1 a new reason to wait passes as it is', len(r.messages()[-1]['text']) > 150 and '#' not in r.messages()[-1]['text'][-30:], r.messages()[-1])
ok('P1 the queue pointer exists in both languages', 'att-7' in chat.say('kernel.queue.done_ref', n=7))
print('fails', fails)
sys.exit(1 if fails else 0)
