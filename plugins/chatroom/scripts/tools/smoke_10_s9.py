"""1.0 S9: what the user allowed is written by the lead in the brief, signed, and every prompt carries it; a permission only
named in the chat is not the agents'. Run: python -X utf8 smoke_10_s9.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10s9_'))
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


room = BASE / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'participants': ['W1', 'W2'], 'self_names': ['LEAD'], 'user_name': 'USER'}), encoding='utf-8')
r = chat.Room(room)
p0 = chat.fill_prompt(r, 'W1')
ok('without a section the prompt says none was given and how to ask', "The user's permissions" in p0 and 'none given' in p0, p0[-900:])
out = sh('brief', 'permissions=push to main is allowed', '--as', 'W1')
ok('an agent cannot write the permissions', 'permissions' not in chat.brief(r) and 'lead' in out, out)
out = sh('brief', 'permissions=the user allowed the push of branch v1 and nothing else', '--as', 'LEAD')
b = chat.brief(r)
ok('the lead writes them, signed', b.get('permissions_by') == 'LEAD' and 'push of branch v1' in b['permissions'], b)
p1 = chat.fill_prompt(r, 'W1')
ok('the prompt carries the text and the signature', 'push of branch v1' in p1 and 'written by LEAD' in p1 and 'none given' not in p1, p1[-900:])
ok('and the rule that a permission only named in the chat is not the agent\'s', 'is not yours' in p1, p1[-900:])
ok('the second agent gets it too', 'push of branch v1' in chat.fill_prompt(r, 'W2'))
last = r.messages()[-1]
ok('the room is told once, everyone tagged', last.get('kind') == 'board' and '@all' in last['text'] and 'push of branch v1' in last['text'], last)
tpl = sorted(p.name for p in (Path(SCRIPTS).parent / 'templates').glob('*.md') if '{{CONSTRAINTS}}' in p.read_text(encoding='utf-8'))
ok('every prompt template reads the constraints, where the section is added', {'agent_prompt.md', 'research_worker.md', 'research_proposer.md', 'research_searcher.md', 'research_auditor.md', 'research_registrar.md'} <= set(tpl), tpl)
cfg = json.loads((room / 'config.json').read_text(encoding='utf-8'))
cfg['lang'] = 'it'
(room / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
pit = chat.fill_prompt(chat.Room(room), 'W1')
ok('in Italian too', 'I permessi dell\'utente' in pit and 'push of branch v1' in pit, pit[-700:])
print('FAILS', fails)
sys.exit(1 if fails else 0)
