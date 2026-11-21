"""lessons: what the rooms keep getting wrong, grouped by cause, and the few rules the user chose to keep from it.

    chat.py lessons                       the causes seen in the last rooms (checks, refusals, valves, guards) and the lessons kept
    chat.py lessons add "rule" --scope "when it applies, when it does not" --note "where it was seen"
    chat.py lessons accept L3             a lesson on trial becomes active: it goes into every prompt
    chat.py lessons retire L3             out of the prompts; it stays in the file with its history
    chat.py lessons propose "rule" --score 1-5 --reach local|general [--kind improvement|bug|plugin] --scope "when" --note "where"
    chat.py lessons close                 the closing summary of the room in its parts (what the harness applied, what is left to decide)

Every improvement or bug found in a room gets a score from 1 to 5. A 5 (a real bug that can bend the process, or something the
user asked of the room) and a 4 (an improvement, certain at 4 of 5) are applied by the harness itself, as an active lesson through
the same gate. A 1 to 3 is never applied: it is kept for the closing, and only when the user is the plugin's creator (a file
`creator` in the chatroom folder, or CHATROOM_CREATOR=1); for anyone else it is not even kept. A bug of the plugin itself
(--kind plugin) is never applied: it goes to the creator apart. Each carries a reach: local (this user's machine: its hardware,
its habits) or general (the harness for anyone), and the closing lists them apart.

A lesson is a rule, its evidence and its conditions together: a rule without the conditions it held under is applied
where it does not hold. It enters on trial (only in rooms whose brief asks for it: brief lessons=trial) and becomes
active when the user says so. Nothing is added by itself: an add-only loop keeps rules for failures that never happened.
The active ones are capped: a new one enters when one leaves."""
import contextlib
import json
import os
import re
import time
from pathlib import Path

import layers
from i18n import say

REACH = ('local', 'general', 'topic')
KINDS = ('improvement', 'bug', 'plugin')
CAP = 8               # active and trial lessons together: every one is read at every request of every agent
LONG = 300            # characters of a rule: a lesson is one instruction, not a page
SPECIFIC = re.compile(r'#\d+\b|\bT\d+\b|[A-Za-z]:[\\/]|(?<![\w.])/(?:[\w.-]+/){2,}|\b[0-9a-f]{7,40}\b|\battempt-?\d+\b', re.IGNORECASE)


def home():
    return layers.chatroom_dir()


