"""0.19.9 T38: the task view shows the notes whole. A note was cut to 300 characters when it was written, and `board T<n>` (also the
MCP board with an id) showed only the last two: a lead lost half of a hand-over note. Now a note is kept up to NOTE_MAX characters,
`board T<n>` prints every note whole, and the compact `board --all` stays short (each of the last two notes cut at a word).
A fake room in a temp dir, a fake HOME: nothing real is read or written.  Run: python -X utf8 tools/smoke_0199_d38.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199d38_'))
for k in ('HOME', 'USERPROFILE'):
    os.environ[k] = str(BASE / 'home')
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'home' / '.claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def run(room, *args):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *args, '--room', str(room)], capture_output=True, timeout=180)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def long_note(tag, n):
    """n characters of words, a marker in the first, the middle and the last words: a cut anywhere loses one"""
    words = [f'w{i:03d}' for i in range(n // 5)]
    words[0], words[len(words) // 2], words[-1] = f'{tag}-FIRST', f'{tag}-MIDDLE', f'{tag}-LAST'
    return ' '.join(words)


room = BASE / 'room'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B,C', '--lang', 'en'], capture_output=True)
run(room, 'task', 'add', 'one task with long notes', '--as', 'A')
run(room, 'task', 'take', 'T1', '--as', 'A')

n1, n2, n3 = long_note('N1', 1200), long_note('N2', 900), long_note('N3', 700)
for n in (n1, n2, n3):
    run(room, 'task', 'note', 'T1', n, '--as', 'A')

print('-- D1 the view of one task')
c, view = run(room, 'board', 'T1')
ok('D1 board T1 prints the three notes whole', all(f'{t}-LAST' in view and f'{t}-MIDDLE' in view for t in ('N1', 'N2', 'N3')), view)
ok('D1 board T1 prints the first note too (not only the last two)', 'N1-FIRST' in view, view)

print('-- D2 the same view in process (what the MCP board with an id calls)')
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402
shown = chat.Board(chat.Room(room)).show('T1')
ok('D2 Board.show(T1) carries every note whole', all(f'{t}-LAST' in shown for t in ('N1', 'N2', 'N3')), shown)

print('-- D3 the compact views stay compact')
c, allv = run(room, 'board', '--all')
ok('D3 board --all shows the last two notes, cut', 'N3-FIRST' in allv and 'N2-FIRST' in allv and 'N1-FIRST' not in allv, allv)
ok('D3 board --all does not print a note whole', 'N3-LAST' not in allv and 'N2-LAST' not in allv, allv)
c, short = run(room, 'board')
ok('D3 board (short) has no notes', 'N3-FIRST' not in short and 'w010' not in short, short)

print('-- D4 the other writers of a note')
run(room, 'task', 'add', 'a task to hand over', '--as', 'A')
run(room, 'task', 'take', 'T2', '--as', 'A')
hand = long_note('HAND', 800)
c, o = run(room, 'task', 'handoff', 'T2', 'B', '--note', hand, '--as', 'A')
c, v2 = run(room, 'board', 'T2')
ok('D4 a hand-over note is whole', 'HAND-LAST' in v2 and 'HAND-MIDDLE' in v2, (o, v2))
run(room, 'task', 'add', 'a task to lend', '--as', 'A')
run(room, 'task', 'take', 'T3', '--as', 'A')
pk = long_note('PACK', 800)
c, o = run(room, 'task', 'help', 'T3', 'C', '--scope', 'the piece', '--done-when', 'it passes', '--note', pk, '--as', 'A')
c, v4 = run(room, 'board', 'T4')
ok('D4 a help packet is whole', 'PACK-LAST' in v4 and 'PACK-MIDDLE' in v4, (o, v4))

print('-- D5 a note has a limit, a large one')
huge = long_note('HUGE', 20000)
run(room, 'task', 'note', 'T1', huge, '--as', 'A')
c, v1 = run(room, 'board', 'T1')
ok('D5 a 20000-character note is kept up to the limit, not unbounded', 'HUGE-FIRST' in v1 and 'HUGE-LAST' not in v1 and len(v1) < 12000, len(v1))

print(f'{"ALL PASS" if not fails else f"{fails} FAIL"}')
sys.exit(1 if fails else 0)
