"""chat.py merge: after an update, what the user changed meets the new version, and nothing is lost in silence.

The user layer (layers.py: <claude dir>/chatroom/user) holds the user's own copies of templates/, guides/ and locales/. Next to
each one, .base/<rel> is the copy of the core file it started from. After an update the core of some files is new, so for
each override:
  - still equal to its base (never edited): the override goes away, the new core is used;
  - the core did not change: nothing to do;
  - both changed: `git merge-file` merges them. Clean: the override becomes the merge, the old override is kept in
    .merged-backup/, the base becomes the new core. Conflict: the old override stays in use, the merge with markers is
    written next to it as <rel>.merged, and the plugin says "needs a merge" once per version of the core, with the command
    ready; `chat.py merge --accept REL` closes it.
locales/<lang>.json overrides are merged key by key against the same base (kept as a whole file).
Line endings are compared and merged as LF: a CRLF checkout of the core must not conflict on every line.
git is needed only when both sides changed a text file; without it the plugin says so and gives the three paths.
Standard library only."""
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = ('templates', 'guides', 'locales')          # what the reader (layers.py) can take from the user layer
BASE, BACKUP, NOTICE, LOCK, STATE = '.base', '.merged-backup', '.merge-notice.json', '.merge.lock', '.merge-state.json'
CURRENT, NEW_BASE, ADOPTED, MERGED, ACCEPTED = 'current', 'new_base', 'adopted', 'merged', 'accepted'
CONFLICT, NO_GIT, FAILED, GONE, MARKERS, NO_BASE = 'conflict', 'no_git', 'failed', 'gone', 'markers', 'no_base'
NEED = (CONFLICT, NO_GIT, FAILED, GONE, NO_BASE)    # the user must do something
MARKER = re.compile(rb'^(<<<<<<<|>>>>>>>) ', re.M)


HARD_STALE = 3600       # a lock this old goes even when its pid runs: the number may be another process's by now


class Busy(Exception):
    """another merge is writing in the user layer right now"""


