"""D8, point 4 of the skill workshop: does the description make the model pick the skill when it should, and not when it should not.
4a activation_check: free and local, reads only the description (no model, no tokens): the "use when" and "do NOT use" clauses, how close they are,
and the skills whose descriptions it can be confused with. 4b activation_test: one headless `claude -p` on a click, with its cost shown first:
it writes 3 requests that must activate the skill and 3 near misses, says which skill of the installed list it would pick for each (a simulation from
the descriptions, not the real trigger), and suggests a better description. Nothing is applied."""
import re
import shutil
import threading
import time
from pathlib import Path

import skills
import skills_d8
from i18n import say
from skills import fail, find, read_front, read_json_file

ACTIONS = ('activation_check', 'activation_test')
KIND = 'activation'
N_ITEMS = 6
BUDGET_USD = 1
STOP = {'the', 'and', 'for', 'not', 'use', 'any', 'can', 'are', 'you', 'our', 'its', 'has', 'was', 'but', 'how', 'all', 'one', 'out', 'who', 'per', 'via', 'get', 'set',
        'when', 'this', 'that', 'with', 'from', 'used', 'using', 'user', 'users', 'skill', 'skills', 'your', 'have', 'into', 'than', 'then', 'them',
        'they', 'will', 'what', 'also', 'only', 'such', 'each', 'does', 'make', 'need', 'like', 'more', 'most', 'claude', 'code', 'these', 'those', 'where', 'which',
        'while', 'about', 'other', 'their', 'there', 'should', 'would', 'could', 'before', 'after', 'always', 'never', 'quando', 'questa', 'questo', 'sono', 'della', 'delle'}
NEG = re.compile(r"(?i)\b(do not use|don'?t use|dont use|never use|not for|not when|not to be used|do not trigger|non usare|non usarla|non va usata|non usa|do not invoke|skip when)\b")
POS = re.compile(r'(?i)\b(use when|use for|use this|use it|use if|used when|when the user|when you|whenever|if the user|trigger|usa quando|usare quando|usare per|quando l|use to)\b')


def words(text):
    return {w for w in re.findall(r'[a-z]{3,}', str(text).lower())} - STOP


def clauses(desc):
    return [c.strip() for c in re.split(r'(?<=[.;!?])\s+|\n+', desc) if c.strip()]


