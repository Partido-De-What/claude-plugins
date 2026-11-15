"""0.19.9, T24 (orphans): what a long command starts dies with it. Run: python -X utf8 smoke_0199_orphans.py
On Windows a viewer started by a Python older than 3.14 is a chain (uv, the environment's python, the real one): killing the top left
the other three alive, 35 `serve` in one night. The job object of chat.job_for_children() ends them with the top.
HOME is a fake config dir: nothing is written in ~/.claude."""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199o_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0
started = []                                   # every pid this test starts: ended at the end whatever happened


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
    """True when the process is gone within `seconds`"""
    end = time.time() + seconds
    while time.time() < end:
        if not chat.pid_alive(pid):
            return True
        time.sleep(0.2)
    return False


if os.name != 'nt':
    print('SKIP: the job object is Windows only; the chain of uv does not exist elsewhere')
else:
    HELPER = BASE / 'helper.py'
    HELPER.write_text(f"""import subprocess, sys, time
sys.path.insert(0, {SCRIPTS!r})
import chat
assert chat.job_for_children(), 'no job'
kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
free = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], creationflags=0x01000000)   # CREATE_BREAKAWAY_FROM_JOB
print(kid.pid, free.pid, flush=True)
time.sleep(120)
""", encoding='utf-8')
    top = subprocess.Popen([sys.executable, str(HELPER)], stdout=subprocess.PIPE, text=True)
    line = top.stdout.readline().split()
    kid, free = int(line[0]), int(line[1])
    started += [top.pid, kid, free]
    ok('O1 a child of the process is alive while its starter is', chat.pid_alive(kid) and chat.pid_alive(free))
    top.kill()
    top.wait()
    ok('O1 killed from outside (no /T), the starter takes its children with it', gone(kid), kid)
    ok('O1 a child that breaks away on purpose outlives it', chat.pid_alive(free), free)

    # the real chain: a Python older than 3.14, uv, `serve`; skipped where either is missing (or no environment is given: it would be built)
    old = None
    if sys.version_info < (3, 14):
        old = sys.executable
    else:
        for tag in ('3.13', '3.12', '3.11'):
            got = subprocess.run(['py', f'-{tag}', '-c', 'import sys; print(sys.executable)'], capture_output=True, text=True) if shutil.which('py') else None
            if got and got.returncode == 0 and got.stdout.strip():
                old = got.stdout.strip()
                break
    if not (old and shutil.which('uv') and os.environ.get('UV_PROJECT_ENVIRONMENT')):
        print('SKIP O2: needs a Python older than 3.14, uv and UV_PROJECT_ENVIRONMENT (an existing environment)')
    else:
        room = BASE / 'room'
        subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B'], capture_output=True)
        with socket.socket() as sk:
            sk.bind(('127.0.0.1', 0))
            port = sk.getsockname()[1]
        srv = subprocess.Popen([old, '-X', 'utf8', CHAT, 'serve', '--room', str(room), '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started.append(srv.pid)

        def answers():
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/config.json', timeout=2):
                    return True
            except OSError:
                return False
        up = False
        for _ in range(240):                     # the first relaunch may fetch Python 3.14
            if answers():
                up = True
                break
            time.sleep(0.5)
        ok('O2 the viewer started through the relaunch answers', up)
        srv.kill()
        srv.wait()
        down = False
        for _ in range(40):
            if not answers():
                down = True
                break
            time.sleep(0.5)
        ok('O2 killed from outside, no process of the chain keeps the port', down)
    for pid in started:
        kill_tree(pid)

# the registry: what a long command starts is listed, and ended on request
def procs(*args):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'procs', *args], capture_output=True, timeout=120)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


room = BASE / 'room3'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B'], capture_output=True)
with socket.socket() as sk:
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
srv = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'serve', '--room', str(room), '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
started.append(srv.pid)
PROCS = BASE / 'claude' / 'chatroom' / 'procs'
real = 0
for _ in range(100):                             # its pid is the real python's: a venv python is a launcher that starts it
    real = next((int(f.stem) for f in PROCS.glob('*.json') if json.loads(f.read_text(encoding='utf-8')).get('port') == port), 0)
    if real:
        break
    time.sleep(0.3)
