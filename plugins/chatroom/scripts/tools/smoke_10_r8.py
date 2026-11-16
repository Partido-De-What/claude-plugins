"""1.0 R8: a DECISION: / DECIDE: of the lead with no tag wakes every idle agent, and an idle agent wakes when the one it declared
in waits_on posts. Run: python -X utf8 smoke_10_r8.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r8_'))
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
(room / 'config.json').write_text(json.dumps({'participants': ['KERN', 'RELE', 'OTHER'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('KERN', 'idle', status=chat.IDLE)
r.append('RELE', 'idle waiting for KERN', status=chat.IDLE, state={'waits_on': 'KERN'})
r.append('OTHER', 'idle', status=chat.IDLE, state={'waits_on': 'LEAD'})
dec = r.append('KERN', 'DECISION: the plan v2 is merged, everybody rebases')
tagged = r.append('LEAD', 'DECISION: @RELE do T5 now, and the others keep out of chat.py')
short = r.append('LEAD', 'DECIDE: @RELE do T5 now')
note = r.append('KERN', 'decision: lower case is a sentence')
ms = {x['n']: x for x in r.messages()}
ok('an untagged DECISION of an agent wakes an idle agent', r.wakes(ms[dec], 'OTHER'))
ok('a tagged DECISION of the lead wakes the others too', r.wakes(ms[tagged], 'OTHER') and r.wakes(ms[tagged], 'KERN'))
ok('DECIDE stays a message to who is tagged', not r.wakes(ms[short], 'KERN') and r.wakes(ms[short], 'RELE'))
ok('a sentence with the word does not wake', not r.wakes(ms[note], 'OTHER'))
ok('decision_for_all reads the heading only', chat.decision_for_all('DECISION: x') and not chat.decision_for_all('We DECISION: x') and not chat.decision_for_all('decision: x') and chat.decision_for_all('@A DECISIONE: x'))
# waits_on
post = r.append('KERN', 'T7 is done, the result is in the board')
ms = {x['n']: x for x in r.messages()}
ok('RELE waits_on KERN: a message of KERN wakes it', r.wakes(ms[post], 'RELE'), r.waits_on_of('RELE'))
ok('OTHER did not wait for KERN: it stays asleep', not r.wakes(ms[post], 'OTHER'))
st = r.append('KERN', 'working', status=True)
ms = {x['n']: x for x in r.messages()}
ok('a status of KERN does not wake RELE', not r.wakes(ms[st], 'RELE'))
print('FAILS', fails)
sys.exit(1 if fails else 0)
