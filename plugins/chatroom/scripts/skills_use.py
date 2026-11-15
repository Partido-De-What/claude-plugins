"""D8, point 3 of the skill workshop: which skills the agents really use. The Skill calls are read from the transcripts of the agents of the known rooms
(only the new bytes since the last scan) into ~/.claude/chatroom/skills-usage.json, and each call is tied to the task the agent held at that moment
(the board's hist) to say how it ended. A skill nobody called is only highlighted, never removed by us."""
import calendar
import json
import threading
import time

import skills
from i18n import say
from skills import claude_dir, fail, find, read_json_file

BUDGET = 20.0           # seconds a scan may take: a bigger job says complete=false and the panel calls again
CHUNK = 8 * 1024 * 1024
USES_MAX = 5000
UNUSED_ROOMS = 3        # a skill is "unused" only after at least this many rooms were scanned
ACTIONS = ('usage_scan', 'usage', 'measure')
_lock = threading.Lock()


def registry_file():
    return claude_dir() / 'chatroom' / 'skills-usage.json'


def registry():
    d = read_json_file(registry_file())
    d = d if isinstance(d, dict) else {}
    return {'offsets': d.get('offsets') if isinstance(d.get('offsets'), dict) else {}, 'rooms': d.get('rooms') if isinstance(d.get('rooms'), dict) else {},
            'uses': [u for u in d.get('uses') or [] if isinstance(u, dict)]}


def save(reg):
    import chat
    reg['uses'] = reg['uses'][-USES_MAX:]
    registry_file().parent.mkdir(parents=True, exist_ok=True)
    chat.write_atomic(registry_file(), json.dumps({'v': 1, **reg}, ensure_ascii=False))


def empty_usage(scanned=0):
    return {'count': 0, 'rooms': 0, 'last': None, 'ok': 0, 'fail': 0, 'unused_rooms': 0, 'scanned_rooms': scanned, 'unused': False, 'log': []}


def epoch(s):
    """the epoch of a transcript timestamp ("2026-11-14T19:30:01.123Z"), 0 when it is not one"""
    try:
        return float(calendar.timegm(time.strptime(str(s)[:19], '%Y-%m-%dT%H:%M:%S')))
    except ValueError:
        return 0.0


def calls_in(data):
    """[(tool_use id, skill ref, epoch)] of the Skill calls in whole lines of a transcript"""
    out = []
    for raw in data.splitlines():
        if b'"Skill"' not in raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        at = epoch(d.get('timestamp'))
        for c in (d.get('message') or {}).get('content') or []:
            if isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('name') == 'Skill':
                ref = (c.get('input') or {}).get('skill')
                if isinstance(ref, str) and ref.strip() and c.get('id'):
                    out.append((str(c['id']), ref.strip().lstrip('/')[:200], at))
    return out


def transcript(aid):
    import cost
    if not (isinstance(aid, str) and aid.startswith('a')):
        return None
    if not skills._paths.get(aid):
        skills._paths[aid] = cost.transcript_of(agent_id=aid)
    return skills._paths.get(aid)


def scan(room, budget=BUDGET):
    """{'rooms', 'transcripts', 'new', 'complete'}: the new Skill calls of the agents of the known rooms are added to the registry"""
    import skills_d6
    t0 = time.time()
    with _lock:
        reg = registry()
        seen = {u.get('id') for u in reg['uses']}
        n_tr = n_new = 0
        complete = True
        for rid, folder in skills_d6.known_rooms(room).items():
            ros = read_json_file(folder / 'roster.json')
            for name, aid in (ros.items() if isinstance(ros, dict) else []):
                path = transcript(aid)
                if not path:
                    continue
                n_tr += 1
                reg['rooms'].setdefault(rid, {'name': folder.name, 'n': 0})['name'] = folder.name
                key = str(path)
                off = reg['offsets'].get(key, 0)
                try:
                    size = path.stat().st_size
                    if size < off:
                        off = 0
                    with open(path, 'rb') as f:
                        while off < size:
                            if time.time() - t0 > budget:
                                complete = False
                                break
                            f.seek(off)
                            data = f.read(CHUNK)
                            end = data.rfind(b'\n') + 1
                            if not end:      # a line longer than the chunk (or still being written): skipped when it is a full chunk
                                if len(data) < CHUNK:
                                    break
                                end = len(data)
                            for cid, ref, at in calls_in(data[:end]):
                                if cid not in seen:      # a streamed message is written more than once
                                    seen.add(cid)
                                    reg['uses'].append({'id': cid, 'room': rid, 'agent': name, 'ref': ref, 'at': at})
                                    n_new += 1
                            off += end
                except OSError:
                    continue
                reg['offsets'][key] = off
                reg['rooms'][rid]['n'] = reg['rooms'][rid].get('n', 0) + 1
                if not complete:
                    break
            if not complete:
                break
        save(reg)
    return {'rooms': len(reg['rooms']), 'transcripts': n_tr, 'new': n_new, 'complete': complete}


