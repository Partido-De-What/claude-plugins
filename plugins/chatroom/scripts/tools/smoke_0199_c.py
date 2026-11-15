"""0.19.9 CIRO: C1 `spawn` and `spawn status` post the "Spawn is ready" line once, C2 a catalog older than a day is updated by itself
(spawn ping, and the Spawn view when it opens). Fake HOME and CLAUDE_CONFIG_DIR, a temp room, no network: the catalog round is a stub.
Run: python smoke_0199_c.py   (needs the spawn packages: Python 3.14 environment; CHATROOM_SCRIPTS = the scripts folder)"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199c_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['HOME'] = os.environ['USERPROFILE'] = str(BASE)
sys.path.insert(0, SCRIPTS)
import chat      # noqa: E402
fails = 0
CHAT = str(Path(SCRIPTS) / 'chat.py')


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def run(*args):
    return subprocess.run([sys.executable, '-X', 'utf8', CHAT, *args], capture_output=True, text=True, encoding='utf-8', timeout=120, stdin=subprocess.DEVNULL)


def mkroom(name):
    room = BASE / name
    run('init', '--room', str(room), '--participants', 'A,B', '--lang', 'en')
    return room


def catalog_aged(days):
    path = BASE / 'claude' / 'chatroom' / 'spawn' / 'catalog.json'      # where layers.chatroom_dir() says: CLAUDE_CONFIG_DIR, set above
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'updated': time.time() - days * 86400, 'models': [], 'providers': {}}), encoding='utf-8')


# ---- C1: the line that says Spawn is ready is in the chat once, whoever asks and however often
room = mkroom('c1')
for extra in ((), (), ('status',), ('--as', 'SPAWN')):
    run('spawn', *extra, '--room', str(room), *(() if '--as' in extra else ('--as', 'LEAD')))
ready = [m for m in chat.Room(room).messages() if 'Spawn is ready' in str(m.get('text', ''))]
ok('C1: spawn, spawn, spawn status and spawn by another name leave one line in the chat', len(ready) == 1, [m['n'] for m in ready])
r = run('spawn', 'status', '--room', str(room), '--as', 'LEAD')
ok('C1: spawn status still answers (it says it, it does not post it)', 'Spawn is ready' in r.stdout and r.returncode == 0, r.stdout + r.stderr)

# ---- C2: spawn ping brings an old catalog up to date first, and says so when it cannot
import spawn.catalog.catalog as cat   # noqa: E402
from spawn import panel               # noqa: E402
asked = []
cat.ping = lambda *a, **k: asked.append('ping') or []
room = chat.Room(mkroom('c2'))
ARGS = SimpleNamespace(pairs=['ping'], name='LEAD', top=None, vision=False)


def ping_out():
    out = io.StringIO()
    with redirect_stdout(out):
        chat.cmd_spawn(room, ARGS)
    return out.getvalue()


catalog_aged(19)
cat.update = lambda room_dir=None, force=False, **kw: asked.append('update') or cat.save({**cat.load(), 'updated': time.time()})
out = ping_out()
ok('C2: a catalog 19 days old is updated before the ping', asked == ['update', 'ping'], (asked, out))
ok('C2: and the old-catalog warning is not printed once it is fresh', 'days old' not in out, out)
asked.clear()
out = ping_out()
ok('C2: a fresh catalog is not updated again', asked == ['ping'], asked)
catalog_aged(19); asked.clear()


def broken(room_dir=None, force=False, **kw):
    asked.append('update')
    raise OSError('network down')


cat.update = broken
out = ping_out()
ok('C2: when the update fails the ping still runs and the warning says the catalog is old', asked == ['update', 'ping'] and '19 days old' in out, (asked, out))
import i18n      # noqa: E402
it = i18n.tr('it', 'spawn.ping.old_catalog', days='19')
ok('T39: the warning says the update just failed and names the button of the Spawn view in the SAME language (no Italian word in the English text)',
   'could not be updated' in out and i18n.tr('en', 'spawnv.update') in out and 'Aggiorna' not in out
   and 'non si è potuto aggiornare' in it and i18n.tr('it', 'spawnv.update') in it and 'Spawn view' not in it, (out, it))

# ---- C2: the Spawn view asks for the update by itself once, not at every poll while it is open
catalog_aged(19)
started = []
panel._update = lambda r, force=False: started.append(force)
for attr in ('auto_at',):
    panel.state.__dict__.pop(attr, None)
try:
    panel.state(room); panel.state(room)
except Exception as exc:         # the view's own state needs the fake HOME only; anything else is a failure of this test
    started.append(f'state failed: {type(exc).__name__}: {exc}')
ok('C2: the Spawn view starts the update of a catalog 19 days old, once', started == [False], started)
catalog_aged(0.1); started.clear()
panel.state.__dict__.pop('auto_at', None)
try:
    panel.state(room)
except Exception as exc:
    started.append(f'state failed: {exc}')
ok('C2: the Spawn view leaves a fresh catalog alone', started == [], started)

print(f'{fails} failed' if fails else 'ALL PASS 0')
sys.exit(1 if fails else 0)
