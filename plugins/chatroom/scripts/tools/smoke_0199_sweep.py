"""0.19.9, T24 (D): `chat.py procs sweep` finds what an older plugin left running, even when it never wrote the registry (a `chat.py serve`
whose starter is dead), and ends it with its children only after a yes. Run: python -X utf8 smoke_0199_sweep.py
The processes here are fakes (a file called chat.py that sleeps, with `serve --room R --port P` on its command line) under a temp folder;
every `--yes` is limited with --room, so a real viewer of this machine can never be touched. HOME is a fake config dir.
Every pid the test starts is ended with its tree at the end, whatever happened; the fakes also end by themselves after 5 minutes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199s_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0
started = []                                   # every pid this test starts, and the children the fakes report: ended at the end


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def kill_tree(pid):
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def gone(pid, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if not chat.pid_alive(pid):
            return True
        time.sleep(0.2)
    return False


def sweep(*args):
    """chat.py procs sweep ...: (exit code, output)"""
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'procs', 'sweep', *args], capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=120, env=dict(os.environ, CLAUDE_CONFIG_DIR=str(BASE / 'claude'), CHATROOM_RELAUNCHED='1'))   # no uv environment built in the fake dir
    return r.returncode, r.stdout + r.stderr


def listed(out, pid):
    return any(w.strip(',;:()=[]#') in (str(pid), f'pid={pid}') for w in out.split())


FAKE = BASE / 'fake' / 'chat.py'                # called chat.py on purpose: the scan looks for `chat.py serve` on a command line
FAKE.parent.mkdir()
FAKE.write_text("""import os, subprocess, sys, time
kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])
Path = __import__('pathlib').Path
Path(os.environ['KIDFILE']).write_text(str(kid.pid))
time.sleep(300)
""", encoding='utf-8')
LAUNCHER = BASE / 'launcher.py'                 # starts a fake and ends at once: the fake is left with a dead parent
LAUNCHER.write_text(f"""import os, subprocess, sys
flags = 0x00000008 | 0x00000200 | 0x01000000 if os.name == 'nt' else 0      # DETACHED, NEW_PROCESS_GROUP, BREAKAWAY_FROM_JOB
kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    p = subprocess.Popen([sys.executable, {str(FAKE)!r}, *sys.argv[1:]], creationflags=flags, start_new_session=os.name != 'nt', **kw)
except OSError:
    p = subprocess.Popen([sys.executable, {str(FAKE)!r}, *sys.argv[1:]], creationflags=flags & ~0x01000000, start_new_session=os.name != 'nt', **kw)
