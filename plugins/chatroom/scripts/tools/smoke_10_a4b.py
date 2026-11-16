"""1.0 A4b: the topic profile remembers the skills of each role (names only, the library stays one) and the prompt of the role names them.
Run: python -X utf8 smoke_10_a4b.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10a4b_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402
import lessons  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def mk(name):
    room = BASE / name
    room.mkdir()
    (room / 'config.json').write_text(json.dumps({'participants': ['W1', 'W2'], 'self_names': ['LEAD'], 'user_name': 'USER',
                                                  'profiles': {'W1': {'role': 'Worker'}}}), encoding='utf-8')
    return room


def sh(room, *a):
    p = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'lessons', 'topic', *a, '--room', str(room), '--as', 'LEAD'], capture_output=True, timeout=90)
    return p.returncode, p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')


r1 = mk('r1')
c, o = sh(r1, 'skills', 'worker', 'ponytail:ponytail')
ok('a room with no topic cannot keep skills', c != 0 and 'topic' in o, o)
sh(r1, 'use', 'kernel-work', '--confirmed')
c, o = sh(r1, 'skills')
ok('no skills yet says so', c == 0 and 'no skills' in o, o)
c, o = sh(r1, 'skills', 'worker', 'ponytail:ponytail,caveman:caveman')
ok('the skills of a role are set', c == 0 and 'WORKER' in o and 'ponytail:ponytail, caveman:caveman' in o, o)
ok('and written in the profile of the topic, as names', lessons.load_topic('kernel-work')['meta']['skills'] == {'WORKER': ['ponytail:ponytail', 'caveman:caveman']}, lessons.load_topic('kernel-work')['meta'])
c, o = sh(r1, 'skills')
ok('the list says them', 'skills for WORKER: ponytail:ponytail, caveman:caveman' in o, o)
c, o = sh(r1, 'show')
ok('and show too', 'skills for WORKER' in o, o)
p1 = chat.fill_prompt(chat.Room(r1), 'W1')
ok('the prompt of that role names them', 'Skills this topic keeps for your role: ponytail:ponytail, caveman:caveman' in p1, p1[-600:])
ok('the prompt of another role does not', 'Skills this topic keeps' not in chat.fill_prompt(chat.Room(r1), 'W2'))
c, o = sh(r1, 'skills', 'worker', 'a/b')
ok('a name with a slash is refused and nothing changes', c != 0 and lessons.load_topic('kernel-work')['meta']['skills']['WORKER'][0] == 'ponytail:ponytail', o)
# a second room on the same topic: the memory travels
r2 = mk('r2')
sh(r2, 'use', 'kernel-work', '--confirmed')
ok('a second room of the topic gets the skills in its prompt', 'ponytail:ponytail' in chat.fill_prompt(chat.Room(r2), 'W1'))
c, o = sh(r1, 'skills', 'worker', '-')
ok('a dash forgets the list', c == 0 and 'skills' not in lessons.load_topic('kernel-work')['meta'].get('skills', {}).get('WORKER', []) and 'Skills this topic keeps' not in chat.fill_prompt(chat.Room(r1), 'W1'), o)
ok('the change is a saved version (it can be taken back)', len(list((lessons.topic_dir('kernel-work') / 'versions').glob('*.json'))) >= 3)
print('FAILS', fails)
sys.exit(1 if fails else 0)
