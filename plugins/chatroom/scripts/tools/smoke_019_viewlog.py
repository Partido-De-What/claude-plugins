"""POST /viewlog (viewlog.py): unit and over HTTP. Run: python tools/smoke_019_viewlog.py"""
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
CHAT = str(Path(SCRIPTS) / 'chat.py')
BASE = Path(tempfile.mkdtemp(prefix='smoke019vl_'))
sys.path.insert(0, SCRIPTS)
import chat      # noqa: E402
import viewlog   # noqa: E402
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:500]}]'), flush=True)
    fails += not cond


room = BASE / 'room'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'VOXEL', '--lang', 'en'], capture_output=True)
r = chat.Room(room)
code, ans = viewlog.append(r, {'events': [{'who': 'mouse', 'yaw': [1, 2]}, {'who': 'x' * 9000}, {'who': 'lone ' + chr(0xd800) + ' surrogate'}]}, '127.0.0.1')
lines = (room / 'viewlog.jsonl').read_text(encoding='utf-8').splitlines()
ok('append: one line per event, ip and time added, a line is capped', code == 200 and ans == {'ok': True, 'n': 3} and len(lines) == 3 and
   json.loads(lines[0])['ip'] == '127.0.0.1' and 'at' in json.loads(lines[0]), (code, ans))
j1 = json.loads(lines[1])
ok('a long event becomes one valid line {cut, n, head}; a lone surrogate is written', j1['cut'] is True and j1['n'] > viewlog.MAX_LINE and len(j1['head']) == 3000 and 'lone' in lines[2], lines[1][:80])
ok('too many events / not objects / not a list: 400, nothing written', all(viewlog.append(r, b, 'x')[0] == 400 for b in
   ({'events': [{}] * 201}, {'events': [1]}, {'events': 'a'}, [], None)) and len((room / 'viewlog.jsonl').read_text(encoding='utf-8').splitlines()) == 3, '')
(room / 'viewlog.jsonl').write_text('x' * viewlog.MAX_FILE, encoding='utf-8')
ok('the file stops growing at the cap', viewlog.append(r, {'events': [{'a': 1}]}, 'x')[1] == {'ok': True, 'n': 0, 'full': True}, '')
(room / 'viewlog.jsonl').unlink()

with socket.socket() as sk:
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
pr = subprocess.Popen([sys.executable, CHAT, 'serve', '--room', str(room), '--port', str(port)], env={**os.environ, 'CHATROOM_LIVE': '1'},
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def post(body, raw=None, headers=None):
    rq = urllib.request.Request(f'http://localhost:{port}/viewlog', data=raw if raw is not None else json.dumps(body).encode(), headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        rs = urllib.request.urlopen(rq, timeout=5)
        return rs.status, json.loads(rs.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:80]
    except ConnectionError:      # refused before the body was read: Windows may reset the socket before the client reads the answer
        return 0, b'reset'


try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f'http://localhost:{port}/preview.json', timeout=2)
            break
        except OSError:
            time.sleep(0.3)
    ok('HTTP: events written', post({'events': [{'who': 'wheel'}]}) == (200, {'ok': True, 'n': 1}) and
       json.loads((room / 'viewlog.jsonl').read_text(encoding='utf-8').splitlines()[0])['who'] == 'wheel', '')
    ok('HTTP: more than 64 KB is 413', post(None, raw=b'{"events":[' + b'{"a":"' + b'x' * 70000 + b'"}' + b']}')[0] in (413, 0), '')
    ok('HTTP: a foreign Host is 403', post({'events': []}, headers={'Host': 'evil.example'})[0] in (403, 0), '')
    o = post({'events': []}, headers={'Origin': 'http://evil.example'})
    ok('HTTP: a foreign Origin is 403', o[0] in (403, 0), o)
    ok('HTTP: a Content-Length that is not a number is answered 400', post(None, raw=b'{}', headers={'Content-Length': 'abc'})[0] in (400, 0), '')
    ok('HTTP: bad json is 400', post(None, raw=b'{nope')[0] == 400, '')
    ok('HTTP: nothing of the refused calls was written', len((room / 'viewlog.jsonl').read_text(encoding='utf-8').splitlines()) == 1, '')
finally:
    pr.terminate()
print(f'OK: {fails} failures' if not fails else f'FAIL: {fails} failures')
sys.exit(1 if fails else 0)
