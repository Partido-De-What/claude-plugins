"""S2: `wait --until-cmd CMD` ends when the command exits 0, and until then never tells the agent to end its turn.
Run: python scripts/tools/smoke_10_s2.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
base = Path(tempfile.mkdtemp(prefix='s2_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(base / 'c')
(base / 'c' / 'chatroom').mkdir(parents=True)
room = base / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'user_name': 'USER', 'self_names': ['LEAD'], 'participants': ['A', 'B'], 'lang': 'en'}))
import chat  # noqa: E402

chat.UNTIL_CMD_EVERY = 1
r = chat.Room(room)
r.append('LEAD', 'start')
r.append('A', '40%: my run goes on the device', 'status')
r.set_cursor('A', 2)
flag = base / 'done.flag'
cmd = f'"{sys.executable}" -c "import sys,os; sys.exit(0 if os.path.exists(r\'{flag}\') else 1)"'


def waited(seconds):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        r.wait('A', seconds, True, until_cmd=cmd)
    return out.getvalue()


t0 = time.time()
text = waited(3)
assert 'not true yet' in text and 'do not end your turn' in text, text            # the condition is false: it waits again
threading.Timer(1.5, flag.write_text, ['x']).start()
t0 = time.time()
text = waited(30)
assert 'condition is true' in text and time.time() - t0 < 28, (text, time.time() - t0)   # true: the wait ends at once
flag.unlink()
r.append('B', '@A stop, the plan changed')
assert 'the plan changed' in waited(20)                                           # a message for it still wakes it first
print('smoke_10_s2 ok')
