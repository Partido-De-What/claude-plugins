"""S1: an idle agent that holds the shared device (research hold) is not told to end its turn by `wait`.
Run: python scripts/tools/smoke_10_s1.py   (the stop hook's side of the rule is in `python scripts/hold.py --prova`)"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
base = Path(tempfile.mkdtemp(prefix='s1_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(base / 'c')
(base / 'c' / 'chatroom').mkdir(parents=True)
room = base / 'room'
room.mkdir()
(room / 'config.json').write_text(json.dumps({'user_name': 'USER', 'self_names': ['LEAD'], 'participants': ['A', 'B'], 'lang': 'en'}))
import chat  # noqa: E402

r = chat.Room(room)
r.append('LEAD', 'start')
r.append('A', '40%: waiting for my bench', 'idle')
r.set_cursor('A', 2)


def waited():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        r.wait('A', 2, True)
    return out.getvalue()


text = waited()
assert 'end your turn' in text and 'hold the shared device' not in text, text     # no hold: the usual idle wait
(room / 'research').mkdir()
(room / 'research' / 'gpu.hold').write_text(json.dumps({'by': 'A', 'reason': 'bench', 'until': time.time() + 600}))
text = waited()
assert 'hold the shared device' in text and 'end your turn' not in text, text     # it holds the device: it goes on
(room / 'research' / 'gpu.hold').write_text(json.dumps({'by': 'B', 'reason': 'bench', 'until': time.time() + 600}))
assert 'end your turn' in waited()                                                # another agent's hold changes nothing
print('smoke_10_s1 ok')
