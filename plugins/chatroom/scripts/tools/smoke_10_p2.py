"""1.0 P2: a draft held back ("crossed") was lost when another post of the same agent went through (one file for each name, and a
successful post deleted every file of the name). Now each held text has its own file, and a post removes only its own.
Run: python -X utf8 smoke_10_p2.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10p2_'))
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


def post(text):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'post', '--as', 'A', '--room', str(room)], input=text.encode('utf-8'),
                       capture_output=True, timeout=200)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def drafts():
    d = room / 'drafts'
    return {f.name: f.read_text(encoding='utf-8') for f in d.glob('A.*.txt')} if d.is_dir() else {}


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
post('hello first')
r.append('B', '@A first thing for you')
c1, o1 = post('draft ONE')
r.append('B', '@A second thing for you')
c2, o2 = post('draft TWO')
ok('R P2 two crossed posts were both refused', c1 != 0 and c2 != 0, (c1, c2, o1, o2))
path1 = re.search(r'kept in (\S+?):? post', o1) or re.search(r'kept in (\S+)', o1)
path2 = re.search(r'kept in (\S+?):? post', o2) or re.search(r'kept in (\S+)', o2)
p1, p2 = (m.group(1).rstrip(':.') if m else '' for m in (path1, path2))
ok('R P2 each held post prints its own path', p1 and p2 and p1 != p2, (p1, p2))
ok('R P2 both drafts are on disk', sorted(drafts().values()) == ['draft ONE', 'draft TWO'], drafts())
c3, o3 = post('plain three')
ok('R P2 a post that goes through keeps the drafts of the others', c3 == 0 and sorted(drafts().values()) == ['draft ONE', 'draft TWO'], (c3, o3, drafts()))
c4, o4 = post('draft ONE')
ok('R P2 posting a draft again removes only that one', c4 == 0 and sorted(drafts().values()) == ['draft TWO'], (c4, o4, drafts()))
print('fails', fails)
sys.exit(1 if fails else 0)
