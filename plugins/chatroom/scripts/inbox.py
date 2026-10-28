"""The room's alarm clock for a Claude Code session (plugin monitor): python inbox.py [--once]

Claude Code runs this for the whole session (monitors/monitors.json); each line it prints becomes a notification that
wakes the session even when it sits idle at the prompt. It finds the room of the session (CLAUDE_CODE_SESSION_ID in the
`sessions` of ~/.claude/chatroom/rooms.json, else a room folder that holds the working directory), and prints a line
for each message that tags that session (its name, @all) or that the user wrote. Prints nothing while no room is
alive (a room opened later in the same session is found: one read of rooms.json every 5 s), and stops when the Claude Code process that started it is gone. A line printed is marked delivered
(ROOM/delivered_NAME.txt, never past what the session already read: cursor_NAME.txt).

Idea and the parent-process check adapted from concord-mcp, plugin/concord-relay/scripts/watch-inbox.sh
(https://github.com/get-concord-ai/concord-mcp, commit 37d48f7, MIT).
Test: python inbox.py --prova"""
import json
import os
import sys
import time
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')
POLL = 2                      # seconds between looks at the chat file
ROOMS_EVERY = 5               # seconds between looks at rooms.json while no room is found
SHOWN = 5                     # lines printed at most for one batch: the older ones are one line of count
MAX_TEXT = 160


SHELLS = {'python', 'python3', 'pythonw', 'py', 'uv', 'bash', 'sh', 'zsh', 'dash', 'fish', 'cmd', 'conhost', 'env', 'timeout'}


def processes():
    """pid -> (name without .exe, parent pid) of every process (Windows: a toolhelp snapshot; elsewhere: ps)"""
    out = {}
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes

        class Entry(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('pid', wintypes.DWORD),
                        ('heap', ctypes.c_size_t), ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                        ('ppid', wintypes.DWORD), ('pri', ctypes.c_long), ('flags', wintypes.DWORD), ('exe', ctypes.c_wchar * 260)]
        k = ctypes.windll.kernel32
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        snap = k.CreateToolhelp32Snapshot(2, 0)                        # TH32CS_SNAPPROCESS
        e = Entry(); e.dwSize = ctypes.sizeof(Entry)
        ok = k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out[e.pid] = (e.exe.lower().removesuffix('.exe'), e.ppid)
            ok = k.Process32NextW(snap, ctypes.byref(e))
        k.CloseHandle(snap)
    else:
        import subprocess
        for line in subprocess.run(['ps', '-A', '-o', 'pid=,ppid=,comm='], capture_output=True, text=True).stdout.splitlines():
            a = line.split(None, 2)
            if len(a) == 3:
                out[int(a[0])] = (os.path.basename(a[2]).lower(), int(a[1]))
    return out


def harness_pid():
    """the process that started this monitor: Claude Code starts it through a shell and the interpreter may be a launcher
    stub, so look through those parents (a monitor that outlives the session keeps marking messages delivered for nobody)"""
    try:
        procs, pid = processes(), os.getppid()
        for _ in range(6):
            name, up = procs.get(pid, ('', 0))
            if name not in SHELLS or up not in procs:       # not a launcher, or its parent is gone already (msys timeout)
                break
            pid = up
        return pid
    except (OSError, ValueError, AttributeError):
        return os.getppid()


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def read_int(path):
    try:
        return int(Path(path).read_text())
    except (OSError, ValueError):
        return 0


def live_rooms():
    """rooms.json without the rooms not stamped for 60 s (the same rule as the mod)"""
    rooms = read_json(CLAUDE_DIR / 'chatroom' / 'rooms.json', {})
    return {k: v for k, v in rooms.items() if isinstance(v, dict) and time.time() - float(v.get('ts', 0)) < 60}


def find_room(rooms, session, cwd):
    """the room folder of this session: its id in `sessions`, else the folder that holds the working directory"""
    for key, room in rooms.items():
        if session and session in room.get('sessions', []):
            return key
    here = os.path.normcase(os.path.abspath(cwd))
    for key in rooms:
        k = os.path.normcase(os.path.abspath(key))
        if here == k or here.startswith(k + os.sep):
            return key
    return None


def who_am_i(room_dir, session):
    """the name this session writes under: sessions.json (written by chat.py when the lead posts or reads), else the user"""
    name = read_json(Path(room_dir) / 'sessions.json', {}).get(session)
    return name or read_json(Path(room_dir) / 'config.json', {}).get('user_name')


def pending(room_dir, name, after=0):
    """messages newer than what `name` read or was handed, that tag it, or @all, or come from the user; oldest first"""
    import chat
    room = chat.Room(room_dir)
    c = room.config()
    users = room.user_names()
    mine = {name} | (users if name in users else set())          # the lead answers to the user's name and its own
    seen = max(after, read_int(Path(room_dir) / f'cursor_{name}.txt'), read_int(Path(room_dir) / f'delivered_{name}.txt'))
    out = []
    for m in room.messages():
        if m['n'] <= seen or m.get('kind') or m['from'] == name:
            continue
        text = m.get('text', '')
        if m['from'] == c.get('user_name') or chat.tags_everyone(text) or any(chat.tags(text, n) for n in mine):
            out.append(m)
    return out, c


def mark_delivered(room_dir, name, n):
    """monotone: never lower than what is there; chat.py's own (under the room lock) when this chat.py has it"""
    import chat
    if hasattr(chat.Room, 'mark_delivered'):
        return chat.Room(room_dir).mark_delivered(name, n)
    p = Path(room_dir) / f'delivered_{name}.txt'
    if n > read_int(p):
        p.write_text(str(n))


