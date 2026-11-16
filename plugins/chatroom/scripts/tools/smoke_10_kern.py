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
    research_room.last = o                            # the init's own output
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

# ---------------------------------------------------------------------------------------------------------------- K9
EVAL9 = 'import os, program\nprint("loss:", (program.X - 2) ** 2 + float(os.environ.get("PROBE_ADD", "0")))\n'
if section('K9'):
    room, repo, work = research_room('k9', eval_src=EVAL9)
    c, o = run(room, 'research', 'evaluate', '--kind', 'probe', '--env', 'PROBE_ADD=7', '--desc', 'too early', '--as', 'W')
    ok('K9 a probe before the baseline still runs in phase 2 (not an attempt)', c == 0 and 'PROBE' in o, o)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    ok('K9 baseline is attempt 1 whatever the probe did', c == 0 and 'KEEP' in o and 'att-1 ' in o and state(room)['evals'] == 1, o)
    c, o = run(room, 'research', 'evaluate', '--kind', 'probe', '--env', 'PROBE_ADD=7,PROBE_B=x', '--desc', 'with env', '--as', 'W')
    ok('K9 probe: measured with the env (9 + 7 = 16), env in the line', c == 0 and 'PROBE' in o and '16' in o and 'PROBE_ADD=7' in o, o)
    s = state(room)
    a = s['attempts'][-1]
    ok('K9 probe: not counted, not best, kind and env registered', s['evals'] == 1 and a['kind'] == 'probe' and a['status'] == 'probe'
       and a.get('env_set') == {'PROBE_ADD': '7', 'PROBE_B': 'x'} and s['best']['n'] == 1 and a['n'] > 100000, a)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('K9 status still shows 1/30 runs and no round opened by a probe', '1/30' in o and 'opens round 1' in o, o[-700:])
    c, o = run(room, 'research', 'evaluate', '--kind', 'attempt', '--env', 'PROBE_ADD=7', '--desc', 'x', '--as', 'W')
    ok('K9 --env on an attempt is refused', c != 0 and 'probe' in o, o)
    c, o = run(room, 'research', 'evaluate', '--kind', 'probe', '--env', 'CHATROOM_RUN=1', '--desc', 'x', '--as', 'W')
    ok('K9 a CHATROOM_ variable cannot be set', c != 0 and 'CHATROOM_RUN' in o, o)
    c, o = run(room, 'research', 'queue', '--desc', 'q', '--env', 'PROBE_ADD=1', '--as', 'W')
    ok('K9 queue refuses --env on an attempt too', c != 0 and 'probe' in o, o)
    # the MCP tool: same call, env passed as a string
    room_obj = chat.Room(str(room))
    text, err = chat.mcp_call(room_obj, 'W', 'research', {'action': 'evaluate', 'kind': 'probe', 'env': 'PROBE_ADD=2', 'desc': 'via mcp'})
    ok('K9 MCP research evaluate takes env (9 + 2 = 11)', not err and 'PROBE' in text and '11' in text, text)
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
    ok('K9 the next attempt is number 2', c == 0 and 'KEEP' in o and state(room)['evals'] == 2, o)
    room2, _, _ = research_room('k9d', extra=['--draft'], eval_src=EVAL9)
    c, o = run(room2, 'research', 'evaluate', '--kind', 'probe', '--desc', 'in drafting', '--as', 'W')
    ok('K9 a probe in phase 1 is refused', c != 0 and 'phase 2' in o, o)

if section('K9Q'):                                                  # the queue runner takes a probe with its env (a detached runner: slower)
    room, repo, work = research_room('k9q', eval_src=EVAL9)
    run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    c, o = run(room, 'research', 'queue', '--kind', 'probe', '--env', 'PROBE_ADD=1', '--desc', 'queued probe', '--as', 'W')
    ok('K9 queue --kind probe --env is accepted', c == 0 and 'queued' in o, o)
    for _ in range(90):                                                  # the detached runner starts it at once
        if any(a['kind'] == 'probe' and 'queued probe' in a['desc'] for a in state(room)['attempts']):
            break
        time.sleep(1)
    q = [a for a in state(room)['attempts'] if 'queued probe' in a['desc']]
    ok('K9 the queue runner ran the probe with its env (loss 9 + 1 = 10)', q and q[0]['env_set'] == {'PROBE_ADD': '1'} and q[0]['metric'] == 10.0
       and state(room)['evals'] == 1, q)

# ---------------------------------------------------------------------------------------------------------------- K7
if section('K7'):
    block = lambda o: o.split('next constraints', 1)[1].split('\n| ', 1)[0].split('\nn\tcommit', 1)[0] if 'next constraints' in o else ''
    room, repo, work = research_room('k7a', extra=['--draft', '--guard', 'mem:min:abs=40'])
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    b = block(o)
    ok('K7 phase 1 status names the seal order', 'smoke' in b and 'seal' in b and 'auditor' in b and 'mem' in b, o[-900:])
    ok('K7 phase 1 status says the contract can still change', 'no baseline yet' in b, b)
    room, repo, work = research_room('k7')
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    b = block(o)
    ok('K7 phase 2 status counts the runs and says which kinds count', '1/30' in b and 'only attempts and fixes' in b, b)
    ok('K7 phase 2 before the first attempt: the round opens by itself', 'opens round 1' in b, b)
    ok('K7 phase 2 after the baseline the amend rule is the strict one', 'frozen' in b and '--reason' in b, b)
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    b = block(o)
    ok('K7 phase 2 shows the round and its attempts', 'round 1: 1/' in b and '2/30' in b, b)
    # the evidence and family lines need roles and assigns: the function itself, on a state
    c1 = {'max_evals': 30, 'roles': {'WORKER': ['W1']}, 'guards': []}
    st1 = {'phase': 2, 'evals': 7, 'rounds': [], 'workers': {'W1': {'since_evidence': 4}, '_main': {}}, 'best': {'n': 1},
           'assigns': [{'family': 'f1'}, {'family': 'f1'}, {'family': 'f1'}]}
    t = research._next_constraints(c1, st1)
    ok('K7 evidence line shows each worker against the limit', 'W1 4/5' in t, t)
    ok('K7 family line shows the recent families', 'f1, f1, f1' in t and '--force' in t, t)
    ok('K7 phase 3 names the kinds', 'ablation' in research._next_constraints(c1, dict(st1, phase=3)))

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

