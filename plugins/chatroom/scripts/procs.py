"""procs: the processes the plugin starts and leaves running (a viewer, a relay, a heavy wrapper), so that someone can end them.

    chat.py procs                         the ones running now: kind, pid, port, room, minutes, purpose, clients
    chat.py procs stop --room ROOM        end the ones of that room (and their children)
    chat.py procs stop --all              end every one
    chat.py procs stop PID ...            end those
    chat.py procs close --room ROOM       at the closing: end the test ones of that room, say which viewer of the user is left
    chat.py procs sweep [--yes] [--room ROOM | PID ...]   the ones nobody needs any more (starter, parent or room gone): listed,
                                          ended with --yes, only those of that room or those pids when given

A viewer ends by itself: a test's (its room is in the temporary folder: purpose "prova") when its starter dies or nobody has
looked at it for prova_idle_min minutes (10); the user's when its room is closed and nobody has looked at it for viewer_idle_min
minutes (30). Both are in the user's settings.json, in minutes, 0 = never. A viewer somebody looks at never ends by itself.

Each long command writes procs/<pid>.json in the chatroom folder when it starts and removes it when it ends; one that was
killed leaves its file, which the next listing drops (its pid is gone). The pid is the top of the relaunch chain (chat.py
relaunch: uv, the environment's python, the real one), so ending it ends the chain. Thirty-five viewers were left by tests in
one night, the computer slower by the hour, and nothing said which they were."""
import atexit
import ctypes
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import layers
from i18n import say

LONG = re.compile(r'chat\.py"?\s+(serve|alerts)\b')
ROOM = re.compile(r'--room\s+("[^"]+"|\S+)')
PORT = re.compile(r'--port\s+(\d+)')


def home():
    return layers.chatroom_dir() / 'procs'


def starter_pid():
    """who started this process, looking through the stub of a Windows venv (its python.exe starts the real one and waits for it)"""
    pid = os.getppid()
    if os.name == 'nt' and sys.prefix != sys.base_prefix:
        from inbox import processes
        name, up = processes().get(pid, ('', 0))
        if name in ('python', 'pythonw') and up:
            return up
    return pid


def purpose_of(room):
    """'prova' for a room in the temporary folder (a test's), 'utente' for the others; CHATROOM_PURPOSE says it outright"""
    if os.environ.get('CHATROOM_PURPOSE') in ('prova', 'utente'):
        return os.environ['CHATROOM_PURPOSE']
    try:
        Path(room).resolve().relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError:
        return 'utente'
    return 'prova' if room else 'utente'


def add(kind, top, room='', port=0, label='', starter=0):
    """note this process (top: the first of its relaunch chain, starter: who started that); the file goes with it. Returns the entry"""
    f = home() / f'{top}.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    e = {'pid': top, 'kind': kind, 'room': str(room), 'port': port, 'label': label[:120], 'since': now,
         'purpose': purpose_of(room) if room else 'utente', 'starter': starter, 'clients': 0, 'last_hit': now}
    f.write_text(json.dumps(e), encoding='utf-8')
    atexit.register(lambda: f.unlink(missing_ok=True))
    return e


def touch(top, **fields):
    """update fields of this process's entry (not when it is gone: one ended from outside stays ended)"""
    f = home() / f'{top}.json'
    try:
        e = json.loads(f.read_text(encoding='utf-8'))
        e.update(fields)
        f.write_text(json.dumps(e), encoding='utf-8')
    except (OSError, ValueError):
        pass


def idle_why(purpose, clients, last_hit, now, starter_alive, shut, mins):
    """why a viewer should end itself now: 'starter', 'quiet', 'closed' or '' (shut: a function, the room's chat is read only when
    needed; mins: {'prova': m, 'viewer': m}, 0 = never). Somebody looking at it keeps it."""
    quiet = (now - last_hit) / 60
    if purpose == 'prova':
        if not starter_alive:
            return 'starter'
        return 'quiet' if not clients and mins['prova'] and quiet >= mins['prova'] else ''
    return 'closed' if not clients and mins['viewer'] and quiet >= mins['viewer'] and shut() else ''


def exit_line(why, minutes):
    """what a viewer says when it ends itself (why: what idle_why gave)"""
    return {'starter': say('procs.exit.starter'), 'quiet': say('procs.exit.quiet', minutes=minutes), 'closed': say('procs.exit.closed', minutes=minutes)}[why]


def started(pid):
    """when the process started (epoch seconds), or None when it cannot be told"""
    if os.name != 'nt':
        return None
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    handle = k.OpenProcess(0x1000, False, pid)                 # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    times = [ctypes.c_ulonglong() for _ in range(4)]            # creation, exit, kernel, user: FILETIMEs
    got = k.GetProcessTimes(ctypes.c_void_p(handle), *[ctypes.byref(t) for t in times])
    k.CloseHandle(ctypes.c_void_p(handle))
    return times[0].value / 1e7 - 11644473600 if got else None


def running():
    """the entries whose process is alive and is the one that wrote them (a pid taken by a newer process is not it)"""
    from chat import pid_alive
    out = []
    for f in sorted(home().glob('*.json')):
        try:
            e = json.loads(f.read_text(encoding='utf-8'))
            alive = pid_alive(int(e['pid']))
            began = started(int(e['pid'])) if alive else None
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if alive and (began is None or began <= float(e['since']) + 5):
            out.append(e)
        else:
            f.unlink(missing_ok=True)
    return out