def lines(room_dir, name, after=0):
    """the notification lines for the new messages (and the number handed); marks them delivered"""
    import i18n
    new, c = pending(room_dir, name, after)
    if not new:
        return [], after
    lang = i18n.lang_of(c)
    title = c.get('title') or c.get('topic', '')
    out = []
    if len(new) > SHOWN:
        out.append(i18n.tr(lang, 'inbox.more', n=len(new) - SHOWN))
    for m in new[-SHOWN:]:
        text = ' '.join(m.get('text', '').split())
        out.append(i18n.tr(lang, 'inbox.line', room=title, n=m['n'], who=m['from'],
                           text=text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1] + '…'))
    mark_delivered(room_dir, name, new[-1]['n'])
    return out, new[-1]['n']


def stamp_of(room_dir, name):
    """what makes a new look worthwhile: the chat file and this name's cursor and delivered marks (size, mtime)"""
    out = []
    for f in ('chat.jsonl', f'cursor_{name}.txt', f'delivered_{name}.txt'):
        try:
            st = (Path(room_dir) / f).stat()
            out.append((st.st_size, st.st_mtime_ns))
        except OSError:
            out.append(None)
    return out


def watch(session, cwd, parent, once=False):
    import chat
    key = name = None
    after = 0
    last_rooms = 0
    seen = None                                       # the stamp of the last look: an unchanged chat is not parsed again (one parse per 2 s per open session would add up)
    while True:
        if parent and not chat.pid_alive(parent):
            return 0
        if key is None or time.time() - last_rooms > ROOMS_EVERY:
            last_rooms = time.time()
            key = find_room(live_rooms(), session, cwd) or key
            name = who_am_i(key, session) if key else None
        stamp = stamp_of(key, name) if key and name else None
        if stamp and (stamp != seen or once):
            out, after = lines(key, name, after)
            seen = stamp_of(key, name)                # after the marks this look wrote
            try:
                for line in out:
                    print(line, flush=True)
            except OSError:
                return 0                              # shortcut: a dead Claude Code closes the pipe, caught at the next line; the pid check above is the main stop
        if once:
            return 0
        time.sleep(POLL)


def _prova():
    """self-check: room found by session id and by folder, nothing without a room, the tags that count, the cap, delivered"""
    import tempfile
    global CLAUDE_DIR
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import chat
    base = Path(tempfile.mkdtemp(prefix='inbox_prova_'))
    CLAUDE_DIR = base / 'claude'
    (CLAUDE_DIR / 'chatroom').mkdir(parents=True)
    room = base / 'room'
    room.mkdir()
    (room / 'config.json').write_text(json.dumps({'user_name': 'Adrian', 'self_names': ['LEAD'], 'participants': ['A'], 'title': 'T'}))
    (room / 'sessions.json').write_text(json.dumps({'sid-1': 'LEAD'}))
    chat.Room(room).append('Adrian', 'hello')                                     # 1: from the user
    chat.Room(room).append('A', 'status, 50%')                                    # 2: tags nobody
    chat.Room(room).append('A', '@LEAD look')                                     # 3: tags the lead
    chat.Room(room).append('A', 'to @all')                                        # 4
    chat.Room(room).append('LEAD', '@A ok')                                       # 5: its own
    stamp = {str(room): {'ts': time.time(), 'sessions': ['sid-1']}}
    (CLAUDE_DIR / 'chatroom' / 'rooms.json').write_text(json.dumps(stamp))
    assert find_room(live_rooms(), 'sid-1', '/nowhere') == str(room)             # by session id
    assert find_room(live_rooms(), 'other', str(room / 'sub')) == str(room)      # by folder
    assert find_room(live_rooms(), 'other', '/nowhere') is None
    assert who_am_i(room, 'sid-1') == 'LEAD' and who_am_i(room, 'x') == 'Adrian'
    out, n = lines(room, 'LEAD')
    assert [x.split(' ')[2] for x in out] == ['#1', '#3', '#4'] and n == 4, out    # user, tag, @all; not #2 (tags nobody), not its own #5
    assert read_int(room / 'delivered_LEAD.txt') == 4
    assert lines(room, 'LEAD')[0] == []                                           # delivered: not again
    mark_delivered(room, 'LEAD', 2)
    assert read_int(room / 'delivered_LEAD.txt') == 4                             # never lowered
    for i in range(8):
        chat.Room(room).append('A', f'@LEAD m{i}')
    (room / 'cursor_LEAD.txt').write_text('0')
    out, n = lines(room, 'LEAD')
    assert len(out) == SHOWN + 1 and n == 13, out                                  # 8 new: SHOWN lines and one count
    (room / 'cursor_LEAD.txt').write_text('13')
    assert lines(room, 'LEAD')[0] == []
    (CLAUDE_DIR / 'chatroom' / 'rooms.json').write_text('{}')
    assert watch('sid-1', '/nowhere', 0, once=True) == 0                          # no room alive: nothing printed
    assert stamp_of(room, 'LEAD')[0] is not None and stamp_of(room, 'NOBODY')[1:] == [None, None]
    print('inbox prova ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
        sys.exit(0)
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(watch(os.environ.get('CLAUDE_CODE_SESSION_ID', ''), os.getcwd(), harness_pid(), once='--once' in sys.argv))
