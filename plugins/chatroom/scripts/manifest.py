"""The manifest of the plugin files, and the recovery of hand edits left in an old installed copy.

An update puts the new version in a new folder of the plugin cache and leaves the old one where it was, so a file edited
by hand in the old folder is not in the new one. manifest.json (one sha256 per file, made at release by `chat.py manifest
--write`) tells which files of an old folder were changed. `chat.py recover` copies them to <user>/recovered/<version>/,
puts the ones the plugin reads in layers (templates, guides, locales) back as overrides when the unmodified original is
known, and lists the rest as "to merge". An old version without manifest is compared with the git history of the
marketplace; with neither, it says so. Nothing is deleted and nothing in a plugin folder is written. Standard library only.

A hash is taken with the line ends of a text file turned into LF: a copy installed through git on Windows has CRLF."""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from doctor import claude_dir, version_of      # the doctor's: where Claude's folder is, and which version a plugin folder holds

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CMD = f'python "{HERE / "chat.py"}"'                  # the command the messages print, ready to copy (merge.py's way)
NAME = 'manifest.json'
HIST = 'history'                                                    # history/<version>.json: the hashes of the files of versions released before this one
HISTORY_KEEP = 8
MARKETPLACE, PLUGIN = 'artyomita-plugins', 'chatroom@artyomita-plugins'
SUB = 'plugins/chatroom'                                          # the plugin inside the marketplace repo
LAYERS = ('templates/', 'guides/', 'locales/')                    # what the plugin reads in layers (user over core)
CONFIG = ('hooks/', 'agents/', 'skills/', 'monitors/', '.claude-plugin/', '.codex-plugin/', '.mcp.json')   # Claude Code reads these


def norm(data):
    """a text file with LF line ends (a binary file as it is): the form that is hashed and that the layers hold"""
    return data if b'\0' in data else data.replace(b'\r\n', b'\n')


def sha_bytes(data):
    return hashlib.sha256(norm(data)).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


PRUNE = ('.git', '__pycache__', '.venv', 'node_modules')           # never the plugin's own files (uv puts a .venv in the folder when no environment is named)


def skipped(rel):
    return rel in (NAME, '.orphaned_at') or rel.endswith(('.pyc', '.pyo')) or any(x in PRUNE for x in rel.split('/')) or rel.startswith('scripts/rtk/')


def listing(root, use_git=False):
    """the files of a plugin folder (posix paths relative to it). use_git, for a release: what git tracks plus what is new and not
    ignored; else a walk (an installed copy is not a work tree)"""
    root, git = Path(root), shutil.which('git')
    if use_git and git:
        r = subprocess.run([git, '-C', str(root), 'ls-files', '-co', '--exclude-standard', '-z', '--', '.'], capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        if r.returncode == 0:
            return sorted(rel for rel in r.stdout.decode('utf-8').split('\0') if rel and (root / rel).is_file() and not skipped(rel))
    out = []
    for top, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in PRUNE]                    # a virtual environment is not walked at all
        out += [rel for rel in (Path(top, f).relative_to(root).as_posix() for f in files) if not skipped(rel)]
    return sorted(out)


def hashes_of(root):
    """{rel: sha} of a folder; the files are read side by side (opening a file is the slow part where a virus scanner looks at each)"""
    rels = listing(root)
    with ThreadPoolExecutor(8) as pool:
        return dict(zip(rels, pool.map(lambda r: sha(Path(root) / r), rels)))


def stat_sig(root):
    """a cheap signature of a folder: names, sizes and modification times, no file opened (an old copy is looked at again at every
    session start until Claude Code removes it; reading 200 files under a virus scanner takes seconds)"""
    items = []
    for rel in listing(root):
        try:
            st = (Path(root) / rel).stat()
            items.append((rel, st.st_size, st.st_mtime_ns))
        except OSError:
            items.append((rel, -1, 0))
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


def vkey(version):
    return tuple(int(x) for x in re.findall(r'\d+', version or '0'))[:3]


def load(root):
    try:
        data = json.loads((Path(root) / NAME).read_text(encoding='utf-8'))
        return data if isinstance(data.get('files'), dict) else None
    except (OSError, ValueError, AttributeError):
        return None


def build(root=ROOT, use_git=True):
    return {'schema': 1, 'version': version_of(root), 'hash': 'sha256, text files with LF line ends',
            'files': {rel: sha(Path(root) / rel) for rel in listing(root, use_git)}}