def end(e):
    """end one entry with everything under it"""
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(e['pid'])], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(e['pid']), signal.SIGTERM)
        except OSError:
            os.kill(e['pid'], signal.SIGTERM)
    (home() / f"{e['pid']}.json").unlink(missing_ok=True)


def scan():
    """the `chat.py serve|alerts` processes of the machine: [(pid, parent pid, command line)]. Windows asks the system, elsewhere ps"""
    if os.name == 'nt':
        cmd = ['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'chat\\.py' } | "
               "ForEach-Object { \"$($_.ProcessId)`t$($_.ParentProcessId)`t$($_.CommandLine)\" }"]
    else:
        cmd = ['ps', '-eo', 'pid=,ppid=,args=']
    try:
        got = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in got.splitlines():
        bits = line.split('\t', 2) if os.name == 'nt' else line.split(None, 2)
        if len(bits) == 3 and bits[0].strip().isdigit() and bits[1].strip().isdigit() and LONG.search(bits[2]):
            rows.append((int(bits[0]), int(bits[1]), bits[2].strip()))
    return rows


def orphans(shown):
    """what nobody needs any more: a test's whose starter is gone, one whose room folder is gone, and the ones the registry never
    knew (an older plugin) whose parent is gone"""
    from chat import pid_alive
    out = [{**e, 'why': 'starter'} for e in shown if e.get('purpose') == 'prova' and e.get('starter') and not pid_alive(int(e['starter']))]
    out += [{**e, 'why': 'room'} for e in shown if e['room'] and not Path(e['room']).is_dir() and e['pid'] not in {x['pid'] for x in out}]
    known, found = {e['pid'] for e in shown}, {}
    for pid, parent, line in scan():
        got = ROOM.search(line)
        room = got.group(1).strip('"') if got else ''
        gone = bool(room) and Path(room).is_absolute() and not Path(room).is_dir()
        if pid not in known and pid != os.getpid() and (gone or not pid_alive(parent)):
            found[pid] = (parent, {'pid': pid, 'kind': LONG.search(line).group(1), 'room': room, 'port': int((PORT.search(line) or [0, 0])[1]), 'since': time.time(), 'why': 'room' if gone else 'parent', 'unknown': True})
    return out + [e for parent, e in found.values() if parent not in found]       # a child of one listed goes with it


def row(e, extra=''):
    return '  ' + say('procs.row', kind=e['kind'], pid=e['pid'], port=e['port'] or '-', room=e['room'] or '-', minutes=int((time.time() - e['since']) // 60)) + extra


def close(room):
    """the closing of a room: end its test processes and the test ones left without a starter; say which viewer of the user is left"""
    here, shown = Path(room).resolve(), running()
    lost = {e['pid'] for e in orphans(shown)}
    for e in shown:
        if e.get('purpose') == 'prova' and (e['pid'] in lost or (e['room'] and Path(e['room']).resolve() == here)):
            end(e)
            print(say('procs.stopped', kind=e['kind'], pid=e['pid'], room=e['room'] or '-'))
    for e in shown:
        if e['kind'] == 'serve' and e.get('purpose') != 'prova' and e['room'] and Path(e['room']).resolve() == here:
            print(say('procs.kept', port=e['port'], n=e.get('clients', 0), pid=e['pid']))


def command(a):
    """chat.py procs [stop --room ROOM | --all | PID ... | close --room ROOM | sweep [--yes]]"""
    act, rest = (a.pairs[0].lower() if a.pairs else ''), a.pairs[1:]
    shown = running()
    if not act:
        print(say('procs.head', n=len(shown)))
        for e in shown:
            print(row(e, f" · {e.get('purpose', 'utente')}" + (f" · {e.get('clients', 0)} clients" if e['kind'] == 'serve' else '')))
        return
    if act == 'close' and a.room:
        return close(a.room)
    if act == 'sweep':
        here, pids = (Path(a.room).resolve() if a.room else None), {int(x) for x in rest if x.isdigit()}
        lost = [e for e in orphans(shown) if (not here or (e['room'] and Path(e['room']).resolve() == here)) and (not pids or e['pid'] in pids)]
        # one the registry never knew (an older plugin started it) may be a viewer somebody is looking at: --yes ends it only when it is
        # named, by its room or its pid
        kept = [e for e in lost if a.yes and e.get('unknown') and not (here or pids)]
        for e in lost:
            print(row(e, f" · {e['why']}" + (' · not in the registry' if e.get('unknown') else '')))
            if a.yes and e not in kept:
                end(e)
        print(say('procs.swept', n=len(lost) - len(kept)) if a.yes else say('procs.ask', n=len(lost)))
        if kept:
            print(say('procs.unregistered', n=len(kept)))
        return
    if act != 'stop':
        raise ValueError(say('procs.usage'))
    here = Path(a.room).resolve() if a.room else None
    pids = {int(x) for x in rest if x.isdigit()}
    if not (getattr(a, 'all', False) or pids or here):
        raise ValueError(say('procs.usage'))
    chosen = [e for e in shown if getattr(a, 'all', False) or e['pid'] in pids or (here and e['room'] and Path(e['room']).resolve() == here)]
    for e in chosen:
        end(e)
        print(say('procs.stopped', kind=e['kind'], pid=e['pid'], room=e['room'] or '-'))
    if not chosen:
        print(say('procs.none'))
