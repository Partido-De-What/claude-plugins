"""1.0 A5+A6: `alerts --from NAME` (the sentinel on one author), `spawn consult` (one question to many models, with a fake provider),
`sources` (the register of what the room read). Run: python -X utf8 smoke_10_a5.py"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10a5_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402
import sources  # noqa: E402
from spawn import consult as sc  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def sh(*a, limit=60):
    p = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *a, '--room', str(room)], capture_output=True, timeout=limit)
    return p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['W1', 'W2'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
r.append('W1', 'old message of W1')
r.append('W2', 'hello')

# A5: the sentinel
p = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--follow', '--from', 'W1', '--room', str(room)],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
time.sleep(3)
ok('the sentinel waits (nothing new of W1)', p.poll() is None)
r.append('W2', 'not for the sentinel')
time.sleep(3)
ok('a message of another author does not end it', p.poll() is None)
r.append('W1', 'the result is ready')
try:
    out, _ = p.communicate(timeout=20)
except subprocess.TimeoutExpired:
    p.kill()
    out = 'TIMEOUT'
ok('it ends when W1 writes and prints it', 'the result is ready' in out and 'old message' not in out, out)
out2 = sh('alerts', '--from', 'W1')
ok('a second start does not print it again', 'the result is ready' not in out2, out2)

# A5: the consult, with a fake provider
models = [{'canonical': 'm-one', 'aa': 50, 'routes': [{'adapter': 'hostA', 'model_id': 'one', 'free': True}]},
          {'canonical': 'm-two', 'aa': 40, 'routes': [{'adapter': 'hostB', 'model_id': 'two', 'free': True}, {'adapter': 'hostA', 'model_id': 'two', 'free': True}]},
          {'canonical': 'm-three', 'aa': 30, 'routes': [{'adapter': 'nokey', 'model_id': 'x', 'free': True}]}]
has_key = lambda adapter: adapter != 'nokey'


def fake(adapter, model, messages, **kw):
    if adapter == 'hostB':
        raise RuntimeError('quota')
    return {'text': f'answer of {model} on {adapter} ' + 'x' * 500}


picked = sc.pick(10, catalog_models=models, has_key=has_key)
ok('a model with no key is not asked', [m['canonical'] for _, m in picked] == ['m-one', 'm-two'], picked)
lines = []
rows = sc.consult('question', BASE / 'out', picked, has_key, fake, say=lines.append)
ok('every answer is a file', sorted(f.name for f in (BASE / 'out').glob('*.md')) == ['01-m-one.md', '02-m-two.md'], list((BASE / 'out').iterdir()))
ok('a failing route falls to the next of the same model', rows[1]['host'] == 'hostA' and rows[1]['errors'] and 'quota' in rows[1]['errors'][0], rows)
ok('the state file lists both', len(json.loads((BASE / 'out' / 'stato.json').read_text(encoding='utf-8'))) == 2)
ids = sc.pick(5, ids='hostA:org/a,org/b')
ok('--ids picks a host and its models', [m['routes'][0]['model_id'] for _, m in ids] == ['org/a', 'org/b'] and ids[0][0] == 'HO', ids)
short = sc.consult('q', BASE / 'out2', picked[:1], has_key, lambda *a, **k: {'text': 'no'}, say=lambda x: None)
ok('an answer under 400 characters is not kept', not short[0]['host'] and not list((BASE / 'out2').glob('*.md')), short)

# A6: the register
out = sh('sources')
ok('an empty register says so', 'no source' in out, out)
out = sh('sources', 'add', 'https://example.org/a', 'a paper on', 'speech', '--as', 'W1')
ok('add registers', 'registered' in out, out)
sh('sources', 'add', 'https://example.org/b', 'second', '--as', 'W2')
out = sh('sources', 'add', 'https://example.org/a', 'a better summary', '--as', 'W2')
ok('the same URL is updated, not doubled', 'updated' in out and len(sources.rows(r)) == 2, out)
out = sh('sources')
ok('the list has link, summary and author', 'https://example.org/a - a better summary (W2' in out and 'https://example.org/b' in out, out)
# a topic: the register moves into the topic folder
cfg = json.loads((room / 'config.json').read_text(encoding='utf-8'))
cfg['topic_profile'] = 'speech'
(room / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
import lessons  # noqa: E402
ok('with a topic profile the register is in the topic folder', sources.path(r) == lessons.topic_dir('speech') / 'sources.jsonl', sources.path(r))
sh('sources', 'add', 'https://example.org/c', 'in the topic', '--as', 'W1')
ok('and it is written there', 'example.org/c' in (lessons.topic_dir('speech') / 'sources.jsonl').read_text(encoding='utf-8'))
# the same register is written by two at once: nothing is lost
(lessons.topic_dir('speech') / 'sources.jsonl').unlink()
ts = [threading.Thread(target=sources.add, args=(r, 'W1', f'https://example.org/t{i}', 'n')) for i in range(8)]
[t.start() for t in ts]
[t.join() for t in ts]
ok('eight adds at once keep eight rows', len(sources.rows(r)) == 8, len(sources.rows(r)))
print('FAILS', fails)
sys.exit(1 if fails else 0)