started.append(real)
c, o = procs()
ok('O3 a viewer is listed with its pid, port and room', c == 0 and f'serve pid {real} port {port}' in o and 'room3' in o, o)
other = BASE / 'room4'
c, o = procs('stop', '--room', str(other))
ok('O3 stop for another room ends nothing', c == 0 and 'nothing to stop' in o and srv.poll() is None, o)
c, o = procs('stop')
ok('O3 stop without a target says how', c != 0 and '--all' in o and srv.poll() is None, o)
c, o = procs('stop', '--room', str(room))
srv.wait(timeout=30)
ok('O3 stop --room ends the viewer of that room', c == 0 and f'ended serve pid {real}' in o and srv.poll() is not None and gone(real), o)
ok('O3 and it leaves the list', f'pid {real}' not in procs()[1] and not (PROCS / f'{real}.json').exists())
dead = subprocess.Popen([sys.executable, '-c', 'pass'])
dead.wait()
(BASE / 'claude' / 'chatroom' / 'procs').mkdir(parents=True, exist_ok=True)
(BASE / 'claude' / 'chatroom' / 'procs' / f'{dead.pid}.json').write_text(json.dumps({'pid': dead.pid, 'kind': 'serve', 'room': '', 'port': 1, 'label': '', 'since': time.time()}), encoding='utf-8')
c, o = procs()
ok('O3 a killed one that left its file is dropped from the list', f'pid {dead.pid}' not in o and not (BASE / 'claude' / 'chatroom' / 'procs' / f'{dead.pid}.json').exists(), o)
if os.name == 'nt':                              # a pid taken by a newer process is not the entry that was written for it
    bystander = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    started.append(bystander.pid)
    (BASE / 'claude' / 'chatroom' / 'procs' / f'{bystander.pid}.json').write_text(
        json.dumps({'pid': bystander.pid, 'kind': 'serve', 'room': '', 'port': 1, 'label': '', 'since': time.time() - 7200}), encoding='utf-8')
    c, o = procs('stop', '--all')
    ok('O3 a pid reused by an unrelated process is neither listed nor ended', f'pid {bystander.pid}' not in o and bystander.poll() is None, o)
# a viewer ends by itself when nobody needs it: a test's (room in the temporary folder) when its starter dies or nobody looks at it,
# the user's when its room is closed and nobody looks at it; one somebody looks at is never ended by itself
HOME = BASE / 'home'
(HOME / '.claude' / 'chatroom').mkdir(parents=True)
ENV = {**os.environ, 'USERPROFILE': str(HOME), 'HOME': str(HOME)}
SETTINGS = [HOME / '.claude' / 'chatroom' / 'settings.json', BASE / 'claude' / 'chatroom' / 'settings.json']      # under the home, or under the config folder (layers)


def put_settings(**kw):
    for f in SETTINGS:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(kw), encoding='utf-8')


def make_room(name):
    r = BASE / name
    subprocess.run([sys.executable, CHAT, 'init', '--room', str(r), '--participants', 'A,B'], capture_output=True, env=ENV)
    return r


def free_port():
    with socket.socket() as sk:
        sk.bind(('127.0.0.1', 0))
        return sk.getsockname()[1]


def start_serve(room, port, **extra):
    log = open(BASE / f'{room.name}.log', 'w', encoding='utf-8')
    p = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'serve', '--room', str(room), '--port', str(port)], env={**ENV, **extra},
                         stdout=log, stderr=subprocess.STDOUT)
    started.append(p.pid)
    return p


