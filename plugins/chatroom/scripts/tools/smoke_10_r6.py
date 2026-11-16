"""1.0 R6: the relay cut a message to the lead at 220 characters (the lead then read chat.jsonl by hand). A message that tags
the lead comes whole; the others stay compact. Run: python -X utf8 smoke_10_r6.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r6_'))
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


room = BASE / 'room'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B', '--lang', 'en'], capture_output=True)
long_to_lead = '@LEAD decision needed: ' + ' '.join(f'word{i}' for i in range(120)) + ' ENDTAG'
long_plain = 'plain note for the room ' + ' '.join(f'word{i}' for i in range(120)) + ' ENDPLAIN'
r = chat.Room(room)
r.append('A', long_to_lead)
r.append('B', long_plain)
p = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--as', 'LEAD', '--messages', '--room', str(room)], capture_output=True, timeout=200)
o = (p.stdout + p.stderr).decode('utf-8', errors='replace')
ok('R6 a message that tags the lead comes whole', 'ENDTAG' in o and '[...]' not in o.split('WATCH #2')[0], o)
ok('R6 a message for the room stays compact', 'WATCH #2' in o and 'ENDPLAIN' not in o and '[...]' in o.split('WATCH #2')[1], o)
print('fails', fails)
sys.exit(1 if fails else 0)
