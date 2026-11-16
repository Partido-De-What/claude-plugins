"""1.0 V2+V6: the marketplace file carries the plugin's version and the doctor says when it does not; the proofs of spawn/bench
(researcher, sources, strengths) pass and read and write nothing of the user's own files. Run: python -X utf8 smoke_10_v2.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
PLUGIN = Path(SCRIPTS).parent
BASE = Path(tempfile.mkdtemp(prefix='smoke10v2_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import doctor  # noqa: E402

fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


# V2: the files of the repo agree on the number (the marketplace file is two folders above the plugin)
want = json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']
mkt = PLUGIN.parent.parent / '.claude-plugin' / 'marketplace.json'
ok('the marketplace file of this repo gives the plugin version', not mkt.is_file() or doctor.marketplace_version(PLUGIN) == want, (doctor.marketplace_version(PLUGIN), want))
# a repo that lags: the doctor fails it
tree = BASE / 'repo'
(tree / 'plugins' / 'chatroom' / '.claude-plugin').mkdir(parents=True)
(tree / '.claude-plugin').mkdir()
(tree / 'plugins' / 'chatroom' / '.claude-plugin' / 'plugin.json').write_text(json.dumps({'version': '1.0.0'}), encoding='utf-8')
(tree / '.claude-plugin' / 'marketplace.json').write_text(json.dumps({'plugins': [{'name': 'chatroom', 'version': '0.12.1'}]}), encoding='utf-8')
res = {c: (s, f) for c, s, f, _ in doctor.checks(None, 'no-such-claude', tree / 'plugins' / 'chatroom')}
ok('the doctor says a marketplace file at another number', res.get('marketplace_differs', (None, {}))[0] == doctor.FAIL and res['marketplace_differs'][1] == {'marketplace': '0.12.1', 'source': '1.0.0'}, res.get('marketplace_differs'))
(tree / '.claude-plugin' / 'marketplace.json').write_text(json.dumps({'plugins': [{'name': 'chatroom', 'version': '1.0.0'}]}), encoding='utf-8')
res = {c: s for c, s, f, _ in doctor.checks(None, 'no-such-claude', tree / 'plugins' / 'chatroom')}
ok('and nothing when they agree', 'marketplace_differs' not in res, res)
ok('a plugin outside a repo (installed copy) has no marketplace to check', doctor.marketplace_version(BASE) is None)

# V6: the proofs, with the user's real files watched
real = Path.home() / '.claude' / 'chatroom' / 'spawn'
watch = [real / n for n in ('boards.json', 'studied.json', 'glossary_extra.json', 'catalog.json')]
before = {p: (p.read_bytes() if p.is_file() else None) for p in watch}
env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_CONFIG_DIR'}      # the proofs run as the user runs them
for f in ('researcher', 'sources', 'strengths'):
    p = subprocess.run([sys.executable, '-X', 'utf8', str(Path(SCRIPTS) / 'spawn' / 'bench' / f'{f}.py')], capture_output=True, text=True, encoding='utf-8', timeout=120, env=env)
    ok(f'the proof of {f}.py passes', p.returncode == 0 and f'{f} ok' in p.stdout, p.stdout[-200:] + p.stderr[-400:])
ok('and left the real files of the user as they were', before == {p: (p.read_bytes() if p.is_file() else None) for p in watch})
print('FAILS', fails)
sys.exit(1 if fails else 0)
