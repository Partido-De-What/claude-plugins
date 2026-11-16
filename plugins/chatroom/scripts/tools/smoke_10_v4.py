"""1.0 V4: the merge lock is not taken from a merge that still runs; the viewer's panel saves the minutes an unwatched viewer lives.
Run: python -X utf8 smoke_10_v4.py"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10v4_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import merge  # noqa: E402

fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:600]}]'), flush=True)
    fails += not cond


def old(lock, secs):
    os.utime(lock, (time.time() - secs, time.time() - secs))


# the lock of a merge that still runs
u = BASE / 'user'
u.mkdir()
lock = u / '.merge.lock'
with merge._lock(u):
    ok('the lock names the pid of its writer', lock.read_text().split()[0] == str(os.getpid()), lock.read_text())
    old(lock, 600)
    try:
        with merge._lock(u):
            got = 'stole it'
    except merge.Busy:
        got = 'busy'
    ok('a lock older than 120 s whose writer still runs is not taken', got == 'busy' and lock.exists(), got)
    old(lock, merge.HARD_STALE + 60)
    try:
        with merge._lock(u):
            got = 'took it'
    except merge.Busy:
        got = 'busy'
    ok('a lock older than the hard limit goes even if its pid runs (the number may be another process\'s)', got == 'took it', got)
dead = subprocess.run([sys.executable, '-c', 'import os; print(os.getpid())'], capture_output=True, text=True).stdout.strip()
lock.write_text(dead)
old(lock, 600)
with merge._lock(u):
    pass
ok('a lock of a writer that is gone, older than 120 s, is taken over', not lock.exists())
lock.write_text(str(os.getpid()))
with_young = None
try:
    with merge._lock(u):
        with_young = 'took it'
except merge.Busy:
    with_young = 'busy'
ok('a young lock is busy as before', with_young == 'busy' and lock.exists(), with_young)
lock.unlink()

# the panel of the viewer: the minutes land in settings.json, a bad one is refused, the avatar is left alone
room = BASE / 'room'
room.mkdir()
env = dict(os.environ)
subprocess.run([sys.executable, '-X', 'utf8', str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(room), '--participants', 'A,B'], env=env, capture_output=True, timeout=60)
sock = socket.socket()
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
sock.close()
proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(SCRIPTS) / 'chat.py'), 'serve', '--room', str(room), '--port', str(port)], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call(path, body=None):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/{path}', data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


try:
    for _ in range(60):
        try:
            call('settings.json')
            break
        except OSError:
            time.sleep(0.5)
    s0 = json.loads(call('settings.json')[1])
    ok('the defaults are 30 and 10', (s0['viewer_idle_min'], s0['prova_idle_min']) == (30, 10), s0)
    call('settings', {'avatar': {'skin': '#aabbcc'}})
    code, _ = call('settings', {'viewer_idle_min': '45', 'prova_idle_min': 0})
    s1 = json.loads(call('settings.json')[1])
    ok('the panel saves the minutes (a string or a number, 0 = never)', code == 200 and (s1['viewer_idle_min'], s1['prova_idle_min']) == (45, 0), (code, s1))
    ok('and leaves the figure alone', s1['avatar'] == {'skin': '#aabbcc'}, s1.get('avatar'))
    code, said = call('settings', {'viewer_idle_min': 'soon'})
    s2 = json.loads(call('settings.json')[1])
    ok('a word for minutes is refused with a line, nothing changes', code == 400 and 'minutes' in said and s2['viewer_idle_min'] == 45, (code, said, s2))
    code, _ = call('settings', {'avatar': {'skin': '#112233'}})
    s3 = json.loads(call('settings.json')[1])
    ok('saving the figure does not reset the minutes', code == 200 and s3['viewer_idle_min'] == 45 and s3['avatar'] == {'skin': '#112233'}, s3)
finally:
    proc.kill()
print('FAILS', fails)
sys.exit(1 if fails else 0)
