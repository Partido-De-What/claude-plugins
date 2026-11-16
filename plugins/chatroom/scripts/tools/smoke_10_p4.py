"""1.0 P4+P6+P7: a long message goes whole to notes/ and the chat carries its start, tags and hash; a status has two percentages
(pct, runs_pct); the line of `task amend` says the version and what the files were. Run: python -X utf8 smoke_10_p4.py"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10p4_'))
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


def sh(*a):
    p = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *a, '--room', str(room)], capture_output=True, timeout=90)
    return p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')


def last(who=None):
    return [m for m in chat.Room(room).messages() if who is None or m['from'] == who][-1]


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['W1', 'W2'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('W2', 'hello')

# P4
long_text = 'The spec of the work.\n' + ''.join(f'line {i}: some words of the specification, long enough to count\n' for i in range(80)) + '@W2 please read the end.'
sh('post', '--as', 'W1', long_text)
m = last('W1')
f = list((room / 'notes').glob('msg-W1-*.md'))
ok('a long message is kept whole in notes/', len(f) == 1 and f[0].read_text(encoding='utf-8').strip() == long_text.strip(), f)
ok('the chat carries a short start, not the whole text', len(m['text']) < 1500 and m['text'].startswith('The spec of the work.'), len(m['text']))
ok('with the path and the hash of the file', f and str(f[0]) in m['text'] and hashlib.sha256(long_text.encode('utf-8')).hexdigest()[:12] in m['text'], m['text'][-300:])
ok('a tag that the cut would lose stays', chat.tags(m['text'], 'W2'), m['text'][-300:])
sh('post', '--as', 'W1', 'short ' * 100)
ok('a message under the limit is whole', last('W1')['text'] == ('short ' * 100).strip(), last('W1')['text'])
plan = 'PLAN v1: the plan\n' + 'a step of the plan with some words\n' * 150
sh('post', '--as', 'W1', plan)
ok('a plan stays whole: everyone reads it', len(last('W1')['text']) >= len(plan.strip()), len(last('W1')['text']))
sh('post', '--as', 'USER', long_text)
ok('a message of the user stays whole', len(last('USER')['text']) >= len(long_text.strip()), len(last('USER')['text']))
sh('post', '--as', 'W1', long_text.replace('The spec', 'The same spec', 1))
ok('another text is another file', len(list((room / 'notes').glob('msg-W1-*.md'))) == 2)

# P6
sh('post', '--as', 'W1', '--status', json.dumps({'task': 'T1', 'step': 'work', 'pct': 60, 'runs_pct': 40}))
m = last('W1')
ok('a status has two percentages, two fields', m['state'].get('pct') == 60 and m['state'].get('runs_pct') == 40, m)
ok('the line says which is which', '(60%)' in m['text'] and 'runs 40%' in m['text'], m['text'])
out = sh('post', '--as', 'W1', '--status', json.dumps({'pct': 60, 'runs_pct': 140}))
ok('runs_pct over 100 is refused', 'runs_pct' in out and last('W1')['text'] == m['text'], out)

# P7
sh('task', 'add', 'work on a', '--files', 'a.py', '--as', 'LEAD')
tid = chat.Room(room).dir and json.loads((room / 'board.json').read_text(encoding='utf-8'))['tasks'][-1]['id']
sh('task', 'take', tid, '--as', 'W1')
out = sh('task', 'amend', tid, '--as', 'W1', '--files', 'b.py')
ok('the amend line names the version and what the files were', 'v' in out and 'a.py' in out and 'b.py' in out and 'were' in out, out)
print('FAILS', fails)
sys.exit(1 if fails else 0)
