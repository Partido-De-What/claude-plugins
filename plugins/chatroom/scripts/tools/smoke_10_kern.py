"""1.0, KERN items (research kernel, hold, templates), one section per ID. Run: python -X utf8 smoke_10_kern.py
ONLY=K3 runs one section. A fake HOME: nothing is written in ~/.claude."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10k_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
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
    if ONLY and ONLY != key:
        return False
    print(f'-- {key}', flush=True)
    return True


def run(room, *args, stdin=None, env=None, timeout=180):
    r = subprocess.run([sys.executable, CHAT, *args, '--room', str(room)], input=(stdin or '').encode(), capture_output=True,
                       timeout=timeout, env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def git(*a, cwd):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True)


def research_room(name, participants='W', extra=(), evaluate=None):
    """a repo (program.py, eval.py) and a research room on it, phase 2 unless --draft is in extra"""
    repo = BASE / f'repo-{name}'
    repo.mkdir()
    git('init', '-q', '-b', 'main', cwd=repo); git('config', 'user.email', 't@t', cwd=repo); git('config', 'user.name', 't', cwd=repo)
    (repo / 'program.py').write_text('X = 5\n')
    (repo / 'eval.py').write_text('import program\nprint("loss:", (program.X - 2) ** 2)\n')
    git('add', '-A', cwd=repo); git('commit', '-qm', 'base', cwd=repo)
    room = BASE / f'room-{name}'
    subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', participants, '--lang', 'en'], capture_output=True)
    (room / 'research').mkdir(exist_ok=True)
    (room / 'research' / 'task.md').write_text('# task: minimise loss')
    args = ['research', 'init', '--repo', str(repo), '--program', 'program.py', '--evaluate', evaluate or f'"{sys.executable}" eval.py',
            '--metric', 'loss', '--direction', 'min', '--budget-min', '0.2', '--max-evals', '30', '--sealed', 'eval.py',
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

print(f'\n{"FAIL" if fails else "ok"}: {fails} failed', flush=True)
sys.exit(1 if fails else 0)
