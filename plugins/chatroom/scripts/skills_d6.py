"""D6 of the skill workshop: skills born from the work and improved by it. Candidates of a room (ROOM/skills-candidates/NAME/
SKILL.md + meta.json), the jobs that write them (derive, suggest, improve: one headless `claude -p` after the user's confirm), the
diff of an improvement and its promotion into the real skills (backup, then the old folder is REPLACED, never appended to).
Contract: stanza-skill/scratch/CORE/skills.d6.contract.md. skills.py routes here (do) and adds candidates to the index.

Nothing is written in a skill folder or in ~/.claude without confirm; the client never sends a path (candidates resolve through
the known rooms); a job reads a digest the server builds (never chat.jsonl or an agent transcript) and writes only into
skills-candidates/**."""
import difflib
import hashlib
import json
import os
import re
import shutil
import threading
import time
from pathlib import Path

import skills
import skills_d8
from i18n import say
from skills import change, claude_dir, fail, find, post, read_front, read_json_file, scan, state_of

KINDS = ('derive', 'suggest', 'improve')
LABEL = {'derive': 'SKILLDERIVE', 'suggest': 'SKILLSUGGEST', 'improve': 'SKILLIMPROVE'}
JOB_NAME = 'SKILLWORK'
CRIT = ('recurrence', 'error_cost', 'specificity', 'overlap', 'weight')
SLUG = re.compile(r'[a-z0-9][a-z0-9-]{0,59}\Z')
BODY_MAX, DIGEST_MAX, ROOMS_MAX, PER_ROOM, STALE, CHAT_STALE = 20000, 60000, 20, 50, 1900, 3600
COVER = 0.6


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-')[:60] or 'skill'


def user_dir():
    return Path(os.environ.get('CHATROOM_SKILLS_USER_DIR') or claude_dir() / 'skills')


# ---------------------------------------------------------------- rooms and candidates

def rid(path):
    return hashlib.sha1(str(Path(path).resolve()).encode('utf-8')).hexdigest()[:8]


def known_rooms(room):
    """{id: folder} of this room and the rooms of known_rooms.json (the newest 50, at most ROOMS_MAX) that still exist"""
    out = {rid(room.dir): Path(room.dir).resolve()}
    known = read_json_file(claude_dir() / 'chatroom' / 'known_rooms.json')
    known = known if isinstance(known, dict) else {}
    for k in sorted(known, key=lambda k: -float(known[k].get('ts', 0)) if isinstance(known[k], dict) else 0):      # the newest first
        p = Path(k)
        if p.is_dir() and len(out) < ROOMS_MAX:
            out.setdefault(rid(p), p.resolve())
    return out


def words(text):
    return {w for w in re.findall(r'[a-z]{4,}', text.lower())}