# ---------------------------------------------------------------------------------------------------------------- H2
if section('H2'):
    room, repo, work = research_room('h2', participants='W1,W2')
    ids = {'W1': 'aaaaaaaa11', 'W2': 'bbbbbbbb22'}
    (room / 'roster.json').write_text(json.dumps(ids), encoding='utf-8')
    sub = BASE / 'claude' / 'projects' / 'p' / 's' / 'subagents'
    sub.mkdir(parents=True)

    def transcript(name, ended):                                     # the last line of an agent's own transcript: a finished turn, or a tool call
        last = {'message': {'role': 'assistant', 'stop_reason': 'end_turn' if ended else 'tool_use', 'content': []}}
        (sub / f'agent-{ids[name]}.jsonl').write_text(json.dumps(last) + '\n', encoding='utf-8')
    transcript('W1', False); transcript('W2', False)
    run(room, 'research', 'hold', '--minutes', '90', '--reason', 'W1 profile', '--as', 'W1')
    run(room, 'research', 'hold', '--minutes', '10', '--reason', 'W2 profile', '--as', 'W2')
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('H2 a holder at work keeps the GPU', gpu_hold(room)['by'] == 'W1' and [x['by'] for x in holdq(room)] == ['W2'], gpu_hold(room))
    transcript('W1', True)
    mark = room / 'waiting_W1.txt'
    mark.write_text(f'{time.time() + 300:.0f} {os.getpid()}')         # held by the stop hook, like a wait: it did not fall
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('H2 a holder kept by a wait keeps the GPU', gpu_hold(room)['by'] == 'W1', gpu_hold(room))
    mark.unlink()
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('H2 a holder whose run ended is released and the line moves on', gpu_hold(room) and gpu_hold(room)['by'] == 'W2' and holdq(room) == [], (gpu_hold(room), o[-300:]))
    c, o = run(room, 'read', '--all', '--as', 'LEAD')
    ok('H2 the board tells the lead and the holder', 'fell holding the GPU' in o and '@W1' in o and 'LEAD, for you' in o, o[-700:])
    log = (room / 'research' / 'log.jsonl').read_text(encoding='utf-8')
    ok('H2 the kernel log has a hold-fell event naming W1', 'hold-fell' in log and '"holder": "W1"' in log, log[-300:])
    transcript('W2', True)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('H2 the last holder that fell leaves the GPU free', gpu_hold(room) is None, gpu_hold(room))
    lock = room / 'research' / 'queue.lock'
    alive = lambda: lock.exists() and chat.pid_alive(int(lock.read_text().split()[0]))
    for _ in range(60):                                                 # the runner of the line polls every 15 s
        if not alive():
            break
        time.sleep(1)
    ok('H2 the runner ended with the line', not alive(), lock.read_text() if lock.exists() else '')