print(p.pid, flush=True)
""", encoding='utf-8')


def fake(room, port, orphan):
    """start a fake `chat.py serve --room R --port P`; orphan: its starter ends at once. Returns (pid, pid of its child)"""
    Path(room).mkdir(exist_ok=True)
    kidfile = BASE / f'kid{port}.txt'
    env = dict(os.environ, KIDFILE=str(kidfile))
    args = ['serve', '--room', str(room), '--port', str(port)]
    if orphan:
        r = subprocess.run([sys.executable, str(LAUNCHER), *args], capture_output=True, text=True, env=env, timeout=60)
        pid = int(r.stdout.split()[0])
    else:
        pid = subprocess.Popen([sys.executable, str(FAKE), *args], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL).pid
    started.append(pid)
    end = time.time() + 20
    while time.time() < end and not kidfile.exists():
        time.sleep(0.1)
    time.sleep(0.2)
    kid = int(kidfile.read_text()) if kidfile.exists() else 0
    started.append(kid)
    return pid, kid


try:
    R1, R2, R3 = BASE / 'room1', BASE / 'room2', BASE / 'room3'
    old, oldkid = fake(R1, 59101, orphan=True)         # what 0.18 left: not in the registry, starter dead, a child under it
    live, livekid = fake(R2, 59102, orphan=False)      # started by this test, which is alive: not an orphan
    other, otherkid = fake(R3, 59103, orphan=True)     # an orphan too, but of another room
    ok('setup: the fakes run', all(chat.pid_alive(p) for p in (old, oldkid, live, livekid, other, otherkid)),
       [(p, chat.pid_alive(p)) for p in (old, oldkid, live, livekid, other, otherkid)])

    code, out = sweep()
    ok('the list names the orphan that is not in the registry and the one of the other room', listed(out, old) and listed(out, other), out)
    ok('the list does not name the one whose starter is alive', code == 0 and not listed(out, live), out)
    ok('without --yes nothing is ended', code == 0 and all(chat.pid_alive(p) for p in (old, oldkid, other, otherkid)), out)

    code, out = sweep('--yes', '--room', str(R1))
    ok('--yes --room ends the orphan of that room', gone(old), out)
    ok('and the child under it', gone(oldkid), out)
    ok('the orphan of another room is left alone', chat.pid_alive(other) and chat.pid_alive(otherkid), out)
    ok('the one with a live starter is left alone', chat.pid_alive(live) and chat.pid_alive(livekid), out)

    code, out = sweep('--yes', '--room', str(R2))
    ok('--yes on the room of a live starter ends nothing', code == 0 and chat.pid_alive(live) and chat.pid_alive(livekid), out)

    code, out = sweep('--yes', '--room', str(R3))
    ok('--yes --room ends the other orphan with its tree', gone(other) and gone(otherkid), out)

    # what the registry knows: a test whose starter died goes, a viewer of the user whose starter died stays (it is the user's)
    gonepid = subprocess.run([sys.executable, '-c', 'import os; print(os.getpid())'], capture_output=True, text=True).stdout.strip()
    gonepid = int(gonepid)                                 # the pid of a process that has ended
    R4, R5, R6, R7 = (BASE / f'room{n}' for n in (4, 5, 6, 7))
    procs_dir = BASE / 'claude' / 'chatroom' / 'procs'
    procs_dir.mkdir(parents=True, exist_ok=True)

    def register(pid, room, port, purpose):
        (procs_dir / f'{pid}.json').write_text(json.dumps({'pid': pid, 'kind': 'serve', 'room': str(room), 'port': port, 'label': '', 'since': time.time(),
                                                           'purpose': purpose, 'starter': gonepid, 'clients': 0, 'last_hit': time.time()}), encoding='utf-8')

    prova, provakid = fake(R4, 59104, orphan=False)
    register(prova, R4, 59104, 'prova')
    mine, minekid = fake(R5, 59105, orphan=False)
    register(mine, R5, 59105, 'utente')
    code, out = sweep()
    ok('a registered test whose starter is dead is listed', listed(out, prova), out)
    ok('a registered viewer of the user whose starter is dead is not', code == 0 and not listed(out, mine), out)
    code, out = sweep('--yes', '--room', str(R5))
    ok('--yes does not end the viewer of the user', code == 0 and chat.pid_alive(mine) and chat.pid_alive(minekid), out)
    code, out = sweep('--yes', '--room', str(R4))
    ok('--yes ends the registered test with its tree', gone(prova) and gone(provakid), out)

    # a room folder that is gone: its viewer is not wanted by anybody, registered or not, even with a live starter
    lost, lostkid = fake(R6, 59106, orphan=False)
    lostreg, lostregkid = fake(R7, 59107, orphan=False)
    register(lostreg, R7, 59107, 'utente')
    shutil.rmtree(R6)
    shutil.rmtree(R7)
    code, out = sweep()
    ok('a viewer whose room folder is gone is listed, registered or not', listed(out, lost) and listed(out, lostreg), out)
    code, out = sweep('--yes', str(lost))
    ok('--yes PID ends that one and only that one', gone(lost) and gone(lostkid) and chat.pid_alive(lostreg) and chat.pid_alive(live), out)
    code, out = sweep('--yes', str(lostreg))
    ok('--yes PID ends the registered one too', gone(lostreg) and gone(lostregkid) and chat.pid_alive(live), out)

    code, out = sweep('--yes', '--room', str(R1))
    ok('nothing left to end: it says so and exits 0', code == 0, (code, out))
finally:
    for pid in started:
        if pid:
            kill_tree(pid)
    left = [p for p in started if p and not gone(p, 5)]
    ok('cleanup: no process of this test is left', not left, left)
    shutil.rmtree(BASE, ignore_errors=True)

print('ALL PASS' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
