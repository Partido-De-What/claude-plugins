"""1.0 R4: the relay does not wake the lead for a message it read itself, keeps its place until the lines are handed over, and the room
waits for the restart after a clean exit before it says the relay is off. Run: python -X utf8 smoke_10_r4.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r4_'))
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


def mkroom(name):
    room = BASE / name
    room.mkdir()
    (room / 'config.json').write_text(json.dumps({'participants': ['A'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
    r = chat.Room(room)
    r.append('A', 'hello')
    r.append('A', '@LEAD I need a decision on the plan')
    r.set_cursor('_alerts_LEAD', 1)
    return room, r


def relay(room, *extra, limit=10):
    p = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--follow', '--messages', '--until-line', '--as', 'LEAD', *extra, '--room', str(room)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
    try:
        p.wait(timeout=limit)
        return p.stdout.read(), True
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
        return p.stdout.read(), False


# 1. the lead read the message itself: no wake
room, r = mkroom('read')
r.set_cursor('LEAD', 2)
out, ended = relay(room, '--batch', '1')
ok('a message the lead read does not wake it', not ended, out)
ev = [json.loads(x) for x in (room / 'events.jsonl').read_text(encoding='utf-8').splitlines()] if (room / 'events.jsonl').exists() else []
ok('the empty wake is counted as an event', any(e['kind'] == 'relay' and e['key'] == 'empty' for e in ev), ev)
# 2. not read: it wakes (control)
room, r = mkroom('unread')
out, ended = relay(room, '--batch', '1')
ok('an unread message wakes the lead', ended and 'decision' in out, out)
# 3. the relay's own place moves at the hand-over, not when the lines are queued
room, r = mkroom('killed')
out, ended = relay(room, '--batch', '600', limit=8)       # the pace holds the lines: the relay is killed with them queued
ok('the relay waited with the lines', not ended, out)
ok('its place did not move past lines nobody saw', r.cursor('_alerts_LEAD') == 1, r.cursor('_alerts_LEAD'))
out, ended = relay(room, '--batch', '1')
ok('the next relay shows them', ended and 'decision' in out, out)
ok('and the place moves when they are handed over', r.cursor('_alerts_LEAD') == 2, r.cursor('_alerts_LEAD'))
# 4. the clean exit: the room waits for the restart
room, r = mkroom('exit')
(room / 'relay_alerts_LEAD.owner').write_text('999999 0')       # a pid that is not running
ok('a dead relay is reported', chat.relay_down(r))
(room / 'relay_alerts_LEAD.exit').write_text(str(time.time()))
ok('not just after its own clean exit', not chat.relay_down(r))
(room / 'relay_alerts_LEAD.exit').write_text(str(time.time() - 3 * chat.RELAY_RESTART_S))
ok('but after the wait', chat.relay_down(r))
out, ended = relay(mkroom('exit2')[0], '--batch', '1')
ok('a relay that ends by itself leaves the stamp', ended and (BASE / 'exit2' / 'relay_alerts_LEAD.exit').exists(), out)
print('FAILS', fails)
sys.exit(1 if fails else 0)
