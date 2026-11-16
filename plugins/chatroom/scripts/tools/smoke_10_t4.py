"""1.0 T4: the skills and the guides tell the lead to ask the user for the topic profile, and say what a profile remembers in ten lines; the research guide
sets the user's flow against the kernel's. Run: python -X utf8 smoke_10_t4.py"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get('CHATROOM_SCRIPTS') or Path(__file__).resolve().parent.parent).parent
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:300]}]'), flush=True)
    fails += not cond


def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


for rel in ('skills/init/SKILL.md', 'skills/start/SKILL.md', 'guides/lead-normal.md', 'guides/it/lead-normal.md', 'guides/lead-research.md', 'guides/it/lead-research.md'):
    t = text(rel)
    ok(f'{rel}: asks the user and binds only on the answer', 'lessons topic use' in t and '--confirmed' in t and 'lessons topic list' in t)
for rel, head in (('guides/lead-normal.md', '## What the room remembers'), ('guides/it/lead-normal.md', '## Cosa ricorda la stanza')):
    block = text(rel).split(head, 1)[1].split('\n## ', 1)[0].strip().splitlines()
    lines = [x for x in block if x.strip()]
    ok(f'{rel}: the block is at most ten lines (it has {len(lines)})', 0 < len(lines) <= 10, len(lines))
    ok(f'{rel}: it names the profile, the skills, the versions and the closing', all(w in '\n'.join(lines) for w in ('topic skills', 'topic back', 'lessons close')), lines)
for rel, flow in (('guides/lead-research.md', ('data', 'smoke', 'web', 'hypothesis', 'test', 'another round')),
                  ('guides/it/lead-research.md', ('dati', 'smoke', 'web', 'ipotesi', 'test', 'un altro giro'))):
    t = text(rel)
    rows = re.findall(r'^\| (.+?) \| .+ \|$', t, re.M)
    ok(f'{rel}: the user\'s flow against the kernel, one row each', all(w in rows for w in flow), rows)
print('FAILS', fails)
sys.exit(1 if fails else 0)