def overlap(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def check_of(desc, name, own_id, skill_list):
    neg = [c for c in clauses(desc) if NEG.search(c)]
    pos = [c for c in clauses(desc) if POS.search(c) and not NEG.search(c)]
    close = round(max((overlap(words(n), words(p)) for n in neg for p in pos), default=0.0), 2)
    mine = words(name + ' ' + desc)
    conf = sorted(({'id': s['id'], 'name': s['name'], 'overlap': round(overlap(mine, words(s['name'] + ' ' + s['description'])), 2)} for s in skill_list if s['id'] != own_id and s['name'] != name),
                  key=lambda x: -x['overlap'])
    conf = [x for x in conf if x['overlap'] >= 0.3][:5]
    advice = (say('skills.d8.advice_nopos') if not pos else say('skills.d8.advice_none') if not neg else say('skills.d8.advice_far') if close < 0.1 and conf
              else say('skills.d8.advice_ok'))
    sug = None
    if not neg and desc:
        who = ', '.join(x['name'] for x in conf[:3]) or '<the nearest skill>'
        sug = f"{desc.rstrip().rstrip('.')}. Do NOT use when the request is really about {who}."
    return {'positives': len(pos), 'negatives': len(neg), 'has_exclusion': bool(neg), 'closeness': close, 'confused_with': conf, 'advice': advice, 'suggestion': sug}


def check(room, body, skill_list):
    t = skills_d8.target(room, body, skill_list)
    if isinstance(t, str):
        return fail(t)
    desc = str(read_front(t['file']).get('description', '') or '')
    return {'ok': True, 'check': check_of(desc, t['name'], t['id'], skill_list)}


# ---------------------------------------------------------------- 4b the test with a model (costs tokens: on a click, cost shown first)

def norm_name(v):
    return re.sub(r'^.*:', '', str(v or '').strip().lstrip('/')).lower()


def result_of(data, name):
    """{'right','wrong','total','tp','fn','fp','tn','items','suggestion'} from what the job wrote, scored here (the job says what it would pick, we say who was right)"""
    items = []
    for x in (data.get('items') if isinstance(data, dict) else None) or []:
        if isinstance(x, dict) and str(x.get('q') or '').strip() and isinstance(x.get('should'), bool):
            items.append({'q': str(x['q']).strip()[:300], 'should': x['should'], 'picked': str(x.get('picked') or 'none')[:80]})
    items = items[:N_ITEMS + 2]
    if not items:
        return None
    hit = [norm_name(i['picked']) == name.lower() for i in items]
    tp = sum(1 for i, h in zip(items, hit) if i['should'] and h)
    fn = sum(1 for i, h in zip(items, hit) if i['should'] and not h)
    fp = sum(1 for i, h in zip(items, hit) if not i['should'] and h)
    tn = sum(1 for i, h in zip(items, hit) if not i['should'] and not h)
    return {'right': tp + tn, 'wrong': fn + fp, 'total': len(items), 'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn, 'items': items,
            'suggestion': str(data.get('suggestion') or '').strip()[:600] or None}


def out_file(req):
    return f'skills-jobs/{req}.activation.json'


def plan(req, name):
    return {'kind': KIND, 'name': 'SKILLWORK', 'task': say('skills.d8.act_task', name=name, n=N_ITEMS), 'prompts': [], 'n': N_ITEMS,
            'reads': [say('skills.d8.act_reads', req=req)], 'writes': [out_file(req)], 'budget_usd': BUDGET_USD, 'note': say('skills.d8.act_note')}


def start(room, body, skill_list, confirm):
    t = skills_d8.target(room, body, skill_list)
    if isinstance(t, str):
        return fail(t)
    st = skills.state_of(room)
    if any(r.get('kind') == KIND and r.get('skill') == t['id'] and time.time() - r.get('at', 0) < 1200 and state_of(room, r) == 'pending' for r in st['requests']):
        return fail(say('skills.d6.err_running'))
    if not confirm:
        return {'ok': True, 'preview': plan(f"r{st['seq'] + 1}", t['name'])}
    import skills_d6
    req = skills_d6.new_job(room, KIND, t['name'], {'kind': 'room', 'label': 'activation', 'folder': Path(room.dir)}, {'id': t['id']})
    r = req['req']
    jobs = Path(room.dir) / 'skills-jobs'
    jobs.mkdir(exist_ok=True)
    have = '\n'.join(f"- {s['name']}: {' '.join(s['description'].split())[:300]}" for s in skill_list if s['id'] != t['id'])[:20000]
    try:
        (jobs / f'{r}.skills.md').write_text(f"- {t['name']}: {' '.join(str(read_front(t['file']).get('description', '')).split())[:500]}\n" + have + '\n', encoding='utf-8')
        shutil.copyfile(t['file'], jobs / f'{r}.skill.md')
    except OSError as exc:
        return fail(say('skills.core.err_launch', exc=str(exc)[:200]))
    cmd = [shutil.which('claude') or 'claude', '-p', '--model', 'sonnet', '--permission-mode', 'dontAsk', '--tools', 'Read,Write', '--allowedTools',
           f"Read(skills-jobs/{r}.skills.md) Read(skills-jobs/{r}.skill.md) Edit({out_file(r)})", '--strict-mcp-config', '--max-budget-usd', str(BUDGET_USD), '--no-session-persistence']
    work = Path(room.dir) / 'skills-temp'
    work.mkdir(exist_ok=True)
    try:
        proc = skills.launch(cmd, say('skills.d8.prompt_act', name=t['name'], req=r, n=N_ITEMS // 2, file=out_file(r)), Path(room.dir), work / f'{r}.log')
    except OSError as exc:
        return fail(say('skills.core.err_launch', exc=str(exc)[:200]))
    skills.post(room, say('skills.d8.act_line', req=r, name=t['name']))
    threading.Thread(target=watch, args=(room, req, t['id'], t['name'], proc), daemon=True).start()
    return {'ok': True, 'req': r, 'name': 'SKILLWORK'}


def watch(room, req, tid, name, proc, timeout=900):
    """when the job is gone: score what it wrote, keep it as the activation of the skill, say it in the chat"""
    import subprocess
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    res = result_of(read_json_file(Path(room.dir) / out_file(req['req'])), name)
    if not res:
        skills.change(room, lambda s: [r.update(failed=proc.returncode if proc.returncode is not None else -1) for r in s['requests'] if r.get('req') == req['req']])
        room.append('SKILLWORK', say('skills.d8.act_failed', req=req['req'], code=proc.returncode, log=f"skills-temp/{req['req']}.log"))
        return
    skills_d8.sidecar_set(tid, activation={k: res[k] for k in ('right', 'wrong', 'total', 'tp', 'fn', 'fp', 'tn', 'suggestion')} | {'at': int(time.time())})
    room.append('SKILLWORK', say('skills.d8.act_done', req=req['req'], name=name, right=res['right'], total=res['total']))


def state_of(room, r):
    if result_of(read_json_file(Path(room.dir) / out_file(r['req'])), '-') and not r.get('failed'):
        return 'done'
    return 'failed' if r.get('failed') is not None else 'pending'


def request_view(room, r):
    """a request of kind activation as the panel shows it, with the scored result when done"""
    st = state_of(room, r)
    res = result_of(read_json_file(Path(room.dir) / out_file(r['req'])), r.get('q', '')) if st == 'done' else None
    return {'req': r['req'], 'kind': KIND, 'q': r.get('q', ''), 'for': [], 'by': r.get('by'), 'at': int(r.get('at', 0)), 'state': st, 'log': f"skills-temp/{r['req']}.log",
            'file': None, 'cards': [], 'via': 'job', 'announced': None, 'note': '', 'skill': r.get('skill'), 'result': res}


def do(room, action, body, skill_list, confirm):
    if action == 'activation_check':
        return check(room, body, skill_list)
    return start(room, body, skill_list, confirm)
