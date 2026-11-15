"""0.19.9: a viewer that does not take messages must not pass the suite. A real `chat.py serve` on a throwaway room (fake
CLAUDE_CONFIG_DIR and HOME, port 8803 or 8804), every route the page uses asked once: none may answer with a server error or
drop the connection; the user's message and the common room's message must come back in the chat; the process tree is ended
at the end and the port must be free. (T24 added `me, began = procs.add(...)` in cmd_serve, which hid the viewer's me():
every route that calls it answered TypeError 'dict' object is not callable, and no test looked.)
Run: python -X utf8 smoke_0199_viewer.py   (CHATROOM_SCRIPTS = the scripts folder to test)"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199v_'))
ENV = {**os.environ, 'CLAUDE_CONFIG_DIR': str(BASE / 'claude'), 'HOME': str(BASE), 'USERPROFILE': str(BASE), 'CHATROOM_RELAUNCHED': '1', 'PYTHONUTF8': '1'}
CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0
srv = None
log = None


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


def free(port):
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1', port)) != 0


def finish():
    if srv is not None:
        kill_tree(srv.pid)
        srv.wait(timeout=30)
    if log is not None:
        log.close()
    shutil.rmtree(BASE, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    print(f'{fails} failed' if fails else 'ALL PASS 0', flush=True)
    sys.exit(1 if fails else 0)


port = next((p for p in (8803, 8804) if free(p)), None)         # the two ports of this test; a busy one is not touched
if port is None:
    print('SKIP: ports 8803 and 8804 are both in use')
    finish()
room = BASE / 'room'
subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'init', '--room', str(room), '--participants', 'A,B', '--lang', 'en'], capture_output=True, env=ENV, timeout=120)
log = (BASE / 'serve.log').open('wb')
srv = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'serve', '--room', str(room), '--port', str(port)], stdout=log, stderr=subprocess.STDOUT, env=ENV, stdin=subprocess.DEVNULL)
URL = f'http://127.0.0.1:{port}'


def call(path, body=None):
    """(status, text); a dropped connection is (0, why): the handler died"""
    req = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'} if body is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')
    except (OSError, ValueError) as exc:
        return 0, f'{type(exc).__name__}: {exc}'


up = False
for _ in range(120):
    if srv.poll() is not None:
        break
    if call('/config.json')[0] == 200:
        up = True
        break
    time.sleep(0.5)
ok('V1 the viewer starts and answers /config.json', up, (BASE / 'serve.log').read_text(encoding='utf-8', errors='replace')[-600:] if (BASE / 'serve.log').exists() else '')
if not up:
    finish()

# V2: every page route the viewer asks for answers without a server error (a route may say 400/404 for a missing query)
GETS = ['/', '/config.json', '/office.json', '/commands.json', '/board.json', '/check.json', '/idle.json', '/research.json', '/state.json',
        '/timeline.json', '/summary.json', '/chat.jsonl', '/neighbors.json', '/common.json', '/presence.json', '/visit.json', '/settings.json',
        '/preview.json', '/skills.json', '/spawn.json', '/cards.json', '/receipts.json', '/packs.json', '/spawn/state.json']
bad = {p: r for p in GETS if (r := call(p))[0] == 0 or r[0] >= 500}
ok('V2 every GET route of the page answers (no 5xx, no dropped connection)', not bad, {p: (r[0], r[1][:120]) for p, r in bad.items()})

# V3: the user writes in the room and in the common room; both come back in their chat
st, out = call('/post', {'text': 'hello from the user'})
ok('V3 POST /post is accepted and the message is in the chat', st == 200 and 'hello from the user' in call('/chat.jsonl')[1], (st, out))
st, out = call('/common/post', {'text': 'hello common'})
ok('V3 POST /common/post is accepted (it asks who is writing: me())', st == 200 and json.loads(out).get('n'), (st, out))
ok('V3 and the common room has it', 'hello common' in call('/common.json')[1])
st, out = call('/post', {'text': '   '})
ok('V3 an empty message is refused with 400, not a crash', st == 400, (st, out))
st, out = call('/common/doc', {'name': 'note.txt', 'data': 'aGVsbG8='})
ok('V3 POST /common/doc (also asks who is writing) answers without a server error', 0 < st < 500, (st, out))
st, out = call('/hook', [{'kind': 'x'}])
ok('V3 POST /hook answers 200', st == 200, (st, out))
for path in ('/presence', '/idle_me'):
    st, out = call(path, {'x': 0, 'y': 0, 'room': 'office'})
    ok(f'V3 POST {path} answers without a server error', 0 < st < 500, (st, out))

# V4: still the same viewer after all that, and the log has no traceback
ok('V4 after the battery the viewer is the same process and still answers', srv.poll() is None and call('/config.json')[0] == 200)
text = (BASE / 'serve.log').read_text(encoding='utf-8', errors='replace')
ok('V4 the viewer wrote no traceback', 'Traceback' not in text, text[-600:])

# V5: the tree is ended with its top, and the port is free
top = srv.pid
kill_tree(top)
srv.wait(timeout=30)
for _ in range(40):
    if free(port):
        break
    time.sleep(0.5)
ok('V5 once ended, the port is free', free(port))
if os.name == 'nt':
    left = [p for p in subprocess.run(['powershell', '-NoProfile', '-Command', f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{BASE.name}*' -and $_.ProcessId -ne $PID }} | Select-Object -ExpandProperty ProcessId"],
                                      capture_output=True, text=True).stdout.split() if p]
    ok('V5 no process of the test is left running', not left, left)
srv = None
finish()
