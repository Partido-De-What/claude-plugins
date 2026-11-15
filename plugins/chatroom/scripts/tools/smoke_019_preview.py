"""0.19.0 CORE T7: live preview (preview.py, `chat.py preview`, GET /preview.json, GET /preview/NAME/...).
Run: python smoke_019_preview.py   (CHATROOM_SCRIPTS = the scripts folder, default: this file's parent)"""
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
BASE = Path(tempfile.mkdtemp(prefix='smoke019prev_'))
CHAT = str(Path(SCRIPTS) / 'chat.py')
sys.path.insert(0, SCRIPTS)
import preview   # noqa: E402
import chat      # noqa: E402
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def cli(room, *args):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, 'preview', *args, '--room', str(room)], capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', 'replace')


room = BASE / 'room'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'UI,VOXEL', '--lang', 'en'], capture_output=True)
site = BASE / 'site'
site.mkdir()
(site / 'index.html').write_text('<h1>hi</h1><script src="a.js"></script>', encoding='utf-8')
(site / 'a.js').write_text('1', encoding='utf-8')
(BASE / 'secret.txt').write_text('SECRET', encoding='utf-8')
(site / 'tex.png').write_bytes(b'\x89PNG\r\n')

c, o = cli(room, str(site / 'index.html'), '--as', 'UI')
ok('declare a file: one line, exit 0', c == 0 and 'Preview on (html)' in o, (c, o))
c, o = cli(room, str(site), '--as', 'VOXEL', '--title', 'folder')
ok('declare a folder = its index.html, with a title', c == 0, (c, o))
c, o = cli(room, 'http://example.com/x', '--as', 'UI')
ok('a non-local url is refused', c != 0 and '127.0.0.1' in o, (c, o))
c, o = cli(room, str(BASE / 'nothing.html'), '--as', 'UI')
ok('a missing file is refused', c != 0, (c, o))
c, o = cli(room, str(BASE / 'secret.txt'), '--as', 'UI')
ok('a kind that cannot be shown is refused', c != 0 and '.txt' in o, (c, o))
c, o = cli(room, 'http://127.0.0.1:5173/', '--as', 'UI')
ok('a local server url is accepted', c == 0, (c, o))
cli(room, str(site / 'index.html'), '--as', 'UI')

r = chat.Room(room)
v = preview.listing(r)
p = {x['agent']: x for x in v['previews']}
ok('listing: v1, sorted by agent, src relative to the viewer', v['v'] == 1 and list(p) == ['UI', 'VOXEL'] and p['UI']['src'] == 'preview/UI/index.html' and
   p['UI']['kind'] == 'html' and p['VOXEL']['title'] == 'folder' and not p['UI']['missing'], v)
m0 = p['UI']['mtime']
time.sleep(0.05)
(site / 'a.js').write_text('2', encoding='utf-8')
os.utime(site / 'a.js', (m0 + 5, m0 + 5))
ok('mtime follows a file next to the page (css/js reload too)', preview.listing(r)['previews'][0]['mtime'] > m0, preview.listing(r))
big = BASE / 'big'
big.mkdir()
(big / 'index.html').write_text('x', encoding='utf-8')
for i in range(preview.SIBLINGS + 50):
    (big / f'f{i}.txt').write_text('x', encoding='utf-8')
os.utime(big / 'index.html', (m0 + 500, m0 + 500))
ok('more files than SIBLINGS: the page itself still counts in mtime', preview.newest(big / 'index.html') >= m0 + 500, preview.newest(big / 'index.html'))

code, body, ct = preview.serve(r, 'UI', '')
ok('serve: the declared file for an empty path', code == 200 and b'<h1>hi</h1>' in body and ct.startswith('text/html'), (code, ct))
ok('serve: a file next to it', preview.serve(r, 'UI', 'a.js')[0] == 200 and preview.serve(r, 'UI', 'tex.png')[2] == 'image/png', '')
ok('serve: no .. and no encoded .. out of the folder', preview.serve(r, 'UI', '../secret.txt')[0] == 404 and preview.serve(r, 'UI', '%2e%2e/secret.txt')[0] == 404 and
   preview.serve(r, 'UI', '..%5Csecret.txt')[0] == 404, 'traversal')
ok('serve: unknown agent / url preview / nothing', preview.serve(r, 'GHOST', '')[0] == 404, '')
(site / 'index.html').unlink()
ok('missing file: flagged, mtime 0', [x for x in preview.listing(r)['previews'] if x['agent'] == 'UI'][0]['missing'] is True, '')
(site / 'index.html').write_text('back', encoding='utf-8')

c, o = cli(room, '--off', '--as', 'UI')
ok('--off removes it, again says it had none', c == 0 and [x['agent'] for x in preview.listing(r)['previews']] == ['VOXEL'] and 'no preview' in cli(room, '--off', '--as', 'UI')[1], o)
ok('preview list', 'VOXEL: html folder' in cli(room, 'list')[1], cli(room, 'list'))

# HTTP
with socket.socket() as sk:
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
pr = subprocess.Popen([sys.executable, CHAT, 'serve', '--room', str(room), '--port', str(port)], env={**os.environ, 'CHATROOM_LIVE': '1'},
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    url = f'http://localhost:{port}'
    for _ in range(60):
        try:
            urllib.request.urlopen(url + '/preview.json', timeout=2)
            break
        except OSError:
            time.sleep(0.3)
    j = json.load(urllib.request.urlopen(url + '/preview.json', timeout=5))
    ok('GET /preview.json', j['previews'][0]['agent'] == 'VOXEL', j)
    rsp = urllib.request.urlopen(url + '/preview/VOXEL/index.html', timeout=5)
    ok('GET /preview/NAME/file: sandbox CSP, no-store, html', rsp.headers['Content-Security-Policy'] == 'sandbox allow-scripts' and rsp.headers['Cache-Control'] == 'no-store' and
       rsp.read() == b'back', dict(rsp.headers))
    try:
        urllib.request.urlopen(url + '/preview/VOXEL/..%2Fsecret.txt', timeout=5)
        ok('GET traversal is 404', False, 'served')
    except urllib.error.HTTPError as e:
        ok('GET traversal is 404', e.code == 404, e.code)
    try:
        urllib.request.urlopen(f'http://localhost:{port}/preview/VOXEL/index.html', timeout=5, data=None)
        rq = urllib.request.Request(url + '/preview/VOXEL/index.html', headers={'Host': 'evil.example'})
        urllib.request.urlopen(rq, timeout=5)
        ok('foreign Host is refused', False, 'served')
    except urllib.error.HTTPError as e:
        ok('foreign Host is refused', e.code == 403, e.code)
except Exception as exc:
    ok('http', False, repr(exc))
finally:
    pr.terminate()
    out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True).stdout if os.name == 'nt' else ''
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 5 and cols[1].endswith(f':{port}') and cols[3] == 'LISTENING':
            subprocess.run(['taskkill', '/F', '/PID', cols[4]], capture_output=True)
print(f'{"FAIL" if fails else "OK"}: {fails} failures')
sys.exit(1 if fails else 0)
