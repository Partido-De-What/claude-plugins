"""1.0 R2: lead_pace held back even a tag to the lead that declares a block (15 min of a stopped viewer), and it ignored the phase of a
research room. Now such a tag wakes the lead at once, and in phase 2 (runs) the pace is lead_pace_runs.
Run: python -X utf8 smoke_10_r2.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r2_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def make(name):
    room = BASE / name
    subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B', '--lang', 'en'], capture_output=True)
    cfg = json.loads((room / 'config.json').read_text(encoding='utf-8'))
    cfg.update({'lead_pace_start': 600, 'lead_pace': 600, 'lead_pace_runs': 7})
    (room / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
    return room


# 1. the pace: phase 2 of a research room has its own
room = make('pace')
r = chat.Room(room)
ok('R2 plain room: lead_pace', chat.relay_pace(r, young=False) == 600, chat.relay_pace(r, young=False))
(room / 'research').mkdir()
(room / 'research' / 'state.json').write_text(json.dumps({'phase': 2}), encoding='utf-8')
ok('R2 research phase 2: lead_pace_runs', chat.relay_pace(r, young=False) == 7, chat.relay_pace(r, young=False))
(room / 'research' / 'state.json').write_text(json.dumps({'phase': 1}), encoding='utf-8')
ok('R2 research phase 1: lead_pace', chat.relay_pace(r, young=False) == 600, chat.relay_pace(r, young=False))
ok('R2 the start of the room keeps lead_pace_start', chat.relay_pace(r, young=True) == 600)

# 2. what declares a block
blk = [{'text': '@LEAD bloccato: la GPU non risponde', 'from': 'A'},
       {'text': '@LEAD blocked on the hold', 'from': 'A'},
       {'text': '@LEAD T3 (40%)', 'from': 'A', 'kind': 'status', 'state': {'blocked_by': 'the hold of B'}}]
fine = [{'text': '@LEAD T3 done, nothing blocks me', 'from': 'A'}, {'text': '@LEAD report', 'from': 'A', 'kind': 'status', 'state': {'blocked_by': ''}}]
ok('R2 a block is declared', all(chat.declares_block(m) for m in blk), [chat.declares_block(m) for m in blk])
ok('R2 a plain report is not a block', not any(chat.declares_block(m) for m in fine), [chat.declares_block(m) for m in fine])

# 3. the relay on a quiet pace wakes at once for a tag that declares a block
room = make('block')
chat.Room(room).append('A', '@LEAD blocked: the hold is taken and nobody answers')
t0 = time.time()
p = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--follow', '--messages', '--until-line', '--as', 'LEAD', '--room', str(room)],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
try:
    p.wait(timeout=100)
    out = p.stdout.read()
except subprocess.TimeoutExpired:
    p.kill()
    p.wait()
    out = p.stdout.read()
    out = 'TIMEOUT ' + out
ok('R2 the relay wakes at once for a tag that declares a block', 'WATCH #1' in out and 'TIMEOUT' not in out, out)
print('fails', fails)
sys.exit(1 if fails else 0)
