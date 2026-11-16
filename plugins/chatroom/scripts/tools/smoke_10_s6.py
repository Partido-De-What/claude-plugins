"""1.0 S6: an idle status says who it waits for (waits_on): the lead is alarmed only when it is the lead. Run: python -X utf8 smoke_10_s6.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10s6_'))
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
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B', 'AUD'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('A', 'first')


def idle(who, **st):
    o, err = chat.mcp_call(r, who, 'chat_post', {'room': str(room), 'as': who, 'idle': True, 'state': {'pct': 50, **st}})
    return o, err


def waiting():
    return [k for k, *_ in chat.waits_for_lead(r)]


o, err = idle('A', step='review', waits_on='AUD', needs='verdict of AUD, the lead can read it later')
ok('S6 the field is accepted and shown', not err and 'waits on: AUD' in r.messages()[-1]['text'], (o, r.messages()[-1]))
ok('S6 an idle that waits for another agent does not alarm the lead, even naming it', waiting() == [], waiting())
idle('B', step='question', waits_on='LEAD')
ok('S6 an idle that waits for the lead does', waiting() == ['B'], waiting())
r.append('AUD', 'LEAD, can you decide? the plan stands on it')
ok('S6 the old text rule still works for a message without the field', 'AUD' in waiting(), waiting())
print('fails', fails)
sys.exit(1 if fails else 0)
