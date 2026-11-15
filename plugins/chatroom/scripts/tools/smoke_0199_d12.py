"""0.19.9 D2: update_apply of a marketplace plugin. `claude plugin update` only reads the marketplace copy on disk (seen live against
a git marketplace served on localhost: update said "already at the latest version" while a newer one was pushed, until `claude plugin
marketplace update` ran). So apply refreshes the marketplace first, and never says "updated" when the tool changed nothing.
The tool is a stub that behaves like the real one; nothing real is read or written.  Run: python tools/smoke_0199_d12.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199d12_'))
C = BASE / 'claude'
os.environ['CLAUDE_CONFIG_DIR'] = str(C)
os.environ['CHATROOM_SKILLS_DIR'] = str(BASE / 'dl')
os.environ['CHATROOM_SKILLS_USER_DIR'] = str(C / 'skills')
os.environ['CLAUDE_DATA_DIR'] = str(BASE / 'desktop')
sys.path.insert(0, SCRIPTS)
import chat        # noqa: E402
import skills      # noqa: E402
import skills_d7   # noqa: E402
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def jw(p, v):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v), encoding='utf-8')


d = C / 'plugins/cache/ghmk/gp/1.0.0/skills/gpskill'
d.mkdir(parents=True)
(d / 'SKILL.md').write_text('---\nname: gpskill\ndescription: A skill of a github plugin\n---\nbody\n', encoding='utf-8')
jw(C / 'plugins' / 'installed_plugins.json', {'version': 2, 'plugins': {'gp@ghmk': [
    {'scope': 'user', 'installPath': str(C / 'plugins/cache/ghmk/gp/1.0.0'), 'version': '1.0.0', 'gitCommitSha': 'a' * 40}]}})
jw(C / 'plugins' / 'known_marketplaces.json', {'ghmk': {'source': {'source': 'github', 'repo': 'bob/market'}}})
jw(C / 'settings.json', {'enabledPlugins': {'gp@ghmk': True}})
room = BASE / 'room'
subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(room), '--participants', 'CORE,UI', '--lang', 'en'], capture_output=True)
r = chat.Room(room)
GH = 'https://raw.githubusercontent.com/bob/market/HEAD/.claude-plugin/marketplace.json'
web = {GH: json.dumps({'plugins': [{'name': 'gp', 'source': './plugins/gp', 'version': '1.2.0'}]})}
skills_d7.http_get = lambda url: web[url] if url in web else (_ for _ in ()).throw(OSError('404'))
skills_d7.git = lambda args, cwd=None: (0, 'c' * 40 + '\tHEAD\n') if args[:1] == ['ls-remote'] else (1, '')


def tool(refreshes):
    """the claude CLI as seen live: the marketplace copy is refreshed only by `marketplace update`; `plugin update` compares with that copy"""
    st = {'copy': '1.0.0', 'ran': []}

    def run(argv, cwd=None):
        st['ran'].append(argv)
        if argv[:4] == ['claude', 'plugin', 'marketplace', 'update']:
            st['copy'] = '1.2.0' if refreshes else st['copy']
            return 0, 'Successfully updated marketplace\n'
        if argv[:3] == ['claude', 'plugin', 'update']:
            return (0, 'Plugin "gp" updated from 1.0.0 to 1.2.0. Restart to apply changes.\n') if st['copy'] != '1.0.0' \
                else (0, 'gp is already at the latest version (1.0.0).\n')
        return 1, 'unexpected\n'
    return st, run


st, skills_d7.run = tool(True)
res = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill', 'confirm': True})
ran = [' '.join(x) for x in st['ran']]
ok('apply refreshes the marketplace first, then updates', ran == ['claude plugin marketplace update ghmk', 'claude plugin update gp@ghmk -s user'], ran)
ok('apply: the update is reported as done', res['ok'] and res['applied'] and res['restart'] and res['installed'] == '1.2.0', res)

st, skills_d7.run = tool(False)
res = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill', 'confirm': True})
ok('apply: the tool changed nothing ("already at the latest") = an error that says so, never "updated"', res['ok'] is False and 'not updated' in res['error'] and 'already at the latest' in res['error'], res)

skills_d7.run = lambda argv, cwd=None: (1, 'network down\n') if argv[:4] == ['claude', 'plugin', 'marketplace', 'update'] else (0, 'x')
res = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill', 'confirm': True})
ok('apply: the marketplace refresh failing is an error with its output, the update is not tried', res['ok'] is False and 'network down' in res['error'], res)

ran = []
skills_d7.run = lambda argv, cwd=None: ran.append(argv) or (0, 'x')
pv = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill'})
ok('apply without confirm: a preview, nothing run', pv['ok'] and 'preview' in pv and ran == [], (pv, ran))

print(f'{fails} failed' if fails else 'all passed')
sys.exit(1 if fails else 0)