def write(root=ROOT):
    """release: history/ first (the manifest lists those files too), then manifest.json"""
    write_history(root)
    data = build(root)
    (Path(root) / NAME).write_bytes((json.dumps(data, indent=1, sort_keys=True) + '\n').encode('utf-8'))
    return data


def check(root=ROOT):
    """release gate: the manifest.json written is the one the tree gives now, and history/ is what git says of the versions before"""
    on = load(root)
    if not (bool(on) and on['files'] == build(root)['files'] and on.get('version') == version_of(root)):
        return False
    want = release_history(root)                                              # {} without git history: then history/ is not judged
    return not want or load_history(root) == {v: {r: [h] if isinstance(h, str) else h for r, h in f.items()} for v, f in want.items()}


def load_history(root):
    """{version: {rel: [sha, ...]}} of history/ in a plugin folder: the files of versions released before it, which have no manifest.json
    (0.18 and before). Several shas for a file: the contents it had while plugin.json named that version, newest first"""
    out = {}
    for f in sorted((Path(root) / HIST).glob('*.json')):
        d = _read_json(f)
        if isinstance(d, dict) and d.get('version') and isinstance(d.get('files'), dict):
            out[str(d['version'])] = {r: [h] if isinstance(h, str) else [x for x in h if isinstance(x, str)] for r, h in d['files'].items()}
    return out


def _git_out(repo, *args, data=None):
    kw = {'input': data} if data is not None else {'stdin': subprocess.DEVNULL}
    r = subprocess.run([shutil.which('git') or 'git', '-C', str(repo), *args], capture_output=True, timeout=300, **kw)
    return r.stdout if r.returncode == 0 else None


def _blobs(repo, ids):
    """{blob id: bytes}, one git call"""
    out, got, pos = _git_out(repo, 'cat-file', '--batch', data=''.join(i + '\n' for i in ids).encode()) or b'', {}, 0
    while pos < len(out):
        end = out.index(b'\n', pos)
        head = out[pos:end].split()
        if len(head) >= 3 and head[1] == b'blob':
            got[head[0].decode()] = out[end + 1:end + 1 + int(head[2])]
            end += int(head[2]) + 1
        pos = end + 1
    return got


def release_history(root=ROOT, keep=HISTORY_KEEP):
    """{version: {rel: sha or [sha, ...]}} of the last `keep` versions before this one, from the git history of the repo this plugin is in:
    for each version every content its files had while plugin.json named it (people updated at different commits), newest first.
    {} without git or without that history. Only a release runs this, never an installed copy"""
    root = Path(root)
    if not shutil.which('git'):
        return {}
    top = (_git_out(root, 'rev-parse', '--show-toplevel') or b'').decode().strip()
    sub = (_git_out(root, 'rev-parse', '--show-prefix') or b'').decode().strip().rstrip('/')
    if not top or not sub:
        return {}
    bumps = {}
    for c in (_git_out(top, 'log', '--first-parent', '--reverse', '--format=%H', '--', f'{sub}/.claude-plugin/plugin.json') or b'').decode().split():
        try:
            bumps[c] = json.loads(_git_out(top, 'show', f'{c}:{sub}/.claude-plugin/plugin.json'))['version']
        except (TypeError, ValueError, KeyError):
            pass
    windows, ver = {}, None
    for c in (_git_out(top, 'log', '--first-parent', '--reverse', '--format=%H', '--', sub) or b'').decode().split():
        ver = bumps.get(c, ver)
        if ver:
            windows.setdefault(ver, []).append(c)
    chosen = sorted((v for v in windows if vkey(v) < vkey(version_of(root))), key=vkey)[-keep:]
    trees = {}
    for v in chosen:
        for c in windows[v]:
            t = {}
            for ent in (_git_out(top, 'ls-tree', '-r', '-z', c, '--', sub) or b'').decode('utf-8', 'replace').split('\0'):
                meta, _, path = ent.partition('\t')
                bits = meta.split()
                if len(bits) == 3 and bits[1] == 'blob' and path.startswith(sub + '/') and not skipped(path[len(sub) + 1:]):
                    t[path[len(sub) + 1:]] = bits[2]
            trees[c] = t
    sha_of = {i: sha_bytes(d) for i, d in _blobs(top, sorted({b for t in trees.values() for b in t.values()})).items()}
    out = {}
    for v in chosen:
        files = {}
        for c in reversed(windows[v]):
            for rel, b in trees[c].items():
                if b in sha_of and sha_of[b] not in files.setdefault(rel, []):
                    files[rel].append(sha_of[b])
        out[v] = {r: h[0] if len(h) == 1 else h for r, h in sorted(files.items())}
    return out


