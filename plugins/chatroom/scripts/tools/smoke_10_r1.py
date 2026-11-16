"""1.0 R1: the relay of a lead delivers the messages of a second lead. self_names lists every lead of the room, so the relay of
LEAD skipped what LEAD2 wrote (a whole room followed through an outside sentinel). Only the lead that runs the relay is skipped.
Run: python -X utf8 smoke_10_r1.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r1_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def relay(room, who):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'alerts', *(['--as', who] if who else []), '--messages', '--room', str(room)], capture_output=True, timeout=120)
    return (r.stdout + r.stderr).decode('utf-8', errors='replace')


room = BASE / 'room'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B', '--lang', 'en'], capture_output=True)
cfg = json.loads((room / 'config.json').read_text(encoding='utf-8'))
cfg['self_names'] = ['LEAD', 'LEAD2']
(room / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
r = chat.Room(room)
r.append('LEAD2', 'second lead plain note ZEBRA')
r.append('LEAD', 'first lead own note YAK')
r.append('A', '@LEAD2 question for the second lead?')
o = relay(room, 'LEAD')
ok('R1 relay of LEAD delivers a message of LEAD2', 'ZEBRA' in o, o)
ok('R1 relay of LEAD skips its own message', 'YAK' not in o, o)
o2 = relay(room, 'LEAD2')
ok('R1 relay of LEAD2 delivers a message of LEAD', 'YAK' in o2, o2)
ok('R1 relay of LEAD2 skips its own message', 'ZEBRA' not in o2, o2)
ok('R1 relay of LEAD2 wakes on a tag to LEAD2', 'question for the second lead' in o2, o2)
# without --as and with two leads: the relay speaks for the first lead only, says so, and still delivers the other lead
o3 = relay(room, None)
ok('R1 no --as, two leads: the relay says to pass --as', '--as' in o3 and 'LEAD ' in o3, o3)
ok('R1 no --as, two leads: the second lead is delivered', 'ZEBRA' in o3, o3)
ok('R1 no --as, two leads: the first lead is skipped', 'YAK' not in o3, o3)
# the relay that stays on (--follow) runs the same loop: its ownership flag must not shadow the lead names
room2 = BASE / 'room2'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room2), '--participants', 'A,B', '--lang', 'en'], capture_output=True)
cfg = json.loads((room2 / 'config.json').read_text(encoding='utf-8'))
cfg['self_names'] = ['LEAD', 'LEAD2']
(room2 / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
chat.Room(room2).append('LEAD2', 'follow note ZEBRA')
p = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--follow', '--messages', '--as', 'LEAD', '--room', str(room2)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
try:
    first = p.stdout.readline()
finally:
    p.kill()
    p.wait()
ok('R1 a following relay of LEAD delivers a message of LEAD2', 'ZEBRA' in first, first)
print('fails', fails)
sys.exit(1 if fails else 0)
