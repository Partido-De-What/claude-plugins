"""lessons: what the rooms keep getting wrong, grouped by cause, and the few rules the user chose to keep from it.

    chat.py lessons                       the causes seen in the last rooms (checks, refusals, valves, guards) and the lessons kept
    chat.py lessons add "rule" --scope "when it applies, when it does not" --note "where it was seen"
    chat.py lessons accept L3             a lesson on trial becomes active: it goes into every prompt
    chat.py lessons retire L3             out of the prompts; it stays in the file with its history

A lesson is a rule, its evidence and its conditions together: a rule without the conditions it held under is applied
where it does not hold. It enters on trial (only in rooms whose brief asks for it: brief lessons=trial) and becomes
active when the user says so. Nothing is added by itself: an add-only loop keeps rules for failures that never happened.
The active ones are capped: a new one enters when one leaves."""
import json
import os
import re
import time
from pathlib import Path

from i18n import say

CAP = 8               # active and trial lessons together: every one is read at every request of every agent
LONG = 300            # characters of a rule: a lesson is one instruction, not a page
SPECIFIC = re.compile(r'#\d+\b|\bT\d+\b|[A-Za-z]:[\\/]|(?<![\w.])/(?:[\w.-]+/){2,}|\b[0-9a-f]{7,40}\b|\battempt-?\d+\b', re.IGNORECASE)


def home():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'chatroom'


