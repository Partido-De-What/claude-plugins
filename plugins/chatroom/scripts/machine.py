"""One lock for the whole machine: what loads the GPU or the CPU hard (a research run's build and measures, a prebuild, a
task's verify command, anything an agent wraps in `chat.py heavy -- <command>`) waits its turn, across every room. Two
rooms on one GPU dirtied each other's measures (a pytest of one room during the runs of another); the GPU hold of a
research room only covers that room.

1.3.3: the lock is the operating system's own (msvcrt / fcntl on NAME.flock), released when its process dies, so no dead
holder has to be guessed. 1.3.2 created the lock file empty and wrote it a moment later: a waiter that read it in between
took it for free, and two heavy jobs ran together, twice in one night. Who holds it is written beside it whole (os.replace),
and the waiters stand in one queue (NAME.queue.json): first come, first served, unless the lead pauses or moves one.
Standard library only."""
import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import layers

POLL = 2
HELD = {}                                 # lock name -> fd, in this process: a build inside a run takes no second turn
LOG_KEEP = 200                            # outcomes of heavy jobs kept in machine.log.jsonl


def lock_path(name='machine'):
    return layers.chatroom_dir() / f'{name}.lock'


def queue_path(name='machine'):
    return layers.chatroom_dir() / f'{name}.queue.json'


def log_path():
    return layers.chatroom_dir() / 'machine.log.jsonl'


def _alive(pid):
    from chat import pid_alive
    return pid_alive(int(pid))


def _write(path, data):
    tmp = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    for _ in range(20):                   # Windows refuses the swap while a reader has the file open for a moment
        try:
            return os.replace(tmp, path)
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


def _try(fd):
    """take the OS lock on byte 0 of fd without waiting; True if taken"""
    try:
        if os.name == 'nt':
            import msvcrt
            os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _release(fd):
    with contextlib.suppress(OSError):
        if os.name == 'nt':
            import msvcrt
            os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    with contextlib.suppress(OSError):
        os.close(fd)


def holder(name='machine'):
    """{'pid', 'label', 'since', ...} of the live holder, or None"""
    try:
        h = json.loads(lock_path(name).read_text(encoding='utf-8'))
        return h if _alive(h['pid']) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def edit_queue(fn, name='machine'):
    """read the queue, fn(list) changes it in place and returns what to give back; written whole, under its own OS lock.
    Waiters whose process is gone are dropped"""
    p = queue_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p.with_suffix('.flock')), os.O_RDWR | os.O_CREAT)
    try:
        end = time.time() + 10
        while not _try(fd):
            if time.time() > end:
                raise OSError(f'the queue of {name} stays locked')
            time.sleep(0.05)
        try:
            q = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            q = []
        q = [e for e in q if isinstance(e, dict) and _alive(e.get('pid', 0))]
        got = fn(q)
        _write(p, q)
        return got
    finally:
        _release(fd)


def queue(name='machine'):
    return edit_queue(lambda q: list(q), name)


def _turn(name, ticket):
    """True when ticket is the first waiter not paused (or is not in the queue at all)"""
    def first(q):
        live = [e for e in q if not e.get('paused')]
        mine = next((e for e in q if e['id'] == ticket), None)
        return mine is None or (not mine.get('paused') and live and live[0]['id'] == ticket)
    return edit_queue(first, name)


