"""1.0 R7: `alerts --follow --heartbeat N` wakes the lead every N seconds even when the room is quiet (the lead started a cron by
hand in every session for it). Run: python -X utf8 smoke_10_r7.py"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10r7_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'      # a fresh config dir has no uv environment yet: relaunching into it costs a minute
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def relay(room, *extra, limit=90):
    p = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'alerts', '--follow', '--messages', '--until-line', '--as', 'LEAD', *extra, '--room', str(room)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
    t0 = time.time()
    try:
        p.wait(timeout=limit)
        return p.stdout.read(), time.time() - t0
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
        return 'TIMEOUT ' + p.stdout.read(), time.time() - t0


room = BASE / 'room'
subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', 'A,B', '--lang', 'en'], capture_output=True)
chat.Room(room).append('A', 'plain note, nothing for the lead')
out, took = relay(room, '--heartbeat', '4')
ok('R7 a quiet room: the relay wakes the lead on its heartbeat', 'HEARTBEAT' in out and 'TIMEOUT' not in out, out)
print('fails', fails)
sys.exit(1 if fails else 0)