def load():
    try:
        data = json.loads((home() / 'lessons.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data.get('lessons'), list) else {'lessons': []}


def save(data):
    home().mkdir(parents=True, exist_ok=True)
    tmp = home() / 'lessons.json.tmp'
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, home() / 'lessons.json')


def rooms(extra=()):
    """the rooms to read: the known ones (the newest 50) and the one in hand"""
    try:
        known = json.loads((home() / 'known_rooms.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        known = {}
    out = [Path(k) for k in known if isinstance(known[k], dict)] + [Path(x) for x in extra]
    return list(dict.fromkeys(p.resolve() for p in out if (p / 'events.jsonl').is_file()))


def events(room_dir):
    out = []
    try:
        for line in (Path(room_dir) / 'events.jsonl').read_text(encoding='utf-8').splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict) and e.get('kind') and e.get('key'):
                out.append(e)
    except OSError:
        pass
    return out


def causes(dirs):
    """[(cause, rooms it was seen in, times, agents)] the most widespread first. A cause seen once stays in the list:
    a rare failure that costs a night is worth more than a frequent one that costs a message"""
    seen = {}
    for d in dirs:
        for e in events(d):
            c = seen.setdefault(f"{e['kind']}:{e['key']}", {'rooms': set(), 'n': 0, 'who': set()})
            c['rooms'].add(str(d))
            c['n'] += 1
            if e.get('name'):
                c['who'].add(e['name'])
    return sorted(((k, len(v['rooms']), v['n'], len(v['who'])) for k, v in seen.items()), key=lambda r: (-r[1], -r[2], r[0]))


def gate(text, data):
    """why a lesson may not enter (None: it may): the quality gate against a harness that grows by itself"""
    if len(text) > LONG:
        return say('lessons.gate.long', n=len(text), max=LONG)
    m = SPECIFIC.search(text)
    if m:
        return say('lessons.gate.specific', what=m.group(0))
    live = [x for x in data['lessons'] if x.get('status') in ('trial', 'active')]
    if any(x['text'].casefold() == text.casefold() for x in live):
        return say('lessons.gate.same')
    if len(live) >= CAP:
        return say('lessons.gate.cap', cap=CAP, ids=', '.join(x['id'] for x in live))
    return None


def for_prompt(trial=False):
    """the lines a prompt carries: the active lessons, and the ones on trial when the room's brief asks for them"""
    want = ('active', 'trial') if trial else ('active',)
    return [f"- {x['text']}" + (f" ({x['when']})" if x.get('when') else '') for x in load()['lessons'] if x.get('status') in want]


def used(room_dir, trial=False):
    """a room whose prompts carried a lesson is written on it: a lesson on trial is accepted on what it did in rooms"""
    data, want, key, changed = load(), ('active', 'trial') if trial else ('active',), str(Path(room_dir).resolve()), False
    for x in data['lessons']:
        if x.get('status') in want and key not in x.setdefault('rooms', []):
            x['rooms'].append(key)
            changed = True
    if changed:
        save(data)


def command(room, a):
    act, rest = (a.pairs[0].lower() if a.pairs else ''), a.pairs[1:]
    data = load()
    if act == 'add':
        text = ' '.join(' '.join(rest).split())
        if not text:
            raise ValueError(say('lessons.usage'))
        refusal = gate(text, data)
        if refusal:
            raise ValueError(refusal)
        when = ' '.join((getattr(a, 'scope', None) or '').split())
        if not when:
            raise ValueError(say('lessons.need_when'))
        lid = f"L{max([int(x['id'][1:]) for x in data['lessons']] or [0]) + 1}"
        data['lessons'].append({'id': lid, 'text': text, 'when': when, 'evidence': (getattr(a, 'note', None) or '')[:300],
                                'status': 'trial', 'rooms': [], 'ts': int(time.time()), 'by': a.name or ''})
        save(data)
        return print(say('lessons.added', id=lid))
    if act in ('accept', 'retire') and rest:
        x = next((x for x in data['lessons'] if x['id'].lower() == rest[0].lower()), None)
        if not x:
            raise ValueError(say('lessons.none', id=rest[0]))
        if act == 'accept' and len(x.get('rooms', [])) < 2 and not getattr(a, 'force', False):
            raise ValueError(say('lessons.two_rooms', id=x['id'], n=len(x.get('rooms', []))))
        x.update(status='active' if act == 'accept' else 'retired', changed=int(time.time()))
        save(data)
        return print(say('lessons.accepted', id=x['id']) if act == 'accept' else say('lessons.retired', id=x['id']))
    if act:
        raise ValueError(say('lessons.usage'))
    dirs = rooms([room.dir])
    rows = causes(dirs)
    print(say('lessons.head', rooms=len(dirs)))
    for cause, n_rooms, n, who in rows[:30]:
        print(f'  {cause:28} {say("lessons.row", rooms=n_rooms, n=n, who=who)}')
    if not rows:
        print('  ' + say('lessons.no_events'))
    print(say('lessons.kept'))
    for x in data['lessons']:
        print(f"  {x['id']} [{x.get('status')}] {x['text']} ({x.get('when', '')}) · {say('lessons.rooms', n=len(x.get('rooms', [])))}")
    if not data['lessons']:
        print('  -')
    print(say('lessons.how'))


def scorecard(room, costs, version):
    """one room in a few numbers, to compare the same work under two versions of the harness: what it cost, what it
    closed, and how often each control fired. Gains and losses are read apart: an average hides the tasks that got worse"""
    board = {}
    try:
        board = json.loads((room.dir / 'board.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    tasks = board.get('tasks', []) if isinstance(board, dict) else []
    done = sum(1 for t in tasks if t.get('state') == 'done')
    leads = room.config().get('self_names', [])
    eq = sum(t['eq'] for n, t in costs.items() if t and n not in leads)
    lead = sum(t['eq'] for n, t in costs.items() if t and n in leads)
    by = {}
    for e in events(room.dir):
        by[f"{e['kind']}:{e['key']}"] = by.get(f"{e['kind']}:{e['key']}", 0) + 1
    out = [say('lessons.score.head', version=version),
           say('lessons.score.tasks', done=done, all=len(tasks)),
           say('lessons.score.tokens', eq=f'{eq / 1e6:.2f}', lead=f'{lead / 1e6:.2f}', per=f'{eq / done / 1e6:.2f}' if done else '-'),
           say('lessons.score.compactions', n=sum(t.get('compactions', 0) for t in costs.values() if t)),
           say('lessons.score.events') + (' ' + ', '.join(f'{k} {v}' for k, v in sorted(by.items(), key=lambda kv: -kv[1])) if by else ' -')]
    return out
