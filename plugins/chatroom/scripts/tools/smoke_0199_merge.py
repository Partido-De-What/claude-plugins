"""0.19.9 ELIO (T19c): after an update, the user's own copies (user layer) are merged with the new core, three ways, and nothing is
lost in silence: a clean merge keeps both changes (old copy backed up), a conflict leaves the old copy in use and says "needs a
merge" once, with the command ready; `merge --accept` closes it. locales/<lang>.json is merged key by key.
Fake CLAUDE_CONFIG_DIR and HOME, temp folders, git needed. Run: python smoke_0199_merge.py   (CHATROOM_SCRIPTS = the scripts folder)"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
TMP = Path(tempfile.mkdtemp(prefix='smoke0199merge_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(TMP / 'claude')
os.environ['HOME'] = os.environ['USERPROFILE'] = str(TMP)
sys.path.insert(0, SCRIPTS)
import merge      # noqa: E402
from i18n import say, use      # noqa: E402
use('en')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8') if isinstance(text, str) else text)
    return path


def fresh(name):
    root = TMP / name
    shutil.rmtree(root, ignore_errors=True)
    return root / 'user', root / 'core'


def state(res, rel):
    return next((x['state'] for x in res if x['rel'] == rel), None)


B, T = 'one\ntwo\nthree\nfour\n', 'ONE\ntwo\nthree\nfour\n'            # base, and the user's edit of line 1

# ---- clean merge: you changed line 1, the new version changed line 4: both are in, the old copy is kept
user, core = fresh('clean')
put(user / 'templates/p.md', T)
put(user / '.base/templates/p.md', B)
put(core / 'templates/p.md', 'one\ntwo\nthree\nFOUR\n')
res = merge.run(user, core)
ok('clean: state merged', state(res, 'templates/p.md') == merge.MERGED, res)
ok('clean: both changes in the override', (user / 'templates/p.md').read_text() == 'ONE\ntwo\nthree\nFOUR\n', (user / 'templates/p.md').read_text())
ok('clean: base is the new core now', (user / '.base/templates/p.md').read_bytes() == (core / 'templates/p.md').read_bytes())
bk = list((user / '.merged-backup').rglob('p.md'))
ok('clean: the old override is kept in .merged-backup', len(bk) == 1 and bk[0].read_text() == T, bk)
ok('clean: second run has nothing to do', state(merge.run(user, core), 'templates/p.md') == merge.CURRENT)

# ---- conflict: both changed line 2: the old override stays, the draft has markers, the notice comes once per core version
user, core = fresh('conflict')
put(user / 'guides/g.md', 'one\nMINE\nthree\n')
put(user / '.base/guides/g.md', 'one\ntwo\nthree\n')
put(core / 'guides/g.md', 'one\nTHEIRS\nthree\n')
res = merge.run(user, core)
ok('conflict: state conflict', state(res, 'guides/g.md') == merge.CONFLICT, res)
ok('conflict: your copy stays as it was', (user / 'guides/g.md').read_text() == 'one\nMINE\nthree\n')
ok('conflict: base not advanced', (user / '.base/guides/g.md').read_text() == 'one\ntwo\nthree\n')
draft = (user / 'guides/g.md.merged').read_text() if (user / 'guides/g.md.merged').is_file() else ''
ok('conflict: the draft has the markers and both sides', '<<<<<<< yours' in draft and 'MINE' in draft and 'THEIRS' in draft and '>>>>>>> new' in draft, draft)
line = merge.sentence(res[0])
ok('conflict: the sentence says needs a merge, names the file and the ready command', 'Needs a merge' in line and 'guides/g.md' in line and 'merge --accept guides/g.md' in line and 'g.md.merged' in line, line)
ok('conflict: announced once', len(merge.announce(user, res)) == 1 and merge.announce(user, merge.run(user, core)) == [])
put(core / 'guides/g.md', 'one\nTHEIRS2\nthree\n')                    # a newer core: said again
ok('conflict: a new version of the core is announced again', len(merge.announce(user, merge.run(user, core))) == 1)

# ---- accept: markers left -> refused; resolved -> override replaced, draft gone, base advanced
r = merge.accept(user, core, 'guides/g.md')
ok('accept: refused while markers are left', r['state'] == merge.MARKERS, r)
put(user / 'guides/g.md.merged', 'one\nBOTH\nthree\n')
r = merge.accept(user, core, 'guides/g.md')
ok('accept: accepted', r['state'] == merge.ACCEPTED and (user / 'guides/g.md').read_text() == 'one\nBOTH\nthree\n', r)
ok('accept: draft removed, old override backed up', not (user / 'guides/g.md.merged').exists() and any((user / '.merged-backup').rglob('g.md')))
ok('accept: the next run has nothing to do and the notice is forgotten', state(merge.run(user, core), 'guides/g.md') == merge.CURRENT and merge.announce(user, merge.run(user, core)) == [] and json.loads((user / '.merge-notice.json').read_text()) == {})

# ---- never edited: the old default must not hide the new core
user, core = fresh('adopt')
put(user / 'templates/a.md', B)
put(user / '.base/templates/a.md', B)
put(core / 'templates/a.md', 'new\n')
ok('adopted: the override that equals its base goes away', state(merge.run(user, core), 'templates/a.md') == merge.ADOPTED and not (user / 'templates/a.md').exists() and not (user / '.base/templates/a.md').exists())

# ---- no base kept: the base is taken from the core as it is now; core equal to base: nothing; user already equal to core: base moves
user, core = fresh('misc')
put(user / 'templates/n.md', 'mine\n')
put(core / 'templates/n.md', 'core\n')
ok('no base: registered, nothing touched', state(merge.run(user, core), 'templates/n.md') == merge.NEW_BASE and (user / '.base/templates/n.md').read_text() == 'core\n' and (user / 'templates/n.md').read_text() == 'mine\n')

# ---- a copy made by hand has no base: while no update came since the last run the core is what it started from; after an update it
# cannot be told, and silence would lose the new version's change (found by the live research proof)
user, core = fresh('nobase')
put(core / '.claude-plugin/plugin.json', '{"version": "1.0.0"}')
put(core / 'guides/h.md', 'a\nb\nc\nd\ne\nf\n')
put(user / 'guides/h.md', 'a\nb MINE\nc\nd\ne\nf\n')               # your hand-made copy: no .base
merge.run(user, core)                                              # a session of 1.0.0: base registered, version noted
ok('hand-made copy, same version: registered silently', (user / '.base/guides/h.md').read_text() == 'a\nb\nc\nd\ne\nf\n' and json.loads((user / '.merge-state.json').read_text())['version'] == '1.0.0')
(user / '.base/guides/h.md').unlink()                              # (as if it had been made after that run)
put(core / '.claude-plugin/plugin.json', '{"version": "1.1.0"}')   # the update
put(core / 'guides/h.md', 'a\nb\nc\nd\ne\nf NEW\n')
res = merge.run(user, core, apply=False)
ok('hand-made copy, no base, after an update: needs a look (dry run too), nothing written', state(res, 'guides/h.md') == merge.NO_BASE and not (user / '.base/guides/h.md').exists() and json.loads((user / '.merge-state.json').read_text())['version'] == '1.0.0')
res = merge.run(user, core)
ok('hand-made copy, no base, after an update: needs a look, your copy stays, no base invented', state(res, 'guides/h.md') == merge.NO_BASE and (user / 'guides/h.md').read_text() == 'a\nb MINE\nc\nd\ne\nf\n' and not (user / '.base/guides/h.md').exists())
sent = merge.sentence(next(x for x in res if x['rel'] == 'guides/h.md'))
ok('hand-made copy: the sentence names the file, both paths and the accept command', 'Needs a look' in sent and 'guides/h.md' in sent and '--accept guides/h.md' in sent, sent)
ok('hand-made copy: said once, and still open at the next run of the same version', len(merge.announce(user, res)) == 1 and state(merge.run(user, core), 'guides/h.md') == merge.NO_BASE and merge.announce(user, merge.run(user, core)) == [])
r = merge.accept(user, core, 'guides/h.md')
ok('hand-made copy: accept makes the new core its base and closes it', r['state'] == merge.ACCEPTED and (user / '.base/guides/h.md').read_text() == 'a\nb\nc\nd\ne\nf NEW\n' and json.loads((user / '.merge-state.json').read_text())['no_base'] == [] and state(merge.run(user, core), 'guides/h.md') == merge.CURRENT)
put(core / 'guides/h.md', 'a\nb\nc\nd2\ne\nf NEW\n')
put(core / '.claude-plugin/plugin.json', '{"version": "1.2.0"}')
ok('hand-made copy: from there the next update merges three ways', state(merge.run(user, core), 'guides/h.md') == merge.MERGED and (user / 'guides/h.md').read_text() == 'a\nb MINE\nc\nd2\ne\nf\n', (user / 'guides/h.md').read_text())
put(user / 'templates/s.md', 'same\n')
put(user / '.base/templates/s.md', 'old\n')
put(core / 'templates/s.md', 'same\n')
ok('already equal to the new core: base moves, no merge', state(merge.run(user, core), 'templates/s.md') == merge.CURRENT and (user / '.base/templates/s.md').read_text() == 'same\n')
put(user / 'templates/own.md', 'only mine\n')
ok('a file the core never had is the user\'s own: left alone', state(merge.run(user, core), 'templates/own.md') is None)
put(user / 'templates/gone.md', 'mine\n')
put(user / '.base/templates/gone.md', 'was\n')
res = merge.run(user, core)
ok('the core dropped the file: said, your copy stays', state(res, 'templates/gone.md') == merge.GONE and (user / 'templates/gone.md').exists() and 'Needs a look' in merge.sentence(next(x for x in res if x['rel'] == 'templates/gone.md')))
put(user / 'recovered/0.18.0/templates/x.md', 'a recovered file is not an override\n')
ok('recovered/ is not scanned', all(not x['rel'].startswith('recovered') for x in merge.run(user, core)))

# ---- CRLF core against an LF base: the same text is not a change; a clean merge works across line endings
user, core = fresh('crlf')
put(core / 'templates/c.md', 'one\r\ntwo\r\nthree\r\n')
put(user / '.base/templates/c.md', 'one\ntwo\nthree\n')
put(user / 'templates/c.md', 'ONE\ntwo\nthree\n')
ok('crlf: same text is current', state(merge.run(user, core), 'templates/c.md') == merge.CURRENT)
put(core / 'templates/c.md', 'one\r\ntwo\r\nTHREE\r\n')
ok('crlf: clean merge across line endings', state(merge.run(user, core), 'templates/c.md') == merge.MERGED and (user / 'templates/c.md').read_bytes() == b'ONE\ntwo\nTHREE\n', (user / 'templates/c.md').read_bytes())

# ---- no git: said, nothing written
user, core = fresh('nogit')
put(user / 'templates/p.md', T)
put(user / '.base/templates/p.md', B)
put(core / 'templates/p.md', 'one\ntwo\nthree\nFOUR\n')
which = shutil.which
merge.shutil.which = lambda name, *a, **k: None if name == 'git' else which(name, *a, **k)
try:
    res = merge.run(user, core)
finally:
    merge.shutil.which = which
line = merge.sentence(res[0])
ok('no git: state, nothing written, the three paths and the accept command are in the sentence', state(res, 'templates/p.md') == merge.NO_GIT and (user / 'templates/p.md').read_text() == T
   and 'git is not installed' in line and 'Base:' in line and 'merge --accept templates/p.md' in line, line)

# ---- git cannot merge (binary): failed, said, nothing written
user, core = fresh('bin')
put(user / 'templates/b.bin', b'a\x00b\nmine\n')
put(user / '.base/templates/b.bin', b'a\x00b\nold\n')
put(core / 'templates/b.bin', b'a\x00b\nnew\n')
res = merge.run(user, core)
ok('binary: failed, your copy untouched', state(res, 'templates/b.bin') == merge.FAILED and (user / 'templates/b.bin').read_bytes() == b'a\x00b\nmine\n', res)

# ---- locales: key by key against the base
user, core = fresh('loc')
put(core / 'locales/it.json', json.dumps({'a': '1', 'b': '2new', 'c': '3new', 'd': '4', 'e': '5new'}))
put(user / '.base/locales/it.json', json.dumps({'a': '1', 'b': '2', 'c': '3', 'd': '4', 'e': '5'}))
put(user / 'locales/it.json', json.dumps({'a': 'X', 'b': '2mine', 'c': '3', 'd': '4mine', 'e': '5new'}))
res = merge.run(user, core)
x = next(x for x in res if x['rel'] == 'locales/it.json')
now = json.loads((user / 'locales/it.json').read_text(encoding='utf-8'))
ok('locales: b changed on both sides is a conflict, only b', x['state'] == merge.CONFLICT and x['keys'] == ['b'], x)
ok('locales: a and d (core untouched) and b (conflict) stay yours; c (yours was the old default) goes, the core wins; e (you already have the new value) goes',
   now == {'a': 'X', 'b': '2mine', 'd': '4mine'}, now)
ok('locales: the base waits while a key is open', json.loads((user / '.base/locales/it.json').read_text())['b'] == '2')
ok('locales: the sentence names the key and the file', 'keys b' in merge.sentence(x) and 'it.json' in merge.sentence(x), merge.sentence(x))
put(user / 'locales/it.json', json.dumps({'a': 'X', 'b': '2new'}))
res = merge.run(user, core)
ok('locales: once b equals the new value the conflict is gone and the base moves',
   state(res, 'locales/it.json') in (merge.CURRENT, merge.MERGED) and json.loads((user / '.base/locales/it.json').read_text())['b'] == '2new' and json.loads((user / 'locales/it.json').read_text()) == {'a': 'X'}, res)
put(user / 'locales/en.json', 'not json')
put(user / '.base/locales/en.json', json.dumps({'a': '1'}))
put(core / 'locales/en.json', json.dumps({'a': '2'}))
ok('locales: a file that is not json is said, not crashed on', state(merge.run(user, core), 'locales/en.json') == merge.FAILED)

# ---- apply=False writes nothing
user, core = fresh('dry')
put(user / 'templates/p.md', T)
put(user / '.base/templates/p.md', B)
put(core / 'templates/p.md', 'one\ntwo\nthree\nFOUR\n')
res = merge.run(user, core, apply=False)
ok('dry: says merged, writes nothing', state(res, 'templates/p.md') == merge.MERGED and (user / 'templates/p.md').read_text() == T and not (user / '.merged-backup').exists())

# ---- the command line: `merge.py --auto` (the SessionStart hook) says a conflict once; `chat.py merge` says it every time and exits 1
cfg = TMP / 'claude'
shutil.rmtree(cfg, ignore_errors=True)
plug = Path(SCRIPTS).parent
real = plug / 'guides' / 'lead-normal.md'
rel = 'guides/lead-normal.md'
u = cfg / 'chatroom' / 'user'
core_text = real.read_text(encoding='utf-8').replace('\r\n', '\n')
put(u / '.base' / rel, core_text + 'BASE-END\n')                      # the new core dropped the last line; you changed it
put(u / rel, (core_text + 'MINE-END\n').replace(core_text.splitlines()[0], 'MINE FIRST LINE', 1))
env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
py = [sys.executable, '-X', 'utf8']
a1 = subprocess.run([*py, str(Path(SCRIPTS) / 'merge.py'), '--auto'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
a2 = subprocess.run([*py, str(Path(SCRIPTS) / 'merge.py'), '--auto'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
ok('cli --auto: the notice comes the first time (exit 0, the hook never fails the session)', a1.returncode == 0 and 'Needs a merge' in a1.stdout and rel in a1.stdout, (a1.returncode, a1.stdout, a1.stderr))
ok('cli --auto: and not the second time, not even an empty line (the hook runs at every start)', a2.returncode == 0 and a2.stdout == '', (a2.returncode, a2.stdout, a2.stderr))
c1 = subprocess.run([*py, str(Path(SCRIPTS) / 'chat.py'), 'merge'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
ok('chat.py merge: says it every time, exit 1', c1.returncode == 1 and 'Needs a merge' in c1.stdout, (c1.returncode, c1.stdout, c1.stderr))
ok('cli: your copy is still the one in use', 'MINE-END' in (u / rel).read_text(encoding='utf-8'))
before = sorted(str(p) for p in u.rglob('*'))
c2 = subprocess.run([*py, str(Path(SCRIPTS) / 'chat.py'), 'merge', '--dry-run'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
ok('chat.py merge --dry-run: says it, writes nothing', c2.returncode == 1 and 'Needs a merge' in c2.stdout and sorted(str(p) for p in u.rglob('*')) == before, (c2.returncode, c2.stdout, c2.stderr))
c3 = subprocess.run([*py, str(Path(SCRIPTS) / 'chat.py'), 'merge', '--accept'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
ok('chat.py merge --accept with no file: the usage line, not a traceback', c3.returncode == 2 and 'Traceback' not in c3.stderr and '--accept' in c3.stderr, (c3.returncode, c3.stderr))
c4 = subprocess.run([*py, str(Path(SCRIPTS) / 'chat.py'), 'merge', '--accept', '../../../etc/passwd'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
ok('chat.py merge --accept of something that is not one of your copies: refused, nothing written', c4.returncode == 1 and sorted(str(p) for p in u.rglob('*')) == before, (c4.returncode, c4.stdout, c4.stderr))
# two sessions at once: one writer in the user layer; a lock left by a dead run is taken over after two minutes
lock = u / '.merge.lock'
lock.write_text('')
c5 = subprocess.run([*py, str(Path(SCRIPTS) / 'chat.py'), 'merge'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
c6 = subprocess.run([*py, str(Path(SCRIPTS) / 'merge.py'), '--auto'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
ok('merge while another one holds the lock: said, exit 1, the lock is not touched', c5.returncode == 1 and 'Another merge' in c5.stdout and lock.exists(), (c5.returncode, c5.stdout, c5.stderr))
ok('the hook meets the lock: silent, exit 0 (the other one will say it)', c6.returncode == 0 and c6.stdout.strip() == '' and lock.exists(), (c6.returncode, c6.stdout, c6.stderr))
os.utime(lock, (time.time() - 600, time.time() - 600))
c7 = subprocess.run([*py, str(Path(SCRIPTS) / 'chat.py'), 'merge'], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL)
ok('a lock older than two minutes is a dead run\'s: the merge goes on and leaves no lock', c7.returncode == 1 and 'Needs a merge' in c7.stdout and not lock.exists(), (c7.returncode, c7.stdout, c7.stderr))
with merge._lock(u):
    try:
        with merge._lock(u):
            nested = False
    except merge.Busy:
        nested = True
ok('lock: a second one inside the first is refused, and both are gone at the end', nested and not lock.exists())

# Windows answers "access denied", not "exists", to a process that creates the lock while the holder is deleting it (found with 4 merges at once on a
# loaded machine: 1 try in ~500 escaped _lock as PermissionError: a stderr line at SessionStart, a traceback for `chat.py merge`)
real_open, calls = os.open, []


def denied(times):
    def f(path, *a, **k):
        if str(path).endswith(merge.LOCK) and len(calls) < times:
            calls.append(1)
            raise PermissionError(13, 'access denied (the lock is being deleted)')
        return real_open(path, *a, **k)
    return f


def try_lock(times):
    calls.clear()
    os.open = denied(times)
    try:
        with merge._lock(u):
            return 'got it'
    except merge.Busy:
        return 'busy'
    except Exception as exc:
        return repr(exc)
    finally:
        os.open = real_open


once, always = try_lock(1), try_lock(99)
ok('lock (Windows): "access denied" once while the holder deletes it: a moment later the merge takes the lock, no error', os.name != 'nt' or (once == 'got it' and not lock.exists()), once)
ok('lock (Windows): "access denied" every time: it is a busy lock (silent for the hook), never an exception', os.name != 'nt' or always == 'busy', always)

# two runs that both saw the SAME old (dead) lock: B has looked and is slow, A takes the lock; B must not delete A's fresh one and walk in too
import pathlib      # noqa: E402
import threading    # noqa: E402
lock.write_bytes(b'')
os.utime(lock, (time.time() - 600, time.time() - 600))
b_looked, a_in, now_in, overlap, outcome = threading.Event(), threading.Event(), set(), [], {}
real_stat = pathlib.Path.stat


def slow_b(self, *a, **k):
    r = real_stat(self, *a, **k)
    if self.name == merge.LOCK and threading.current_thread().name == 'B' and not b_looked.is_set():
        b_looked.set()
        a_in.wait(1.5)                    # B saw the old lock; A gets the lock before B goes on
    return r


def run(who, hold):
    try:
        with merge._lock(u):
            now_in.add(who)
            if len(now_in) > 1:
                overlap.append(who)
            if who == 'A':
                a_in.set()
            time.sleep(hold)
            now_in.discard(who)
        outcome[who] = 'ran'
    except merge.Busy:
        outcome[who] = 'busy'
    except Exception as exc:
        outcome[who] = repr(exc)


pathlib.Path.stat = slow_b
try:
    tb = threading.Thread(target=run, args=('B', 0.2), name='B')
    ta = threading.Thread(target=lambda: (b_looked.wait(2), run('A', 0.8)), name='A')
    tb.start()
    ta.start()
    tb.join(10)
    ta.join(10)
finally:
    pathlib.Path.stat = real_stat
ok('lock: two runs that saw the same dead lock never write together (the one that came second is told "busy")', not overlap and outcome.get('A') == 'ran' and outcome.get('B') == 'busy', (overlap, outcome))
ok('lock: nothing left behind (no lock, no gate)', not lock.exists() and not (u / (merge.LOCK + '.steal')).exists())

# ---- the SessionStart hook of the plugin runs merge.py --auto (the command as hooks.json has it, in a shell)
hooks = json.loads((plug / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))['hooks']['SessionStart']
cmds = [x['command'] for g in hooks for x in g['hooks'] if 'merge.py' in x['command']]
ok('hook: SessionStart declares merge.py --auto after the recovery of hand edits (one command, in this order)', len(cmds) == 1 and cmds[0].index('manifest.py') < cmds[0].index('merge.py') and '--auto' in cmds[0], cmds)
(u / '.merge-notice.json').unlink()
bash = shutil.which('bash')                                                    # the hooks of the plugin are bash commands
h = subprocess.run([bash, '-c', cmds[0].replace('${CLAUDE_PLUGIN_ROOT}', Path(plug).as_posix())], capture_output=True, text=True, encoding='utf-8', env=env, stdin=subprocess.DEVNULL) if bash else None
ok('hook: the command runs (manifest.py may be absent), says the notice, exit 0', h is not None and h.returncode == 0 and 'Needs a merge' in h.stdout, h and (h.returncode, h.stdout, h.stderr))

# ---- the MCP launcher: registered once, it follows the installed version; an update needs no new registration
import doctor      # noqa: E402
cfg = TMP / 'claude2'
os.environ['CLAUDE_CONFIG_DIR'] = str(cfg)          # layers.py (when the copy has it) reads the environment, the fallback reads doctor.claude_dir
inst = cfg / 'plugins' / 'installed_plugins.json'


def install_at(ver):
    folder = TMP / 'cache' / ver
    put(folder / 'scripts' / 'chat.py', '# fake chat.py\n')
    put(inst, json.dumps({'plugins': {doctor.PLUGIN: [{'version': ver, 'installPath': str(folder)}]}}))
    return folder


stub = TMP / 'uvstub.py'
put(stub, 'import json, os, sys\nopen(os.path.join(os.path.dirname(__file__), "uvenv.txt"), "w").write(os.environ.get("UV_PROJECT_ENVIRONMENT", "NONE"))\nprint(json.dumps(sys.argv[1:]))\nsys.exit(7)\n')
uvcmd = TMP / ('uvstub.cmd' if os.name == 'nt' else 'uvstub')
put(uvcmd, f'@"{sys.executable}" "{stub}" %*\r\n' if os.name == 'nt' else f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@"\n')
uvcmd.chmod(0o755)
lenv = {**os.environ, 'CLAUDE_CONFIG_DIR': str(cfg), 'CHATROOM_UV': str(uvcmd), 'PYTHONIOENCODING': 'utf-8', 'UV_PROJECT_ENVIRONMENT': ''}
inst_r = subprocess.run([*py, str(Path(SCRIPTS) / 'mcp_launch.py'), '--install'], capture_output=True, text=True, encoding='utf-8', env=lenv, stdin=subprocess.DEVNULL)
launcher = cfg / 'chatroom' / 'bin' / 'mcp_launch.py'
ok('launcher: --install copies it where an update does not move it', inst_r.returncode == 0 and launcher.is_file() and launcher.read_bytes() == (Path(SCRIPTS) / 'mcp_launch.py').read_bytes(), (inst_r.returncode, inst_r.stdout, inst_r.stderr))
old = install_at('0.19.0')


def launch():
    r = subprocess.run([*py, str(launcher)], capture_output=True, text=True, encoding='utf-8', env=lenv, stdin=subprocess.DEVNULL)
    return r.returncode, (json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None), r.stderr


rc, args, err = launch()
ok('launcher: starts chat.py mcp of the installed version through uv, passes the exit code on', rc == 7 and args and args[-2:] == [str(old / 'scripts' / 'chat.py'), 'mcp'] and args[:5] == ['run', '--python', '3.14', '--project', str(old)], (rc, args, err))
uvenv = (TMP / 'uvenv.txt').read_text(encoding='utf-8')
ok('launcher: uv gets the environment folder of chat.py (not a .venv inside the plugin, which an update leaves behind)', Path(uvenv) == cfg / 'chatroom' / 'env', uvenv)
new = install_at('0.19.9')                                                   # the update: installed_plugins.json now names the new folder
rc, args, err = launch()
ok('launcher: after an update the same registration starts the new version', rc == 7 and args and args[4] == str(new) and args[-2] == str(new / 'scripts' / 'chat.py'), (rc, args, err))
inst.unlink()
rc, args, err = launch()
ok('launcher: plugin not installed: a clear line on stderr, exit 1, no traceback', rc == 1 and 'not installed' in err and 'Traceback' not in err, (rc, err))

# ---- doctor: an MCP registered with a versioned path is told to move to the launcher (the existing mcp_stale/mcp_ok lines stay); a launcher one is ok
fake = TMP / ('claude.cmd' if os.name == 'nt' else 'claude')


def fake_claude(*lines):
    body = ['echo chatroom:', 'echo   Status: Connected', *[f'echo {x}' for x in lines]]
    put(fake, '\r\n'.join(['@echo off', *body]) + '\r\n' if os.name == 'nt' else '#!/bin/sh\n' + '\n'.join(body) + '\n')
    fake.chmod(0o755)


src = TMP / 'src'
put(src / '.claude-plugin' / 'plugin.json', '{"version": "0.19.9"}')
doctor.claude_dir = lambda: cfg
os.environ['CHATROOM_CLAUDE'] = str(fake)
install_at('0.19.9')
fake_claude(f'  Args: run --project {new} python {new}/scripts/chat.py mcp', '  Environment:', '    UV_CACHE_DIR=D:/c')
res = {c: (st, f) for c, st, _, f in doctor.checks(None, None, src)}
ok('doctor: versioned registration that works now is ok, with the one-time launcher line beside it', res['mcp_ok'][0] == doctor.OK and res['mcp_launcher'][0] == doctor.WARN, res)
fix = res['mcp_launcher'][1]
ok('doctor: the launcher line is one command: install, remove, add with the environment kept and the stable path',
   'mcp_launch.py" --install' in fix and 'claude mcp remove chatroom -s user' in fix and '-e UV_CACHE_DIR=D:/c' in fix and 'chatroom/bin/mcp_launch.py' in fix and str(new) not in fix.split('claude mcp add')[1], fix)
fake_claude(f'  Args: run --no-project --python 3.14 python {cfg}/chatroom/bin/mcp_launch.py')
res = {c: (st, f) for c, st, _, f in doctor.checks(None, None, src)}
ok('doctor: registered through the launcher: ok, nothing to move', res['mcp_ok'][0] == doctor.OK and 'mcp_launcher' not in res and 'mcp_stale' not in res, res)
put(new / 'scripts' / 'mcp_launch.py', 'new launcher\n')
put(cfg / 'chatroom' / 'bin' / 'mcp_launch.py', 'old launcher\n')
res = {c: (st, f) for c, st, _, f in doctor.checks(None, None, src)}
ok('doctor: the launcher copy in bin/ is older than the installed one: a warning with the one command that copies it again', res.get('mcp_launcher_old', ('', ''))[0] == doctor.WARN and res['mcp_launcher_old'][1].endswith('mcp_launch.py" --install'), res.get('mcp_launcher_old'))
put(cfg / 'chatroom' / 'bin' / 'mcp_launch.py', 'new launcher\r\n')
res = {c: st for c, st, _, f in doctor.checks(None, None, src)}
ok('doctor: the same launcher (whatever the line ends): nothing said', 'mcp_launcher_old' not in res, res)

# ---- doctor: the user's copies (read only): a conflict is named, a clean merge waiting is said, nothing is written
u2 = cfg / 'chatroom' / 'user'
core2 = Path(SCRIPTS).parent
real_rel = 'templates/agent_prompt.md' if (core2 / 'templates' / 'agent_prompt.md').is_file() else 'guides/lead-normal.md'
cl = (core2 / real_rel).read_text(encoding='utf-8').replace('\r\n', '\n')
put(u2 / '.base' / real_rel, cl + 'BASE-END\n')
put(u2 / real_rel, (cl + 'MINE-END\n'))
before = sorted(str(p) for p in u2.rglob('*'))
res = {c: (st, f) for c, st, f_, f in doctor.checks(None, None, src)}
shown = doctor.render(doctor.checks(None, None, src), lambda k, **f: k + ' ' + json.dumps(f, ensure_ascii=False))
ok('doctor: a conflict with the new version is a warning that says needs a merge', res.get('merge_need', ('', ''))[0] == doctor.WARN and 'Needs a merge' in shown and real_rel in shown, shown)
ok('doctor: reads only (no .merged draft, no backup, nothing changed in the user layer)', sorted(str(p) for p in u2.rglob('*')) == before)
put(u2 / real_rel, cl.replace(cl.splitlines()[0], 'MINE FIRST LINE', 1) + 'BASE-END\n')          # you changed line 1, the core dropped the last line: clean
res = {c: (st, f) for c, st, _, f in doctor.checks(None, None, src)}
ok('doctor: a clean merge that is waiting is a warning with the command', res.get('merge_ready', ('', ''))[0] == doctor.WARN and 'merge' in res['merge_ready'][1], res)

# ---- doctor shows what manifest.py (recovery of hand edits) found: the contract is pending() and verify(folder)
import types      # noqa: E402
fake_m = types.ModuleType('manifest')
fake_m.pending = lambda: [{'ver': '0.18.0', 'rel': 'hooks/hooks.json', 'kind': 'config', 'why': 'core_changed'}]
fake_m.verify = lambda d: {'modified': ['scripts/chat.py'], 'added': [], 'removed': ['agents/x.md']}
had = sys.modules.get('manifest')
sys.modules['manifest'] = fake_m
try:
    res = {c: (st, f, fx) for c, st, f, fx in doctor.checks(None, None, src)}
    ok('doctor: a hand edit still to merge is a warning with its version, file and the list command', res.get('recover_pending', ('',))[0] == doctor.WARN and res['recover_pending'][1]['files'] == '0.18.0:hooks/hooks.json' and 'recover --list' in res['recover_pending'][2], res.get('recover_pending'))
    ok('doctor: an installed copy edited by hand is a warning naming the files', res.get('install_modified', ('',))[0] == doctor.WARN and res['install_modified'][1]['n'] == 2, res.get('install_modified'))
    fake_m.pending = lambda: [{'ver': '0.18.0', 'rel': '*', 'kind': 'all', 'why': 'no_reference'}]
    res = {c: fx for c, st, f, fx in doctor.checks(None, None, src)}
    ok('doctor: a whole old copy not compared yet (no manifest) points at the full recover, which has git', res.get('recover_pending', '').endswith('chat.py" recover'), res.get('recover_pending'))
    fake_m.pending, fake_m.verify = (lambda: []), (lambda d: None)
    res = {c: st for c, st, f, fx in doctor.checks(None, None, src)}
    ok('doctor: nothing to merge and no manifest: nothing said about hand edits', 'recover_pending' not in res and 'install_modified' not in res and 'recover_error' not in res, res)
finally:
    if had is None:
        del sys.modules['manifest']
    else:
        sys.modules['manifest'] = had

# ---- the whole way of an update, with manifest.py when this copy has it: a hand edit in the OLD installed folder survives
# the update (recover makes it your copy + its base), and the new version's own change comes in too (merge)
try:
    import manifest as M
except ImportError:
    M = None
    print('SKIP update end to end: this copy has no manifest.py')
if M:
    e2e = TMP / 'e2e'
    V1 = {'templates/room.md': 'one\ntwo\nthree\nfour\nfive\n', 'scripts/chat.py': 'print(1)\n'}          # lines next to each other changed on both sides are a conflict for git too

    def plant(root, files, version):
        for r, text in files.items():
            put(root / r, text)
        put(root / '.claude-plugin' / 'plugin.json', json.dumps({'name': 'chatroom', 'version': version}))

    old, cu = e2e / 'cache' / 'chatroom' / '0.19.8', e2e / 'user'
    plant(old, V1, '0.19.8')
    M.write(old)
    M.snapshot(old, cu)                                                                                          # what a session of that version did while the copy was untouched
    put(old / 'templates/room.md', 'one\ntwo\nthree\nfour MINE\nfive\n')                                         # you edit the installed copy by hand
    new = e2e / 'cache' / 'chatroom' / '1.0.0'
    plant(new, {**V1, 'templates/room.md': 'one NEW\ntwo\nthree\nfour\nfive\n'}, '1.0.0')                        # the update changes another line
    M.recover(new, user=cu, claude=e2e / 'claude')
    ok('update end to end: recover makes your edit your copy, with the original as its base', (cu / 'templates/room.md').read_text(encoding='utf-8') == 'one\ntwo\nthree\nfour MINE\nfive\n' and (cu / '.base/templates/room.md').read_text(encoding='utf-8') == V1['templates/room.md'])
    res = merge.run(cu, new)
    ok('update end to end: your change and the new version\'s both end up in your copy', state(res, 'templates/room.md') == merge.MERGED and (cu / 'templates/room.md').read_text(encoding='utf-8') == 'one NEW\ntwo\nthree\nfour MINE\nfive\n', (state(res, 'templates/room.md'), (cu / 'templates/room.md').read_text(encoding='utf-8')))
    ok('update end to end: the next session has nothing to merge', state(merge.run(cu, new), 'templates/room.md') == merge.CURRENT)
    old2, cu2 = e2e / 'cache2' / 'chatroom' / '0.19.8', e2e / 'user2'
    plant(old2, V1, '0.19.8')
    M.write(old2)
    M.snapshot(old2, cu2)
    put(old2 / 'templates/room.md', 'one\ntwo\nthree\nfour MINE\nfive\n')
    new2 = e2e / 'cache2' / 'chatroom' / '1.0.0'
    plant(new2, {**V1, 'templates/room.md': 'one\ntwo\nthree\nfour THEIRS\nfive\n'}, '1.0.0')                    # the update changes the same line
    M.recover(new2, user=cu2, claude=e2e / 'claude')
    res = merge.run(cu2, new2)
    ok('update end to end: the same line changed on both sides is not guessed: needs a merge, your copy still in use', state(res, 'templates/room.md') == merge.CONFLICT and (cu2 / 'templates/room.md').read_text(encoding='utf-8') == 'one\ntwo\nthree\nfour MINE\nfive\n' and (cu2 / 'templates/room.md.merged').is_file(), state(res, 'templates/room.md'))

shutil.rmtree(TMP, ignore_errors=True)
print('all passed' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