# ---------------------------------------------------------------- what a call led to

def held(board, agent, at):
    """(task, outcome, ok) of the task `agent` held at epoch `at`: from the hist entry that gave it to the agent until the next entry; (None, 'none', None) when none"""
    best = None
    for t in board.get('tasks') or []:
        h = [x for x in t.get('hist') or [] if isinstance(x, dict)]
        for i, x in enumerate(h):
            start = float(x.get('ts') or 0)
            end = float(h[i + 1].get('ts') or 0) if i + 1 < len(h) else 1e18      # the next change of the task ends this turn of the agent
            if x.get('owner') == agent and x.get('state') == 'taken' and start - 1 <= at <= end + 60 and (best is None or start > best[0]):
                best = (start, t)
    if not best:
        return None, 'none', None
    t = best[1]
    st = t.get('state')
    return t, ('done' if st == 'done' else 'open' if st in ('open', 'taken') else 'dropped'), (True if st == 'done' else None if st in ('open', 'taken') else False)


def uses_of(reg, skill_list):
    """{skill id: [use]} in time order; the ref of a call is resolved against the skills known now"""
    refs, out = {}, {}
    for u in sorted(reg['uses'], key=lambda u: u.get('at') or 0):
        ref = u.get('ref')
        if ref not in refs:
            refs[ref] = find(skill_list, ref)
        if refs[ref]:
            out.setdefault(refs[ref]['id'], []).append(u)
    return out


def entries(uses, reg, boards):
    """each use with the task the agent held and how it ended"""
    out = []
    for u in uses:
        t, outcome, good = held(boards(u['room']), u.get('agent'), u.get('at') or 0)
        out.append({'room': u['room'], 'room_name': (reg['rooms'].get(u['room']) or {}).get('name'), 'agent': u.get('agent'), 'task': t.get('id') if t else None,
                    'task_title': (t.get('title') or '')[:120] if t else None, 'outcome': outcome, 'ok': good, 'at': int(u.get('at') or 0)})
    return out


def view_of(es, reg):
    """the "usage" object of one skill from its entries (see the contract)"""
    scanned, rooms = len(reg['rooms']), {e['room'] for e in es}
    return {'count': len(es), 'rooms': len(rooms), 'last': max((e['at'] for e in es), default=0) or None, 'ok': sum(e['ok'] is True for e in es),
            'fail': sum(e['ok'] is False for e in es), 'unused_rooms': scanned - len(rooms), 'scanned_rooms': scanned,
            'unused': scanned >= UNUSED_ROOMS and not es, 'log': [{k: e[k] for k in ('room', 'agent', 'task', 'ok', 'at')} for e in es[-20:]]}


def board_reader(room):
    import skills_d6
    cache, known = {}, skills_d6.known_rooms(room)

    def get(rid):
        if rid not in cache:
            d = read_json_file(known[rid] / 'board.json') if rid in known else None
            cache[rid] = d if isinstance(d, dict) else {}
        return cache[rid]
    return get


def decorate(room, skill_list):
    """skills[].usage from the registry (cheap: no transcript is read here)"""
    reg = registry()
    by, boards = uses_of(reg, skill_list), board_reader(room)
    for s in skill_list:
        s['usage'] = view_of(entries(by.get(s['id'], []), reg, boards), reg)


def act(room, action, body, skill_list, confirm):
    if action == 'measure':
        return measure(room, body, skill_list)
    if action == 'usage_scan':
        r = scan(room)
        return {'ok': True, 'scanned': {k: r[k] for k in ('rooms', 'transcripts', 'new')}, 'complete': r['complete']}
    ref = str(body.get('id') or body.get('skill') or '')
    s = find(skill_list, ref)
    if not s:
        return fail(say('skills.core.err_no_skill', skill=ref))
    reg = registry()
    es = entries(uses_of(reg, skill_list).get(s['id'], []), reg, board_reader(room))
    return {'ok': True, 'uses': es[-200:], 'usage': view_of(es, reg)}


def do(room, action, body, skill_list, confirm):
    return act(room, action, body, skill_list, confirm)


# ---------------------------------------------------------------- 2 measured tokens and steps (a measure, never an estimate)

MIN_N = 3                # tasks needed with the skill and without it before a number is given
MEASURE_BUDGET = 90.0
_tl = {}                 # transcript path -> what was read of it: read once, then only what was added
_tl_lock = threading.Lock()      # two measures at once would both advance the same offset: one at a time


