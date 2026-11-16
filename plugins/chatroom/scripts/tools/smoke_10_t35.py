import os, sys, json, time, tempfile, subprocess, pathlib
tmp = tempfile.mkdtemp()
os.environ['CLAUDE_CONFIG_DIR'] = tmp; os.environ['CHATROOM_RELAUNCHED'] = '1'
here = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(here))
import chat, activity
fails = []
def ok(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
# e) stale tmp purged, own tmp never left behind
d = activity.REGISTRY.parent; d.mkdir(parents=True, exist_ok=True)
old = d / 'rooms.999999.tmp'; old.write_text('{}')
os.utime(old, (time.time() - 3600,) * 2)
fresh = d / 'rooms.888888.tmp'; fresh.write_text('{}')
activity.register_room.__wrapped__ if hasattr(activity.register_room, '__wrapped__') else None
src = (here / 'activity.py').read_text(encoding='utf-8')
ns = {}
import re
m = re.search(r"def edit\(fn\):.*?(?=\n\S)", src, re.S)
ok('rooms.*.tmp' in src and 'finally' in src, 'activity source purges stale tmp and unlinks in finally')
# c/d/b via the shell
room = pathlib.Path(tmp) / 'room'; room.mkdir()
def run(*a):
    return subprocess.run([sys.executable, '-X', 'utf8', str(here / 'chat.py'), *a], capture_output=True, text=True, env=os.environ, encoding='utf-8').stdout
out = run('rooms')
ok(str(activity.REGISTRY) in out, 'rooms names the registry it looked in: ' + out.strip()[:100])
loc = (here.parent / 'guides' / 'lead-normal.md').read_text(encoding='utf-8')
ok('agent_types.json' in loc, 'guide documents agent_types.json')
r0 = pathlib.Path(tmp) / 'r0'; r0.mkdir(exist_ok=True)
(r0 / 'config.json').write_text(json.dumps({'participants': ['A'], 'user_name': 'USER'}), encoding='utf-8')
activity.register_room(chat.Room(r0), 1, 'h')
ok(not old.exists(), 'a stale rooms.*.tmp is purged by the next stamp')
ok(fresh.exists(), 'a fresh one is left (its writer may be swapping it)')
ok(not list(d.glob(f'rooms.{os.getpid()}.tmp')), 'own tmp is gone after the stamp')
# c/d: a room with a lead as self name
rd = pathlib.Path(tmp) / 'r2'; rd.mkdir()
(rd / 'config.json').write_text(json.dumps({'participants': ['A', 'B'], 'self_names': ['A'], 'user_name': 'USER'}), encoding='utf-8')
run('remove', '--room', str(rd), '--participants', 'A')
cfg = json.loads((rd / 'config.json').read_text(encoding='utf-8'))
ok('A' not in cfg.get('self_names', []), 'remove drops the name from self_names: ' + str(cfg.get('self_names')))
out = run('remove', '--room', str(rd), '--participants', 'B')
ok('none' in out, 'remove of the last one prints none: ' + out.strip()[-80:])
sys.exit(1 if fails else 0)