def entry_of(room, kind='serve'):
    for _ in range(120):
        for f in PROCS.glob('*.json'):
            try:
                e = json.loads(f.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if e.get('kind') == kind and e.get('room') == str(Path(room).resolve()):
                started.append(e['pid'])
                return e
        time.sleep(0.25)
    return {}


def hit(port):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{port}/config.json', timeout=2).read()
    except OSError:
        pass


def watched(port, seconds):
    """somebody looks at the viewer for `seconds`"""
    end = time.time() + seconds
    while time.time() < end:
        hit(port)
        time.sleep(1.5)


def said(room):
    return (BASE / f'{room.name}.log').read_text(encoding='utf-8', errors='replace')


def shut_room(room):
    chat.Room(str(room)).append('A', 'CLOSED v1\nthe plan')               # a closing as the chat holds it (the post command wants the votes first)


try:
    put_settings(prova_idle_min=0.1, viewer_idle_min=0.1)      # 6 s
    # the starter dies: a helper starts the viewer, the helper is ended (alone, not its children)
    room = make_room('r_starter')
    port = free_port()
    helper = BASE / 'starter.py'
    helper.write_text(f"""import os, subprocess, sys, time
log = open({str(BASE / 'r_starter.log')!r}, 'w')
p = subprocess.Popen([sys.executable, '-X', 'utf8', {CHAT!r}, 'serve', '--room', {str(room)!r}, '--port', '{port}'], stdout=log, stderr=subprocess.STDOUT)
print(os.getpid(), flush=True)
time.sleep(300)
""", encoding='utf-8')
    top = subprocess.Popen([sys.executable, str(helper)], stdout=subprocess.PIPE, text=True, env=ENV)
    started.append(top.pid)
    mine = int(top.stdout.readline())
    e = entry_of(room)
    ok('O4 a test viewer is noted as such, with who started it', e.get('purpose') == 'prova' and e.get('starter') == mine, e)
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/PID', str(mine)], capture_output=True)
    else:
        os.kill(mine, 9)
    ok('O4 a test viewer ends when its starter is gone', gone(e.get('pid', 0), 40), e)
    ok('O4 and says why, and leaves no entry', 'what started it is gone' in said(room) and not (PROCS / f"{e.get('pid')}.json").exists(), said(room)[-300:])

    # nobody looks at it: a test viewer ends; somebody looking keeps it, and `procs close` ends it
    room = make_room('r_quiet')
    srv = start_serve(room, free_port())
    e = entry_of(room)
    ok('O4 a test viewer nobody looks at ends by itself', gone(e.get('pid', 0), 60), e)
    ok('O4 and says why', 'nobody has looked at it' in said(room), said(room)[-300:])

    room = make_room('r_watched')
    port = free_port()
    srv = start_serve(room, port)
    e = entry_of(room)
    time.sleep(3)
    watched(port, 16)                                          # more than twice its patience
    f = PROCS / f"{e['pid']}.json"
    live = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    ok('O4 a test viewer somebody looks at stays, and counts them', chat.pid_alive(e.get('pid', 0)) and live.get('clients', 0) >= 1, live)
    try:
        got = urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/common/post', data=json.dumps({'text': 'hi'}).encode(), headers={'Content-Type': 'application/json'}), timeout=5).status
    except OSError as exc:
        got = str(exc)
    ok("O4 a route that calls the viewer's me() answers: the serve entry does not shadow it", got == 200, got)
    c, o = procs('close', '--room', str(room))
    ok('O4 the closing ends the test viewers of the room and lists them', c == 0 and f"ended serve pid {e['pid']}" in o and gone(e['pid'], 20), o)

    # the user's viewer: an open room keeps it; a closed one with nobody looking ends it; with somebody looking it stays
    room = make_room('r_user')
    port = free_port()
    srv = start_serve(room, port, CHATROOM_PURPOSE='utente')
    e = entry_of(room)
    ok("O4 the user's viewer is noted as such", e.get('purpose') == 'utente', e)
    time.sleep(16)
    ok('O4 the viewer of an open room nobody looks at stays', chat.pid_alive(e.get('pid', 0)))
    shut_room(room)
    watched(port, 14)
    ok('O4 the viewer of a closed room somebody looks at stays', chat.pid_alive(e.get('pid', 0)))
    c, o = procs('close', '--room', str(room))
    ok('O4 the closing does not end it: it says the port', c == 0 and f'port {port} stays' in o, o)
    ok('O4 and the viewer is still there', chat.pid_alive(e['pid']))
    ok('O4 the viewer of a closed room nobody looks at ends by itself', gone(e['pid'], 140) and 'room is closed' in said(room), said(room)[-300:])
    put_settings(prova_idle_min=0.1, viewer_idle_min=0)
    srv = start_serve(room, free_port(), CHATROOM_PURPOSE='utente')
    e = entry_of(room)
    time.sleep(16)
    ok("O4 0 minutes in the user's settings: it never ends by itself", chat.pid_alive(e.get('pid', 0)), e)

    # the relay of a closed room ends; the one of an open room does not
    room = make_room('r_relay')
    relay = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--room', str(room), '--follow'], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    started.append(relay.pid)
    time.sleep(6)
    ok('O4 the relay of an open room goes on', relay.poll() is None)
    relay.kill()
    shut_room(room)
    relay = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--room', str(room), '--follow'], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    started.append(relay.pid)
    try:
        out = relay.communicate(timeout=60)[0]
    except subprocess.TimeoutExpired:
        out = ''
    ok('O4 the relay of a closed room ends, and says so', relay.poll() == 0 and 'room is closed' in out, out[-300:])

    c, o = procs('sweep')
    ok('O4 sweep lists and ends nothing without --yes', c == 0 and 'sweep --yes' in o, o)

    # one the registry never knew (an older plugin started it) may be a viewer somebody looks at: `sweep --yes` ends it only when it is named
    import contextlib
    import io
    import procs as P
    import types
    ended = []
    old = {'pid': 999999, 'kind': 'serve', 'room': str(BASE / 'old_room'), 'port': 1, 'since': time.time(), 'why': 'parent', 'unknown': True}
    kept = {**old, 'pid': 999998, 'room': '', 'unknown': False}          # the registry's own: a test viewer whose starter is gone
    saved = (P.orphans, P.end)
    P.orphans, P.end = (lambda shown: [dict(old), dict(kept)]), (lambda e: ended.append(e['pid']))

    def sweep(*pairs, room=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            P.command(types.SimpleNamespace(pairs=['sweep', *pairs], room=room, yes=True))
        return buf.getvalue()

    try:
        o = sweep()
        ok('O5 sweep --yes ends the registered orphan and not the unknown one, and says which stays', ended == [999998] and 'not in the registry' in o and 'they stay' in o, (ended, o))
        ended.clear()
        sweep('999999')
        ok('O5 named by its pid, the unknown one is ended', ended == [999999], ended)
        ended.clear()
        sweep(room=str(BASE / 'old_room'))
        ok('O5 named by its room, the unknown one is ended', ended == [999999], ended)
    finally:
        P.orphans, P.end = saved
finally:
    for pid in started:
        kill_tree(pid)

for pid in started:
    kill_tree(pid)

print(f'\n{fails} FAIL' if fails else '\nALL PASS')
sys.exit(1 if fails else 0)
