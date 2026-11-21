"""One lock for the whole machine: what loads the GPU or the CPU hard (a research run's build and measures, a prebuild, a
task's verify command, anything an agent wraps in `chat.py heavy -- <command>`) waits its turn, across every room. Two
rooms on one GPU dirtied each other's measures (a pytest of one room during the runs of another); the GPU hold of a
research room only covers that room. The lock is a file created exclusively, with the holder's pid: a dead holder's
lock is taken over. Standard library only."""
import contextlib
import json
import os
import sys
import time
from pathlib import Path

import layers

POLL = 2


def lock_path(name='machine'):
    return layers.chatroom_dir() / f'{name}.lock'


def holder(name='machine'):
    """{'pid', 'label', 'since'} of the live holder, or None"""
    try:
        h = json.loads(lock_path(name).read_text(encoding='utf-8'))
        from chat import pid_alive
        return h if pid_alive(int(h['pid'])) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


@contextlib.contextmanager
def machine_lock(label, tell=None, poll=POLL, name='machine'):
    """hold the machine for the block; wait while another process holds it (tell(holder) once, to say who). name: another
    lock of the same kind (the verifies of the tasks queue among themselves on 'verify')"""
    p = lock_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    told = False
    while True:
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            h = holder(name)
            if h is None:                                 # its holder is dead: take it over
                with contextlib.suppress(OSError):
                    p.unlink()
                continue
            if h['pid'] == os.getpid():                   # already ours (a build inside a run): no second wait
                yield
                return
            if tell and not told:
                tell(h)
                told = True
            time.sleep(poll)
            continue
        os.write(fd, json.dumps({'pid': os.getpid(), 'label': label[:120], 'since': time.time()}).encode())
        os.close(fd)
        break
    try:
        yield
    finally:
        with contextlib.suppress(OSError, ValueError, KeyError):
            if json.loads(p.read_text(encoding='utf-8'))['pid'] == os.getpid():
                p.unlink()


def _prova():
    import tempfile
    import threading
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ['CLAUDE_CONFIG_DIR'] = tempfile.mkdtemp(prefix='machine_')
    order = []
    with machine_lock('first'):
        assert holder() and holder()['label'] == 'first'
        with machine_lock('nested'):                      # the same process: no deadlock
            order.append('nested')
    assert holder() is None
    lock_path().write_text(json.dumps({'pid': 999999, 'label': 'dead', 'since': 0}))
    with machine_lock('after a dead one'):                # taken over
        order.append('taken')
    print('machine prova ok', order)


if __name__ == '__main__':
    _prova()