def _holder_runs(path):
    """the lock names a pid (the holder's) and that process still runs; a lock with no pid (an older version's) says nothing"""
    try:
        pid = int(path.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return False
    from chat import pid_alive      # the same check machine.py and lessons.py use (a process we may not query counts as running)
    return pid_alive(pid)


def _steal(path, stale):
    """remove a dead run's lock, one process at a time and looking at it again under that turn: two that both saw it old would
    otherwise be able to delete each other's fresh lock and both write (a gate left by a dead one goes after 10 s)"""
    gate = path.with_name(LOCK + '.steal')
    try:
        os.close(os.open(gate, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except (FileExistsError, PermissionError):
        try:
            if time.time() - gate.stat().st_mtime > 10:
                gate.unlink()
        except (FileNotFoundError, PermissionError):
            pass
        raise Busy
    try:
        age = time.time() - path.stat().st_mtime
        if age >= HARD_STALE or (age >= stale and not _holder_runs(path)):      # a slow merge that still runs keeps its lock
            path.unlink()
        else:
            raise Busy
    finally:
        gate.unlink(missing_ok=True)


@contextlib.contextmanager
def _lock(user, stale=120):
    """one writer at a time in the user layer (two sessions started together would see a half-merged copy and call it a conflict):
    the lock file is made exclusively and holds the pid of its writer; one older than `stale` seconds whose writer no longer runs
    (or with no pid) is a dead run's, and any one older than HARD_STALE"""
    path = Path(user) / LOCK
    for _ in range(3):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except (FileExistsError, PermissionError) as exc:
            if isinstance(exc, PermissionError) and os.name != 'nt':      # Windows says "access denied" (not "exists") while the holder is deleting it
                raise
            try:
                if time.time() - path.stat().st_mtime < stale:
                    raise Busy
                _steal(path, stale)
            except (FileNotFoundError, PermissionError):                  # gone, or going: look again in a moment
                time.sleep(0.05)
    else:
        raise Busy
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def roots():
    """(user layer, core): the reader's roots (layers.py), the core being the plugin's own folder"""
    import layers
    return Path(layers.user_root()), Path(layers.core_root())


def _version(core):
    try:
        import doctor
        return doctor.version_of(core)
    except Exception:                                     # no plugin.json (a test folder): the version is not known
        return None


def _state(user):
    """{'version': core version at the last merge run, 'no_base': [rel]} : what tells an update from a steady state"""
    try:
        d = json.loads((Path(user) / STATE).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _lf(data):
    return data.replace(b'\r\n', b'\n')


def _read(p):
    return _lf(p.read_bytes()) if p.is_file() else None


def _write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, p)


def _backup(user, rel):
    """the override as it is now, in .merged-backup/<stamp>/<rel>: a merge never destroys the user's copy"""
    src = user / rel
    if src.is_file():
        dest = user / BACKUP / time.strftime('%Y%m%d-%H%M%S') / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest
    return None


def overrides(user):
    """[rel] of the user's own copies of templates/, guides/, locales/ (not the .merged drafts, not the dot folders)"""
    out = []
    for kind in KINDS:
        for p in sorted((Path(user) / kind).rglob('*')):
            if p.is_file() and p.suffix not in ('.merged', '.tmp'):
                out.append(p.relative_to(user).as_posix())
    return out


def _merge_text(user, core, rel, apply, r):
    git = shutil.which('git')
    if not git:
        return {**r, 'state': NO_GIT}
    ub, bb, cb = _read(user / rel), _read(user / BASE / rel), _read(core / rel)
    with tempfile.TemporaryDirectory() as d:              # LF copies: the real files stay as they are until the merge is clean
        paths = []
        for name, data in (('yours', ub), ('base', bb), ('new', cb)):
            (Path(d) / name).write_bytes(data)
            paths.append(str(Path(d) / name))
        try:
            g = subprocess.run([git, 'merge-file', '-p', '-L', 'yours', '-L', 'base', '-L', 'new', *paths],
                               capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {**r, 'state': FAILED, 'why': type(exc).__name__}
    if g.returncode < 0 or g.returncode > 127:           # git merge-file: n conflicts (up to 127), anything else is an error
        return {**r, 'state': FAILED, 'why': (g.stderr or b'').decode('utf-8', 'replace').strip()[:200] or str(g.returncode)}
    if g.returncode == 0:
        if apply:
            r['backup'] = str(_backup(user, rel))
            _write(user / rel, g.stdout)
            _write(user / BASE / rel, cb)
        return {**r, 'state': MERGED}
    if apply:
        _write(user / (rel + '.merged'), g.stdout)
    return {**r, 'state': CONFLICT, 'conflicts': g.returncode, 'merged': str(user / (rel + '.merged'))}


def _merge_keys(user, core, rel, apply, r):
    try:
        uo, bo, co = (json.loads((root / sub).read_text(encoding='utf-8')) for root, sub in ((user, rel), (user / BASE, rel), (core, rel)))
        assert all(isinstance(x, dict) for x in (uo, bo, co))
    except (OSError, ValueError, AssertionError):
        return {**r, 'state': FAILED, 'why': 'json'}
    keep, drop, bad = {}, [], {}
    for k, v in uo.items():
        bv, cv = bo.get(k), co.get(k)
        if bv == cv:                                      # the core did not touch this key
            keep[k] = v
        elif v == cv or v == bv:                          # yours is the old default or now equals the new one: the core's wins
            drop.append(k)
        else:                                             # both changed: yours stays, the new one is shown
            keep[k], bad[k] = v, {'yours': v, 'old': bv, 'new': cv}
    if apply:
        if drop:
            r['backup'] = str(_backup(user, rel))
            _write(user / rel, json.dumps(keep, ensure_ascii=False, indent=1).encode('utf-8'))
        if not bad:
            _write(user / BASE / rel, _read(core / rel))
    if bad:
        return {**r, 'state': CONFLICT, 'keys': sorted(bad), 'values': bad}
    return {**r, 'state': MERGED if drop else CURRENT, 'keys': drop}


def merge_one(user, core, rel, apply=True, state=None):
    """one override against the new core: {'rel', 'state', ...} (None for a file the core never had: the user's own).
    With apply=False nothing is written. `state` is _state(user): it tells whether an update came since the last run"""
    user, core, state = Path(user), Path(core), state or {}
    r = {'rel': rel, 'user': str(user / rel), 'base': str(user / BASE / rel), 'core': str(core / rel)}
    ub, bb, cb = _read(user / rel), _read(user / BASE / rel), _read(core / rel)
    if cb is None:
        return {**r, 'state': GONE} if bb is not None else None
    if bb is None:                                        # a copy made by hand, never seen by a merge: what it started from is not kept
        ver = _version(core)
        if ub != cb and (rel in state.get('no_base', []) or (state.get('version') and ver and state['version'] != ver)):
            return {**r, 'state': NO_BASE}                # an update came since: the core may have changed, and silence would lose it
        if apply:                                         # no update since: the core is what the copy started from
            _write(user / BASE / rel, cb)
        return {**r, 'state': NEW_BASE}
    if bb == cb:
        return {**r, 'state': CURRENT}
    if ub == bb:                                          # never edited: the old default must not hide the new core
        if apply:
            (user / rel).unlink()
            (user / BASE / rel).unlink()
        return {**r, 'state': ADOPTED}
    if ub == cb:                                          # the user already made the same change
        if apply:
            _write(user / BASE / rel, cb)
        return {**r, 'state': CURRENT}
    if rel.startswith('locales/') and rel.endswith('.json'):
        return _merge_keys(user, core, rel, apply, r)
    return _merge_text(user, core, rel, apply, r)


def run(user=None, core=None, apply=True):
    """[result] for every override of the user layer (see merge_one)"""
    user, core = (Path(x) for x in (user, core)) if user and core else roots()
    state = _state(user)
    res = [x for x in (merge_one(user, core, rel, apply, state) for rel in overrides(user)) if x]
    if apply and user.is_dir():
        new = {'version': _version(core), 'no_base': sorted(x['rel'] for x in res if x['state'] == NO_BASE)}
        if new != state:
            _write(user / STATE, json.dumps(new).encode('utf-8'))
    return res


def accept(user, core, rel):
    """the user resolved `rel`: the .merged draft (when there is one and no marker is left) becomes the override, and the
    base becomes the new core, so the next update merges from here"""
    user, core, rel = Path(user), Path(core), rel.replace('\\', '/')
    r = {'rel': rel, 'user': str(user / rel)}
    if rel not in overrides(user) or _read(core / rel) is None:         # only one of the user's own copies: no path out of the layer
        return {**r, 'state': FAILED, 'why': 'file'}
    draft = user / (rel + '.merged')
    if draft.is_file():
        data = draft.read_bytes()
        if MARKER.search(data):
            return {**r, 'state': MARKERS, 'merged': str(draft)}
        r['backup'] = str(_backup(user, rel))
        _write(user / rel, data)
        draft.unlink()
    _write(user / BASE / rel, _read(core / rel))
    st = _state(user)
    if rel in st.get('no_base', []):
        _write(user / STATE, json.dumps({**st, 'no_base': [x for x in st['no_base'] if x != rel]}).encode('utf-8'))
    return {**r, 'state': ACCEPTED}


def announce(user, results):
    """the results that need the user and were not said yet for this version of their core file; marks them said, forgets the
    ones that are resolved. This is the "once" of the notice"""
    path = Path(user) / NOTICE
    try:
        seen = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        seen = {}
    need = [x for x in results if x['state'] in NEED]
    new = []
    for x in need:
        stamp = hashlib.sha256(_read(Path(x['core'])) or b'').hexdigest()[:16]
        if seen.get(x['rel']) != stamp:
            new.append(x)
        seen[x['rel']] = stamp
    seen = {k: v for k, v in seen.items() if k in {x['rel'] for x in need}}
    if seen or path.is_file():
        _write(path, json.dumps(seen).encode('utf-8'))
    return new


def sentence(x):
    """the line for one result, in the language in use (None when there is nothing to say)"""
    from i18n import say
    st = x['state']
    f = {'cmd': f'python "{HERE / "chat.py"}"', 'rel': x['rel'], 'user': x['user'], 'base': x.get('base', ''), 'core': x.get('core', ''),
         'backup': x.get('backup', ''), 'why': x.get('why', ''), 'merged': x.get('merged', ''), 'path': x['user'], 'keys': ', '.join(x.get('keys', []))}
    if st == CONFLICT:
        return say('merge.need_keys', **f) if 'keys' in x else say('merge.need', **f)
    return say('merge.' + st, **f) if st in (NO_GIT, GONE, FAILED, MERGED, ADOPTED, ACCEPTED, MARKERS, NO_BASE) else None


def main(argv=None):
    import argparse
    from i18n import say, use
    use(None)
    p = argparse.ArgumentParser(prog='chat.py merge', description=__doc__.split('\n')[0])
    p.add_argument('--auto', action='store_true', help='what the session hook runs: only what is new, once; never fails the session')
    p.add_argument('--dry-run', action='store_true', help='say what would be merged, write nothing')
    p.add_argument('--accept', metavar='REL', help='the .merged draft of REL is resolved: it becomes your copy')
    a = p.parse_args(argv)
    try:
        user, core = roots()
        with (contextlib.nullcontext() if a.dry_run or not user.is_dir() else _lock(user)):
            res = [accept(user, core, a.accept)] if a.accept else run(user, core, apply=not a.dry_run)
            shown = [] if a.dry_run or a.accept else announce(user, res)
    except Busy:                                          # the other one is doing it, and will say it
        if not a.auto:
            print(say('merge.busy'))
        return 0 if a.auto else 1
    except Exception as exc:                              # a session must never fail to start because of this
        if not a.auto:
            raise
        print(f'merge --auto: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 0
    lines = [sentence(x) for x in res if x['state'] not in (CURRENT, NEW_BASE) and (not a.auto or x['state'] not in NEED or x in shown)]
    lines = [ln for ln in lines if ln]
    if lines or not a.auto:                               # the hook says nothing when there is nothing (no blank line at every start)
        print('\n'.join(lines) if lines else say('merge.none'))
    return 0 if a.auto else int(any(x['state'] in NEED + (MARKERS,) for x in res))


if __name__ == '__main__':
    sys.path.insert(0, str(HERE))
    sys.exit(main())
