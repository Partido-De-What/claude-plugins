"""0.19.9 T19 end to end: an update that keeps what the user changed, or says plainly that a merge is needed.
A fake CLAUDE_CONFIG_DIR holds an old installed copy (0.18.0, files changed by hand, its manifest.json), the marketplace repo
the old copy came from, and the plugin under test as the new version. Run: python smoke_0199_update.py
(CHATROOM_SCRIPTS = the scripts folder of the tree to test, default: this file's parent; it needs layers.py, manifest.py and merge.py,
so against a tree without them the checks FAIL). Nothing real is read or written; no process is left running."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(os.environ.get('CHATROOM_SCRIPTS') or Path(__file__).resolve().parent.parent)
PLUGIN = SCRIPTS.parent
TMP = Path(tempfile.mkdtemp(prefix='smoke0199u_'))
CFG = TMP / 'claude'
ENV = {**os.environ, 'CLAUDE_CONFIG_DIR': str(CFG), 'HOME': str(TMP), 'USERPROFILE': str(TMP), 'CHATROOM_RELAUNCHED': '1', 'PYTHONUTF8': '1'}
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:600]}]'), flush=True)
    fails += not cond


def finish():
    shutil.rmtree(TMP, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))      # git's object files are read-only on Windows
    print('FAIL' if fails else 'ALL PASS', fails, flush=True)
    sys.exit(1 if fails else 0)


ok('T19 e2e: the tree has layers.py (the user layer)', (SCRIPTS / 'layers.py').is_file())
if not (SCRIPTS / 'layers.py').is_file():
    finish()
if not all((SCRIPTS / f).is_file() for f in ('manifest.py', 'merge.py')):      # fix-b alone has the layer but not the recovery and the merge
    print('SKIP T19 e2e: no manifest.py / merge.py in this tree; run it on the one with all of 0.19.9')
    finish()

version = json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']
CACHE = CFG / 'plugins' / 'cache' / 'artyomita-plugins' / 'chatroom'
NEW, OLD = CACHE / version, CACHE / '0.18.0'
MARKET = CFG / 'plugins' / 'marketplaces' / 'artyomita-plugins'
USER = CFG / 'chatroom' / 'user'
CHAT = NEW / 'scripts' / 'chat.py'
A, B, C, D = 'guides/lead-research.md', 'templates/help_lock.md', 'templates/it/help_lock.md', 'guides/it/lead-normal.md'
MINE = 'templates/my_own.md'


def run(*args, git=True, cwd=None):
    env = dict(ENV)
    if not git:                                   # a machine without git: the python folder is all the PATH there is
        env['PATH'] = str(Path(sys.executable).parent)
    r = subprocess.run([sys.executable, '-X', 'utf8', str(CHAT), *args], capture_output=True, text=True, encoding='utf-8', timeout=180,
                       env=env, stdin=subprocess.DEVNULL, cwd=str(cwd or TMP))
    return r


def lf(b):
    return b.replace(b'\r\n', b'\n')


def read(p):
    return lf(Path(p).read_bytes()).decode('utf-8')


def write(root, rel, text, crlf=False):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((text.replace('\n', '\r\n') if crlf else text).encode('utf-8'))


# ---- the world: the plugin under test is the new version in the cache; the old copy and the marketplace hold the originals
shutil.copytree(PLUGIN, NEW, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'node_modules', 'manifest.json'))
orig = {rel: read(NEW / rel) for rel in (A, B, C, D)}
for root in (OLD, MARKET / 'plugins' / 'chatroom'):
    write(root, '.claude-plugin/plugin.json', json.dumps({'name': 'chatroom', 'version': '0.18.0'}, indent=1) + '\n')
    for rel, text in orig.items():
        write(root, rel, text, crlf=root == OLD)          # an installed copy on Windows has CRLF
git = lambda *a: subprocess.run(['git', '-C', str(MARKET), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *a], capture_output=True, text=True, env=ENV)
git('init', '-q')
git('add', '-A')
ok('T19 e2e: the marketplace repo of the old version', git('commit', '-q', '-m', 'v0.18.0').returncode == 0)
sys.path.insert(0, str(SCRIPTS))
os.environ.update(CLAUDE_CONFIG_DIR=str(CFG), HOME=str(TMP), USERPROFILE=str(TMP))
import manifest      # noqa: E402
manifest.write(OLD)                                       # what a release does: the hashes of the files as they were shipped
hand = {A: orig[A] + '\nMY NOTE\n', B: orig[B] + '\nMY EXTRA LINE\n',
        C: 'MINE FIRST\n' + orig[C].split('\n', 1)[1], D: 'MY TOP\n' + orig[D]}
for rel, text in hand.items():
    write(OLD, rel, text, crlf=True)                      # the user edits the old installed copy by hand
core2 = {B: 'CORE ADDED LINE\n' + orig[B], C: 'CORE FIRST\n' + orig[C].split('\n', 1)[1], D: orig[D] + '\nCORE BOTTOM\n'}
for rel, text in core2.items():                           # the update: the core changes, A not at all
    write(NEW, rel, text, crlf=(rel == B))
write(USER, MINE, 'a file of the user with no core twin\n')
for lang in ('en', 'it'):
    run('init', '--room', str(TMP / f'room_{lang}'), '--participants', 'A,B', '--lang', lang)
helptext = lambda lang: run('help', 'lock', '--as', 'A', '--room', str(TMP / f'room_{lang}')).stdout
guide = lambda mode, lang='en': run('guide', mode, '--room', str(TMP / f'room_{lang}')).stdout

# ---- 1. recover: the hand edits come back as overrides, each with the unmodified original as its base
r = run('recover')
ok('T19 e2e: recover runs', r.returncode == 0, r.stdout + r.stderr)
for rel in (A, B, C, D):
    ok(f'T19 e2e: {rel} is an override with what the user wrote', (USER / rel).is_file() and read(USER / rel) == hand[rel], (r.stdout + r.stderr))
    ok(f'T19 e2e: {rel} has its original as base', (USER / '.base' / rel).is_file() and read(USER / '.base' / rel) == orig[rel])
ok('T19 e2e: the plugin reads the user\'s copy, not the core', 'MY EXTRA LINE' in helptext('en') and 'MY NOTE' in guide('research'), helptext('en')[:200])
ok('T19 e2e: the old folder is not touched', read(OLD / B) == hand[B])
ok('T19 e2e: the file of the user with no twin in the core stays', read(USER / MINE).startswith('a file of the user'))

# ---- 2. a machine with no git: nothing is lost, and it is said what to do
r = run('merge', git=False)
ok('T19 e2e: no git: it says so (exit 1), the override stays', r.returncode == 1 and 'git' in r.stdout.lower() and read(USER / B) == hand[B], r.stdout + r.stderr)
ok('T19 e2e: no git: the three files of the merge are named', B in r.stdout and str(USER / '.base' / B).replace('\\', '/') in r.stdout.replace('\\', '/'), r.stdout)

# ---- 3. with git: A (core unchanged) stays, B and D merge cleanly, C is a conflict that keeps the user's copy in use
r = run('merge')
ok('T19 e2e: a conflict makes merge exit 1', r.returncode == 1, r.stdout + r.stderr)
ok('T19 e2e: A stays as the user wrote it', read(USER / A) == hand[A])
for rel in (B, D):
    merged = read(USER / rel)
    ok(f'T19 e2e: {rel} keeps the user\'s change and takes the new core\'s', ('MY EXTRA LINE' in merged and 'CORE ADDED LINE' in merged) if rel == B else ('MY TOP' in merged and 'CORE BOTTOM' in merged), merged[:300])
    ok(f'T19 e2e: {rel} has a backup of what it was', any(p.name == Path(rel).name for p in (USER / '.merged-backup').rglob('*')) if (USER / '.merged-backup').is_dir() else False)
    ok(f'T19 e2e: {rel} has the new core as base', read(USER / '.base' / rel) == read(NEW / rel))
ok('T19 e2e: C: the user\'s copy is still the one in use, with no markers', read(USER / C) == hand[C] and '<<<<<<<' not in read(USER / C))
draft = USER / (C + '.merged')
ok('T19 e2e: C: the merge with markers is next to it', draft.is_file() and '<<<<<<<' in read(draft) and 'MINE FIRST' in read(draft) and 'CORE FIRST' in read(draft))
ok('T19 e2e: C: the conflict is said (needs a merge) with a command ready', C in r.stdout and 'merge --accept' in r.stdout, r.stdout)
ok('T19 e2e: the Italian room reads the user\'s copy of C', 'MINE FIRST' in helptext('it'), helptext('it')[:200])
ok('T19 e2e: the English room reads the merge of B', 'CORE ADDED LINE' in helptext('en') and 'MY EXTRA LINE' in helptext('en'))

# ---- 4. once: a session start (--auto) does not say it again
merged_b, merged_d = read(USER / B), read(USER / D)
r = run('merge', '--auto')
ok('T19 e2e: --auto says nothing the second time and never fails', r.returncode == 0 and r.stdout.strip() == '', r.stdout + r.stderr)
ok('T19 e2e: the second merge did not touch the merged files', read(USER / B) == merged_b and read(USER / C) == hand[C] and read(USER / D) == merged_d)

# ---- 5. the user resolves the conflict: accept refuses markers, then takes the resolved draft and moves the base
r = run('merge', '--accept', C)
ok('T19 e2e: accept refuses a draft that still has markers', r.returncode == 1 and read(USER / C) == hand[C], r.stdout + r.stderr)
write(USER, C + '.merged', 'RESOLVED FIRST\n' + orig[C].split('\n', 1)[1])
r = run('merge', '--accept', C)
ok('T19 e2e: accept takes the resolved draft', r.returncode == 0 and read(USER / C).startswith('RESOLVED FIRST') and not draft.exists(), r.stdout + r.stderr)
ok('T19 e2e: and the base is the new core', read(USER / '.base' / C) == read(NEW / C))
ok('T19 e2e: now there is nothing to merge', run('merge').returncode == 0)

# ---- 6. a second update: the core of A changes too; the user's note and the new text both stay
write(NEW, A, 'NEW CORE TOP\n' + orig[A])
r = run('merge')
ok('T19 e2e: second update: A merges cleanly', r.returncode == 0 and 'MY NOTE' in read(USER / A) and 'NEW CORE TOP' in read(USER / A), r.stdout + r.stderr)
ok('T19 e2e: second update: what was resolved stays resolved', read(USER / C).startswith('RESOLVED FIRST') and 'CORE ADDED LINE' in read(USER / B))
ok('T19 e2e: the user\'s own file is still there', read(USER / MINE).startswith('a file of the user'))
ok('T19 e2e: the guide the lead reads is the user\'s merged one', 'MY NOTE' in guide('research') and 'NEW CORE TOP' in guide('research'))

# ---- 7. an override made by hand (no base) and read once: the core it was read with is its base, so the next update merges it
E = 'guides/lead-normal.md'
write(USER, E, read(NEW / E) + '\nMY OWN LINE\n')
before = read(NEW / E)
ok('T19 e2e: a hand made override has no base yet', not (USER / '.base' / E).exists())
ok('T19 e2e: the lead reads the hand made override', 'MY OWN LINE' in guide('normal'))
ok('T19 e2e: the first read saved the core of that moment as its base', (USER / '.base' / E).is_file() and read(USER / '.base' / E) == before)
write(NEW, E, 'NEW CORE FIRST\n' + before)
r = run('merge')
ok('T19 e2e: then the update brings a line of the core: both are in the merge', r.returncode == 0 and 'MY OWN LINE' in read(USER / E) and 'NEW CORE FIRST' in read(USER / E), r.stdout + r.stderr)
ok('T19 e2e: and the lead reads both', 'MY OWN LINE' in guide('normal') and 'NEW CORE FIRST' in guide('normal'))
leftovers = [p for p in subprocess.run(['powershell', '-NoProfile', '-Command', f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{TMP.name}*' -and $_.ProcessId -ne $PID }} | Select-Object -ExpandProperty ProcessId"],
                                       capture_output=True, text=True).stdout.split() if p] if os.name == 'nt' else []
ok('T19 e2e: no process of the test is left running', not leftovers, leftovers)
finish()
