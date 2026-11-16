"""1.0, A4: topic profiles. A room bound to a topic keeps what it learns in the topic's own store; the next room on the same
topic starts with it in its prompts; a room on another topic does not see it; every change can be taken back.
Run: python -X utf8 smoke_10_a4.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10a4_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def run(room, *args):
    r = subprocess.run([sys.executable, CHAT, *args, '--room', str(room)], capture_output=True, timeout=120, env=dict(os.environ))
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def new_room(name):
    room = BASE / name
    subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B', '--lang', 'en'], capture_output=True, env=dict(os.environ))
    return room


def prompt(room):
    c, o = run(room, 'prompt', 'A', '--tools', 'shell', '--out', str(room / 'A.md'))
    return (room / 'A.md').read_text(encoding='utf-8') if c == 0 else o


RULE = 'measure the reference arm in the same run as the patch arm and read both absolute values'
store = BASE / 'claude' / 'chatroom' / 'topics' / 'kernel-inference' / 'lessons.json'

r1 = new_room('room1')
c, o = run(r1, 'lessons', 'propose', RULE, '--score', '4', '--reach', 'topic', '--scope', 'ratio metrics', '--expect', 'no discarded honest gain', '--as', 'LEAD')
ok('A4 a topic lesson in a room with no topic is refused', c != 0 and 'topic' in o, o)
c, o = run(r1, 'lessons', 'topic', 'use', 'kernel-inference', '--as', 'LEAD')
ok('A4 binding a topic needs the user\'s yes', c != 0 and '--confirmed' in o and not store.is_file(), o)
c, o = run(r1, 'lessons', 'topic', 'use', 'Kernel Inference!', '--confirmed', '--as', 'LEAD')
ok('A4 a topic name that is not a slug is refused', c != 0, o)
c, o = run(r1, 'lessons', 'topic', 'use', 'kernel-inference', '--confirmed', '--as', 'LEAD')
ok('A4 a new topic is born on trial, outside the plugin', c == 0 and 'new profile' in o and store.is_file(), o)
ok('A4 the room is bound to it', json.loads((r1 / 'config.json').read_text(encoding='utf-8')).get('topic_profile') == 'kernel-inference')
c, o = run(r1, 'lessons', 'propose', RULE, '--score', '4', '--reach', 'topic', '--scope', 'ratio metrics', '--as', 'LEAD')
ok('A4 a topic lesson says what it should improve (--expect) or is refused', c != 0 and '--expect' in o, o)
c, o = run(r1, 'lessons', 'propose', RULE, '--score', '4', '--reach', 'topic', '--scope', 'ratio metrics', '--expect', 'no discarded honest gain',
           '--note', 'six runs lost in one night', '--as', 'LEAD')
data = json.loads(store.read_text(encoding='utf-8'))
t1 = data['lessons'][0] if data['lessons'] else {}
ok('A4 it enters on trial with where it came from and what it should improve',
   c == 0 and t1.get('status') == 'trial' and t1.get('expect') == 'no discarded honest gain' and t1.get('by') == 'LEAD' and t1.get('rooms'), (o, t1))
c, o = run(r1, 'lessons', 'propose', 'a weak idea about naming', '--score', '2', '--reach', 'topic', '--scope', 'always', '--expect', 'clearer names', '--as', 'LEAD')
ok('A4 a low score is kept as a proposal', c == 0 and json.loads(store.read_text(encoding='utf-8'))['lessons'][1]['status'] == 'proposed', o)
ok('A4 the global lessons are untouched', not (BASE / 'claude' / 'chatroom' / 'lessons.json').is_file())

r2 = new_room('room2')
ok('A4 a room with no topic does not carry the lesson', RULE not in prompt(r2))
c, o = run(r2, 'lessons', 'topic', 'use', 'kernel-inference', '--confirmed', '--as', 'LEAD')
ok('A4 the second room reuses the profile', c == 0 and 'reused' in o and '1 live' in o, o)
text = prompt(r2)
ok('A4 its prompts carry the lesson on trial, not the low proposal', RULE in text and 'weak idea' not in text, text[-600:])
r3 = new_room('room3')
run(r3, 'lessons', 'topic', 'use', 'rust-porting', '--confirmed', '--as', 'LEAD')
ok('A4 a room on another topic does not see it', RULE not in prompt(r3))

c, o = run(r2, 'lessons', 'retire', 'T1', '--as', 'LEAD')
ok('A4 a lesson that did not hold is retired and leaves the prompts', c == 0 and RULE not in prompt(r2), o)
c, o = run(r2, 'lessons', 'topic', 'back', 'kernel-inference', '--as', 'LEAD')
ok('A4 the change is taken back: the earlier version returns', c == 0 and RULE in prompt(r2), o)
c, o = run(r2, 'lessons', 'topic', 'list', '--as', 'LEAD')
ok('A4 list shows the topics', c == 0 and 'kernel-inference' in o and 'rust-porting' in o, o)
c, o = run(r2, 'lessons', 'topic', 'show', '--as', 'LEAD')
ok('A4 show gives each lesson with its provenance and its promise', c == 0 and 'no discarded honest gain' in o and 'LEAD' in o, o)
print(f'fails {fails}')
sys.exit(1 if fails else 0)