def load():
    try:
        data = json.loads((home() / 'lessons.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data.get('lessons'), list) else {'lessons': []}


def save(data):
    home().mkdir(parents=True, exist_ok=True)
    tmp = home() / f'lessons.json.{os.getpid()}.tmp'
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    for attempt in range(20):                  # Windows refuses the swap while another process has the file open for a moment
        try:
            return os.replace(tmp, home() / 'lessons.json')
        except PermissionError:
            if attempt == 19:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.02 + 0.02 * attempt)


@contextlib.contextmanager
def lessons_lock():
    """one process at a time reads, changes and writes lessons.json (two `lessons add` together kept only the last, and a prompt
    that wrote the rooms it served undid a lesson added at that moment). The lock is a file made exclusively, as machine.py does,
    with the holder's pid: a dead holder's is taken over at once, and any one older than 20 s (the work inside takes milliseconds)"""
    home().mkdir(parents=True, exist_ok=True)
    lock, start = home() / 'lessons.lock', time.time()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except (FileExistsError, PermissionError):      # PermissionError: Windows, the holder is deleting it
            from chat import pid_alive                  # only when the lock is taken: the import costs
            with contextlib.suppress(OSError, ValueError):
                held = lock.read_text(encoding='utf-8').strip()
                if time.time() - lock.stat().st_mtime > 20 or (held and not pid_alive(int(held))):
                    lock.unlink()
                    continue
            if time.time() - start > 30:
                raise TimeoutError(say('lessons.busy'))
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.unlink()


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


def for_prompt(trial=False, topic=''):
    """the lines a prompt carries: the active lessons, the ones on trial when the room's brief asks for them, and the lessons
    of the room's topic profile"""
    want = ('active', 'trial') if trial else ('active',)
    return [f"- {x['text']}" + (f" ({x['when']})" if x.get('when') else '') for x in load()['lessons'] if x.get('status') in want] + topic_lines(topic)


def used(room_dir, trial=False):
    """a room whose prompts carried a lesson is written on it: a lesson on trial is accepted on what it did in rooms"""
    want, key = ('active', 'trial') if trial else ('active',), str(Path(room_dir).resolve())
    with lessons_lock():
        data, changed = load(), False
        for x in data['lessons']:
            if x.get('status') in want and key not in x.setdefault('rooms', []):
                x['rooms'].append(key)
                changed = True
        if changed:
            save(data)


# ------------------------------------------------------------------------------------------------------- topic profiles
TOPIC_CAP = 12            # live lessons of one topic: read at every request of the agents of its rooms only (8 filled at the first closing)
CAUSE_AT = 3              # times a cause fires in one room before the closing lists it as a candidate
CAUSE_KINDS = ('refusal', 'lead', 'hold', 'check')     # what went wrong, was fixed by hand or was warned about; the relay's own wakes teach nothing
TOPIC_VERSIONS = 20       # saved versions of a topic's store kept for `lessons topic back`
SLUG = re.compile(r'[a-z0-9][a-z0-9-]{1,40}')


def topic_of(room):
    """the topic profile this room is bound to ('' when none): the lead binds it with the user's yes (lessons topic use)"""
    try:
        return str(room.config().get('topic_profile') or '')
    except (OSError, ValueError, AttributeError):
        return ''


def topic_dir(slug):
    return home() / 'topics' / slug


def load_topic(slug):
    """a topic's store: its lessons and what it is (format, the core it was born under, the rooms that used it). It lives in
    the user's chatroom folder, which no update of the plugin touches"""
    try:
        data = json.loads((topic_dir(slug) / 'lessons.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data.get('lessons'), list):
        data['lessons'] = []
    data.setdefault('meta', {})
    return data


def save_topic(slug, data):
    """write the store and keep this version beside it: every change of a profile can be taken back (lessons topic back)"""
    d = topic_dir(slug)
    (d / 'versions').mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1, ensure_ascii=False) + '\n'
    tmp = d / f'lessons.json.{os.getpid()}.tmp'
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, d / 'lessons.json')
    old = sorted((d / 'versions').glob('*.json'))
    n = int(old[-1].stem) + 1 if old else 1
    (d / 'versions' / f'{n:05d}.json').write_text(text, encoding='utf-8')
    for f in old[:max(0, len(old) + 1 - TOPIC_VERSIONS)]:
        f.unlink(missing_ok=True)


def topic_lines(slug):
    """what the prompts of a room on this topic carry: its active lessons and the ones on trial (a topic's trial runs in its own rooms)"""
    if not slug:
        return []
    return [f"- {x['text']}" + (f" ({x['when']})" if x.get('when') else '') for x in load_topic(slug)['lessons'] if x.get('status') in ('trial', 'active')]


def topic_propose(room, a, text, p):
    """a lesson for this room's topic only: it needs when it applies and what it should improve (the next room checks that),
    it enters on trial with where it came from, and a low score is kept without reaching the prompts"""
    slug = topic_of(room)
    if not slug:
        raise ValueError(say('lessons.topic.none'))
    when, expect = ' '.join((getattr(a, 'scope', None) or '').split()), ' '.join((getattr(a, 'expect', None) or '').split())
    if not when or not expect:
        raise ValueError(say('lessons.topic.need'))
    data = load_topic(slug)
    live = [x for x in data['lessons'] if x.get('status') in ('trial', 'active')]
    refusal = (say('lessons.gate.long', n=len(text), max=LONG) if len(text) > LONG else
               say('lessons.gate.same') if any(x['text'].casefold() == text.casefold() for x in live) else
               say('lessons.gate.cap', cap=TOPIC_CAP, ids=', '.join(x['id'] for x in live)) if p['score'] >= 4 and len(live) >= TOPIC_CAP else None)
    if refusal:
        raise ValueError(refusal)
    tid = f"T{max([int(x['id'][1:]) for x in data['lessons']] or [0]) + 1}"
    data['lessons'].append({'id': tid, 'text': text, 'when': when, 'expect': expect, 'evidence': p['note'], 'reach': 'topic', 'score': p['score'],
                            'kind': p['kind'], 'status': 'trial' if p['score'] >= 4 else 'proposed', 'rooms': [str(Path(room.dir).resolve())],
                            'ts': p['ts'], 'by': p['by']})
    save_topic(slug, data)
    print(say('lessons.topic.applied', id=tid, slug=slug, score=p['score']) if p['score'] >= 4 else say('lessons.topic.kept', id=tid, slug=slug, score=p['score']))


SKILL_NAME = re.compile(r'[\w.@:-]{1,80}')


def role_skills(slug, roles):
    """the skills the topic keeps for the first of `roles` it knows (case does not matter): a list of names, [] for none"""
    kept = {k.casefold(): v for k, v in (load_topic(slug)['meta'].get('skills') or {}).items()}
    return next((list(kept[r.casefold()]) for r in roles if r and r.casefold() in kept), [])


def topic_skills(room, rest):
    """lessons topic skills [ROLE [a,b | -]]: the skills the topic remembers for a role, as a list of names only (the skills stay in
    the one library of the skills panel); the prompt of that role names them. `-` forgets the role's list"""
    slug = topic_of(room)
    if not slug:
        raise ValueError(say('lessons.topic.none'))
    data = load_topic(slug)
    kept = data['meta'].setdefault('skills', {})
    if len(rest) < 2:                                          # none, or only a role: what is kept
        for role, names in kept.items():
            if not rest or role.casefold() == rest[0].casefold():
                print(say('lessons.topic.skills_row', role=role, skills=', '.join(names)))
        return print(say('lessons.topic.skills_none', slug=slug)) if not any(not rest or r.casefold() == rest[0].casefold() for r in kept) else None
    role = rest[0].upper()
    names = [] if rest[1:] == ['-'] else [n for n in re.split(r'[,\s]+', ' '.join(rest[1:])) if n]
    bad = [n for n in names if not SKILL_NAME.fullmatch(n)]
    if bad:
        raise ValueError(say('lessons.topic.skills_name', names=', '.join(bad)))
    kept.pop(next((r for r in kept if r.casefold() == role.casefold()), role), None)
    if names:
        kept[role] = list(dict.fromkeys(names))
    save_topic(slug, data)
    try:                                                       # a name the library does not know is kept, and said
        import skills
        lib = skills.scan(room.dir)
        unknown = [n for n in names if skills.find(lib, n) is None]
    except Exception:                                          # no library to read: the list is kept as given
        unknown = []
    print(say('lessons.topic.skills_set', role=role, slug=slug, skills=', '.join(names) or '-'))
    if unknown:
        print(say('lessons.topic.skills_unknown', names=', '.join(unknown)))


def topic_command(room, a, rest):
    """lessons topic use SLUG --confirmed | list | show [SLUG] | back SLUG | skills [ROLE [a,b | -]]"""
    act, slug = (rest[0].lower() if rest else 'show'), (rest[1].lower() if len(rest) > 1 else '')
    if act == 'skills':
        return topic_skills(room, rest[1:])
    if act == 'list':
        found = sorted(p.name for p in (home() / 'topics').glob('*') if (p / 'lessons.json').is_file()) if (home() / 'topics').is_dir() else []
        for s in found:
            d = load_topic(s)
            live = sum(1 for x in d['lessons'] if x.get('status') in ('trial', 'active'))
            print(say('lessons.topic.row', slug=s, live=live, all=len(d['lessons']), rooms=len(d['meta'].get('rooms', []))))
        return print(say('lessons.topic.none_yet')) if not found else None
    if act == 'use':
        if not SLUG.fullmatch(slug):
            raise ValueError(say('lessons.topic.slug'))
        if not getattr(a, 'confirmed', False):                # the choice of a topic is the user's: a wrong profile bends a whole room
            raise ValueError(say('lessons.topic.confirm', slug=slug))
        data, key = load_topic(slug), str(Path(room.dir).resolve())
        new = not (topic_dir(slug) / 'lessons.json').is_file()
        meta = data['meta']
        if new:
            meta.update(format=1, topic=slug, born=int(time.time()), core=core_version())
        if key not in meta.setdefault('rooms', []):
            meta['rooms'].append(key)
        save_topic(slug, data)
        room.update_config(settings={'topic_profile': slug})
        live = sum(1 for x in data['lessons'] if x.get('status') in ('trial', 'active'))
        return print(say('lessons.topic.new', slug=slug) if new else say('lessons.topic.reused', slug=slug, live=live, rooms=len(meta['rooms'])))
    slug = slug or topic_of(room)
    if not slug or not (topic_dir(slug) / 'lessons.json').is_file():
        raise ValueError(say('lessons.topic.none'))
    if act == 'back':
        old = sorted((topic_dir(slug) / 'versions').glob('*.json'))
        if len(old) < 2:
            raise ValueError(say('lessons.topic.no_version', slug=slug))
        data = json.loads(old[-2].read_text(encoding='utf-8'))
        save_topic(slug, data)                                 # the return is a version too: it can be taken back in its turn
        return print(say('lessons.topic.back', slug=slug, n=int(old[-2].stem), live=sum(1 for x in data['lessons'] if x.get('status') in ('trial', 'active'))))
    if act == 'show':
        data = load_topic(slug)
        print(say('lessons.topic.head', slug=slug, core=data['meta'].get('core', '?'), rooms=len(data['meta'].get('rooms', []))))
        for role, names in (data['meta'].get('skills') or {}).items():
            print(say('lessons.topic.skills_row', role=role, skills=', '.join(names)))
        for x in data['lessons']:
            print(f"  {x['id']} [{x.get('status')}] {x['text']} ({x.get('when', '')}) -> {x.get('expect', '')} · {say('lessons.rooms', n=len(x.get('rooms', [])))} · {x.get('by', '')}")
        return print('  -') if not data['lessons'] else None
    raise ValueError(say('lessons.topic.usage'))


def core_version():
    try:
        return json.loads((Path(__file__).resolve().parents[1] / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8')).get('version', '?')
    except (OSError, ValueError):
        return '?'


def creator():
    """the user is the plugin's creator: scores 1 to 3 and the plugin's bugs are for them alone"""
    return os.environ.get('CHATROOM_CREATOR') == '1' or (home() / 'creator').is_file()


def proposals(room):
    try:
        got = json.loads((Path(room.dir) / 'proposals.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return got if isinstance(got, list) else []


def propose(room, a, rest, data):
    """a scored improvement or bug of this room: 4 and 5 are applied now as an active lesson, 1 to 3 and the plugin's bugs wait
    for the closing (the creator's), and for any other user they are not kept"""
    text = ' '.join(' '.join(rest).split())
    score, reach, kind = getattr(a, 'score', None), getattr(a, 'reach', None), getattr(a, 'kind', None) or 'improvement'
    if not text or score not in (1, 2, 3, 4, 5) or reach not in REACH or kind not in KINDS:
        raise ValueError(say('lessons.propose.usage'))
    p = {'text': text, 'score': score, 'reach': reach, 'kind': kind, 'note': (getattr(a, 'note', None) or '')[:300],
         'by': a.name or '', 'ts': int(time.time())}
    if reach == 'topic' and kind != 'plugin':             # what holds for this kind of work only: the topic's own store
        return topic_propose(room, a, text, p)

    def keep():                                   # the id is taken inside the lock: two proposals together never share one
        got = proposals(room)
        p['id'] = f"P{max([int(x['id'][1:]) for x in got] or [0]) + 1}"
        (Path(room.dir) / 'proposals.json').write_text(json.dumps([*got, p], indent=1, ensure_ascii=False), encoding='utf-8')
    if kind == 'plugin' or score <= 3:
        if not creator():
            return print(say('lessons.propose.not_kept'))
        p['status'] = 'presented'
    else:
        when = ' '.join((getattr(a, 'scope', None) or '').split())
        refusal = gate(text, data) if when else say('lessons.need_when')
        if refusal:                               # a 4 or a 5 the gate stops is still written: the closing lists it, it never disappears
            p.update(status='refused', why=refusal)
            room.locked(keep)
            raise ValueError(refusal)
        lid = f"L{max([int(x['id'][1:]) for x in data['lessons']] or [0]) + 1}"
        data['lessons'].append({'id': lid, 'text': text, 'when': when, 'evidence': p['note'], 'status': 'active', 'reach': reach, 'score': score,
                                'auto': True, 'rooms': [str(Path(room.dir).resolve())], 'ts': p['ts'], 'by': p['by']})
        save(data)
        p.update(status='applied', lesson=lid)
    room.locked(keep)
    print(say('lessons.propose.kept', id=p['id'], score=score, reach=reach) if p['status'] == 'presented'
          else say('lessons.propose.applied', id=p['id'], score=score, reach=reach, lesson=p['lesson']))


def room_causes(room, at=CAUSE_AT):
    """[(cause, times, agents, last detail)] of this room's events that fired at least `at` times, the most frequent first"""
    seen = {}
    for e in events(room.dir):
        if e.get('kind') in CAUSE_KINDS and e.get('key'):
            c = seen.setdefault(f"{e['kind']}:{e['key']}", {'n': 0, 'who': set(), 'detail': ''})
            c['n'] += 1
            if e.get('name'):
                c['who'].add(e['name'])
            c['detail'] = e.get('detail') or c['detail']
    return sorted(((k, c['n'], sorted(c['who']), c['detail']) for k, c in seen.items() if c['n'] >= at), key=lambda x: -x[1])


def auto_propose(room, cause, n, who, detail):
    """3.1: a cause that fired many times in this room becomes a proposal to decide at the closing (score 3: never applied by
    itself), once; kept only for the plugin's creator, as every score from 1 to 3. Returns the id, or None"""
    if not creator():
        return None
    note = f'auto:{cause}'
    out = []

    def keep():
        got = proposals(room)
        if any(p.get('note', '').startswith(note) for p in got):
            return
        pid = f"P{max([int(x['id'][1:]) for x in got] or [0]) + 1}"
        text = say('lessons.auto.text', cause=cause, n=n, who=', '.join(who) or '-', detail=' '.join(str(detail).split())[:200] or '-')
        got.append({'text': text, 'score': 3, 'reach': 'general', 'kind': 'improvement', 'note': f'{note} x{n}', 'by': 'harness',
                    'ts': int(time.time()), 'status': 'presented', 'id': pid})
        (Path(room.dir) / 'proposals.json').write_text(json.dumps(got, indent=1, ensure_ascii=False), encoding='utf-8')
        out.append(pid)
    room.locked(keep)
    return out[0] if out else None


def closing(room):
    """the closing summary of a room, in the parts the user's rule asks: a. what the harness learned and applied by itself, b. what
    the session found and is left to decide (the creator's), c. the plugin's bugs (the creator's), each listed local and general apart"""
    items, out = proposals(room), [say('lessons.close.head')]
    labels = {'local': say('lessons.reach.local'), 'general': say('lessons.reach.general')}

    def block(title, rows):
        out.append(title)
        for reach in labels:                              # the topic's lessons have their own part below
            out.append('  ' + labels[reach])
            mine = [p for p in rows if p['reach'] == reach]
            out.extend(f"    {p.get('lesson') or p['id']} (score {p['score']}) {p['text']}" + (f" · {p['note']}" if p.get('note') else '') for p in mine)
            if not mine:
                out.append('    -')
    block(say('lessons.close.auto'), [p for p in items if p['status'] == 'applied'])
    refused = [p for p in items if p['status'] == 'refused']
    if refused:
        out.append(say('lessons.close.refused'))
        out.extend(f"    {p['id']} (score {p['score']}, {p['reach']}) {p['text']} · {p.get('why', '')}" for p in refused)
    if not creator():
        out.append(say('lessons.close.not_creator'))
    if creator():
        block(say('lessons.close.session'), [p for p in items if p['status'] == 'presented' and p['kind'] != 'plugin'])
        block(say('lessons.close.plugin'), [p for p in items if p['status'] == 'presented' and p['kind'] == 'plugin'])
    slug = topic_of(room)
    if slug:                                              # d. what the topic holds: each lesson with what it promised, to accept or retire
        out.append(say('lessons.close.topic', slug=slug))
        rows = [x for x in load_topic(slug)['lessons'] if x.get('status') in ('trial', 'proposed', 'active')]
        out.extend(f"    {x['id']} [{x['status']}] {x['text']} -> {x.get('expect', '')} · {say('lessons.rooms', n=len(x.get('rooms', [])))}" for x in rows)
        out.append('    -' if not rows else say('lessons.close.topic_how', slug=slug))
    causes = room_causes(room)                           # e. 3.3: what kept going wrong here, a candidate even in a first room
    out.append(say('lessons.close.causes', at=CAUSE_AT))
    out.extend(f"    {k} x{n} ({', '.join(who) or '-'}) {' '.join(str(d).split())[:120]}" for k, n, who, d in causes[:12])
    out.append('    -' if not causes else say('lessons.close.causes_how'))
    return out


def command(room, a):
    if (a.pairs[:1] or [''])[0].lower() in ('propose', 'add', 'accept', 'retire', 'topic'):
        with lessons_lock():
            return _command(room, a)
    return _command(room, a)


def _command(room, a):
    act, rest = (a.pairs[0].lower() if a.pairs else ''), a.pairs[1:]
    data = load()
    if act == 'list':                             # the name everyone tries first: the same listing as no word at all
        act = ''
    if act == 'propose':
        return propose(room, a, rest, data)
    if act == 'close':
        return print('\n'.join(closing(room)))
    if act == 'topic':
        return topic_command(room, a, rest)
    if act in ('accept', 'retire') and rest and rest[0][:1].upper() == 'T' and rest[0][1:].isdigit():   # a lesson of the room's topic
        slug = topic_of(room)
        tdata = load_topic(slug) if slug else {'lessons': []}
        x = next((x for x in tdata['lessons'] if x['id'].lower() == rest[0].lower()), None)
        if not x:
            raise ValueError(say('lessons.none', id=rest[0]))
        x.update(status='active' if act == 'accept' else 'retired', changed=int(time.time()))
        save_topic(slug, tdata)
        return print(say('lessons.accepted', id=x['id']) if act == 'accept' else say('lessons.retired', id=x['id']))
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
        reach = getattr(a, 'reach', None) or 'local'
        if reach not in REACH:
            raise ValueError(say('lessons.propose.usage'))
        lid = f"L{max([int(x['id'][1:]) for x in data['lessons']] or [0]) + 1}"
        data['lessons'].append({'id': lid, 'text': text, 'when': when, 'evidence': (getattr(a, 'note', None) or '')[:300], 'reach': reach,
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
    for reach, label in (('local', say('lessons.reach.local')), ('general', say('lessons.reach.general'))):
        print('  ' + label)
        mine = [x for x in data['lessons'] if x.get('reach', 'local') == reach]    # a lesson of an older version has no reach: it was written on this machine
        for x in mine:
            print(f"    {x['id']} [{x.get('status')}] {x['text']} ({x.get('when', '')}) · {say('lessons.rooms', n=len(x.get('rooms', [])))}")
        if not mine:
            print('    -')
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
