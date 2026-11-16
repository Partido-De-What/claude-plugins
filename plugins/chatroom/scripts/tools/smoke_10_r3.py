"""1.0 R3: a line counts as delivered to the lead when its relay has put it in front of it (not when it was queued), and it
comes again when no command of the lead follows. Run: python -X utf8 smoke_10_r3.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r3_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def sh(*a, limit=90):
    p = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *a], capture_output=True, timeout=limit)
    return p.stdout.decode('utf-8', 'replace')


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('A', 'hello')
r.append('A', '@LEAD I need a decision on the plan')
n = r.messages()[-1]['n']
r.set_cursor('_alerts_LEAD', 1)
out = sh('alerts', '--follow', '--messages', '--until-line', '--batch', '1', '--as', 'LEAD', '--room', str(room))
ok('the relay printed the tagged message', 'decision' in out, out)
rec = chat.read_json(room / 'relay_sent_LEAD.json', None)
ok('a hand-over record names the message and the lines', isinstance(rec, dict) and rec.get('upto') == n and any('decision' in x for x in rec.get('lines', [])), rec)
ok('delivered is marked at the hand-over', r.delivered('LEAD') == n, r.delivered('LEAD'))
r.count('LEAD', 'read')                              # at once: not yet a sign of reading
ok('a command in the same second does not confirm', (room / 'relay_sent_LEAD.json').exists())
time.sleep(chat.RELAY_CONFIRM_S + 1)
r.count('LEAD', 'read')
ok('a command after the hand-over confirms it', not (room / 'relay_sent_LEAD.json').exists())
import hold  # noqa: E402
(room / 'research').mkdir(exist_ok=True)
(room / 'research' / 'gpu.hold').write_text(json.dumps({'by': 'A', 'until': time.time() + 600}), encoding='utf-8')
(room / 'gone.json').write_text(json.dumps({'A': 1, 'B': 1}))
it = r.messages()
ok('a worker with a device hold is not closed', chat.turn_state(r, it, 'A', chat.gone_numbers(r), r.roster()) != 'closed' and chat.turn_state(r, it, 'B', chat.gone_numbers(r), r.roster()) == 'closed')
(room / 'gone.json').unlink()
# no command: the lines come again, twice at most
chat.relay_handover(r, 'LEAD', n, ['WATCH #2 A: @LEAD I need a decision'])
ok('nothing to redeliver at once', chat.relay_redeliver(r, 'LEAD') == '')
for want in (1, 2):
    rec = chat.read_json(room / 'relay_sent_LEAD.json', {})
    rec['ts'] = time.time() - 400
    (room / 'relay_sent_LEAD.json').write_text(json.dumps(rec), encoding='utf-8')
    again = chat.relay_redeliver(r, 'LEAD')
    ok(f'redelivery {want} carries the line', 'decision' in again and f'({want})' in again, again)
rec = chat.read_json(room / 'relay_sent_LEAD.json', {})
rec['ts'] = time.time() - 400
(room / 'relay_sent_LEAD.json').write_text(json.dumps(rec), encoding='utf-8')
ok('after two redeliveries it stops and forgets', chat.relay_redeliver(r, 'LEAD') == '' and not (room / 'relay_sent_LEAD.json').exists())
ev = [json.loads(x) for x in (room / 'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
ok('the relay leaves wake and redelivered events', {e['key'] for e in ev if e['kind'] == 'relay'} >= {'wake', 'redelivered'}, ev)
print('FAILS', fails)
sys.exit(1 if fails else 0)
