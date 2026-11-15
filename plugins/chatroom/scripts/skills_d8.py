"""D8 of the skill workshop: verification of skills (the six ideas of the papers in research/PAPER-SKILL.md): an executable check and a
"verified" state, the usage registry read from the transcripts, tokens and steps measured (never estimated), three levels, the activation
test and nearby cases. Contract: stanza-skill/scratch/CORE/skills.d8.contract.md.

Where the data lives: a candidate keeps it in its meta.json, a real skill in ~/.claude/chatroom/skills-meta.json (never in the skill's own
folder). Nothing runs, spends tokens or is written outside the room without confirm; a command always comes from the STORED check and the
preview shows it whole with a token of what it will run (the confirm must send the token back: the check cannot change in between)."""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from i18n import say
from skills import claude_dir, fail, find, read_json_file

TIMEOUT, TIMEOUT_MAX = 110, 600
LEVELS = ('strategy', 'function', 'step')
ACTIONS = ('check_set', 'check_run', 'level_set', 'cases_set', 'cases_run')      # skills_use and skills_act bring their own
_lock = threading.Lock()


# ---------------------------------------------------------------- the sidecar of the real skills

def meta_file():
    return claude_dir() / 'chatroom' / 'skills-meta.json'


_seen = {}


def sidecar():
    f = meta_file()
    try:
        st = f.stat()
    except OSError:
        return {}
    key = (st.st_mtime_ns, st.st_size)
    if _seen.get('key') != key:      # read again only when the file changed (the index asks for it once per skill and candidate)
        d = read_json_file(f)
        s = d.get('skills') if isinstance(d, dict) else None
        _seen.update(key=key, data=s if isinstance(s, dict) else {})
    return _seen['data']