def write_history(root=ROOT, keep=HISTORY_KEEP):
    """write history/<version>.json for the versions before this one (and drop the ones that fell out of `keep`); [] when git says nothing"""
    root = Path(root)
    new = release_history(root, keep)
    if not new:
        return []
    (root / HIST).mkdir(exist_ok=True)
    for f in (root / HIST).glob('*.json'):
        if f.stem not in new:
            f.unlink()
    for v, files in new.items():
        data = {'schema': 1, 'version': v, 'hash': 'sha256, text files with LF line ends', 'files': files}
        (root / HIST / f'{v}.json').write_bytes((json.dumps(data, indent=0, sort_keys=True) + '\n').encode('utf-8'))
    return sorted(new, key=vkey)


def verify(root):
    """{'modified', 'added', 'removed'} of a folder against its own manifest.json, or None when it has none"""
    man = load(root)
    if man is None:
        return None
    root = Path(root)
    files = man['files']
    return {'modified': sorted(r for r, h in files.items() if (root / r).is_file() and sha(root / r) != h),
            'removed': sorted(r for r in files if not (root / r).is_file()),
            'added': [r for r in listing(root) if r not in files]}


def user_root():
    try:
        import layers
        return Path(layers.user_root())
    except (ImportError, AttributeError):             # shortcut: layers.py (T19a) is the one that knows; this is its formula until it is merged
        return claude_dir() / 'chatroom' / 'user'


def kind_of(rel):
    return 'layer' if rel.startswith(LAYERS) else 'config' if rel.startswith(CONFIG) else 'code'


def olds(new_root=ROOT, cache=None):
    """[(version, folder)] of the copies of the plugin older than new_root, in the cache folder next to it"""
    new_root = Path(new_root).resolve()
    cache = Path(cache) if cache else new_root.parent
    found = [(version_of(d), d) for d in sorted(cache.iterdir()) if d.is_dir() and d.resolve() != new_root] if cache.is_dir() else []
    return sorted(((v, d) for v, d in found if v and vkey(v) < vkey(version_of(new_root))), key=lambda x: vkey(x[0]))


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None


def _repo(claude):
    """(git, folder of the marketplace repo), or (None, None) when there is no git or no repo to read"""
    git = shutil.which('git')
    mk = (_read_json(claude / 'plugins' / 'known_marketplaces.json') or {}).get(MARKETPLACE) or {}
    repo = Path(mk.get('installLocation') or claude / 'plugins' / 'marketplaces' / MARKETPLACE)
    return (git, repo) if git and (repo / SUB).is_dir() else (None, None)


