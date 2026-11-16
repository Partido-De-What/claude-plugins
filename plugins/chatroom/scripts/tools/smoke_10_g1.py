"""1.0 G1: the lead hears (a CHECK) when an agent near a compaction has an old or missing notebook state, with the hour it was written and the messages
since, and the line to send. Run: python -X utf8 smoke_10_g1.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10g1_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:600]}]'), flush=True)
    fails += not cond


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'user_name': 'USER', 'self_names': ['LEAD'], 'participants': ['A', 'B'], 'lang': 'en'}))
(room / 'roster.json').write_text(json.dumps({'A': 'aaaaaaaaaaaaaaaa', 'B': 'bbbbbbbbbbbbbbbb'}))
r = chat.Room(room)
chat.use('en')
for who in ('A', 'A', 'B'):
    r.append(who, 'work')
ctxs = {'aaaaaaaaaaaaaaaa': 160_000, 'bbbbbbbbbbbbbbbb': 90_000}
chat.agent_context = lambda aid: ctxs.get(aid)
old = lambda: [(k, t) for k, t in chat.failures(r) if k.startswith('oldstate:')]

got = old()
ok('no state, context near a compaction: the lead is told, with the line to send', len(got) == 1 and got[0][0].startswith('oldstate:A:') and 'no notebook state' in got[0][1]
   and '@A write your notebook state now' in got[0][1] and 'its messages so far: 2' in got[0][1], got)
ok('an agent with a small context is not mentioned', not any(k.startswith('oldstate:B') for k, _ in got), got)
notes = room / 'notes'
notes.mkdir()
st = notes / 'A.state.md'
st.write_text('goal | done')
os.utime(st, (time.time() - 3600, time.time() - 3600))
r.append('A', 'one more')
got = old()
ok('an old state says its age, the hour and the messages since', len(got) == 1 and '60 minutes old' in got[0][1] and time.strftime('%H:%M', time.localtime(time.time() - 3600)) in got[0][1]
   and 'its messages since then: 3' in got[0][1], got)
os.utime(st, None)
ok('a fresh state is not a CHECK', old() == [], old())
os.utime(st, (time.time() - 3600, time.time() - 3600))
ctxs['aaaaaaaaaaaaaaaa'] = 210_000
ok('the next 50k step is a new CHECK (once per step)', [k for k, _ in old()] != [], old())
chat.use('it')
ok('and it speaks Italian', 'token di contesto' in old()[0][1], old())
print('FAILS', fails)
sys.exit(1 if fails else 0)