def sidecar_set(sid, **kv):
    import chat
    with _lock:
        s = sidecar()
        cur = s.get(sid) if isinstance(s.get(sid), dict) else {}
        cur.update(kv)
        _seen.clear()
        s[sid] = {k: v for k, v in cur.items() if v is not None}
        meta_file().parent.mkdir(parents=True, exist_ok=True)
        chat.write_atomic(meta_file(), json.dumps({'v': 1, 'skills': s}, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- shapes (every field is always there)

def norm_check(v):
    """{'cmd', 'cwd', 'timeout'} or None"""
    if not isinstance(v, dict):
        return None
    cmd = str(v.get('cmd') or '').strip()
    if not cmd or len(cmd) > 1000:
        return None
    try:
        t = max(1, min(TIMEOUT_MAX, int(v.get('timeout') or TIMEOUT)))
    except (TypeError, ValueError):
        t = TIMEOUT
    cwd = str(v['cwd']).strip()[:500] if v.get('cwd') else None
    return {'cmd': cmd, 'cwd': cwd or None, 'timeout': t}


def file_hash(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
    except OSError:
        return None


def verified_view(v, current):
    """verified | failed | unverified: a result counts only for the SKILL.md it was run against"""
    v = v if isinstance(v, dict) else {}
    same = bool(current) and v.get('skill_hash') == current
    state = ('verified' if v.get('ok') else 'failed') if same and v.get('at') else 'unverified'
    return {'state': state, 'ok': state == 'verified', 'at': v.get('at') if same else None, 'exit': v.get('exit') if same else None, 'hash': v.get('hash') if same else None}


def measured_view(m):
    """what was measured (skills_use.measure) or null: a candidate never has it, and a number in a meta.json is not a measure"""
    if not isinstance(m, dict):
        return None
    return {k: m.get(k) for k in ('tokens_saved', 'steps_saved', 'basis', 'with', 'without', 'min_n', 'at')}


def activation_view(a):
    if not isinstance(a, dict):
        return None
    return {k: a.get(k) for k in ('right', 'wrong', 'total', 'at', 'suggestion', 'tp', 'fn', 'fp', 'tn')}


def cases_run_view(c, skill_hash):
    """the last run of the cases, or null; stale when SKILL.md changed since"""
    if not isinstance(c, dict) or not isinstance(c.get('results'), list):
        return None
    return {'at': c.get('at'), 'results': c['results'], 'passed': all(x.get('passed') is True for x in c['results'] if isinstance(x, dict)), 'stale': c.get('skill_hash') != skill_hash}


def fields(meta, skill_hash, entry):
    """the D8 fields of a candidate (its meta.json) or of a real skill (its sidecar entry), always all of them. `verified` always comes from the
    server's own sidecar, never from a meta.json: a job writes that file and must not be able to say "verified" (the sidecar is keyed by the candidate id)"""
    m = meta if isinstance(meta, dict) else {}
    e = entry if isinstance(entry, dict) else {}      # the server's own sidecar entry: the verdict, the measure and the activation come only from there
    import skills_use
    return {'check': norm_check(m.get('check')), 'verified': verified_view(e.get('verified'), skill_hash), 'usage': skills_use.empty_usage(),
            'measured': measured_view(e.get('measured')), 'activation': activation_view(e.get('activation')), 'level': m.get('level') if m.get('level') in LEVELS else None,
            'parent': m['parent'][:200] if isinstance(m.get('parent'), str) and m.get('parent') else None, 'children': [],
            'cases': norm_cases(m.get('cases')), 'cases_run': cases_run_view(e.get('cases_run'), skill_hash)}


def decorate(skills):
    """skills[] of the index: the D8 fields from the sidecar (local file, no network)"""
    side = sidecar()
    for s in skills:
        e = side.get(s['id'])
        s.update(fields(e, file_hash(s['path']) if s.get('path') else None, e))
    by = {s['id']: s for s in skills}
    for s in skills:      # the tree: a parent that is gone is no parent; children are the skills that name this one
        if s['parent'] and s['parent'] not in by:
            s['parent'] = None
        if s['parent']:
            by[s['parent']]['children'].append(s['id'])


# ---------------------------------------------------------------- the target of an action: a candidate or a real skill

def target(room, body, skill_list):
    """{'kind', 'id', 'name', 'folder', 'file', 'meta', 'save'} of body.id|skill|cand, or an error text"""
    import skills_d6
    ref = str(body.get('id') or body.get('skill') or body.get('cand') or '')
    if ref.startswith('cand:'):
        found = skills_d6.one(room, ref, skill_list)
        if not found:
            return say('skills.d6.err_no_candidate', id=ref)
        c, d, _ = found
        def save(**kv):      # the check is the job's to write too (meta.json); the verdict only the server's (sidecar)
            own = {k: kv.pop(k) for k in ('verified', 'cases_run') if k in kv}
            if own:
                sidecar_set(ref, **own)
            if kv:
                skills_d6.write_meta(d, **kv)
        return {'kind': 'candidate', 'id': ref, 'name': c['name'], 'folder': d, 'file': d / 'SKILL.md', 'meta': read_json_file(d / 'meta.json') or {},
                'verdict': sidecar().get(ref) or {}, 'save': save}
    s = find(skill_list, ref)
    if not s:
        return say('skills.core.err_no_skill', skill=ref)
    if not s.get('path'):
        return say('skills.d8.err_no_folder', skill=s['name'])
    return {'kind': 'skill', 'id': s['id'], 'name': s['name'], 'folder': Path(s['path']).parent, 'file': Path(s['path']), 'meta': sidecar().get(s['id']) or {}, 'verdict': sidecar().get(s['id']) or {},
            'save': lambda **kv: sidecar_set(s['id'], **kv)}


# ---------------------------------------------------------------- 1 the check

class Busy(OSError):
    pass


def run_cmd(cmd, cwd, limit):
    """(exit code or None when over the limit, output): like a task's --verify (own process group, one heavy job at a time on the machine)"""
    import chat
    from machine import machine_lock
    from machine import holder
    h = holder()
    if h and h.get('pid') != os.getpid():      # another heavy job runs: answer at once, a request must not hang on the machine
        raise Busy(str(h.get('label') or '?'))
    with machine_lock(f'skill check: {cmd}'):
        return chat.run_tree(cmd, cwd, limit)


def token_of(*checks):
    return hashlib.sha256(json.dumps([c for c in checks], sort_keys=True).encode('utf-8')).hexdigest()[:12]


def run_one(check, folder):
    """{'passed', 'exit', 'out', 'hash', 'at'} of one stored check, or an error text when its folder is not there"""
    cwd = Path(check['cwd']) if check['cwd'] else Path(folder)
    if not cwd.is_dir():
        return say('skills.d8.err_cwd', cwd=str(cwd))
    try:
        code, out = run_cmd(check['cmd'], str(cwd), check['timeout'])
    except Busy as exc:
        return say('skills.d8.err_busy', label=str(exc)[:120])
    except OSError as exc:
        return say('skills.d8.err_run', exc=str(exc)[:200])
    return {'passed': code == 0, 'exit': code, 'out': '\n'.join(out.strip().splitlines()[-15:]), 'hash': hashlib.sha256(out.encode('utf-8')).hexdigest()[:12], 'at': int(time.time())}


def act(room, action, body, skill_list, confirm):
    t = target(room, body, skill_list)
    if isinstance(t, str):
        return fail(t)
    if action == 'check_set':
        raw = body.get('check')
        ck = norm_check(raw)
        if raw is not None and ck is None:
            return fail(say('skills.d8.err_bad_check'))
        t['save'](check=ck, verified=None)      # a new command is a new question: the old answer goes
        return {'ok': True, 'check': ck}
    if action == 'check_run':
        ck = norm_check(t['meta'].get('check'))
        if not ck:
            return fail(say('skills.d8.err_no_check', name=t['name']))
        cwd = (ck['cwd'] or str(t['folder'])).replace(chr(92), '/')
        tok = token_of(ck, cwd)
        if not confirm:
            return {'ok': True, 'preview': {'name': t['name'], 'what': t['kind'], 'cmd': ck['cmd'], 'cwd': cwd, 'timeout': ck['timeout'], 'token': tok,
                                            'note': say('skills.d8.runs_here')}}
        if str(body.get('token') or '') != tok:
            return {'ok': False, 'error': say('skills.d8.err_token'), 'needs': 'token', 'token': tok}
        r = run_one(ck, t['folder'])
        if isinstance(r, str):
            return fail(r)
        v = {'ok': r['passed'], 'at': r['at'], 'exit': r['exit'], 'hash': r['hash'], 'skill_hash': file_hash(t['file'])}
        t['save'](verified=v)
        return {'ok': True, **r, 'verified': verified_view(v, v['skill_hash'])}
    if action == 'level_set':
        return level_set(t, body, skill_list)
    if action == 'cases_set':
        return cases_set(t, body)
    if action == 'cases_run':
        return cases_run(t, body, confirm)
    return fail(say('skills.core.err_unknown_action', action=action))


CASES_MAX = 4      # SkillMaster uses K=4 nearby cases


def cases_set(t, body):
    """1 to 4 cases of the same family as the skill, each a task and the check that proves it (a case is an executable check, not a model run)"""
    raw = body.get('cases')
    if raw is None:
        t['save'](cases=None)
        return {'ok': True, 'cases': []}
    if not isinstance(raw, list) or not 1 <= len(raw) <= CASES_MAX:
        return fail(say('skills.d8.err_bad_cases', k=CASES_MAX))
    out = []
    for i, c in enumerate(raw):
        ck = norm_check(c.get('check')) if isinstance(c, dict) else None
        if not ck:
            return fail(say('skills.d8.err_bad_case', n=i + 1))
        out.append({'id': f'c{i + 1}', 'task': str(c.get('task') or '').strip()[:300], 'check': ck})
    t['save'](cases=out, cases_run=None)      # new cases are new questions: the last run goes
    return {'ok': True, 'cases': out}


def cases_run(t, body, confirm):
    cases = norm_cases(t['meta'].get('cases'))
    if not cases:
        return fail(say('skills.d8.err_no_cases', name=t['name']))
    here = str(t['folder']).replace(chr(92), '/')
    shown = [{'id': c['id'], 'task': c['task'], 'check': {**c['check'], 'cwd': (c['check']['cwd'] or here).replace(chr(92), '/')}} for c in cases]
    tok = token_of(shown)
    if not confirm:
        return {'ok': True, 'preview': {'name': t['name'], 'what': t['kind'], 'cases': shown, 'cwd': here, 'timeout': max(c['check']['timeout'] for c in cases), 'runs': len(cases),
                                        'token': tok, 'note': say('skills.d8.runs_here')}}
    if str(body.get('token') or '') != tok:
        return {'ok': False, 'error': say('skills.d8.err_token'), 'needs': 'token', 'token': tok}
    results = []
    for c in shown:
        r = run_one(c['check'], t['folder'])
        if isinstance(r, str):
            return fail(r)
        results.append({'id': c['id'], 'passed': r['passed'], 'exit': r['exit']})
    at = int(time.time())
    t['save'](cases_run={'at': at, 'results': results, 'skill_hash': file_hash(t['file'])})
    return {'ok': True, 'results': results, 'passed': all(x['passed'] for x in results), 'at': at}


def level_set(t, body, skill_list):
    """level and parent of a skill or candidate: strategy > function > step; a parent is a real skill of a strictly higher level, so there is no cycle"""
    cur = t['meta'] if isinstance(t['meta'], dict) else {}
    level = body['level'] if 'level' in body else cur.get('level')
    parent = body['parent'] if 'parent' in body else cur.get('parent')
    if level not in LEVELS and level is not None:
        return fail(say('skills.d8.err_bad_level', levels=', '.join(LEVELS)))
    rank = {n: i for i, n in enumerate(LEVELS)}
    pid = None
    if parent:
        p = find(skill_list, str(parent))
        if not p:
            return fail(say('skills.d8.err_no_parent', parent=str(parent)[:80]))
        pid = p['id']
        plevel = (sidecar().get(pid) or {}).get('level')
        if level is None or plevel not in rank:
            return fail(say('skills.d8.err_level_needed', parent=p['name']))
        if rank[plevel] >= rank[level] or pid == t['id']:
            return fail(say('skills.d8.err_not_higher', parent=p['name'], plevel=plevel, level=level))
    if t['kind'] == 'skill':
        for sid, e in sidecar().items():      # a child must stay below this skill
            if isinstance(e, dict) and e.get('parent') == t['id'] and (level is None or e.get('level') not in rank or rank[e['level']] <= rank[level]):
                return fail(say('skills.d8.err_children', child=sid, level=str(level)))
    t['save'](level=level, parent=pid)
    return {'ok': True, 'level': level, 'parent': pid}


def do(room, action, body, skill_list, confirm):
    return act(room, action, body, skill_list, confirm)


# ---------------------------------------------------------------- the gate of an improvement (promote over an existing skill)

def gate_of(raw, skill_id):
    """what must still hold after a candidate replaces a skill: the check of the candidate AND the check the skill already had (a candidate cannot
    weaken the gate by bringing an easier one), the cases of both"""
    old = sidecar().get(skill_id) if skill_id else None
    old = old if isinstance(old, dict) else {}
    raw = raw if isinstance(raw, dict) else {}
    new_ck, old_ck = norm_check(raw.get('check')), norm_check(old.get('check'))
    checks = []
    if new_ck or old_ck:
        checks.append(('check', new_ck or old_ck))      # the first is the one the new skill keeps and is verified by
    if new_ck and old_ck and new_ck != old_ck:
        checks.append(('check-old', old_ck))
    cases, ids = [], set()
    for c in norm_cases(old.get('cases')) + norm_cases(raw.get('cases')):
        cid = c['id']
        while cid in ids:
            cid += '+'
        ids.add(cid)
        cases.append({**c, 'id': cid})
    return {'checks': checks, 'cases': cases[:8]}


def norm_cases(v):
    out = []
    for i, c in enumerate(v if isinstance(v, list) else []):
        ck = norm_check(c.get('check')) if isinstance(c, dict) else None
        if ck:
            out.append({'id': str(c.get('id') or f'c{i + 1}')[:20], 'task': str(c.get('task') or '')[:300], 'check': ck})
    return out[:4]


def gate_runs(gate):
    """how many executions an improvement costs: every check once (after), every case twice (before and after)"""
    return len(gate['checks']) + 2 * len(gate['cases'])


def gate_list(gate, folder):
    """the commands of the gate, whole, each with the folder it runs in (the target)"""
    here = str(folder).replace(chr(92), '/')
    items = list(gate['checks']) + [(c['id'], c['check']) for c in gate['cases']]
    return [{'id': i, 'cmd': ck['cmd'], 'cwd': (ck['cwd'] or here).replace(chr(92), '/'), 'timeout': ck['timeout']} for i, ck in items]


def gate_run(item):
    r = run_one({'cmd': item['cmd'], 'cwd': item['cwd'], 'timeout': item['timeout']}, item['cwd'])
    return r if isinstance(r, dict) else {'passed': False, 'exit': None, 'out': r, 'hash': None, 'at': int(time.time())}


def gate_baseline(gate, folder):
    """{case id: passed} on the folder as it is now (only cases need a before)"""
    ids = {c['id'] for c in gate['cases']}
    return {i['id']: gate_run(i)['passed'] for i in gate_list(gate, folder) if i['id'] in ids}


def gate_after(gate, before, folder):
    """{'refused', 'why', 'view': {cases_result, better, worse, utility}, 'check': the result of the first check or None}: every check must pass,
    no case may go from passing to failing"""
    res, check, why = [], None, ''
    names = {i for i, _ in gate['checks']}
    for i in gate_list(gate, folder):
        r = gate_run(i)
        if i['id'] in names:
            check = r if i['id'] == 'check' else check
            if not r['passed'] and not why:
                why = say('skills.d8.err_gate_check', cmd=i['cmd'][:120], exit=r['exit'])
        else:
            res.append({'id': i['id'], 'before': bool(before.get(i['id'])), 'after': r['passed']})
    better = sum(1 for x in res if x['after'] and not x['before'])
    worse = sum(1 for x in res if x['before'] and not x['after'])
    if not why and worse:
        why = say('skills.d8.err_gate_case', ids=', '.join(x['id'] for x in res if x['before'] and not x['after']))
    util = round(sum(int(x['after']) - int(x['before']) for x in res) / len(res), 2) if res else 0.0      # the paper's utility: mean of the deltas (informative; our rule is stricter)
    return {'refused': bool(why), 'why': why, 'check': check, 'view': {'cases_result': res, 'better': better, 'worse': worse, 'utility': util}}


def carry(raw, new_id, file, old_verified, gated, gate=None):
    """the new skill keeps the check and the cases of its candidate and a verified state (the gate's own run, else the candidate's, else unverified)"""
    raw = raw if isinstance(raw, dict) else {}
    h = file_hash(file)
    v = None
    if gated and gated['check']:
        c = gated['check']
        v = {'ok': c['passed'], 'at': c['at'], 'exit': c['exit'], 'hash': c['hash'], 'skill_hash': h}
    elif old_verified and old_verified.get('state') == 'verified':
        v = {'ok': True, 'at': old_verified['at'], 'exit': old_verified['exit'], 'hash': old_verified['hash'], 'skill_hash': h}
    kv = {'verified': v}
    ck = norm_check(raw.get('check')) or (gate['checks'][0][1] if gate and gate['checks'] else None)
    if ck:
        kv['check'] = ck
    if gate and gate['cases']:      # an accepted improvement keeps the cases the gate ran (old ones first, then the candidate's): no case is lost, at most 4 stored
        kv['cases'] = [dict(c) for c in gate['cases'][:4]]
    elif raw.get('cases'):
        kv['cases'] = norm_cases(raw.get('cases'))
    lv = raw.get('level')
    if lv in LEVELS:      # where the candidate sits in the tree goes with it, under the same rules as level_set: a real parent of a strictly higher level, never itself
        rank = {n: i for i, n in enumerate(LEVELS)}
        side = sidecar()
        pa = raw.get('parent') if isinstance(raw.get('parent'), str) else None
        if pa == new_id or (side.get(pa) or {}).get('level') not in rank or rank[(side.get(pa) or {})['level']] >= rank[lv]:
            pa = None
        below = any(isinstance(e, dict) and e.get('parent') == new_id and (e.get('level') not in rank or rank[e['level']] <= rank[lv]) for e in side.values())
        if not below:      # a skill that already has children below it keeps its level when the new one would put them level with it or above
            kv['level'], kv['parent'] = lv, pa
    sidecar_set(new_id, **kv)