# ---------------------------------------------------------------------------------------------------------------- K16
if section('K16'):
    # the evaluator writes out/clip.txt (like the wavs of a voice run): each run's copy must stay, the next run overwrites it
    EVAL16 = ('import os, program\nos.makedirs("out", exist_ok=True)\nopen("out/clip.txt", "w").write(str(program.X))\n'
              'print("loss:", (program.X - 2) ** 2)\n')
    ok_py, bad_py = BASE / 'dry_ok.py', BASE / 'dry_bad.py'
    ok_py.write_text('print("dry ok")\n')
    bad_py.write_text('import sys\nprint("held-out data missing")\nsys.exit(3)\n')
    try:
        room, repo, work = research_room('k16', eval_src=EVAL16, extra=['--artifacts', 'out', '--final', f'"{sys.executable}" eval.py'])
    except AssertionError as e:
        ok('K16 init takes --artifacts', False, e)
        room = None
    if room:
        ok('K16 the contract keeps the artifact paths', contract(room).get('artifacts') == ['out'], contract(room))
        run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
        (work / 'program.py').write_text('X = 3\n')
        run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
        f1, f2 = room / 'research' / 'runs' / '1' / 'artifacts' / 'out' / 'clip.txt', room / 'research' / 'runs' / '2' / 'artifacts' / 'out' / 'clip.txt'
        ok('K16 each run keeps its own artifacts (5 then 3)', f1.is_file() and f2.is_file() and f1.read_text() == '5' and f2.read_text() == '3',
           [p for p in (room / 'research' / 'runs').rglob('*') if 'artifacts' in str(p)][:6])
        c, o = run(room, 'research', 'amend', '--artifacts', '../etc', '--as', 'LEAD')
        ok('K16 an artifact path outside the worktree is refused', c != 0 and 'artifacts' in o, o)
        c, o = run(room, 'research', 'final', '--dry', '--as', 'LEAD')
        ok('K16 final --dry without a dry command says how to set one', c != 0 and 'final-dry' in o, o)
        c, o = run(room, 'research', 'status', '--as', 'LEAD')
        ok('K16 status says the final has no dry run', 'no dry run' in o, o[-700:])
        run(room, 'research', 'amend', '--final-dry', f'"{sys.executable}" "{bad_py}"', '--as', 'LEAD')
        c, o = run(room, 'research', 'final', '--dry', '--as', 'LEAD')
        ok('K16 a failing dry run is refused with its exit and the log tail', c != 0 and 'exit 3' in o and 'held-out data missing' in o, o)
        run(room, 'research', 'amend', '--final-dry', f'"{sys.executable}" "{ok_py}"', '--as', 'LEAD')
        c, o = run(room, 'research', 'final', '--dry', '--as', 'LEAD')
        ok('K16 a passing dry run is reported in phase 2, and the final did not run', c == 0 and 'passed' in o and not state(room).get('final'), o)
    # the pruning, on made-up runs: the newest ARTIFACT_RUNS and every keep stay
    d, w = BASE / 'k16-prune', BASE / 'k16-prune-work'
    (d / 'runs').mkdir(parents=True)
    (w / 'out').mkdir(parents=True)
    (w / 'out' / 'a.txt').write_text('x')
    (d / 'results.tsv').write_text(research.TSV_HEAD + '\n'.join(f'{n}\tc\t1\t{"keep" if n == 1 else "discard"}\t1\t\tW\td\tattempt\t\t' for n in range(1, 5)) + '\n')
    for n in range(1, 5):
        (d / 'runs' / str(n) / 'artifacts').mkdir(parents=True)
        os.utime(d / 'runs' / str(n) / 'artifacts', (1000 + n, 1000 + n))
    old, research.ARTIFACT_RUNS = research.ARTIFACT_RUNS, 2
    try:
        research._keep_artifacts({'artifacts': ['out']}, w, d, 5, 0)
    finally:
        research.ARTIFACT_RUNS = old
    left = sorted(p.parent.name for p in (d / 'runs').glob('*/artifacts'))
    ok('K16 pruning keeps the keep and the newest runs', left == ['1', '4', '5'], left)