def weight_of(body):
    """prompt weight 0-10 from the length (PAPER-SKILL: < 300 words 0-3, > 800 words 7-10)"""
    n = len(body.split())
    return min(3, round(n / 100)) if n < 300 else min(10, 7 + (n - 800) // 300) if n > 800 else 4 + (n - 300) * 2 // 500


def score_of(c):
    """S = 2*recurrence + error_cost + 2*specificity + (10-overlap) + (10-weight), score = max(1, floor(S/7+.5)) (PAPER-SKILL, T18)"""
    s = 2 * c['recurrence'] + c['error_cost'] + 2 * c['specificity'] + (10 - c['overlap']) + (10 - c['weight'])
    return max(1, min(10, int(s / 7 + 0.5)))


def num(v, lo, hi, default=0):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def lines(v, n=8):
    return [str(x).strip()[:200] for x in v if str(x).strip()][:n] if isinstance(v, list) else []


def covered(body_desc, name, others):
    """(id of the closest existing skill, ratio): the same name, or the words of its description mostly in an existing one"""
    w, best = words(body_desc), (None, 0.0)
    for s in others:
        r = 1.0 if s['name'] == name else len(w & words(s['description'])) / len(w) if w else 0.0
        if r > best[1]:
            best = (s['id'], r)
    return best


def candidate(room_id, d, others):
    """one candidate folder as the index shows it (no body), or None when its meta or its SKILL.md is unusable"""
    meta, f = read_json_file(d / 'meta.json'), d / 'SKILL.md'
    if not isinstance(meta, dict) or not f.is_file() or not SLUG.match(d.name):
        return None
    try:
        body = f.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return None
    status = meta.get('status') if meta.get('status') in ('new', 'added', 'dismissed') else 'new'
    improves = meta.get('improves') if isinstance(meta.get('improves'), str) else None
    cov, ratio = (None, 0.0) if status == 'added' else covered(read_front(f).get('description', ''), d.name, [s for s in others if s['id'] != improves])
    raw = meta.get('criteria') if isinstance(meta.get('criteria'), dict) else {}
    crit = {k: num(raw.get(k), 0, 10) for k in CRIT}
    crit['overlap'] = max(crit['overlap'], round(ratio * 10) if ratio >= COVER else 0)       # the server's own checks beat the job's word
    crit['weight'] = weight_of(body)
    return {'id': f'cand:{room_id}:{d.name}', 'room': room_id, 'name': d.name, 'score': score_of(crit), 'why': str(meta.get('why') or '')[:300],
            'kind': meta.get('kind') if meta.get('kind') in KINDS else 'derive', 'tasks': lines(meta.get('tasks'), 20), 'criteria': crit,
            'repeated': lines(meta.get('repeated')), 'hard': lines(meta.get('hard')),
            'tokens_saved': None,      # D8: only a measure counts (skills_use.measure), never what a job says
             'tokens': len(body.encode('utf-8')) // 4,
            'covered_by': cov if ratio >= COVER else None, 'improves': improves, 'status': status, 'req': str(meta.get('req') or ''),
            'at': num(meta.get('at'), 0, 2 ** 40), **skills_d8.fields(meta, skills_d8.file_hash(f), skills_d8.sidecar().get(f'cand:{room_id}:{d.name}'))}


def room_candidates(room_id, folder, others):
    base, out = folder / 'skills-candidates', []
    try:
        dirs = sorted(p for p in base.iterdir() if p.is_dir())[:PER_ROOM * 4]
    except OSError:
        return out
    out = [c for c in (candidate(room_id, d, others) for d in dirs) if c]
    out.sort(key=lambda c: (-c['score'], -c['at']))
    return out[:PER_ROOM]


def listing(room, skill_list):
    """(rooms[], candidates[]) for GET /skills.json"""
    rooms, cands = [], []
    for k, p in known_rooms(room).items():
        cs = room_candidates(k, p, skill_list)
        cands += cs
        if cs or p == Path(room.dir).resolve():
            rooms.append({'id': k, 'name': p.name, 'current': p == Path(room.dir).resolve(), 'n': len(cs)})
    return rooms, cands


def resolve(room, cid):
    """(room id, room folder, candidate folder) of "cand:<room>:<name>", only through the known rooms; None otherwise"""
    m = re.fullmatch(r'cand:([0-9a-f]{8}):([a-z0-9][a-z0-9-]{0,59})', str(cid or ''))
    p = known_rooms(room).get(m[1]) if m else None
    d = p / 'skills-candidates' / m[2] if p else None
    return (m[1], p, d) if d and (d / 'SKILL.md').is_file() else None


# ---------------------------------------------------------------- jobs

def digest(folder, req):
    """what a job may know of a room: tasks with proofs and gaps, decisions, facts, the state notebooks, the tail of events.jsonl.
    Never chat.jsonl, never a transcript. Written in ROOM/skills-jobs/rN.input.md, returns its relative path"""
    b = read_json_file(folder / 'board.json')
    b = b if isinstance(b, dict) else {}
    out = [f'# Room {folder.name}: what was done (digest)\n', '## Tasks']
    for t in b.get('tasks') or []:
        if isinstance(t, dict):
            out.append(f"- {t.get('id')} [{t.get('state')}] {t.get('title')} (owner {t.get('owner')})" + (f"\n  proof: {t['proof']}" if t.get('proof') else '') +
                       (f"\n  gaps: {t['gaps']}" if t.get('gaps') else '') + ''.join(f'\n  note: {n[:300]}' for n in (t.get('notes') or [])[:5]))
    out += ['\n## Decisions'] + [f"- {d.get('text', d)}" for d in b.get('decisions') or [] if d and not (isinstance(d, dict) and d.get('retired'))]
    out += ['\n## Facts'] + [f"- {d.get('text', d)}" for d in b.get('facts') or [] if d]
    out.append('\n## State notebooks')
    for f in sorted((folder / 'notes').glob('*.state.md'))[:12] if (folder / 'notes').is_dir() else []:
        try:
            out.append(f'### {f.stem}\n' + f.read_text(encoding='utf-8')[:3000])
        except (OSError, UnicodeError):
            pass
    try:
        tail = (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()[-40:]
    except (OSError, UnicodeError):
        tail = []
    out += ['\n## Events (tail)'] + tail
    rel = f'skills-jobs/{req}.input.md'
    (folder / 'skills-jobs').mkdir(exist_ok=True)
    (folder / rel).write_text('\n'.join(str(x) for x in out)[:DIGEST_MAX], encoding='utf-8')
    return rel


def abs_rule(path):
    """the permission rule of a folder: //c/dir/** (the drive letter as a folder)"""
    p = str(Path(path).resolve()).replace('\\', '/')
    return '//' + (p[0].lower() + p[2:] if len(p) > 1 and p[1] == ':' else p.lstrip('/')) + '/**'


def parse_source(room, body):
    """{'kind': room|folder|repo, 'label', 'folder'?, 'room_id'?, 'url'?} of the "source" of an action, or an error text"""
    s = body.get('source') if isinstance(body.get('source'), dict) else {}
    if s.get('chat'):
        return {'kind': 'chat', 'label': 'chat'}      # D7: the lead's own session does the work (see start_chat)
    if s.get('folder'):
        p = Path(str(s['folder'])).expanduser()
        return ({'kind': 'folder', 'label': f'folder:{p}', 'folder': p.resolve()} if p.is_dir() else say('skills.d6.err_no_source', src=str(s['folder'])))
    if s.get('repo'):
        m = skills.REPO.match(str(s['repo']))
        return ({'kind': 'repo', 'label': f'repo:https://github.com/{m[1]}/{m[2]}', 'url': f'https://github.com/{m[1]}/{m[2]}'} if m
                else say('skills.d6.err_no_repo', url=str(s['repo'])))
    want = str(s.get('room') or 'current')
    rooms = known_rooms(room)
    k = rid(room.dir) if want == 'current' else want
    if k not in rooms:
        return say('skills.d6.err_no_source', src=want)
    return {'kind': 'room', 'label': f'room:{rooms[k].name}', 'folder': rooms[k], 'room_id': k}


def job_plan(room, kind, body, src, target=None, req='r?'):
    """the job as the user will confirm it: its text, what it reads and writes, the budget"""
    q = re.sub(r'\s+', ' ', str(body.get('desc') or body.get('q') or '')).strip()[:400]
    here = src['folder'] if src['kind'] == 'room' else Path(room.dir)
    reads = [f'skills-jobs/{req}.input.md'] if src['kind'] == 'room' else [src['label']]
    if kind == 'improve':
        reads.append(f'skills-jobs/{req}.current.md')
    task = (say('skills.d6.task_derive', q=q, src=src['label']) if kind == 'derive' else say('skills.d6.task_suggest', src=src['label']) if kind == 'suggest'
            else say('skills.d6.task_improve', skill=target['name'], src=src['label'], q=q or '-'))
    return {'q': q, 'cwd': here, 'reads': reads, 'writes': ['skills-candidates/**'], 'budget_usd': 2 if kind == 'improve' else 1, 'task': task}


def prompt_for(kind, name, req, plan, src, target):
    where = {'room': say('skills.d6.src_room', input=f'skills-jobs/{req}.input.md'),
             'folder': say('skills.d6.src_folder', folder=str(src.get('folder'))),
             'repo': say('skills.d6.src_repo', url=str(src.get('url')))}[src['kind']]
    head = (say('skills.d6.prompt_derive', name=name, src=where, q=plan['q']) if kind == 'derive' else say('skills.d6.prompt_suggest', name=name, src=where)
            if kind == 'suggest' else say('skills.d6.prompt_improve', name=name, src=where, q=plan["q"] or "-", skill=target["name"], sid=target["id"], slug=slug(target["name"]),
                                          current=f'skills-jobs/{req}.current.md'))
    return head + ' ' + say('skills.d6.prompt_rules', req=req, kind=kind) + ' ' + say('skills.d6.prompt_end')


def tools_for(src, kind, req):
    tools, allow = ['Read', 'Write'], ['Edit(skills-candidates/**)']
    if src['kind'] == 'room':
        allow.append(f'Read(skills-jobs/{req}.input.md)')
    elif src['kind'] == 'folder':
        tools += ['Glob', 'Grep']
        allow.append(f"Read({abs_rule(src['folder'])})")
    else:
        tools.append('WebFetch')
        allow.append('WebFetch')
    if kind == 'improve':
        allow.append(f'Read(skills-jobs/{req}.current.md)')
    return ','.join(tools), ' '.join(allow)


def start(room, kind, body, skill_list, confirm):
    src = parse_source(room, body)
    if isinstance(src, str):
        return fail(src)
    target = None
    if kind == 'derive' and src['kind'] != 'chat' and not re.sub(r'\s+', ' ', str(body.get('desc') or body.get('q') or '')).strip():
        return fail(say('skills.d6.err_empty_desc'))      # from the conversation the lead decides what is worth a skill
    if kind == 'improve':
        s = find(skill_list, body.get('skill') or body.get('id'))
        if not s:
            return fail(say('skills.core.err_no_skill', skill=str(body.get('skill') or body.get('id') or '')))
        if s['origin'] == 'builtin':
            return fail(say('skills.d6.err_builtin', skill=s['name']))
        target = {'id': s['id'], 'name': s['name'], 'origin': s['origin'], 'file': s['path'], 'copy': s['origin'] in ('plugin', 'account')}
        target['path'] = str((user_dir() / s['name']) if target['copy'] else Path(s['path']).parent).replace('\\', '/')
    if src['kind'] == 'chat':
        return start_chat(room, kind, body, skill_list, confirm, target)
    st = state_of(room)
    plan = job_plan(room, kind, body, src, target, f"r{st['seq'] + 1}")      # the number the job will get: the preview names its real files
    if any(r.get('kind') == kind and r.get('src') == src['label'] and time.time() - r.get('at', 0) < STALE and request_state(room, r) == 'pending'
           for r in st['requests']):
        return fail(say('skills.d6.err_running'))
    if not confirm:
        pv = {'kind': kind, 'name': JOB_NAME, 'task': plan['task'], 'reads': plan['reads'], 'writes': plan['writes'], 'budget_usd': plan['budget_usd']}
        if target:
            pv['target'] = {k: target[k] for k in ('id', 'path', 'origin', 'copy')}
        return {'ok': True, 'preview': pv}
    req = new_job(room, kind, plan['q'] or plan['task'], src, target)
    cwd = plan['cwd']
    if src['kind'] == 'room':
        digest(cwd, req['req'])
    if kind == 'improve':
        (cwd / 'skills-jobs').mkdir(exist_ok=True)
        try:
            shutil.copyfile(target['file'], cwd / 'skills-jobs' / f"{req['req']}.current.md")
        except OSError as exc:
            return fail(say('skills.core.err_launch', exc=str(exc)[:200]))
    (cwd / 'skills-candidates').mkdir(exist_ok=True)
    tools, allow = tools_for(src, kind, req['req'])
    cmd = [shutil.which('claude') or 'claude', '-p', '--model', 'sonnet', '--permission-mode', 'dontAsk', '--tools', tools, '--allowedTools', allow, '--strict-mcp-config',
           '--max-budget-usd', str(plan['budget_usd']), '--no-session-persistence']
    work = Path(room.dir) / 'skills-temp'
    work.mkdir(exist_ok=True)
    try:
        proc = skills.launch(cmd, prompt_for(kind, JOB_NAME, req['req'], plan, src, target), cwd, work / f"{req['req']}.log")
    except OSError as exc:
        return fail(say('skills.core.err_launch', exc=str(exc)[:200]))
    post(room, say('skills.d6.line', label=LABEL[kind], req=req['req'], q=plan['q'] or plan['task'], src=src['label'], name=JOB_NAME))
    threading.Thread(target=watch, args=(room, req, kind, proc, cwd), daemon=True).start()
    return {'ok': True, 'req': req['req'], 'name': JOB_NAME}


def start_chat(room, kind, body, skill_list, confirm, target):
    """D7: the lead's session derives the skill from the conversation it already has. Nothing is started here: the request waits in
    skills.json, the lead's relay prints one line for it (chat.skill_lines) and the lead writes the candidates like a D6 job does"""
    lead = (room.config().get('self_names') or [''])[0]
    if not lead:
        return fail(say('skills.d7.err_no_lead'))
    q = re.sub(r'\s+', ' ', str(body.get('desc') or body.get('q') or '')).strip()[:400]
    st = state_of(room)
    if any(r.get('src') == 'chat' and r.get('kind') == kind and time.time() - r.get('at', 0) < CHAT_STALE and request_state(room, r) == 'pending' for r in st['requests']):
        return fail(say('skills.d6.err_running'))
    sk = target['name'] if target else '-'
    task = {'derive': lambda: say('skills.d7.task_derive', q=q or '-'), 'suggest': lambda: say('skills.d7.task_suggest'),
            'improve': lambda: say('skills.d7.task_improve', skill=sk, q=q or '-')}[kind]()
    if not confirm:
        pv = {'kind': kind, 'name': lead, 'task': task, 'reads': [say('skills.d7.reads_chat')], 'writes': ['skills-candidates/**']}
        if target:
            pv['target'] = {k: target[k] for k in ('id', 'path', 'origin', 'copy')}
        return {'ok': True, 'preview': pv}
    import chat
    if chat.relay_down(room):
        return fail(say('skills.d7.err_relay'))
    req = new_job(room, kind, q or task, {'kind': 'chat', 'label': 'chat'}, target, by=lead, extra={'announced': False})
    jobs = Path(room.dir) / 'skills-jobs'
    jobs.mkdir(exist_ok=True)
    if target:
        try:
            shutil.copyfile(target['file'], jobs / f"{req['req']}.current.md")
        except OSError as exc:
            return fail(say('skills.core.err_launch', exc=str(exc)[:200]))
    (Path(room.dir) / 'skills-candidates').mkdir(exist_ok=True)
    (jobs / f"{req['req']}.brief.md").write_text(brief(req, kind, q, target, skill_list), encoding='utf-8')
    return {'ok': True, 'req': req['req'], 'name': lead, 'via': 'lead'}


def brief(req, kind, q, target, skill_list):
    """what the lead reads: the task, the D6 rules for a candidate, the skills that exist (to see the overlap), what to post when done"""
    have = '\n'.join(f"- {s['id']} ({s['origin']}): {s['brief'][:100]}" for s in skill_list if s['origin'] != 'builtin')[:12000]
    a = {'req': req['req'], 'q': q or '-', 'skill': target['name'] if target else '-', 'sid': target['id'] if target else '-',
         'slug': slug(target['name']) if target else '-', 'current': f"skills-jobs/{req['req']}.current.md"}
    head = {'derive': lambda: say('skills.d7.brief_derive', **a), 'suggest': lambda: say('skills.d7.brief_suggest', **a),
            'improve': lambda: say('skills.d7.brief_improve', **a)}[kind]()
    return '\n\n'.join([head, say('skills.d6.prompt_rules', req=req['req'], kind=kind), say('skills.d7.brief_end', req=req['req'], label=LABEL[kind]),
                         say('skills.d7.brief_have'), have]) + '\n'


def new_job(room, kind, q, src, target, by=JOB_NAME, extra=None):
    def run(s):
        s['seq'] += 1
        r = {'req': f"r{s['seq']}", 'kind': kind, 'q': q[:300], 'for': [], 'by': room.config().get('user_name', 'USER'), 'at': int(time.time()),
             'searcher': by, 'src': src['label'], 'dir': str(src.get('folder') if src['kind'] == 'room' else room.dir), **(extra or {})}
        if target:
            r['skill'] = target['id']
        s['requests'].append(r)
        return r
    return change(room, run)


def mine(r):
    """the candidates a request wrote, in the folder it ran in"""
    base = Path(r.get('dir') or '') / 'skills-candidates'
    out = []
    try:
        for d in base.iterdir():
            m = read_json_file(d / 'meta.json')
            if isinstance(m, dict) and m.get('req') == r['req'] and (d / 'SKILL.md').is_file():
                out.append(d.name)
    except OSError:
        pass
    return out


def request_state(room, r):
    """done when a candidate of the request exists, failed when the job ended without one, else pending. A request the lead
    does (src chat) is also done when the lead said so in the chat, and failed when an hour passed without either"""
    if mine(r):
        return 'done'
    if r.get('src') == 'chat':
        return 'done' if answer_of(room, r) else 'failed' if time.time() - r.get('at', 0) > CHAT_STALE else 'pending'
    return 'failed' if r.get('failed') is not None else 'pending'


def answer_of(room, r):
    """the text of the lead's "SKILLDERIVE rN done..." line, or ''"""
    pat = re.compile(r'SKILL(?:DERIVE|SUGGEST|IMPROVE)\s+' + re.escape(r['req']) + r'\s+(?:done|fatto)', re.I)
    for m in room.messages():
        if m.get('from') == r.get('searcher') and float(m.get('ts') or 0) >= r.get('at', 0) and pat.search(m.get('text', '')):
            return ' '.join(m['text'].split())[:300]
    return ''


def watch(room, req, kind, proc, cwd, timeout=1200):
    """one chat line when the job is gone (or killed after the timeout); a job without a candidate is marked failed"""
    import subprocess
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    n = len(mine({'req': req['req'], 'dir': str(cwd)}))
    if n:
        room.append(JOB_NAME, say('skills.d6.done', label=LABEL[kind], req=req['req'], n=n))
        return
    code = proc.returncode if proc.returncode is not None else -1
    change(room, lambda s: [r.update(failed=code) for r in s['requests'] if r.get('req') == req['req']])
    room.append(JOB_NAME, say('skills.d6.failed', label=LABEL[kind], req=req['req'], code=code, log=f"skills-temp/{req['req']}.log"))


# ---------------------------------------------------------------- body, diff, promote, dismiss

def body_of(d):
    try:
        return (d / 'SKILL.md').read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return ''


def target_of(room, c, skill_list):
    """where a candidate goes: {'path': folder, 'origin', 'copy', 'id', 'exists': bool, 'old': the folder the new one starts from or None};
    improves=plugin/account -> a user copy (starting from the plugin's folder, scripts and references included)"""
    if c['improves']:
        s = find(skill_list, c['improves'])
        if not s or s['origin'] == 'builtin':
            return None
        if s['origin'] in ('plugin', 'account'):
            p = user_dir() / c['name']
            return {'id': s['id'], 'path': p, 'origin': s['origin'], 'copy': True, 'exists': p.is_dir(), 'old': p if p.is_dir() else Path(s['path']).parent}
        p = Path(s['path']).parent
        return {'id': s['id'], 'path': p, 'origin': s['origin'], 'copy': False, 'exists': True, 'old': p}
    p = user_dir() / c['name']
    return {'id': None, 'path': p, 'origin': 'user', 'copy': False, 'exists': p.is_dir(), 'old': None}


def current_text(t):
    return body_of(t['old']) if t and t['old'] else ''


def make_diff(old, new, name):
    d = list(difflib.unified_diff(old.splitlines(), new.splitlines(), f'{name} (now)', f'{name} (candidate)', lineterm=''))
    return '\n'.join(d[:600]), sum(1 for x in d if x.startswith('+') and not x.startswith('+++')), sum(1 for x in d if x.startswith('-') and not x.startswith('---'))


def backup_dir(path):
    base = path.parent.parent / (path.parent.name + '-backup') / path.name
    stamp = time.strftime('%Y%m%d-%H%M%S')
    n, out = 1, base / stamp
    while out.exists():      # two promotes in one second (a double click) get their own folder
        n += 1
        out = base / f'{stamp}-{n}'
    return out


def one(room, cid, skill_list):
    r = resolve(room, cid)
    if not r:
        return None
    k, p, d = r
    c = candidate(k, d, skill_list)
    return (c, d, p) if c else None


def act(room, action, body, skill_list, confirm):
    found = one(room, body.get('id') or body.get('candidate'), skill_list)
    if not found:
        return fail(say('skills.d6.err_no_candidate', id=str(body.get('id') or body.get('candidate') or '')))
    c, d, p = found
    t = target_of(room, c, skill_list)
    if action == 'candidate':
        return {'ok': True, 'candidate': {**c, 'body': body_of(d)[:BODY_MAX]}}
    if action == 'diff':
        diff, add, rem = make_diff(current_text(t), body_of(d), c['name'])
        return {'ok': True, 'diff': diff, 'added': add, 'removed': rem,
                'target': {'id': t['id'], 'path': str(t['path']).replace('\\', '/'), 'origin': t['origin'], 'copy': t['copy']} if c['improves'] and t else None}
    if action == 'dismiss':
        write_meta(d, status='dismissed')
        return {'ok': True}
    if t is None:
        return fail(say('skills.d6.err_no_target', skill=c['improves'] or ''))
    if t['exists'] and not c['improves']:
        return fail(say('skills.d6.err_exists', name=c['name']))
    to, bk = str(t['path']).replace('\\', '/'), (str(backup_dir(t['path'])).replace('\\', '/') if t['exists'] else None)
    raw = read_json_file(d / 'meta.json') or {}
    gate = skills_d8.gate_of(raw, t['id'] if c['improves'] else None)      # D8: what must still pass after an improvement
    glist = skills_d8.gate_list(gate, t['path'])
    if not confirm:
        pv = {'name': c['name'], 'from': str(d).replace('\\', '/'), 'to': to, 'backup': bk, 'replaces': t['exists'], 'verified': c['verified'],
              'unverified': c['verified']['state'] != 'verified'}
        if glist and t['exists']:
            pv['gate'], pv['token'], pv['runs'] = glist, skills_d8.token_of(glist), skills_d8.gate_runs(gate)
        if t['old']:
            pv['diff'] = make_diff(current_text(t), body_of(d), c['name'])[0]
        return {'ok': True, 'preview': pv}
    if c['verified']['state'] != 'verified' and not body.get('unverified_ok'):
        return {'ok': False, 'error': say('skills.d8.err_unverified', name=c['name']), 'needs': 'unverified_ok'}
    if glist and t['exists'] and str(body.get('token') or '') != skills_d8.token_of(glist):
        return {'ok': False, 'error': say('skills.d8.err_token'), 'needs': 'token', 'token': skills_d8.token_of(glist)}
    before = skills_d8.gate_baseline(gate, t['path']) if t['exists'] and glist else None
    tmp = t['path'].with_name(t['path'].name + '.new')
    try:
        if t['exists']:
            shutil.copytree(t['path'], bk)
        shutil.rmtree(tmp, ignore_errors=True)
        if t['old']:      # the old folder first (its scripts and references stay), then the candidate over it: SKILL.md and what it brings replace
            shutil.copytree(t['old'], tmp)
        shutil.copytree(d, tmp, ignore=shutil.ignore_patterns('meta.json'), dirs_exist_ok=True)
        if t['exists']:
            shutil.rmtree(t['path'])
        t['path'].parent.mkdir(parents=True, exist_ok=True)
        tmp.rename(t['path'])
    except OSError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return fail(say('skills.d6.err_write', exc=str(exc)[:200]))
    new_id = t['id'] if c['improves'] and not t['copy'] else f"user:-:{c['name']}"
    gated = skills_d8.gate_after(gate, before, t['path']) if before is not None else None
    if gated and gated['refused']:      # the check failed or a case got worse: the old folder is put back
        try:
            shutil.rmtree(t['path'])
            shutil.copytree(bk, t['path'])
        except OSError as exc:
            return fail(say('skills.d6.err_write', exc=str(exc)[:200]))
        return {'ok': False, 'error': gated['why'], 'reverted': True, **gated['view']}
    write_meta(d, status='added')
    skills_d8.carry(raw, new_id, t['path'] / 'SKILL.md', c['verified'], gated, gate)
    return {'ok': True, 'id': new_id, 'backup': bk, **(gated['view'] if gated else {})}


def write_meta(d, **kv):
    import chat
    m = read_json_file(d / 'meta.json')
    m = m if isinstance(m, dict) else {}
    m.update(kv)
    chat.write_atomic(d / 'meta.json', json.dumps(m, indent=1, ensure_ascii=False))


def do(room, action, body, skill_list, confirm):
    if action in KINDS:
        return start(room, action, body, skill_list, confirm)
    return act(room, action, body, skill_list, confirm)


ACTIONS = KINDS + ('candidate', 'diff', 'promote', 'dismiss')