def history(claude, rels):
    """{rel: set of git blob ids}: every version of those plugin files the marketplace ever released (one git call)"""
    git, repo = _repo(claude)
    if not git or not rels:
        return {}
    where = [f'{SUB}/{r}' for r in rels] if len(rels) <= 40 else [SUB]
    r = subprocess.run([git, '-C', str(repo), 'log', '--format=', '--raw', '--no-abbrev', '--no-renames', '--', *where], capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    out = {}
    for line in r.stdout.decode('utf-8', 'replace').splitlines() if r.returncode == 0 else []:
        meta, _, path = line.partition('\t')
        bits = meta.split()
        if meta.startswith(':') and len(bits) >= 4 and path.startswith(SUB + '/'):
            out.setdefault(path[len(SUB) + 1:], set()).update(bits[2:4])
    return out


def blob_ids(data):
    """the git blob ids a text file can have in a repo: with LF line ends, or committed with CRLF"""
    data = norm(data)
    return {hashlib.sha1(b'blob %d\0' % len(x) + x).hexdigest() for x in (data, data.replace(b'\n', b'\r\n'))}


def git_tree(claude, ver, commit=None):
    """({rel: bytes} of the plugin as it was at the version ver, 'git:<sha>', exact) from the marketplace repo, else (None, '', False).
    exact: the commit was named (--ref) or is the one Claude Code installed. Else it is the last one with that version in
    plugin.json: a later commit with no version change makes files look changed, so reference() checks them against the history"""
    git, repo = _repo(claude)
    if not git:
        return None, '', False

    def run(*args):
        r = subprocess.run([git, '-C', str(repo), *args], capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
        return r.stdout if r.returncode == 0 else None
    exact = bool(commit)
    if not commit:
        inst = ((_read_json(claude / 'plugins' / 'installed_plugins.json') or {}).get('plugins', {}).get(PLUGIN) or [{}])[0]
        if inst.get('version') == ver and inst.get('gitCommitSha'):
            commit, exact = inst['gitCommitSha'], True
        else:
            log = (run('log', '--format=%H', f'-S"version": "{ver}"', '--', f'{SUB}/.claude-plugin/plugin.json') or b'').decode().split()
            commit = (log[0] + '^' if len(log) > 1 else log[0]) if log else None
    full = (run('rev-parse', '--verify', str(commit) + '^{commit}') or b'').decode().strip() if commit else ''
    blob = run('archive', '--format=tar', full, SUB) if full else None
    if blob is None:
        return None, '', False
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        tree = {m.name[len(SUB) + 1:]: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile() and m.name.startswith(SUB + '/')}
    return tree, 'git:' + full[:10], exact


def reference(old, ver, user, claude, commit=None, git=True, hist=None):
    """(ref, hashes, get, past, alts): where the unmodified files of the old folder come from ('manifest', 'history:<ver>', 'git:<sha>'
    or 'none'), {rel: sha} of them, get(rel) -> the unmodified bytes or None (content is taken only when it matches the hash),
    past(rels) -> {rel: ids (sha or git blob ids) of every version the project released} when the reference is not exact (a guessed
    commit, or the history: a file that differs but was released is not an edit), else {}, and alts {rel: every sha the file may
    have had} for the history. hist: load_history() of the new plugin, used when the old copy has no manifest (0.18 and before: the
    marketplace clone Claude Code keeps is shallow, so git cannot tell). git=False: only the manifest, the history and the snapshot
    (the quick path of the session hook)"""
    man, box, alts = load(old), {}, {}
    hist = {} if (man or commit) else (hist or {})

    def tree():
        if 'v' not in box:
            box['v'] = git_tree(claude, ver, commit) if git else (None, '', False)
        return box['v']
    if man and not commit:
        hashes, ref = man['files'], 'manifest'
    elif ver in hist:
        alts = {r: set(h) for r, h in hist[ver].items() if h}
        hashes, ref = {r: h[0] for r, h in hist[ver].items() if h}, 'history:' + ver
    elif tree()[0] is not None:
        hashes, ref = {r: sha_bytes(b) for r, b in tree()[0].items() if not skipped(r)}, tree()[1]
    else:
        return 'none', {}, lambda rel: None, lambda rels: {}, {}

    def get(rel):
        want = alts.get(rel) or {hashes.get(rel)}
        for src in (lambda: _snap(user, ver, rel), lambda: (tree()[0] or {}).get(rel)):       # git is asked only when the snapshot has nothing
            data = src()
            if data is not None and sha_bytes(data) in want:
                return data
        return None

    def past(rels):
        if ref.startswith('history:'):
            return {r: {h for v in hist.values() for h in v.get(r, [])} for r in rels}
        return {} if ref == 'manifest' or tree()[2] else history(claude, rels)       # the manifest, or the commit that was installed, is exact
    return ref, hashes, get, past, alts


def _snap(user, ver, rel):
    try:
        return (Path(user) / '.pristine' / ver / rel).read_bytes()
    except OSError:
        return None


def snapshot(root=ROOT, user=None):
    """keep a copy of what the plugin reads in layers, taken from a folder that matches its manifest: the day an old copy was
    changed by hand, this is the unmodified original that the merge needs. Safe to repeat. Returns the files copied"""
    user, ver, man = Path(user or user_root()), version_of(root), load(root)
    n = 0
    for rel, h in (man or {}).get('files', {}).items():
        dst = Path(user) / '.pristine' / str(ver) / rel
        if rel.startswith(LAYERS) and not dst.exists() and (Path(root) / rel).is_file() and sha(Path(root) / rel) == h:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(root) / rel, dst)
            n += 1
    return n


def _activate(rel, data, base, user, in_core):
    """a changed file the plugin reads in layers becomes an override, with the unmodified original beside it as the base of
    the merge; (status, why). A file the user already overrides is never replaced"""
    dst, bdst = user / rel, user / '.base' / rel
    data, base = norm(data), base if base is None else norm(base)
    if rel.startswith('locales/') and base is not None:                       # a locale is overridden key by key
        try:
            new, old = json.loads(data.decode('utf-8-sig')), json.loads(base.decode('utf-8-sig'))
            overlay = {k: v for k, v in new.items() if old.get(k) != v}
            if not overlay:
                return 'same', ''
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps({**overlay, **(_read_json(dst) or {})}, indent=1, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
            if not bdst.exists():
                bdst.parent.mkdir(parents=True, exist_ok=True)
                bdst.write_bytes(base)
            return 'activated', ''
        except (ValueError, AttributeError):
            return 'to_merge', 'no_base'
    if dst.exists():
        if norm(dst.read_bytes()) == data:                                              # a first run cut short by the hook's time limit already did it
            return 'activated', ''
        return 'to_merge', 'override_exists'
    if base is None and in_core:                                              # without the original the new core would vanish silently
        return 'to_merge', 'no_base'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    if base is not None:
        bdst.parent.mkdir(parents=True, exist_ok=True)
        bdst.write_bytes(base)
    return 'activated', ''


def _index(user, ver, entry=None):
    path = user / 'recovered' / ver / 'index.json'
    if entry is None:
        return (_read_json(path) or {}).get('files', {})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def recover(new_root=ROOT, user=None, claude=None, cache=None, old=None, commit=None, dry=False, git=True, seconds=None, retry=True, git_max=None):
    """one entry per older copy: {'ver', 'dir', 'ref', 'files': {rel: {state, kind, sha, status, why}}}, with 'fresh' set when it
    was looked at now (a copy that did not change since the last time is not looked at again); with dry nothing is written;
    after `seconds` the copies not yet looked at wait for the next time (the newest are looked at first); a copy that git could
    not explain is asked again only with retry (the session hook does not: it would ask git again at every start); git_max: how
    many copies with no manifest may be compared with git (the others are left for `chat.py recover`, which has no limit)"""
    stop = time.monotonic() + seconds if seconds else None
    user, claude, new_root = Path(user or user_root()), Path(claude or claude_dir()), Path(new_root)
    out, used, hist = [], 0, load_history(new_root)
    for ver, d in ([(version_of(old), Path(old))] if old else reversed(olds(new_root, cache))):
        if stop and time.monotonic() > stop:
            break
        if git and git_max is not None and not load(d) and ver not in hist:       # the history needs no git
            if used >= git_max:
                continue
            used += 1
        last = _read_json(user / 'recovered' / ver / 'index.json') or {}
        seen = stat_sig(d)
        quiet = not commit and (last.get('ref') != 'none' or not git or (last.get('git') and not retry))      # a copy git could not explain is not asked again
        if quiet and last.get('stat') == seen:                                      # not a file of it was touched since the last time: nothing is opened
            out.append(last)
            continue
        here = hashes_of(d)
        sig = hashlib.sha256(json.dumps(sorted(here.items())).encode()).hexdigest()
        if quiet and last.get('sig') == sig:                                        # touched, not changed
            if not dry:
                _index(user, ver, {**last, 'stat': seen})
            out.append(last)
            continue
        ref, hashes, get, past, alts = reference(d, ver, user, claude, commit, git, hist)
        known = past([r for r in here if r in hashes and here[r] != hashes[r]])
        entry = {'ver': ver, 'dir': str(d), 'ref': ref, 'sig': sig, 'stat': seen, 'git': bool(git), 'files': {}}
        out.append(entry)
        prev = last.get('files', {})
        for rel in ([] if ref == 'none' else sorted(set(here) | set(hashes))):
            core = new_root / rel
            state = ('removed' if rel not in here and ref == 'manifest' and core.is_file() else   # a git tree has files an install never had
                     'added' if rel in here and rel not in hashes else 'modified' if rel in here and here[rel] != hashes.get(rel) else None)
            if not state or (state == 'modified' and ({here[rel]} | blob_ids((d / rel).read_bytes())) & known.get(rel, set())):
                continue
            e = {'state': state, 'kind': kind_of(rel), 'sha': here.get(rel), 'status': 'to_merge', 'why': 'no_base'}
            if rel in prev and prev[rel].get('sha') == e['sha'] and prev[rel].get('state') == state:
                entry['files'][rel] = prev[rel]                               # seen before: what was decided stays decided
            elif state == 'removed':
                e['why'] = 'removed'
            elif core.is_file() and sha(core) == e['sha']:
                e.update(status='same', why='')
            else:
                if not dry:
                    (user / 'recovered' / ver / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(d / rel, user / 'recovered' / ver / rel)
                base = get(rel) if e['kind'] == 'layer' else None
                if base is None and e['kind'] == 'layer' and core.is_file() and sha(core) in (alts.get(rel) or {hashes.get(rel)}):
                    base = core.read_bytes()                                  # the update did not touch it: the new core is the original
                if e['kind'] == 'layer' and (state == 'added' or base is not None):
                    if dry:                                                   # say what would happen, write nothing
                        e['status'], e['why'] = ('to_merge', 'override_exists') if (user / rel).exists() else ('activated', '')
                    else:
                        e['status'], e['why'] = _activate(rel, (d / rel).read_bytes(), base, user, core.is_file())
                else:
                    e['why'] = ('new_file' if state == 'added' and not core.is_file() else 'core_gone' if not core.is_file() else
                                'no_base' if e['kind'] == 'layer' and state == 'modified' and base is None else
                                'core_same' if sha(core) in (alts.get(rel) or {hashes.get(rel)}) else 'core_changed')
            entry['files'].setdefault(rel, e)
        if not dry:
            _index(user, ver, entry)
        entry['fresh'] = True
    if not dry and out:
        write_notes(user, new_root)
    return sorted(out, key=lambda e: vkey(e['ver']))


def pending(user=None):
    """[{'ver', 'rel', 'kind', 'why'}]: what is still to merge by hand (a recovered file the new version does not hold as it is);
    an old copy that cannot be compared is one line with rel '*'"""
    out = []
    for idx in sorted(Path(user or user_root()).glob('recovered/*/index.json')):
        d = _read_json(idx) or {}
        if d.get('ref') == 'none':
            out.append({'ver': d.get('ver'), 'rel': '*', 'kind': 'all', 'why': 'no_reference', 'dir': d.get('dir')})
        out += [{'ver': d.get('ver'), 'rel': r, 'kind': e['kind'], 'why': e.get('why', '')}
                for r, e in sorted(d.get('files', {}).items()) if e.get('status') == 'to_merge']
    return out


def done(ver, rel=None, user=None):
    """mark as merged by hand one file of a recovered version (or all of it); returns how many"""
    idx, n = Path(user or user_root()) / 'recovered' / ver / 'index.json', 0
    d = _read_json(idx)
    for r, e in (d or {}).get('files', {}).items():
        if rel in (None, r) and e.get('status') == 'to_merge':
            e['status'], n = 'done', n + 1
    if n:
        idx.write_text(json.dumps(d, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        write_notes(Path(user or user_root()), ROOT)
    return n


def write_notes(user, new_root):
    """<user>/recovered/RECOVER.md: for each recovered file what to do, with the command ready"""
    from i18n import say
    user, lines = Path(user), [say('recover.md.title'), '']
    for idx in sorted((user / 'recovered').glob('*/index.json')):
        d = _read_json(idx) or {}
        lines += [say('recover.md.version', ver=d.get('ver'), ref=d.get('ref'), dir=d.get('dir')), '']
        if d.get('ref') == 'none':
            lines += [say('recover.md.none'), f'    git diff --no-index "{d.get("dir")}" "{new_root}"', '']
        for rel, e in sorted(d.get('files', {}).items()):
            mine = user / 'recovered' / str(d.get('ver')) / rel
            lines.append(f'- {rel} ({e["state"]}, {e["status"]}' + (f', {e["why"]}' if e.get('why') else '') + ')')
            if e['status'] == 'to_merge' and e['state'] != 'removed':
                lines.append(f'    git diff --no-index "{new_root / rel}" "{mine}"')
        lines.append('')
    (user / 'recovered').mkdir(parents=True, exist_ok=True)
    (user / 'recovered' / 'RECOVER.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    from i18n import say, use
    use(None)
    p = argparse.ArgumentParser(prog='chat.py recover|manifest', description=__doc__.split('\n')[0])
    p.add_argument('what', nargs='?', default='recover', choices=['manifest', 'recover'])
    p.add_argument('--auto', action='store_true', help='recover: what the session hook runs: quick (git only for the newest copy with no manifest), silent unless there is news')
    p.add_argument('--write', action='store_true', help='manifest: write manifest.json of this plugin (at release)')
    p.add_argument('--check', action='store_true', help='manifest: exit 1 if manifest.json is not what the tree gives now')
    p.add_argument('--verify', metavar='DIR', help='manifest: list what in DIR differs from its own manifest.json')
    p.add_argument('--from', dest='old', metavar='DIR', help='recover: one older copy of the plugin (default: every older one in the cache)')
    p.add_argument('--cache', help='recover: the folder with the versions (default: the one next to this plugin)')
    p.add_argument('--ref', help='recover: the marketplace git commit the old copy came from (default: found by version)')
    p.add_argument('--dry-run', '--dry', action='store_true', help='recover: say what would be recovered, write nothing (--dry as in merge)')
    p.add_argument('--list', action='store_true', help='recover: only what is still to merge')
    p.add_argument('--done', metavar='VER[:REL]', help='recover: mark one recovered file (or a whole version) as merged by hand')
    a = p.parse_args(argv)
    if a.what == 'manifest':
        if a.verify:
            r = verify(a.verify)
            if r is None:
                print(say('manifest.none', dir=a.verify))
                return 1
            print(say('manifest.verified', dir=a.verify, m=len(r['modified']), a=len(r['added']), r=len(r['removed'])))
            for k in ('modified', 'added', 'removed'):
                print('\n'.join(f'  {k}: {x}' for x in r[k]))
            return 1 if any(r.values()) else 0
        if a.check:
            ok = check()
            print(say('manifest.fresh') if ok else say('manifest.stale'))
            return 0 if ok else 1
        d = write()
        print(say('manifest.written', n=len(d['files']), version=d['version']))
        if load_history(ROOT):
            print(say('manifest.history', versions=', '.join(sorted(load_history(ROOT), key=vkey))))
        return 0
    if a.done:
        ver, _, rel = a.done.partition(':')
        print(say('recover.done', n=done(ver, rel or None)))
        return 0
    if a.list:
        todo = pending()
        for t in todo:
            print(say('recover.pending', ver=t['ver'], rel=t['rel'], why=say('recover.why.' + (t['why'] or 'other'))))
            mine = user_root() / 'recovered' / str(t['ver']) / t['rel']
            if t['rel'] != '*' and mine.is_file() and (ROOT / t['rel']).is_file():
                print(f'    git diff --no-index "{ROOT / t["rel"]}" "{mine}"')
        if todo:
            print(say('recover.how', cmd=CMD, path=user_root() / 'recovered' / 'RECOVER.md', first=f"{todo[0]['ver']}:{todo[0]['rel']}"))
        return 1 if todo else 0
    if a.auto:
        try:                                                  # a session must never fail to start because of this
            found = [e for e in recover(ROOT, cache=a.cache, seconds=4, retry=False, git_max=1) if e.get('fresh')]   # git only for a copy without manifest (0.18)
            snapshot()
            n = [sum(1 for f in e['files'].values() if f['status'] == s) for e in found for s in ('activated', 'to_merge')]
            news = [e for e in found if any(f['status'] in ('activated', 'to_merge') for f in e['files'].values())]
            if sum(n):
                print(say('recover.auto', ver=news[-1]['ver'], act=sum(n[0::2]), mrg=sum(n[1::2]), cmd=CMD))
            blind = [e for e in found if e['ref'] == 'none']                 # no manifest and no git history: said once, then the copy is not asked again
            if blind:
                print(say('recover.unverifiable', ver=blind[-1]['ver'], dir=blind[-1]['dir']))
        except Exception as exc:                              # shortcut: said on stderr only, the hook ignores it
            print(f'recover --auto: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 0
    found = recover(ROOT, cache=a.cache, old=a.old, commit=a.ref, dry=a.dry_run)
    if not found:
        print(say('recover.no_old'))
    for e in found:
        if e['ref'] == 'none':
            print(say('recover.unverifiable', ver=e['ver'], dir=e['dir']))
            continue
        n = {s: sum(1 for f in e['files'].values() if f['status'] == s) for s in ('activated', 'to_merge', 'same')}
        print(say('recover.version', ver=e['ver'], ref=e['ref'], n=len(e['files']), act=n['activated'], mrg=n['to_merge'], same=n['same']))
    if not a.dry_run:
        n = snapshot()
        todo = pending()
        if found or todo:
            print(say('recover.notes', path=user_root() / 'recovered' / 'RECOVER.md'))
        return 1 if todo else 0
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['recover']))
