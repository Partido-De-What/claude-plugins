"""1.0, KERN items (research kernel, hold, templates), one section per ID. Run: python -X utf8 smoke_10_kern.py
ONLY=K3 runs one section. A fake HOME: nothing is written in ~/.claude."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10k_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'            # a fresh config dir makes chat.py rebuild its uv environment (60 s) in every subprocess
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402
import research  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
ONLY = os.environ.get('ONLY')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:600]}]'), flush=True)
    fails += not cond


def section(key):
    if ONLY and key not in ONLY.split(','):
        return False
    print(f'-- {key}', flush=True)
    return True


def run(room, *args, stdin=None, env=None, timeout=180):
    r = subprocess.run([sys.executable, CHAT, *args, '--room', str(room)], input=(stdin or '').encode(), capture_output=True,
                       timeout=timeout, env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def git(*a, cwd):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True)


EVAL = 'import program\nprint("loss:", (program.X - 2) ** 2)\nprint("mem:", program.X * 10)\n'   # mem: a guard number, 10 per X


def research_room(name, participants='W', extra=(), evaluate=None, eval_src=EVAL):
    """a repo (program.py, eval.py) and a research room on it, phase 2 unless --draft is in extra"""
    repo = BASE / f'repo-{name}'
    repo.mkdir()
    git('init', '-q', '-b', 'main', cwd=repo); git('config', 'user.email', 't@t', cwd=repo); git('config', 'user.name', 't', cwd=repo)
    (repo / 'program.py').write_text('X = 5\n')
    (repo / 'eval.py').write_text(eval_src)
    git('add', '-A', cwd=repo); git('commit', '-qm', 'base', cwd=repo)
    room = BASE / f'room-{name}'
    subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', participants, '--lang', 'en'], capture_output=True)
    (room / 'research').mkdir(exist_ok=True)
    (room / 'research' / 'task.md').write_text('# task: minimise loss')
    args = ['research', 'init', '--repo', str(repo), '--program', 'program.py', '--evaluate', evaluate or f'"{sys.executable}" eval.py',
            '--metric', 'loss', '--direction', 'min', '--budget-min', '0.5', '--max-evals', '30', '--sealed', 'eval.py',
            '--tag', name, '--as', 'LEAD', *extra]
    c, o = run(room, *args)
    assert c == 0, o
    return room, repo, room / 'research' / 'work'


# ---------------------------------------------------------------------------------------------------------------- K3
if section('K3'):
    # the plugin's python is the one that runs the room: its prefix (a venv) or a uv-managed base must never be in the
    # PATH of a contract command, even when VIRTUAL_ENV is not set (a venv python started directly, `uv run --no-project`)
    fake_venv, fake_base = BASE / 'venv', BASE / 'uv' / 'python' / 'cpython-3.14-x'
    user_py = BASE / 'userpy'
    for d in (fake_venv / 'Scripts', fake_venv / 'bin', fake_base / 'Scripts', user_py):
        d.mkdir(parents=True, exist_ok=True)
    old = (sys.prefix, sys.exec_prefix, sys.base_prefix)
    try:
        sys.prefix = sys.exec_prefix = str(fake_venv)
        sys.base_prefix = str(fake_base)
        path = os.pathsep.join([str(fake_venv / 'Scripts'), str(fake_venv), str(fake_base), str(fake_base / 'Scripts'), str(user_py)])
        env = chat.user_env({'PATH': path})                            # no VIRTUAL_ENV
        out = env['PATH'].split(os.pathsep)
        ok('K3 user_env: venv prefix out of PATH without VIRTUAL_ENV', all(not p.startswith(str(fake_venv)) for p in out), out)
        ok('K3 user_env: uv-managed base python out of PATH', all(not p.startswith(str(fake_base)) for p in out), out)
        ok('K3 user_env: the user\'s own dirs stay', str(user_py) in out, out)
        sys.prefix = sys.exec_prefix = sys.base_prefix = str(user_py)  # not in a venv, base is the user's python: nothing to strip
        ok('K3 user_env: outside a venv PATH is left alone', chat.user_env({'PATH': path})['PATH'] == path)
    finally:
        sys.prefix, sys.exec_prefix, sys.base_prefix = old
    ok('K3 resolved_python names an interpreter', research.resolved_python().lower().endswith(('python', 'python.exe', 'python3', 'python3.exe'))
       or research.resolved_python().startswith('not found'), research.resolved_python())
    room, repo, work = research_room('k3', extra=['--draft'])
    c, o = run(room, 'research', 'evaluate', '--kind', 'smoke', '--desc', 'smoke', '--as', 'W')
    c, o = run(room, 'research', 'seal', '--as', 'LEAD')
    ok('K3 seal prints the python a contract command resolves', c == 0 and 'sealed' in o and 'python' in o.split('sealed', 1)[1].lower()
       and research.resolved_python() in o, o)


def state(room):
    return json.loads((room / 'research' / 'state.json').read_text(encoding='utf-8'))


def contract(room):
    return json.loads((room / 'research' / 'contract.json').read_text(encoding='utf-8'))


# ---------------------------------------------------------------------------------------------------------------- K8
if section('K8'):
    room, repo, work = research_room('k8', extra=['--guard', 'cold:min:5%', '--guard', 'mem:min:abs=40'])
    ok('K8 --guard repeated: both kept', [g['name'] for g in contract(room)['guards']] == ['cold', 'mem'], contract(room)['guards'])
    ok('K8 abs guard parsed', contract(room)['guards'][1]['tol'] == 'abs=40', contract(room)['guards'])
    # eval prints cold too: patch the sealed eval in the worktree is refused, so a new room with both lines
    room, repo, work = research_room('k8b', extra=['--guard', 'mem:min:abs=40'])
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    ok('K8 baseline X=5 (mem 50 > 40) is not judged by the abs guard', c == 0 and 'KEEP' in o, o)
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
    ok('K8 attempt within the abs limit (mem 30 <= 40) kept', c == 0 and 'KEEP' in o, o)
    (work / 'program.py').write_text('X = 4\n')                      # mem 40 is on the limit (fine), loss 4 is worse than 1
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 4', '--as', 'W')
    ok('K8 attempt on the abs limit is not a guard breach', 'DISCARD' in o and 'guard' not in o.lower(), o)
    c, o = run(room, 'research', 'amend', '--guard', 'mem:min:abs=20', '--reason', 'tighter absolute limit', '--as', 'LEAD')
    ok('K8 amend to an abs guard after the baseline needs no baseline value', c == 0 and 'mem' in o, o)
    ok('K8 amend line shows old and new', 'abs=40' in o and 'abs=20' in o, o)
    (work / 'program.py').write_text('X = 2.5\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 2.5 over the limit', '--as', 'W')
    ok('K8 attempt over the new abs limit is refused with the limit in the line', 'mem' in o and '20' in o and ('CRASH' in o or 'DISCARD' in o), o)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('K8 status prints the effective guard limit', 'mem <= 20' in o, o)

if section('K8S'):                                                    # seal: a guard the smoke never measured
    room, repo, work = research_room('k8s', extra=['--draft'])
    c, o = run(room, 'research', 'evaluate', '--kind', 'smoke', '--desc', 'smoke', '--as', 'W')
    c, o = run(room, 'research', 'amend', '--guard', 'nothing:min:5%', '--as', 'LEAD')
    c, o = run(room, 'research', 'seal', '--as', 'LEAD')
    ok('K8 seal refuses a guard the smoke run never printed', c != 0 and 'nothing' in o and state(room)['phase'] == 1, o)
    c, o = run(room, 'research', 'amend', '--guard', 'mem:min:5%', '--as', 'LEAD')
    c, o = run(room, 'research', 'evaluate', '--kind', 'smoke', '--desc', 'smoke 2', '--as', 'W')
    c, o = run(room, 'research', 'seal', '--as', 'LEAD')
    ok('K8 seal passes once the smoke printed every guard', c == 0 and state(room)['phase'] == 2, o)

# ---------------------------------------------------------------------------------------------------------------- H1
def holdq(room):
    p = room / 'research' / 'holdq.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.is_file() else []


def gpu_hold(room):
    p = room / 'research' / 'gpu.hold'
    return json.loads(p.read_text(encoding='utf-8')) if p.is_file() else None


if section('H1'):
    room, repo, work = research_room('h1', participants='W1,W2,W3')
    h = lambda who, *a: run(room, 'research', 'hold', '--minutes', '10', '--reason', f'{who} profile', *a, '--as', who)
    c, o = h('W1')
    ok('H1 W1 holds', c == 0 and gpu_hold(room)['by'] == 'W1', o)
    c, o = h('W2')
    ok('H1 W2 is queued, not refused', c == 0 and 'in the line' in o and [x['by'] for x in holdq(room)] == ['W2'], o)
    c, o = h('W2')
    ok('H1 asking twice keeps one place', c == 0 and [x['by'] for x in holdq(room)] == ['W2'], o)
    c, o = h('W3')
    ok('H1 third in line', 'position 2' in o, o)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('H1 status lists the hold and the line', 'W1' in o and 'W2' in o and 'W3' in o and 'line' in o.lower(), o)
    c, o = run(room, 'research', 'release', '--as', 'W3')
    ok('H1 a queued agent releases = leaves the line', c == 0 and [x['by'] for x in holdq(room)] == ['W2'] and gpu_hold(room)['by'] == 'W1', o)
    c, o = run(room, 'research', 'release', '--as', 'W1')
    ok('H1 release hands the GPU to the first in line', c == 0 and gpu_hold(room)['by'] == 'W2' and holdq(room) == [], o)
    c, o = run(room, 'read', '--all', '--as', 'LEAD')
    ok('H1 the board tags the new holder', '@W2' in o and 'yours' in o.lower(), o[-400:])
    # reservation: W2 reserves the next turn for W3, then releases
    c, o = h('W2', '--for', 'W3')
    ok('H1 hold --for a participant reserves the next turn', c == 0 and gpu_hold(room).get('reserve_next') == 'W3', o)
    c, o = run(room, 'research', 'release', '--as', 'W2')
    g = gpu_hold(room)
    ok('H1 release gives it reserved to W3', c == 0 and g and g['by'] == 'W3' and g.get('reserved'), g)
    c, o = h('W1')
    ok('H1 others queue behind a reservation', c == 0 and [x['by'] for x in holdq(room)] == ['W1'], o)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('H1 status says reserved for W3', 'reserved for W3' in o, o)
    run(room, 'research', 'release', '--as', 'W1')                      # leave the line: the room's runner (it watches the line) ends
    run(room, 'research', 'release', '--as', 'LEAD')
    ok('H1 line and hold cleaned up', holdq(room) == [] and gpu_hold(room) is None or not gpu_hold(room), gpu_hold(room))
    lock = room / 'research' / 'queue.lock'
    alive = lambda: lock.exists() and chat.pid_alive(int(lock.read_text().split()[0]))   # on Windows the lock names the launcher's pid
    for _ in range(60):                                                 # the runner polls every 15 s
        if not alive():
            break
        time.sleep(1)
    ok('H1 the runner ended with the line', not alive(), lock.read_text() if lock.exists() else '')

# ---------------------------------------------------------------------------------------------------------------- K6
EVAL6 = ('import sys, program\n'
         'if program.X == 3:\n    raise ValueError("coherence check: shapes differ")\n'
         'if program.X == 4:\n    print("setup ok")\n    print("ERROR: device busy")\n    sys.exit(1)\n'
         'print("loss:", (program.X - 2) ** 2)\nprint("mem:", program.X * 10)\nprint("cold:", program.X * 10)\n')
if section('K6'):
    room, repo, work = research_room('k6', extra=['--guard', 'mem:min:abs=20', '--guard', 'cold:min:abs=20'], eval_src=EVAL6)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    ok('K6 baseline kept', c == 0 and 'KEEP' in o, o)
    head = lambda o: next((l for l in o.splitlines() if 'CRASH' in l or 'DISCARD' in l or 'KEEP' in l), '')
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'raises', '--as', 'W')
    ok('K6 a Python exception: the board line has its message', 'CRASH' in head(o) and 'exit 1' in head(o) and 'coherence check: shapes differ' in head(o), head(o))
    (work / 'program.py').write_text('X = 4\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'exits', '--as', 'W')
    ok('K6 an error line printed before exit(1): the board line has it', 'CRASH' in head(o) and 'ERROR: device busy' in head(o), head(o))
    (work / 'program.py').write_text('X = 2.5\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'two guards over', '--as', 'W')
    ok('K6 every broken guard is named in the verdict', 'mem' in head(o) and 'cold' in head(o), head(o))
    ok('K6 the guard values of the run are kept', state(room)['attempts'][-1]['guards'] == {'mem': 25.0, 'cold': 25.0}, state(room)['attempts'][-1])

# ---------------------------------------------------------------------------------------------------------------- T1
if section('T1'):
    # a research prompt carries the brief's constraints and closing, as agent_prompt.md does
    room, repo, work = research_room('t1', participants='W,A')
    run(room, 'brief', 'constraints=MARK-CONSTRAINTS-7', 'closing=MARK-CLOSING-9')
    roles = ('worker', 'searcher', 'proposer', 'registrar', 'auditor')
    for role in roles:
        c, o = run(room, 'prompt', 'W', '--template', f'research_{role}.md')
        ok(f'T1 research_{role} carries the brief constraints', c == 0 and 'MARK-CONSTRAINTS-7' in o, o[:300])
        ok(f'T1 research_{role} carries the brief closing', c == 0 and 'MARK-CLOSING-9' in o, o[:300])
        ok(f'T1 research_{role} leaves no placeholder', '{{' not in o, o[o.find('{{'):][:80])
    tpl = Path(SCRIPTS).parent / 'templates'
    for role in roles:
        for sub in ('', 'it'):
            text = (tpl / sub / f'research_{role}.md').read_text(encoding='utf-8')
            ok(f'T1 template {sub or "en"}/research_{role} names both placeholders', '{{CONSTRAINTS}}' in text and '{{CLOSING}}' in text)

print(f'\n{"FAIL" if fails else "ok"}: {fails} failed', flush=True)
sys.exit(1 if fails else 0)