# ---------------------------------------------------------------------------------------------------------------- K4
if section('K4'):                                                     # a run that dies with the machine is invalid: not a run of the 40
    flag = BASE / 'k4-machine-down'
    pre = BASE / 'k4_precheck.py'
    pre.write_text(f'import os, sys\nsys.exit(1 if os.path.exists(r"{flag}") else 0)\n')
    ev = (f'import program, os, sys\nif program.X == 3 and not os.path.exists(r"{flag}.once"):\n    open(r"{flag}", "w").write("x")\n    open(r"{flag}.once", "w").write("x")\n    sys.exit(1)\n'    # X 3: the machine goes down, once
          'if program.X == 9:\n    sys.exit(1)\nprint("loss:", (program.X - 2) ** 2)\n')                         # X 9: the program itself dies
    room, repo, work = research_room('k4', extra=['--precheck', f'"{sys.executable}" "{pre}"'], eval_src=ev)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    ok('K4 baseline runs', c == 0 and 'KEEP' in o, o)
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'machine dies', '--as', 'W')
    st = state(room)
    ok('K4 a run that dies while the precheck now fails is INVALID, not a crash', 'INVALID' in o and 'CRASH' not in o, o)
    ok('K4 the budget does not move', st['evals'] == 1 and not st['pending'], (st['evals'], st['pending']))
    ok('K4 recorded as an invalid aux-numbered run', [a['status'] for a in st['attempts']] == ['keep', 'invalid']
       and st['attempts'][-1]['n'] > 100000 and st['aux'] == 1, st['attempts'])
    wk = list(st['workers'].values())[0]
    ok('K4 the worker is not counted as crashing', wk.get('crashes', 0) == 0 and len(wk['programs']) == 1, wk)
    tsv = (room / 'research' / 'results.tsv').read_text(encoding='utf-8').splitlines()
    ok('K4 results.tsv has the invalid row', tsv[-1].split('\t')[3] == 'invalid', tsv[-1])
    ok('K4 the log says run-invalid', '"run-invalid"' in (room / 'research' / 'log.jsonl').read_text(encoding='utf-8'))
    ok('K4 the tag att-2 is free and the code stays staged', not git('tag', '--list', '*/att-2', cwd=work).stdout.strip()
       and (work / 'program.py').read_text().strip() == 'X = 3' and git('log', '--oneline', cwd=work).stdout.count('att-') == 1,
       git('tag', '--list', cwd=work).stdout)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('K4 status counts it apart', 'invalid 1' in o and '1/30 runs' in o, o)
    flag.unlink()
    c, o = run(room, 'research', 'evaluate', '--desc', 'machine dies', '--as', 'W')       # the same code, the machine is back
    ok('K4 the same code runs again as att-2', c == 0 and 'att-2' in o and 'KEEP' in o and state(room)['evals'] == 2, o)
    (work / 'program.py').write_text('X = 9\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'program dies', '--as', 'W')
    ok('K4 a crash with the machine fine is still a crash and counts', 'CRASH' in o and state(room)['evals'] == 3
       and list(state(room)['workers'].values())[0]['crashes'] == 1, o)

# ---------------------------------------------------------------------------------------------------------------- K5
if section('K5'):                                                     # a queued run the machine cannot take waits and tries again
    import threading
    flag = BASE / 'k5-machine-down'
    pre = BASE / 'k5_precheck.py'
    pre.write_text(f'import os, sys\nsys.exit(1 if os.path.exists(r"{flag}") else 0)\n')
    ev = (f'import program, os, sys\nif program.X == 3 and not os.path.exists(r"{flag}.once"):\n    open(r"{flag}", "w").write("x")\n'
          f'    open(r"{flag}.once", "w").write("x")\n    sys.exit(1)\nprint("loss:", (program.X - 2) ** 2)\n')     # X 3 kills the machine once
    room, repo, work = research_room('k5', extra=['--precheck', f'"{sys.executable}" "{pre}"'], eval_src=ev)
    run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    (work / 'program.py').write_text('X = 3\n')
    flag.write_text('down')                                           # the machine is not ready when the run's turn comes
    room_obj = chat.Room(str(room))
    old_retry = getattr(research, 'QUEUE_RETRY_S', 300)
    research.QUEUE_RETRY_S = 1
    research._queue_edit(room_obj, lambda q: q.append({'by': 'W', 'desc': 'queued X 3', 'idea': None, 'kind': 'attempt', 'after': None,
                                                       'of': None, 'seed': None, 'env': {}, 'ts': time.time()}))
    th = threading.Thread(target=research.run_queue, args=(room_obj, 0.2), daemon=True)
    th.start()

    def until(cond, secs=12):
        for _ in range(int(secs * 5)):
            if cond():
                return True
            time.sleep(0.2)
        return False
    queued = lambda: research._queue(room_obj)
    ok('K5 a run the precheck refuses stays in the queue with its tries', until(lambda: queued() and queued()[0].get('tries', 0) >= 2)
       and queued()[0]['desc'] == 'queued X 3' and state(room)['evals'] == 1, queued())
    text = ' '.join(p.read_text(encoding='utf-8', errors='ignore') for p in room.glob('*') if p.is_file())
    ok('K5 its author is told once on the board', text.count('stays in the queue') == 1 and '"queue-retry"' in (room / 'research' / 'log.jsonl').read_text(encoding='utf-8'), text.count('stays in the queue'))
    flag.unlink(missing_ok=True)                                                     # the machine is back: the run starts, and the machine dies under it
    ok('K5 a run that ends invalid is queued again', until(lambda: any(a['status'] == 'invalid' for a in state(room)['attempts']))
       and until(lambda: queued() and queued()[0].get('tries', 0) >= 1 and flag.exists()), (state(room)['attempts'][-1:], queued()))
    flag.unlink(missing_ok=True)                                                     # fixed again: the same code runs and counts
    ok('K5 the retry runs the same code as att-2', until(lambda: state(room)['evals'] == 2) and not queued()
       and state(room)['attempts'][-1]['status'] == 'keep', (state(room)['evals'], queued()))
    th.join(15)
    ok('K5 the runner ends with the queue', not th.is_alive())
    research.QUEUE_RETRY_S = old_retry

# ---------------------------------------------------------------------------------------------------------------- K17
if section('K17'):                                                    # a wake for "N runs closed" or "the list is finished", and the auditor told
    import threading
    room, repo, work = research_room('k17', participants='W,A')
    c, o = run(room, 'research', 'roles', 'WORKER=W', 'AUDITOR=A', '--as', 'LEAD')
    c, o = run(room, 'research', 'wait', '--as', 'LEAD')
    ok('K17 wait with nothing queued and no count says so at once', c == 0 and 'nothing to wait for' in o, o)
    c, o = run(room, 'research', 'wait', '--runs', '1', '--minutes', '0.03', '--as', 'LEAD')
    ok('K17 wait --runs gives up at --minutes and says how many closed', c == 0 and 'min passed with 0 new runs' in o, o)
    room_obj = chat.Room(str(room))
    got = {}
    th = threading.Thread(target=lambda: got.update(t=research.wait_runs(room_obj, runs=2, minutes=1, poll=0.2)), daemon=True)
    th.start()
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    ok('K17 one run closed does not wake a wait for two', th.is_alive() or 'att-1' not in got.get('t', ''), got)
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
    th.join(15)
    ok('K17 two closed runs wake it with their lines', not th.is_alive() and 'att-1' in got['t'] and 'att-2' in got['t'] and 'are closed' in got['t'], got)
    text = ' '.join(p.read_text(encoding='utf-8', errors='ignore') for p in room.glob('*') if p.is_file())
    ok('K17 a keep tags the auditor on the run line (not the baseline)', text.count('a new best to check') == 1 and '@A' in text, text.count('a new best to check'))
    # the queued list: wait without a count returns when the runner has emptied the queue
    (work / 'program.py').write_text('X = 4\n')
    research._queue_edit(room_obj, lambda q: q.append({'by': 'W', 'desc': 'queued X 4', 'idea': None, 'kind': 'attempt', 'after': None,
                                                       'of': None, 'seed': None, 'env': {}, 'ts': time.time()}))
    got.clear()
    tw = threading.Thread(target=lambda: got.update(t=research.wait_runs(room_obj, minutes=1, poll=0.2)), daemon=True)
    tw.start()
    tr = threading.Thread(target=research.run_queue, args=(room_obj, 0.2), daemon=True)
    tr.start()
    tw.join(40)
    ok('K17 wait returns when the queued list is finished, with the run', not tw.is_alive() and 'list is finished' in got.get('t', '')
       and 'att-3' in got['t'], got)
    tr.join(15)
    text = ' '.join(p.read_text(encoding='utf-8', errors='ignore') for p in room.glob('*') if p.is_file())
    ok('K17 the runner says once the list is finished and tags the auditor and the author', text.count('the queued list is finished:') == 1
       and '@A @W' in text and 'list is finished: 1 runs closed' in text, text[-600:])

# ---------------------------------------------------------------------------------------------------------------- K11
if section('K11'):                                                    # soft budget, --round confirmed, replica said, noise advice only when the noise is unknown
    SLOW = 'import program, time\ntime.sleep(1.4)\nprint("loss:", 100 - program.X)\n'
    room, repo, work = research_room('k11', extra=['--budget-min', '0.02', '--round', '7'], eval_src=SLOW)
    init = research_room.last
    ok('K11 init says what the budget is and when it kills', 'Budget: 1 s' in init and 'over 2 s' in init and 'does not count in the runs' in init, init)
    ok('K11 init confirms --round', '7 runs (--round)' in init, init)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    ok('K11 a measure over the budget (not yet the kill) is said on the run line', c == 0 and 'KEEP' in o and 'over the 1 s budget' in o and 'killed at 2 s' in o, o)
    ok('K12 without a reference or repeats the baseline still says the noise is unknown', 'noise is unknown' in o, o)
    (work / 'program.py').write_text('X = 6\n')                        # 94 against 95: a gain of about 1%, under the 10% that gets a second measure
    c, o = run(room, 'research', 'evaluate', '--desc', 'small gain', '--as', 'W')
    text = ' '.join(p.read_text(encoding='utf-8', errors='ignore') for p in room.glob('*') if p.is_file())
    ok('K13 the automatic replica is announced on the board before it runs', c == 0 and 'measuring att-2 once more' in text, text[-400:])
    room, repo, work = research_room('k12', extra=['--draft'])
    c, o = run(room, 'research', 'evaluate', '--kind', 'smoke', '--desc', 'smoke', '--as', 'W')
    ok('K12 a smoke says the noise is unknown while the contract has no reference', 'noise is unknown' in o, o)
    c, o = run(room, 'research', 'amend', '--info', 'mem', '--reference', 'mem', '--reason', 'reference arm', '--as', 'LEAD')
    c, o = run(room, 'research', 'evaluate', '--kind', 'smoke', '--desc', 'smoke 2', '--as', 'W')
    ok('K12 with a reference arm in the contract the advice is silent', c == 0 and 'noise is unknown' not in o, o)

# ---------------------------------------------------------------------------------------------------------------- K10
if section('K10'):                                                    # class and level in the attempt; a register of shelved ideas with its sums
    room, repo, work = research_room('k10')
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--class', 'explore', '--level', '2', '--as', 'W')
    st = state(room)
    ok('K10 an attempt keeps its class and level as fields', c == 0 and st['attempts'][0].get('cls') == 'explore' and st['attempts'][0].get('level') == '2', (c, o))
    ok('K10 the run line says them', 'class explore, level 2' in o, o)
    (work / 'program.py').write_text('X = 4\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'bad class', '--class', 'not a word!', '--as', 'W')
    ok('K10 a class that is not a short word is refused before the run', c != 0 and 'short word' in o and state(room)['evals'] == 1, o)
    c, o = run(room, 'research', 'queue', '--desc', 'queued one', '--class', 'tuning', '--level', '1', '--as', 'W')
    ok('K10 queue takes them too', c == 0 and '"cls": "tuning"' in (room / 'research' / 'log.jsonl').read_text(encoding='utf-8'), o)
    t0 = time.time()
    while time.time() - t0 < 40 and state(room)['evals'] < 2:
        time.sleep(1)
    last = state(room)['attempts'][-1]
    ok('K10 the queued run carries them into its record', last.get('cls') == 'tuning' and last.get('level') == '1', last)
    c, o = run(room, 'research', 'shelve', '--text', 'wider search', '--class', 'explore', '--level', '1', '--value', '0.5', '--as', 'W')
    ok('K10 shelve registers an idea', c == 0 and 'S1' in o, o)
    c, o = run(room, 'research', 'shelve', '--text', 'bigger batch', '--class', 'explore', '--value', '1.5', '--as', 'W')
    c, o = run(room, 'research', 'shelve', '--text', 'other thing', '--class', 'misc', '--as', 'W')
    c, o = run(room, 'research', 'shelved', '--as', 'LEAD')
    ok('K10 shelved lists them with the sum per class', c == 0 and 'S1 [explore L1]' in o and 'S3' in o and 'explore 2 (sum 2)' in o and 'misc 1 (sum 0)' in o and '3 shelved' in o, o)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('K10 status counts them per class', 'shelved: 3 (explore 2, misc 1)' in o, o)
    c, o = run(room, 'research', 'unshelve', 'S2', '--as', 'W')
    c2, o2 = run(room, 'research', 'unshelve', 'S2', '--as', 'W')
    c3, o3 = run(room, 'research', 'shelved', '--as', 'LEAD')
    ok('K10 unshelve takes one off, an unknown id is refused', c == 0 and c2 != 0 and 'S2' not in o3 and '2 shelved' in o3, (o, o2, o3))
    c, o = run(room, 'research', 'shelve', '--text', 'x', '--value', 'many', '--as', 'W')
    ok('K10 a value that is not a number is refused', c != 0 and 'not a number' in o, o)

# ---------------------------------------------------------------------------------------------------------------- K18
if section('K18'):                                                    # the evaluator tried outside the kernel: nothing recorded
    cand = BASE / 'k18_cand.py'
    cand.write_text('print("loss: 4")\nprint("protocol: dry")\n')
    bad = BASE / 'k18_bad.py'
    bad.write_text('import sys\nprint("boom")\nsys.exit(3)\n')
    room, repo, work = research_room('k18')
    c, o = run(room, 'research', 'dry-eval', '--as', 'W')
    ok('K18 dry-eval runs the contract evaluator and prints the metric', c == 0 and 'loss = 9' in o and 'Nothing recorded' in o, o)
    ok('K18 it guards: the guard-less contract prints no guard', 'mem' not in o, o)
    c, o = run(room, 'research', 'dry-eval', '--evaluate', f'"{sys.executable}" "{cand}"', '--as', 'W')
    ok('K18 a candidate command can be tried instead', c == 0 and 'loss = 4' in o and 'protocol dry' in o, o)
    c, o = run(room, 'research', 'dry-eval', '--evaluate', f'"{sys.executable}" "{bad}"', '--as', 'W')
    ok('K18 a failing evaluator says why, still records nothing', 'dry-eval failed' in o and 'exit' in o, o)
    st = state(room)
    tsv = (room / 'research' / 'results.tsv').read_text(encoding='utf-8').splitlines()
    ok('K18 no run, no number, no pending, no row', st['evals'] == 0 and not st['attempts'] and not st['pending'] and st['aux'] == 0 and len(tsv) == 1, (st, tsv))
    ok('K18 no commit and no tag in the worktree, no lock left', git('log', '--oneline', cwd=work).stdout.count('att-') == 0
       and not git('tag', '--list', cwd=work).stdout.strip() and not (room / 'research' / 'eval.lock').exists(), git('log', '--oneline', cwd=work).stdout)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    ok('K18 the real baseline is still att-1', c == 0 and 'att-1' in o and 'KEEP' in o, o)

# ---------------------------------------------------------------------------------------------------------------- H3
if section('H3'):                                                     # the "still running" warning: whose it is, how old, no shell tools
    room, repo, work = research_room('h3')
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    keep = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    tool = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    try:
        (room / 'research' / 'runs' / 'pids-1.txt').write_text(f'{keep.pid} python\n{tool.pid} sleep\n', encoding='utf-8')
        time.sleep(1.2)
        c, o = run(room, 'research', 'status', '--as', 'LEAD')
        ok('H3 a process the evaluator left is named with its run author and age', f'python {keep.pid} (of W, ' in o and 'min old)' in o, o)
        ok('H3 a shell tool (sleep) is not a stray', f'sleep {tool.pid}' not in o, o)
        ok('H3 exactly one process is listed (the tool is out)', o.count(' min old)') == 1, o)
    finally:
        keep.kill(); tool.kill(); keep.wait(); tool.wait()

# ---------------------------------------------------------------------------------------------------------------- H4
if section('H4'):                                                     # the hold texts name the contract's resource, a long reason says it was cut
    long_reason = 'profile the kernel ' + 'x' * 160
    room, repo, work = research_room('h4', extra=['--resource', 'camera rig'])
    c, o = run(room, 'research', 'hold', '--minutes', '5', '--reason', long_reason, '--as', 'W')
    ok('H4 the hold text names the resource, not the GPU', c == 0 and 'camera rig held by W' in o and 'GPU' not in o, o)
    c, o = run(room, 'research', 'release', '--as', 'W')
    full = research.hold(chat.Room(str(room)), 'W', 5, long_reason)           # the returned text itself (the CLI shortens a long line again)
    ok('H4 a long reason is cut with an ellipsis', 'xxx…' in full and long_reason not in full, full)
    c, o = run(room, 'research', 'status', '--as', 'LEAD')
    ok('H4 status names it too', 'camera rig held by W' in o and 'GPU' not in o, o)
    c, o = run(room, 'research', 'release', '--as', 'W')
    ok('H4 release names it', 'camera rig released' in o and 'GPU' not in o, o)
    c, o = run(room, 'research', 'hold', '--minutes', '5', '--reason', 'short', '--as', 'LEAD')
    c, o = run(room, 'research', 'hold', '--minutes', '5', '--reason', 'second', '--as', 'W')
    ok('H4 the line for it', 'in the line for the camera rig' in o, o)
    run(room, 'research', 'release', '--as', 'LEAD')                    # the line is emptied: its runner has nothing to keep and ends
    run(room, 'research', 'release', '--as', 'W')
    room2, repo2, work2 = research_room('h4b')
    c, o = run(room2, 'research', 'hold', '--minutes', '5', '--reason', 'plain', '--as', 'W')
    ok('H4 without --resource the word stays GPU', 'GPU held by W' in o, o)
    try:
        research_room('h4c', extra=['--resource', 'bad/name!'])
        refused = ''
    except AssertionError as e:
        refused = str(e)
    ok('H4 a bad resource name is refused', '--resource' in refused, refused)

# ---------------------------------------------------------------------------------------------------------------- K2b
if section('K2B'):                                                    # --info and --reference at init, and an info column in results.tsv
    room, repo, work = research_room('k2b', extra=['--info', 'mem', '--reference', 'mem'])
    ok('K2b init says the info numbers and the reference arm', 'Info numbers mem' in research_room.last and 'reference arm mem' in research_room.last, research_room.last)
    ok('K2b the contract has them', contract(room).get('info') == ['mem'] and contract(room).get('reference') == 'mem', contract(room))
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    rows = (room / 'research' / 'results.tsv').read_text(encoding='utf-8').splitlines()
    ok('K2b results.tsv has an info column', rows[0].split('\t')[-1] == 'info' and rows[1].split('\t')[-1] == 'mem=50', rows)
    ok('K2b the run line shows the info number', 'mem 50' in o, o)
    try:
        research_room('k2c', extra=['--info', 'mem', '--reference', 'nope'])
        refused = ''
    except AssertionError as e:
        refused = str(e)
    ok('K2b a reference that is not an info number is refused at init', 'name it in --info first' in refused, refused)
    room, repo, work = research_room('k2d')                            # a room that began before the column: rows keep their shape
    tsv = room / 'research' / 'results.tsv'
    tsv.write_text(tsv.read_text(encoding='utf-8').replace('\tinfo\n', '\n'), encoding='utf-8')
    c, o = run(room, 'research', 'amend', '--info', 'mem', '--as', 'LEAD')
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    rows = tsv.read_text(encoding='utf-8').splitlines()
    ok('K2b an old header gets old-shape rows', c == 0 and len(rows[0].split('\t')) == 11 and len(rows[1].split('\t')) == 11, rows)

# ---------------------------------------------------------------------------------------------------------------- K2c
if section('K2C'):                                                    # a challenger near the best while the reference moved: the best is measured again in the same run
    scale = BASE / 'k2c_scale.txt'
    src = f'import program\ns = float(open({str(scale)!r}).read())\nprint("loss:", (80 + 3 * program.X) * s)\nprint("ref:", 100 * s)\n'
    scale.write_text('1.0')
    room, repo, work = research_room('k2c1', extra=['--info', 'ref', '--reference', 'ref', '--min-gain', '5%'], eval_src=src)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')           # 95, ref 100
    scale.write_text('1.08')                                           # the machine got 8% slower: X=3 reads 96.1 against 95 (a worse run), measured beside the best 102.6
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
    text = ' '.join(p.read_text(encoding='utf-8', errors='ignore') for p in room.glob('*') if p.is_file())
    ok('K2c a false discard turns into a keep from the paired measure', c == 0 and 'KEEP' in o and 'paired measure' in o and 'measured again in this run at 102.6' in o, o)
    ok('K2c it is announced on the board before it runs', 'measuring att-1 again here' in text, text[-400:])
    st = state(room)
    ok('K2c the best is the challenger, the record has the paired number', st['best']['n'] == 2 and st['attempts'][1].get('paired', {}).get('of') == 1, st['attempts'][1])
    ok('K2c the run\'s own program is back in the worktree, committed and clean', (work / 'program.py').read_text() == 'X = 3\n'
       and not git('status', '--porcelain', cwd=work).stdout.strip(), git('status', '--porcelain', cwd=work).stdout)
    ok('K2c a log of the paired measure exists', (room / 'research' / 'runs' / '2-paired.log').is_file())
    # the other way: a gain that is only the machine going faster
    room, repo, work = research_room('k2c2', extra=['--info', 'ref', '--reference', 'ref', '--min-gain', '5%'], eval_src=src)
    scale.write_text('1.0')
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    scale.write_text('0.95')                                           # 8% better on paper (87.4 against 95), 3.2% against the best now (90.25)
    (work / 'program.py').write_text('X = 4\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 4', '--as', 'W')
    ok('K2c a false keep turns into a discard', c == 0 and 'DISCARD' in o and 'not better by the minimal gain' in o and 'at 90.25' in o, o)
    ok('K2c the line is back at the best', state(room)['best']['n'] == 1 and (work / 'program.py').read_text() == 'X = 5\n', state(room)['best'])
    # a reference that did not move, or a run far from the best: no second measure
    room, repo, work = research_room('k2c3', extra=['--info', 'ref', '--reference', 'ref', '--min-gain', '5%'], eval_src=src)
    scale.write_text('1.0')
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    (work / 'program.py').write_text('X = 4\n')                        # 92 against 95: a keep by 3.2%? not by 5%: discard, same reference
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 4', '--as', 'W')
    ok('K2c a steady reference is not measured twice', c == 0 and 'DISCARD' in o and 'paired measure' not in o and not (room / 'research' / 'runs' / '2-paired.log').exists(), o)
    # a contract with a build: the binary left is the best's while the worktree goes back to the challenger's program; the next run builds again
    bld = BASE / 'k2c_build.py'
    bld.write_text('import re\nopen("built.txt", "w").write(re.search(r"X = (\\d+)", open("program.py").read()).group(1))\n')
    src_b = f'import program\ns = float(open({str(scale)!r}).read())\nx = int(open("built.txt").read())\nprint("loss:", (80 + 3 * x) * s)\nprint("ref:", 100 * s)\n'
    scale.write_text('1.0')
    room, repo, work = research_room('k2c4', extra=['--info', 'ref', '--reference', 'ref', '--min-gain', '5%', '--build', f'"{sys.executable}" "{bld}"'], eval_src=src_b)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    scale.write_text('1.08')
    (work / 'program.py').write_text('X = 3\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
    ok('K2c with a build the paired measure still decides', c == 0 and 'KEEP' in o and 'at 102.6' in o, o)
    (work / 'program.py').write_text('X = 0\n')
    c, o = run(room, 'research', 'evaluate', '--desc', 'X 0', '--as', 'W')
    ok('K2c the next run builds its own program again (86.4 is X 0, not the best\'s X 5 or X 3)', c == 0 and 'loss = 86.4' in o, o)

# ---------------------------------------------------------------------------------------------------------------- K14
if section('K14'):                                                    # -text on the sealed files; promote brings the corrected harness into the shared worktree
    room, repo, work = research_room('k14', participants='W,V')
    attrs = repo / '.git' / 'info' / 'attributes'
    ok('K14 init writes -text for the sealed file in info/attributes', attrs.is_file() and '/eval.py -text' in attrs.read_text(encoding='utf-8'), attrs.is_file() and attrs.read_text(encoding='utf-8'))
    ok('K14 git treats it as binary for the eval: text unset', 'unset' in git('check-attr', 'text', '--', 'eval.py', cwd=work).stdout, git('check-attr', 'text', '--', 'eval.py', cwd=work).stdout)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
    c, o = run(room, 'research', 'assign', 'V', '--as', 'LEAD')
    ok('K14 a second worker has its own worktree', c == 0 and (room / 'research' / 'work-V').is_dir(), o)
    c, o = run(room, 'research', 'promote', 'main', '--as', 'LEAD')
    ok('K14 promote in phase 2 is refused and names reseal', c != 0 and 'phase 1' in o and 'reseal' in o, o)
    c, o = run(room, 'research', 'reseal', '--reason', 'the loss ignores the offset', '--as', 'LEAD')
    (repo / 'eval.py').write_text('import program\nprint("loss:", (program.X - 2) ** 2 + 1)\nprint("mem:", program.X * 10)\n')
    git('commit', '-qam', 'corrected harness', cwd=repo)
    c, o = run(room, 'research', 'promote', 'main', '--as', 'W')
    ok('K14 promote by a worker is refused', c != 0 and 'only the lead' in o, o)
    c, o = run(room, 'research', 'promote', '--as', 'LEAD')
    ok('K14 promote without a source says what it wants', c != 0 and 'SOURCE' in o, o)
    c, o = run(room, 'research', 'promote', 'nowhere', '--as', 'LEAD')
    ok('K14 an unknown source is refused', c != 0 and 'neither a worker' in o, o)
    c, o = run(room, 'research', 'promote', 'main', '--files', 'program.py', '--as', 'LEAD')
    ok('K14 the program is never promoted', c != 0 and 'never the program' in o, o)
    c, o = run(room, 'research', 'promote', 'main', '--files', 'nope.py', '--as', 'LEAD')
    ok('K14 a file the source lacks is refused', c != 0 and 'is not in main' in o, o)
    before = git('rev-parse', 'HEAD', cwd=work).stdout.strip()
    c, o = run(room, 'research', 'promote', 'main', '--as', 'LEAD')
    ok('K14 promote brings the sealed file in one kernel commit', c == 0 and 'eval.py from main' in o and '+ 1' in (work / 'eval.py').read_text()
       and git('rev-list', '--count', f'{before}..HEAD', cwd=work).stdout.strip() == '1' and not git('status', '--porcelain', cwd=work).stdout.strip(), (o, git('log', '-2', '--oneline', cwd=work).stdout))
    ok('K14 the other worktree starts from it and says so', 'worktrees of V start from it' in o, o)
    ok('K14 the other worktree has the corrected file', '+ 1' in (room / 'research' / 'work-V' / 'eval.py').read_text(), (room / 'research' / 'work-V' / 'eval.py').read_text())
    st = state(room)
    ok('K14 the smoke before it no longer counts, heads follow', st['smoke_ok'] is None and st['workers']['_main']['head'] == git('rev-parse', 'HEAD', cwd=work).stdout.strip()
       and st['workers']['V']['head'] == st['workers']['_main']['head'], st['workers'])
    c, o = run(room, 'research', 'promote', 'main', '--as', 'LEAD')
    ok('K14 promoting what is already there says so and changes nothing', c == 0 and 'nothing to promote' in o and git('rev-list', '--count', f'{before}..HEAD', cwd=work).stdout.strip() == '1', o)
    c, o = run(room, 'research', 'evaluate', '--desc', 'smoke on the corrected harness', '--as', 'V')
    ok('K14 a smoke runs the corrected evaluator', c == 0 and 'SMOKE' in o and 'loss = 10' in o, o)
    c, o = run(room, 'research', 'seal', '--as', 'LEAD')
    ok('K14 the seal takes the corrected file and the history numbers go on', c == 0 and state(room)['phase'] == 2 and state(room)['evals'] == 1
       and '+ 1' in (work / 'eval.py').read_text(), o)
    c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'V')
    ok('K14 the new baseline is att-2, ideas and numbers did not restart', c == 0 and 'att-2' in o and 'KEEP' in o and 'loss = 10' in o, o)

print(f'\n{"FAIL" if fails else "ok"}: {fails} failed', flush=True)
sys.exit(1 if fails else 0)
