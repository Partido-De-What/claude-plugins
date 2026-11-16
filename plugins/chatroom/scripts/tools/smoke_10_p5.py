"""1.0 P5: post says the number and the hour of the message; {n} and {time} (or {ora}) in any agent's text are filled by chat.py, not
written from memory. Run: python -X utf8 smoke_10_p5.py"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10p5_'))
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
r.append('B', 'hello')
out, err = chat.mcp_call(r, 'A', 'chat_post', {'room': str(room), 'as': 'A', 'text': 'checked at {time}, message #{n}, {ora}'})
m = r.messages()[-1]
ok('P5 the answer has the number and the hour', not err and re.search(r'#2 at \d\d:\d\d:\d\d', out), out)
ok('P5 an agent text is filled in', m['from'] == 'A' and re.search(r'at \d\d:\d\d, message #2, \d\d:\d\d', m['text']), m)
print('fails', fails)
sys.exit(1 if fails else 0)
