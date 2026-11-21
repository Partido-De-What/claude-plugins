"""0.19.9 T19b: the manifest of the plugin files and the recovery of hand edits from an old installed copy (manifest.py).
Everything runs in a temporary folder with its own fake Claude home and a fake marketplace repo; nothing real is read or written.
CHATROOM_RELEASE=1 also checks that manifest.json of this plugin is the one its files give now.   Run: python tools/smoke_0199_manifest.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199man_'))
C = BASE / 'claude'
os.environ['CLAUDE_CONFIG_DIR'] = str(C)
os.environ['HOME'] = os.environ['USERPROFILE'] = str(BASE / 'home')
sys.path.insert(0, SCRIPTS)
import manifest as M  # noqa: E402
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def plant(root, files, version):
    root = Path(root)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(text if isinstance(text, bytes) else text.encode('utf-8'))
    (root / '.claude-plugin').mkdir(exist_ok=True)
    (root / '.claude-plugin' / 'plugin.json').write_text(json.dumps({'name': 'chatroom', 'version': version}), encoding='utf-8')


V1 = {'templates/room.md': 'Room {{NAME}}\nline two\nline three\n', 'guides/lead.md': 'Lead guide\n', 'locales/it.json': '{\n "a.one": "uno",\n "a.two": "due"\n}\n',
      'hooks/hooks.json': '{"hooks": {}}\n', 'scripts/chat.py': 'print(1)\n', 'scripts/__pycache__/chat.pyc': 'junk', 'scripts/blob.bin': b'\0\1\2\r\n'}
user = BASE / 'user'

# 1. manifest: hashes ignore CRLF, skip the cache of Python, see a changed byte
pristine = BASE / 'cache' / 'chatroom' / '0.19.9'
plant(pristine, V1, '0.19.9')
data = M.write(pristine)
ok('manifest lists the files, not itself nor the python cache', set(data['files']) == {r for r in V1 if '__pycache__' not in r} | {'.claude-plugin/plugin.json'} and 'manifest.json' not in data['files'], data['files'].keys())
ok('verify of an untouched copy is clean', M.verify(pristine) == {'modified': [], 'removed': [], 'added': []}, M.verify(pristine))
ok('check: manifest.json is what the tree gives', M.check(pristine))
crlf = BASE / 'crlf'
shutil.copytree(pristine, crlf)
for rel in ('templates/room.md', 'scripts/chat.py'):
    (crlf / rel).write_bytes((crlf / rel).read_bytes().replace(b'\n', b'\r\n'))
ok('a copy with CRLF line ends is not "modified"; a binary file is hashed as it is', M.verify(crlf)['modified'] == [], M.verify(crlf))
snap_n = M.snapshot(pristine, user)
ok('snapshot keeps only what the plugin reads in layers, of a copy that matches its manifest', snap_n == 3 and (user / '.pristine/0.19.9/templates/room.md').is_file() and not (user / '.pristine/0.19.9/scripts').exists(), snap_n)

# 2. the user edits the installed copy by hand
old = BASE / 'cache' / 'chatroom' / '0.19.9'
(old / 'templates/room.md').write_text('Room {{NAME}}\nline two EDITED\nline three\n', encoding='utf-8')
(old / 'locales/it.json').write_text('{\n "a.one": "UNO MIO",\n "a.two": "due"\n}\n', encoding='utf-8')
(old / 'hooks/hooks.json').write_text('{"hooks": {"Stop": []}}\n', encoding='utf-8')
(old / 'scripts/chat.py').write_text('print(2)\n', encoding='utf-8')
(old / 'templates/mine.md').write_text('my own template\n', encoding='utf-8')
(old / 'guides/lead.md').unlink()
(old / '.orphaned_at').write_text('1794704038439', encoding='utf-8')              # Claude Code marks a superseded folder: not a change of the user
(old / 'scripts/__pycache__/other.pyc').write_text('x', encoding='utf-8')
(old / '.venv/Lib/site-packages/pkg').mkdir(parents=True)                         # uv puts an environment in the plugin folder when none is named
for n in range(3):
    (old / f'.venv/Lib/site-packages/pkg/m{n}.py').write_text('x', encoding='utf-8')
v = M.verify(old)
ok('verify names what was changed, added and removed', v == {'modified': ['hooks/hooks.json', 'locales/it.json', 'scripts/chat.py', 'templates/room.md'], 'removed': ['guides/lead.md'], 'added': ['templates/mine.md']}, v)

# 3. the new version: core changed room.md (clean merge possible) and chat.py; hooks.json and it.json as they were
new = BASE / 'cache' / 'chatroom' / '1.0.0'
plant(new, {**V1, 'templates/room.md': 'Room {{NAME}} NEW\nline two\nline three\n', 'scripts/chat.py': 'print(3)\n'}, '1.0.0')
res = M.recover(new, user=user, claude=C)
files = res[0]['files']
ok('one older copy found, compared by its manifest', len(res) == 1 and res[0]['ver'] == '0.19.9' and res[0]['ref'] == 'manifest', res)
ok('a layer file with a known original becomes an override; the base beside it is the unmodified original',
   files['templates/room.md']['status'] == 'activated'
   and (user / 'templates/room.md').read_text(encoding='utf-8') == 'Room {{NAME}}\nline two EDITED\nline three\n'
   and (user / '.base/templates/room.md').read_text(encoding='utf-8') == V1['templates/room.md'], files['templates/room.md'])
ok('a locale becomes an overlay with only the keys the user changed, the base is the whole unmodified file',
   json.loads((user / 'locales/it.json').read_text(encoding='utf-8')) == {'a.one': 'UNO MIO'} and (user / '.base/locales/it.json').read_text(encoding='utf-8') == V1['locales/it.json'], files['locales/it.json'])
ok('a file the user added in a layer folder is kept as an override (no core file to lose)', files['templates/mine.md']['status'] == 'activated' and (user / 'templates/mine.md').is_file(), files['templates/mine.md'])
ok('code and config are copied aside and listed as to merge, never activated',
   all(files[r]['status'] == 'to_merge' for r in ('scripts/chat.py', 'hooks/hooks.json')) and files['scripts/chat.py']['why'] == 'core_changed' and files['hooks/hooks.json']['why'] == 'core_same'
   and not (user / 'scripts').exists() and (user / 'recovered/0.19.9/scripts/chat.py').read_text(encoding='utf-8') == 'print(2)\n', files)
ok('a file the user deleted and the new version has again is reported', files['guides/lead.md']['state'] == 'removed' and files['guides/lead.md']['status'] == 'to_merge', files.get('guides/lead.md'))
ok('the unmodified files are not touched', 'templates/room.md' in files and 'scripts/blob.bin' not in files, list(files))
ok('a virtual environment inside the old folder is neither listed nor copied', not [r for r in files if '.venv' in r] and not (user / 'recovered/0.19.9/.venv').exists(), list(files))
pend = M.pending(user)
ok('pending lists the to-merge files, with the reason', {(p['rel'], p['why']) for p in pend} == {('scripts/chat.py', 'core_changed'), ('hooks/hooks.json', 'core_same'), ('guides/lead.md', 'removed')}, pend)
notes = (user / 'recovered/RECOVER.md').read_text(encoding='utf-8')
ok('RECOVER.md has the version and a ready command per file to merge', '0.19.9' in notes and 'git diff --no-index' in notes and 'scripts/chat.py' in notes, notes)
before = {p.relative_to(user).as_posix(): p.read_bytes() for p in user.rglob('*') if p.is_file()}
again = M.recover(new, user=user, claude=C)
after = {p.relative_to(user).as_posix(): p.read_bytes() for p in user.rglob('*') if p.is_file()}
ok('recovering again changes nothing, and a copy that did not change is not looked at again', before == after and not again[0].get('fresh') and res[0].get('fresh'), set(before) ^ set(after))
ok('done marks a file as merged and takes it out of pending', M.done('0.19.9', 'scripts/chat.py', user) == 1 and 'scripts/chat.py' not in {p['rel'] for p in M.pending(user)})

# 4. never replace an override the user already has; never activate without the original
user2 = BASE / 'user2'
(user2 / 'templates').mkdir(parents=True)
(user2 / 'templates/room.md').write_text('already mine\n', encoding='utf-8')
shutil.copytree(old, BASE / 'cache5' / 'chatroom' / '0.19.9')
new2 = BASE / 'cache5' / 'chatroom' / '1.0.1'
plant(new2, {**V1, 'locales/it.json': '{\n "a.one": "uno",\n "a.two": "due",\n "a.three": "tre"\n}\n'}, '1.0.1')
r2 = M.recover(new2, user=user2, claude=C)[0]['files']          # no snapshot in user2, and the core changed the locale: the original is not known
ok('an existing override stays as it is', (user2 / 'templates/room.md').read_text(encoding='utf-8') == 'already mine\n' and r2['templates/room.md']['status'] == 'to_merge' and r2['templates/room.md']['why'] == 'override_exists', r2['templates/room.md'])
ok('without the unmodified original a layer file is only kept aside, so the new core never vanishes silently',
   not (user2 / 'locales').exists() and r2['locales/it.json']['status'] == 'to_merge' and r2['locales/it.json']['why'] == 'no_base' and (user2 / 'recovered/0.19.9/locales/it.json').is_file(), r2['locales/it.json'])
(user2 / 'templates/room.md').write_text('Room {{NAME}}\nline two EDITED\nline three\n', encoding='utf-8')       # the same text already in place: a run cut short did it
(user2 / 'recovered/0.19.9/index.json').unlink()                                                                  # the index is the last thing written
r2b = M.recover(new2, user=user2, claude=C, old=BASE / 'cache5' / 'chatroom' / '0.19.9')[0]['files']
ok('an override that already holds the recovered text is not a merge to do (a run cut short by the hook time limit)', r2b['templates/room.md']['status'] == 'activated', r2b['templates/room.md'])
user5 = BASE / 'user5'                                          # no snapshot either, but this core did not touch the locale: it is the original
r5 = M.recover(new, user=user5, claude=C, old=BASE / 'cache5' / 'chatroom' / '0.19.9')[0]['files']
ok('when the update did not touch a file, the new core is its original and the edit becomes an override',
   r5['locales/it.json']['status'] == 'activated' and json.loads((user5 / 'locales/it.json').read_text(encoding='utf-8')) == {'a.one': 'UNO MIO'}, r5['locales/it.json'])

# 5. no manifest: the git history of the marketplace is the reference (what older versions have)
git = shutil.which('git')
if git:
    repo = BASE / 'market'
    G = [git, '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid']
    plant(repo / 'plugins/chatroom', V1, '0.18.0')
    subprocess.run([git, 'init', '-q', str(repo)], check=True)
    subprocess.run(G + ['add', '-A'], check=True)
    subprocess.run(G + ['commit', '-qm', 'chatroom 0.18.0'], check=True)
    (repo / 'plugins/chatroom/.claude-plugin/plugin.json').write_text(json.dumps({'name': 'chatroom', 'version': '0.18.9'}), encoding='utf-8')
    subprocess.run(G + ['commit', '-qam', 'chatroom 0.18.9'], check=True)      # 0.18.9: a version the shipped history/ does not list (C7 below)
    (repo / 'plugins/chatroom/.claude-plugin/plugin.json').write_text(json.dumps({'name': 'chatroom', 'version': '0.19.0'}), encoding='utf-8')
    subprocess.run(G + ['commit', '-qam', 'chatroom 0.19.0'], check=True)
    (C / 'plugins').mkdir(parents=True, exist_ok=True)
    (C / 'plugins/known_marketplaces.json').write_text(json.dumps({'artyomita-plugins': {'source': {'source': 'directory', 'path': str(repo)}, 'installLocation': str(repo)}}), encoding='utf-8')
    gold = BASE / 'cache3' / 'chatroom' / '0.18.0'
    plant(gold, {k: v for k, v in V1.items() if '__pycache__' not in k}, '0.18.0')
    for rel in ('templates/room.md', 'scripts/chat.py', 'locales/it.json'):                  # installed through git on Windows: CRLF
        (gold / rel).write_bytes((gold / rel).read_bytes().replace(b'\n', b'\r\n'))
    (gold / 'templates/room.md').write_bytes(b'Room {{NAME}}\r\nline two EDITED\r\nline three\r\n')
    gnew = BASE / 'cache3' / 'chatroom' / '0.19.9'
    plant(gnew, V1, '0.19.9')
    user3 = BASE / 'user3'
    r3 = M.recover(gnew, user=user3, claude=C)[0]
    ok('with no manifest the old copy is compared with the git history (the last commit with that version)', r3['ref'].startswith('git:'), r3['ref'])
    ok('only the real edit shows (CRLF is not a change); its base is the original from git',
       list(r3['files']) == ['templates/room.md'] and r3['files']['templates/room.md']['status'] == 'activated'
       and (user3 / '.base/templates/room.md').read_bytes() == V1['templates/room.md'].encode(), r3['files'])
    # the session hook on the real case (0.18 has no manifest): git is the reference, one line with the count, said once
    C7 = BASE / 'claude7'
    (C7 / 'plugins').mkdir(parents=True)
    shutil.copyfile(C / 'plugins/known_marketplaces.json', C7 / 'plugins/known_marketplaces.json')
    shutil.copytree(gold, BASE / 'cache7' / 'chatroom' / '0.18.9')      # the real chat.py runs here: the history/ it ships has 0.18.0, which would be the reference, not git
    (BASE / 'cache7' / 'chatroom' / '0.18.9' / '.claude-plugin' / 'plugin.json').write_text(json.dumps({'name': 'chatroom', 'version': '0.18.9'}), encoding='utf-8')
    env7 = {**os.environ, 'CLAUDE_CONFIG_DIR': str(C7), 'CHATROOM_LANG': 'en', 'CHATROOM_RELAUNCHED': '1'}
    cmd7 = [sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'recover', '--auto', '--cache', str(BASE / 'cache7' / 'chatroom')]
    first7 = subprocess.run(cmd7, capture_output=True, text=True, encoding='utf-8', env=env7)
    second7 = subprocess.run(cmd7, capture_output=True, text=True, encoding='utf-8', env=env7)
    ok('recover --auto on a copy with no manifest compares with git and says once how many changes it kept',
       first7.returncode == 0 and first7.stdout.count('\n') == 1 and 'updated from 0.18.9: 1 change(s)' in first7.stdout and second7.stdout == '' and second7.returncode == 0,
       (first7.stdout, first7.stderr, second7.stdout))
    ok('and the edit is an override with the original from git as its base',
       (C7 / 'chatroom/user/templates/room.md').read_bytes() == b'Room {{NAME}}\nline two EDITED\nline three\n'
       and (C7 / 'chatroom/user/.base/templates/room.md').read_bytes() == V1['templates/room.md'].encode(), list((C7 / 'chatroom/user').rglob('*')))
    # a commit that changed a file without changing the version: the guessed commit (the last one with that version) is newer than
    # the copy the user installed; the old file is a release of the project, not an edit
    m2 = BASE / 'market2'
    G2 = [git, '-C', str(m2), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid']
    plant(m2 / 'plugins/chatroom', {'templates/room.md': 'Room A\n', 'templates/other.md': 'other\n'}, '1.0.0')
    subprocess.run([git, 'init', '-q', str(m2)], check=True)
    subprocess.run(G2 + ['add', '-A'], check=True)
    subprocess.run(G2 + ['commit', '-qm', 'A'], check=True)
    (m2 / 'plugins/chatroom/templates/room.md').write_text('Room B better\n', encoding='utf-8')
    subprocess.run(G2 + ['commit', '-qam', 'B, same version'], check=True)
    (m2 / 'plugins/chatroom/.claude-plugin/plugin.json').write_text(json.dumps({'name': 'chatroom', 'version': '1.1.0'}), encoding='utf-8')
    subprocess.run(G2 + ['commit', '-qam', 'C, 1.1.0'], check=True)
    C9 = BASE / 'claude9'
    (C9 / 'plugins').mkdir(parents=True)
    (C9 / 'plugins/known_marketplaces.json').write_text(json.dumps({'artyomita-plugins': {'installLocation': str(m2)}}), encoding='utf-8')
    had = BASE / 'cache9' / 'chatroom' / '1.0.0'                                      # what the user installed: commit A
    plant(had, {'templates/room.md': 'Room A\n', 'templates/other.md': 'other\n'}, '1.0.0')
    now = BASE / 'cache9' / 'chatroom' / '1.1.0'
    plant(now, {'templates/room.md': 'Room B better\n', 'templates/other.md': 'other\n'}, '1.1.0')
    r9 = M.recover(now, user=BASE / 'user9', claude=C9)[0]
    ok('a file that is an older release of the project (the guessed commit is a later one) is not an edit and does not become an override',
       r9['ref'].startswith('git:') and r9['files'] == {} and not (BASE / 'user9/templates').exists(), r9)
    (had / 'templates/room.md').write_text('Room A mine\n', encoding='utf-8')
    r9b = M.recover(now, user=BASE / 'user9b', claude=C9)[0]
    ok('a real edit on that copy still shows', list(r9b['files']) == ['templates/room.md'] and r9b['files']['templates/room.md']['state'] == 'modified', r9b)
    first = subprocess.run([git, '-C', str(m2), 'rev-list', '--max-parents=0', 'HEAD'], capture_output=True, text=True).stdout.split()[0]     # commit A
    (C9 / 'plugins/installed_plugins.json').write_text(json.dumps({'plugins': {'chatroom@artyomita-plugins': [{'version': '1.0.0', 'gitCommitSha': first}]}}), encoding='utf-8')
    asked = []
    real_history, M.history = M.history, lambda claude, rels: asked.append(1) or {}
    r9c = M.recover(now, user=BASE / 'user9c', claude=C9)[0]
    M.history = real_history
    ok('the commit Claude Code installed is exact: the edit is based on that very file and the history is not read',
       list(r9c['files']) == ['templates/room.md'] and (BASE / 'user9c/.base/templates/room.md').read_bytes() == b'Room A\n' and not asked, (r9c, asked))
    two = BASE / 'cache10' / 'chatroom'                                              # git_max: only the newest copy with no manifest goes to git
    shutil.copytree(gold, two / '0.18.0')
    plant(two / '0.17.0', V1, '0.17.0')
    r10 = M.recover(gnew, user=BASE / 'user10', claude=C, cache=two, git_max=1)
    ok('git_max: only the newest copy with no manifest is compared with git, the older one is left alone (no entry, nothing pending)',
       [e['ver'] for e in r10] == ['0.18.0'] and not (BASE / 'user10/recovered/0.17.0').exists() and not any(t['ver'] == '0.17.0' for t in M.pending(BASE / 'user10')), r10)
else:
    print('SKIP git reference (git not found)')

# 5b. the real 0.18 case: no manifest in the old copy, and the marketplace clone Claude Code keeps is shallow (git cannot say what the old
# copy was). history/<version>.json, shipped with the new plugin, holds the hashes of what was released: edits are found without git.
H1 = {'templates/room.md': 'Room {{NAME}}\nline two\nline three\n', 'guides/lead.md': 'Lead guide\n', 'hooks/hooks.json': '{"hooks": {}}\n',
      'scripts/mine.py': 'print(1)\n', 'scripts/blob.bin': b'\0\1\2\r\n'}
pr18 = BASE / 'cache11a' / 'chatroom' / '0.18.0'                                         # what 0.18.0 shipped
plant(pr18, H1, '0.18.0')
hroot = BASE / 'cache11' / 'chatroom' / '0.19.9'                                         # the new version: a copy of the real scripts (the hook runs them) and its locales
plant(hroot, {**H1, 'templates/room.md': 'Room {{NAME}}\nline two NEW\nline three\n'}, '0.19.9')
shutil.copytree(SCRIPTS, hroot / 'scripts', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '.venv', 'tools'))
(hroot / 'locales').mkdir(exist_ok=True)
for loc in ('en.json', 'it.json'):
    shutil.copyfile(Path(SCRIPTS).parent / 'locales' / loc, hroot / 'locales' / loc)
hist18 = M.hashes_of(pr18)
hist18['scripts/mine.py'] = [hist18['scripts/mine.py'], M.sha_bytes(b'print(0)\n')]       # two contents while the version was 0.18.0: people updated at different commits
(hroot / 'history').mkdir()
(hroot / 'history' / '0.18.0.json').write_text(json.dumps({'schema': 1, 'version': '0.18.0', 'files': hist18}), encoding='utf-8')
h18 = BASE / 'cache11' / 'chatroom' / '0.18.0'
shutil.copytree(pr18, h18)
(h18 / 'templates/room.md').write_text('Room {{NAME}}\nline two EDITED\nline three\n', encoding='utf-8')     # a layer file the new version changed too: no original to merge with
(h18 / 'guides/lead.md').write_text('Lead guide MINE\n', encoding='utf-8')                  # a layer file the new version did not touch: the new core is the original
(h18 / 'hooks/hooks.json').write_text('{"hooks": {"Stop": []}}\n', encoding='utf-8')         # not read in layers
(h18 / 'scripts/mine.py').write_text('print(0)\n', encoding='utf-8')                       # the other content of the version: released, not an edit
(h18 / 'scripts/extra.py').write_text('print("mine")\n', encoding='utf-8')
user11 = BASE / 'user11'
r11 = M.recover(hroot, user=user11, claude=BASE / 'claude-nogit', old=h18)[0]
st11 = {r: (f['state'], f['status'], f['why']) for r, f in r11['files'].items()}
ok('history/<version>.json is the reference of an old copy with no manifest, git is not needed', r11['ref'] == 'history:0.18.0', r11['ref'])
ok('only the real edits show: a content the version had at another commit is not one',
   st11 == {'templates/room.md': ('modified', 'to_merge', 'no_base'), 'guides/lead.md': ('modified', 'activated', ''), 'hooks/hooks.json': ('modified', 'to_merge', 'core_same'),
            'scripts/extra.py': ('added', 'to_merge', 'new_file')}, st11)
ok('a layer file the update did not touch becomes an override (the new core is its original); one it changed does not, and is kept aside',
   (user11 / 'guides/lead.md').read_text(encoding='utf-8') == 'Lead guide MINE\n' and not (user11 / 'templates/room.md').exists()
   and (user11 / 'recovered/0.18.0/templates/room.md').read_text(encoding='utf-8') == 'Room {{NAME}}\nline two EDITED\nline three\n', list(user11.rglob('*')))
opened = []
real_hashes, M.hashes_of = M.hashes_of, lambda root: opened.append(str(root)) or real_hashes(root)
M.recover(hroot, user=user11, claude=BASE / 'claude-nogit', old=h18)
ok('an old copy that was not touched since the last time is not read again (the hook runs at every start): no file opened', opened == [], opened)
os.utime(h18 / 'guides/lead.md', None)                                                 # touched, same content
M.recover(hroot, user=user11, claude=BASE / 'claude-nogit', old=h18)
n_touch = len(opened)
M.recover(hroot, user=user11, claude=BASE / 'claude-nogit', old=h18)
ok('touched but not changed: read once, then not again', n_touch == 1 and len(opened) == 1, opened)
(h18 / 'guides/lead.md').write_text('Lead guide MINE AGAIN\n', encoding='utf-8')
r11c = M.recover(hroot, user=user11, claude=BASE / 'claude-nogit', old=h18)[0]
M.hashes_of = real_hashes
ok('a change after that is seen', len(opened) == 2 and r11c['files']['guides/lead.md']['sha'] == M.sha_bytes(b'Lead guide MINE AGAIN\n'), (opened, r11c['files'].get('guides/lead.md')))
(h18 / 'guides/lead.md').write_text('Lead guide MINE\n', encoding='utf-8')
if git:
    shallow = BASE / 'market-shallow'                                                    # what Claude Code keeps: one commit, the old one is not in it
    subprocess.run([git, 'clone', '-q', '--depth', '1', repo.as_uri(), str(shallow)], check=True, capture_output=True)
    ok('setup: the marketplace clone is shallow and cannot tell 0.18.0', (shallow / '.git/shallow').is_file()
       and not subprocess.run([git, '-C', str(shallow), 'log', '--format=%H', '-S"version": "0.18.0"', '--', 'plugins/chatroom/.claude-plugin/plugin.json'], capture_output=True, text=True).stdout.strip())
    C12 = BASE / 'claude12'
    (C12 / 'plugins').mkdir(parents=True)
    (C12 / 'plugins/known_marketplaces.json').write_text(json.dumps({'artyomita-plugins': {'installLocation': str(shallow)}}), encoding='utf-8')
    r12 = M.recover(hroot, user=BASE / 'user12', claude=C12, old=h18)[0]
    ok('with that shallow clone the result is the same as without git', r12['ref'] == 'history:0.18.0' and {r: (f['state'], f['status'], f['why']) for r, f in r12['files'].items()} == st11, r12)
env12 = {**os.environ, 'CLAUDE_CONFIG_DIR': str(BASE / 'claude12h'), 'CHATROOM_LANG': 'en', 'CHATROOM_RELAUNCHED': '1', 'PATH': str(Path(sys.executable).parent)}   # no git on the path
(BASE / 'claude12h').mkdir()
cmd12 = [sys.executable, str(hroot / 'scripts' / 'chat.py'), 'recover', '--auto', '--cache', str(BASE / 'cache11' / 'chatroom')]
first12 = subprocess.run(cmd12, capture_output=True, text=True, encoding='utf-8', env=env12)
second12 = subprocess.run(cmd12, capture_output=True, text=True, encoding='utf-8', env=env12)
ok('the session hook with no git and no manifest: one line, with the command to type, once',
   first12.returncode == 0 and first12.stdout.count('\n') == 1 and 'updated from 0.18.0: 1 change(s)' in first12.stdout and '3 need a merge by hand' in first12.stdout
   and 'chat.py"' in first12.stdout and 'recover --list' in first12.stdout and second12.stdout == '', (first12.stdout, first12.stderr, second12.stdout))
lst12 = subprocess.run([sys.executable, str(hroot / 'scripts' / 'chat.py'), 'recover', '--list'], capture_output=True, text=True, encoding='utf-8', env=env12)
ok('recover --list gives, under each file, the command that compares it with this version, and how to close it',
   lst12.returncode == 1 and lst12.stdout.count('git diff --no-index') == 2 and 'hooks' in lst12.stdout and 'recover --done' in lst12.stdout     # the added file has no counterpart to compare with
   and str((hroot / 'templates' / 'room.md').resolve()) in lst12.stdout, lst12.stdout)
if git:
    # the release: history/ is made from git (every content a file had while plugin.json named the version), written with the manifest, and checked with it
    rel_root = m2 / 'plugins' / 'chatroom'
    hh = M.release_history(rel_root)
    ok('release_history: the versions before this one, every content of a file newest first, the current version not in it',
       list(hh) == ['1.0.0'] and hh['1.0.0']['templates/room.md'] == [M.sha_bytes(b'Room B better\n'), M.sha_bytes(b'Room A\n')]
       and hh['1.0.0']['templates/other.md'] == M.sha_bytes(b'other\n'), hh)
    M.write(rel_root)
    hf = json.loads((rel_root / 'history/1.0.0.json').read_text(encoding='utf-8'))
    ok('write: history/<version>.json is written, and the manifest lists it', hf['version'] == '1.0.0' and 'history/1.0.0.json' in M.load(rel_root)['files'] and M.load_history(rel_root)['1.0.0']['templates/room.md'][0] == M.sha_bytes(b'Room B better\n'))
    ok('check: manifest and history/ are what the tree and git give', M.check(rel_root))
    (rel_root / 'history/1.0.0.json').write_text(json.dumps({**hf, 'files': {**hf['files'], 'templates/room.md': 'x' * 64}}), encoding='utf-8')
    (rel_root / 'manifest.json').write_text(json.dumps(M.build(rel_root)), encoding='utf-8')            # the manifest is fresh, only history/ is wrong
    ok('check: a history/ that git does not confirm is not released', not M.check(rel_root))

# 6. nothing to compare with: said, not silent
lone = BASE / 'cache4' / 'chatroom' / '0.12.1'
plant(lone, V1, '0.12.1')
shutil.rmtree(C / 'plugins')
nnew = BASE / 'cache4' / 'chatroom' / '99.0.0'          # a version no real history/ holds (0.19.9 is in it since 1.0.0)
plant(nnew, V1, '99.0.0')
user4 = BASE / 'user4'
r4 = M.recover(nnew, user=user4, claude=C)[0]
ok('an old copy with no manifest and no git history is reported as not comparable and copies nothing',
   r4['ref'] == 'none' and r4['files'] == {} and not (user4 / 'recovered/0.12.1/scripts').exists() and M.pending(user4)[0]['rel'] == '*', (r4, M.pending(user4)))

# 7. the command line and the release gate
env = {**os.environ, 'CLAUDE_CONFIG_DIR': str(C), 'CHATROOM_LANG': 'en', 'CHATROOM_RELAUNCHED': '1'}      # relaunched: it needs no package, and a fake config dir would build a whole uv environment
out = subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'manifest', '--verify', str(old)], capture_output=True, text=True, encoding='utf-8', env=env)
ok('chat.py manifest --verify lists the changes and exits 1', out.returncode == 1 and 'modified: scripts/chat.py' in out.stdout, (out.returncode, out.stdout, out.stderr))
out = subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'recover', '--dry-run', '--cache', str(BASE / 'cache4')], capture_output=True, text=True, encoding='utf-8', env=env)
ok('chat.py recover --dry-run runs without a room and writes nothing', out.returncode == 0 and not (C / 'chatroom').exists(), (out.returncode, out.stdout, out.stderr))
p6 = BASE / 'cache6' / 'chatroom' / '0.19.0'                       # the session hook: quick, silent unless there is news
plant(p6, {'templates/room.md': 'Room\n'}, '0.19.0')
M.write(p6)
M.snapshot(p6, C / 'chatroom' / 'user')
(p6 / 'templates/room.md').write_text('Room mine\n', encoding='utf-8')
cmd = [sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'recover', '--auto', '--cache', str(BASE / 'cache6' / 'chatroom')]
first = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env)
second = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env)
ok('recover --auto tells once that a change was kept, then stays silent', first.returncode == 0 and 'updated from 0.19.0: 1 change' in first.stdout and second.stdout == '' and second.returncode == 0
   and (C / 'chatroom/user/templates/room.md').read_text(encoding='utf-8') == 'Room mine\n', (first.stdout, first.stderr, second.stdout))
C8 = BASE / 'claude8'                                               # no manifest and no marketplace repo: said once, not asked again
C8.mkdir()
env8 = {**env, 'CLAUDE_CONFIG_DIR': str(C8)}
cmd8 = [sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'recover', '--auto', '--cache', str(BASE / 'cache4' / 'chatroom')]
first8 = subprocess.run(cmd8, capture_output=True, text=True, encoding='utf-8', env=env8)
second8 = subprocess.run(cmd8, capture_output=True, text=True, encoding='utf-8', env=env8)
ok('recover --auto with nothing to compare with says so once, in one line, then stays silent',
   first8.returncode == 0 and first8.stdout.count('\n') == 1 and 'no manifest.json' in first8.stdout and second8.stdout == '' and second8.returncode == 0,
   (first8.stdout, first8.stderr, second8.stdout))
hooks = json.loads((Path(SCRIPTS).parent / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))['hooks']['SessionStart']
recover_hook = [h for g in hooks for h in g['hooks'] if 'manifest.py' in h['command'] and 'recover --auto' in h['command']]
ok('the session hook that recovers hand edits has time for a first start on a slow disk (the first start measured 7 s loaded, hashing 200 files under a virus scanner)',
   len(recover_hook) == 1 and recover_hook[0].get('timeout', 0) >= 30, recover_hook)
if os.environ.get('CHATROOM_RELEASE'):
    ok('release: manifest.json and history/ of this plugin are the ones its files and git give now (python chat.py manifest --write)', M.check(Path(SCRIPTS).parent))
    ok('release: history/0.18.0.json is shipped (the version the users have, and has no manifest.json)', (Path(SCRIPTS).parent / 'history' / '0.18.0.json').is_file())

print('ALL PASS' if not fails else f'{fails} FAIL', 'exit', 1 if fails else 0)
shutil.rmtree(BASE, ignore_errors=True)
sys.exit(1 if fails else 0)