@contextlib.contextmanager
def machine_lock(label, tell=None, poll=POLL, name='machine', room='', who=''):
    """hold the machine for the block; wait in the queue while another process holds it (tell(holder) once, to say who).
    name: another lock of the same kind (the verifies of the tasks queue among themselves on 'verify')"""
    if name in HELD:                                      # already ours (a build inside a run): no second wait
        yield
        return
    p = lock_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p.with_suffix('.flock')), os.O_RDWR | os.O_CREAT)
    ticket = f'{os.getpid()}-{int(time.time() * 1000) % 10 ** 9}'
    edit_queue(lambda q: q.append({'id': ticket, 'pid': os.getpid(), 'label': label[:160], 'room': str(room), 'who': who,
                                   'at': time.time()}), name)
    told = False
    try:
        while True:
            if _turn(name, ticket) and _try(fd):
                old = holder(name)
                if old is None or old['pid'] == os.getpid() or old.get('os'):
                    break
                _release(fd)                              # an older chatroom holds it its own way (a file made exclusively): wait for it
                fd = os.open(str(p.with_suffix('.flock')), os.O_RDWR | os.O_CREAT)
            h = holder(name)
            if tell and not told and h:
                tell(h)
                told = True
            time.sleep(poll)
    except BaseException:
        _release(fd)
        raise
    finally:
        edit_queue(lambda q: q.__setitem__(slice(None), [e for e in q if e['id'] != ticket]), name)
    _write(p, {'pid': os.getpid(), 'label': label[:160], 'since': time.time(), 'room': str(room), 'who': who, 'id': ticket, 'os': 1})
    HELD[name] = fd
    try:
        yield
    finally:
        HELD.pop(name, None)
        with contextlib.suppress(OSError, ValueError, KeyError):
            if json.loads(p.read_text(encoding='utf-8'))['pid'] == os.getpid():
                p.unlink()
        _release(fd)


def note_outcome(entry):
    """one finished heavy job: label, room, who, key, code, seconds; the last LOG_KEEP are kept"""
    p = log_path()
    try:
        rows = p.read_text(encoding='utf-8').splitlines()[-(LOG_KEEP - 1):]
    except OSError:
        rows = []
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(''.join(r + '\n' for r in [*rows, json.dumps(entry, ensure_ascii=False)]), encoding='utf-8')


def outcomes():
    out = []
    try:
        for r in log_path().read_text(encoding='utf-8').splitlines():
            with contextlib.suppress(ValueError):
                out.append(json.loads(r))
    except OSError:
        pass
    return out


def done_before(key):
    """the last outcome of a job with this key that ended well, or None: the job need not run again"""
    return next((e for e in reversed(outcomes()) if key and e.get('key') == key and e.get('code') == 0), None)


def _prova():
    import subprocess
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ['CLAUDE_CONFIG_DIR'] = tempfile.mkdtemp(prefix='machine_')
    order = []
    with machine_lock('first'):
        assert holder() and holder()['label'] == 'first'
        with machine_lock('nested'):                      # the same process: no deadlock
            order.append('nested')
        assert queue() == []
    assert holder() is None
    lock_path().write_text('', encoding='utf-8')          # P2: an empty or half-written file is not a lock: the OS lock is
    with machine_lock('after an empty file'):
        order.append('taken')
    lock_path().write_text(json.dumps({'pid': 999999, 'label': 'dead', 'since': 0}))
    with machine_lock('after a dead one'):                # its process is gone: nothing to take over by hand
        order.append('dead')
    code = ("import sys,time; sys.path.insert(0, sys.argv[1]); import machine\n"
            "with machine.machine_lock(sys.argv[2]):\n    print('in', sys.argv[2], flush=True); time.sleep(float(sys.argv[3]))\n")
    here = str(Path(__file__).resolve().parent)
    first = subprocess.Popen([sys.executable, '-c', code, here, 'A', '6'], stdout=subprocess.PIPE, text=True)
    assert first.stdout.readline().strip() == 'in A'
    def queued(n):                                        # a busy machine starts a Python in more than a second: wait for it, not a fixed time
        end = time.time() + 15
        while len(queue()) < n and time.time() < end:
            time.sleep(0.1)
    second = subprocess.Popen([sys.executable, '-c', code, here, 'B', '0'], stdout=subprocess.PIPE, text=True)
    queued(1)
    third = subprocess.Popen([sys.executable, '-c', code, here, 'C', '0'], stdout=subprocess.PIPE, text=True)
    queued(2)
    assert [e['label'] for e in queue()] == ['B', 'C'], queue()
    edit_queue(lambda q: q.reverse())                     # the lead moves C first
    second.wait(), third.wait(), first.wait()
    assert second.stdout.read() and third.stdout.read()
    note_outcome({'key': 'k1', 'code': 0}), note_outcome({'key': 'k2', 'code': 1})
    assert done_before('k1') and not done_before('k2') and not done_before('')
    print('machine prova ok', order)


if __name__ == '__main__':
    _prova()
