"""1.0, A1 + A3: a cause that keeps firing in a room (the same refusal, the same remedy by hand) becomes a CHECK for the lead
with the lesson command ready, while the room runs. Run: python -X utf8 smoke_10_a1.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10a1_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:500]}]'), flush=True)
    fails += not cond


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'user_name': 'USER', 'self_names': ['LEAD'], 'participants': ['A', 'B'], 'lang': 'en'}))
r = chat.Room(room)
r.append('LEAD', 'start')
chat.use('en')

ok('A1 a quiet room has nothing to learn', chat.learn_checks(r) == [], chat.learn_checks(r))
for who in ('A', 'A'):
    chat.note_event(r, 'refusal', 'research:hold', who, detail='the GPU is already held by B')
ok('A1 twice is not yet a pattern', chat.learn_checks(r) == [], chat.learn_checks(r))
chat.note_event(r, 'refusal', 'research:hold', 'B', detail='a run is going')
got = chat.learn_checks(r)
ok('A1 the third time the lead is told, with the cause and who met it',
   len(got) == 1 and got[0][0] == 'learn:refusal:research:hold:3' and 'research:hold' in got[0][1] and 'A, B' in got[0][1], got)
ok('A1 the line carries the command to copy', 'lessons propose' in got[0][1] and '--note "refusal:research:hold x3"' in got[0][1], got)
for _ in range(4):
    chat.note_event(r, 'refusal', 'research:hold', 'A', detail='a run is going')
ok('A1 the key does not change at 7 times: said once', [k for k, _ in chat.learn_checks(r)] == ['learn:refusal:research:hold:3'], chat.learn_checks(r))
for _ in range(3):
    chat.note_event(r, 'refusal', 'research:hold', 'A', detail='a run is going')
ok('A1 at 10 times it is said again', [k for k, _ in chat.learn_checks(r)] == ['learn:refusal:research:hold:10'], chat.learn_checks(r))
for _ in range(5):
    chat.note_event(r, 'kernel', 'hold', 'A')
    chat.note_event(r, 'check', 'gone', 'A')
ok('A1 actions that passed and plain checks are not causes to learn from', len(chat.learn_checks(r)) == 1, chat.learn_checks(r))
for _ in range(3):
    chat.note_event(r, 'lead', 'rotate', 'LEAD', detail='A')
ok('A1 a remedy the lead repeats by hand is a cause too', 'learn:lead:rotate:3' in [k for k, _ in chat.learn_checks(r)], chat.learn_checks(r))
ok('A1 the room checks carry the learn lines', any(k.startswith('learn:') for k, _ in chat.failures(r)), [k for k, _ in chat.failures(r)])
print(f'fails {fails}')
sys.exit(1 if fails else 0)
