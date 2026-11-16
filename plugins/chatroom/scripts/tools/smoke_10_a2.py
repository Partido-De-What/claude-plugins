"""1.0, A2: events.jsonl records what the harness needs to learn from: a refused command (who, which, why), the kernel's
actions and refusals, and what a lead does by hand to keep the room going. Before, it held the CHECK lines only.
Run: python -X utf8 smoke_10_a2.py"""
import json
import sys
from pathlib import Path

src = Path(__file__).with_name('smoke_10_kern.py')        # the helpers of the kernel smoke: its text up to the first section
k = {'__file__': str(src), '__name__': 'helpers'}
exec(compile(src.read_text(encoding='utf-8').split("if section('K3'):")[0], str(src), 'exec'), k)
ok, run, research_room = k['ok'], k['run'], k['research_room']


def events(room):
    path = room / 'events.jsonl'
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()] if path.is_file() else []


def has(room, kind, key, name=None):
    return [e for e in events(room) if e['kind'] == kind and e['key'] == key and (name is None or e.get('name') == name)]


room, repo, work = research_room('a2')
c, o = run(room, 'research', 'reseal', '--as', 'LEAD')
ok('A2 a refused kernel action is an event with its reason', c != 0 and has(room, 'refusal', 'research:reseal', 'LEAD')
   and 'reason' in has(room, 'refusal', 'research:reseal')[0].get('detail', ''), (o, events(room)))
c, o = run(room, 'research', 'hold', '--minutes', '5', '--reason', 'bench', '--as', 'W')
ok('A2 a kernel action that passed is an event too', c == 0 and has(room, 'kernel', 'hold', 'W'), (o, events(room)))
c, o = run(room, 'research', 'release', '--as', 'W')
ok('A2 release recorded', c == 0 and has(room, 'kernel', 'release', 'W'), (o, events(room)))
n = len(events(room))
c, o = run(room, 'research', 'status', '--as', 'LEAD')
ok('A2 a read-only command leaves no event', c == 0 and len(events(room)) == n, events(room)[n:])
c, o = run(room, 'task', 'done', 'T99', '--note', 'x', '--as', 'W')
ok('A2 a refused room command is an event: who, which command, why', c != 0 and has(room, 'refusal', 'task:done', 'W')
   and has(room, 'refusal', 'task:done')[0].get('detail'), (o, events(room)))
c, o = run(room, 'retire', 'W', '--as', 'LEAD')
ok('A2 a remedy of the lead (retire) is an event', c == 0 and has(room, 'lead', 'retire'), (o, events(room)))
print(f"ok: {ok.__globals__['fails']} failed")
sys.exit(1 if ok.__globals__['fails'] else 0)