def timeline(path, deadline):
    """(requests [(ts, input-equivalent tokens)], tool calls [ts], complete): the transcript read from where the last call stopped"""
    import cost
    st = _tl.setdefault(str(path), {'off': 0, 'req': [], 'calls': [], 'msg': set(), 'call': set()})
    try:
        size = path.stat().st_size
        if size < st['off']:
            st.update(off=0, req=[], calls=[], msg=set(), call=set())
        with open(path, 'rb') as f:
            while st['off'] < size:
                if time.time() > deadline:
                    return st['req'], st['calls'], False
                f.seek(st['off'])
                data = f.read(CHUNK)
                end = data.rfind(b'\n') + 1 or (len(data) if len(data) == CHUNK else 0)
                if not end:
                    break
                for raw in data[:end].splitlines():
                    if b'"assistant"' not in raw:
                        continue
                    try:
                        d = json.loads(raw)
                    except ValueError:
                        continue
                    m, ts = d.get('message') or {}, epoch(d.get('timestamp'))
                    for c in m.get('content') or []:
                        if isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('id') not in st['call']:
                            st['call'].add(c.get('id'))
                            st['calls'].append(ts)
                    u = m.get('usage')
                    if d.get('type') == 'assistant' and isinstance(u, dict) and m.get('id') not in st['msg']:
                        st['msg'].add(m.get('id'))
                        w, w1 = int(u.get('cache_creation_input_tokens') or 0), int((u.get('cache_creation') or {}).get('ephemeral_1h_input_tokens') or 0)
                        st['req'].append((ts, int(u.get('input_tokens') or 0) * cost.W_IN + (w - w1) * cost.W_W5 + w1 * cost.W_W1
                                          + int(u.get('cache_read_input_tokens') or 0) * cost.W_READ + int(u.get('output_tokens') or 0) * cost.W_OUT))
                st['off'] += end
    except OSError:
        pass
    return st['req'], st['calls'], True


def spans(board, agent):
    """[(task, start, end)] of the closed tasks `agent` held: from taking it until the next change"""
    out = []
    for t in board.get('tasks') or []:
        h = [x for x in t.get('hist') or [] if isinstance(x, dict)]
        for i, x in enumerate(h[:-1]):
            if x.get('owner') == agent and x.get('state') == 'taken' and h[i + 1].get('state') == 'done':
                out.append((t, float(x['ts']), float(h[i + 1]['ts'])))
    return out


def mean(v):
    return round(sum(v) / len(v)) if v else None


def measure_of(room, s, skill_list, budget=MEASURE_BUDGET):
    """{'with': {n, tokens_mean, steps_mean}, 'without': {...}, 'complete': bool}: the closed tasks of the rooms where the skill was called,
    split by whether the agent called it during the task"""
    import skills_d6
    used = uses_of(registry(), skill_list).get(s['id'], [])
    known = skills_d6.known_rooms(room)
    deadline = time.time() + budget
    complete = True
    rows = {'with': [], 'without': []}
    for rid in sorted({u['room'] for u in used}):
        folder = known.get(rid)
        if not folder:
            continue
        board, ros = read_json_file(folder / 'board.json'), read_json_file(folder / 'roster.json')
        board = board if isinstance(board, dict) else {}
        for agent, aid in (ros.items() if isinstance(ros, dict) else []):
            path = transcript(aid)
            if not path:
                continue
            req, calls, done = timeline(path, deadline)
            complete = complete and done
            for t, a, b in spans(board, agent):
                called = any(u['room'] == rid and u.get('agent') == agent and a - 1 <= (u.get('at') or 0) <= b + 1 for u in used)
                rows['with' if called else 'without'].append((sum(e for ts, e in req if a <= ts <= b), sum(1 for ts in calls if a <= ts <= b)))
    out = {k: {'n': len(v), 'tokens_mean': mean([x[0] for x in v]), 'steps_mean': mean([x[1] for x in v])} for k, v in rows.items()}
    return {**out, 'complete': complete}


def measure(room, body, skill_list):
    ref = str(body.get('id') or body.get('skill') or '')
    s = find(skill_list, ref)
    if not s:
        return fail(say('skills.core.err_no_skill', skill=ref))
    with _tl_lock:
        m = measure_of(room, s, skill_list)
    if not m['complete']:
        return {'ok': False, 'error': say('skills.d8.err_measure_slow'), 'complete': False}
    a, b = m['with'], m['without']
    enough = a['n'] >= MIN_N and b['n'] >= MIN_N
    out = {'tokens_saved': b['tokens_mean'] - a['tokens_mean'] if enough else None, 'steps_saved': b['steps_mean'] - a['steps_mean'] if enough else None,
           'basis': say('skills.d8.basis_ok', a=a['n'], b=b['n']) if enough else say('skills.d8.basis_few', a=a['n'], b=b['n'], n=MIN_N), 'with': a, 'without': b, 'min_n': MIN_N, 'at': int(time.time())}
    import skills_d8
    skills_d8.sidecar_set(s['id'], measured=out)
    return {'ok': True, 'measured': out}
