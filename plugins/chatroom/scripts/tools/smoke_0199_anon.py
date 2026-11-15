"""0.19.9 ANON: the plugin is updated by other people and shown in videos, so no file of the repo names this machine or its user.
Scans every tracked file for a machine path, a user name or a mail box; the author's own credit (licence, manifests, README, hangar
credits) and third-party credits are listed in ALLOWED. A new hit fails the test: fix the file, or add it to ALLOWED with the reason.
Run: python tools/smoke_0199_anon.py"""
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(os.environ.get('CHATROOM_SCRIPTS') or Path(__file__).resolve().parent.parent).resolve().parent
ROOT = PLUGIN.parent.parent if (PLUGIN.parent.parent / '.git').exists() else PLUGIN
BAD = re.compile(r'claudecode pesante|\bAdministrator\b|[A-Za-z]:[\\/]+Users[\\/]+(?!me\b|name\b|you\b|user\b)\w+|\bAdrian\b|\bIancu\b|[Gg]mail')
ALLOWED = {   # path (from the repo root) -> why the hit is fine
    'LICENSE': 'author credit', 'plugins/chatroom/LICENSE': 'author credit', 'plugins/chatroom/NOTICE': 'author credit', 'README.md': 'author credit and profile links',
    'plugins/chatroom/README.md': 'author credit and profile links', 'plugins/chatroom/.claude-plugin/plugin.json': 'author field',
    'plugins/chatroom/.codex-plugin/plugin.json': 'author field', 'plugins/chatroom/scripts/office-hangar.js': 'credits easter egg of the author',
    'plugins/chatroom/scripts/tools/test_hangar.mjs': 'tests the credits',
    'plugins/chatroom/scripts/tools/smoke_0199_anon.py': 'this file',
}
ALLOWED_DIRS = ('plugins/chatroom/arcade/',)      # the games of other authors, with their own credits
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:900]}]'), flush=True)
    fails += not cond


def tracked():
    p = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], capture_output=True)
    if p.returncode == 0 and p.stdout:
        return [f for f in p.stdout.decode('utf-8').split('\0') if f]
    return [str(f.relative_to(ROOT)).replace('\\', '/') for f in ROOT.rglob('*') if f.is_file()]       # not a git checkout: every file


files = [f for f in tracked() if '/vendor/' not in f and not f.endswith(('uv.lock', '.png', '.jpg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.glb', '.mp3', '.ogg', '.wav', '.zip'))]
hits = []
for f in files:
    if f in ALLOWED or f.startswith(ALLOWED_DIRS):
        continue
    try:
        text = (ROOT / f).read_text(encoding='utf-8', errors='replace')
    except OSError:
        continue
    for n, line in enumerate(text.splitlines(), 1):
        m = BAD.search(line)
        if m:
            hits.append(f'{f}:{n}: {m.group(0)}')
ok(f'no file names this machine or its user ({len(files)} files scanned)', not hits, '; '.join(hits[:12]) + (f' ... +{len(hits) - 12}' if len(hits) > 12 else ''))
ok('no internal documents folder in the repo', not (ROOT / 'docs').exists() or not any(f.startswith('docs/') for f in files), 'docs/ is tracked')
print(f'{fails} failed' if fails else 'all passed')
sys.exit(1 if fails else 0)
