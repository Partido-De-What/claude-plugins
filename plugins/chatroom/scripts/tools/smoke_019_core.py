"""0.19.0 CORE: the skill workshop (skills.py, GET /skills.json, POST /skills/do). Fake CLAUDE_CONFIG_DIR, nothing real is read or written.
Run: python smoke_019_core.py   (CHATROOM_SCRIPTS = the scripts folder, default: this file's parent)"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke019core_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_SKILLS_DIR'] = str(BASE / 'dl')
os.environ['CLAUDE_DATA_DIR'] = str(BASE / 'desktop')     # the desktop app's folder: a fake one, never the real one
sys.path.insert(0, SCRIPTS)
import chat      # noqa: E402
import skills    # noqa: E402
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def mk(root, name, desc, extra=''):
    d = Path(root) / name
    d.mkdir(parents=True)
    (d / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {desc}\n{extra}---\nBODY-MUST-NOT-APPEAR\n', encoding='utf-8')
    return d


C = BASE / 'claude'
mk(C / 'skills', 'mine', 'Does mine things. Second sentence here.')
mk(C / 'plugins/cache/mk/pl/1.0.0/skills', 'old', 'old version')
mk(C / 'plugins/cache/mk/pl/1.10.0/skills', 'new', 'folded >\n  text over two lines'.replace('>', '"x"') if False else 'New thing')
mk(C / 'plugins/cache/mk/pl/1.10.0/skills', 'caveman', 'Terse style')
(C / 'plugins/cache/mk/pl/1.10.0/agents').mkdir(parents=True)
(C / 'plugins/cache/mk/pl/1.10.0/agents/worker.md').write_text('---\nname: worker\nskills:\n  - mine\n  - pl:new\n---\nhi', encoding='utf-8')
extra = mk(BASE / 'extra', 'foo', 'Foo skill')
room = BASE / 'room'
subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(room), '--participants', 'CORE,SEARCHER,UI', '--lang', 'en'], capture_output=True)
(room / 'prompts').mkdir(exist_ok=True)
(room / 'prompts' / 'UI.md').write_text('First invoke the skill pl:caveman. Then close.', encoding='utf-8')
sub = C / 'projects' / 'p' / 's' / 'subagents'
sub.mkdir(parents=True)
(sub / 'agent-aabbccdd11223344.jsonl').write_text(
    json.dumps({'message': {'content': [{'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'mine'}}]}}) + '\n', encoding='utf-8')
(sub / 'agent-aabbccdd11223344.meta.json').write_text(json.dumps({'agentType': 'pl:worker'}), encoding='utf-8')
r = chat.Room(room)
r.update_roster(lambda ro: ro.update({'CORE': 'aabbccdd11223344'}))

# index
before = sorted(str(p) for p in BASE.rglob('*'))
idx = skills.index(r)
byname = {s['name']: s for s in idx['skills'] if s['origin'] != 'builtin'}
ok('index: user, plugin skills found, only the newest plugin version', set(byname) == {'mine', 'new', 'caveman'}, list(byname))
ok('index: ids and origins', byname['mine']['id'] == 'user:-:mine' and byname['new']['id'] == 'plugin:pl:new' and byname['new']['plugin'] == 'pl@mk' and byname['new']['version'] == '1.10.0', byname)
ok('index: brief is the first sentence, body never read', byname['mine']['brief'] == 'Does mine things.' and 'BODY' not in json.dumps(idx), byname['mine'])
ag = {a['name']: a for a in idx['agents']}
ok('agents: used (transcript) + type (agent file) for CORE', {(s['id'], tuple(s['via'])) for s in ag['CORE']['skills']} ==
   {('user:-:mine', ('type', 'used')), ('plugin:pl:new', ('type',))} and ag['CORE']['type'] == 'worker', ag['CORE'])
ok('agents: count of calls', next(s for s in ag['CORE']['skills'] if s['id'] == 'user:-:mine')['count'] == 1, ag['CORE'])
ok('agents: prompt mention counts, a bare word does not', [(s['id'], s['via']) for s in ag['UI']['skills']] == [('plugin:pl:caveman', ['brief'])], ag['UI'])
ok('index: agents list on the skill', byname['mine']['agents'] == ['CORE'] and byname['caveman']['agents'] == ['UI'], byname)
ok('searcher present by name, not busy', idx['searcher'] == {'present': True, 'name': 'SEARCHER', 'busy': False}, idx['searcher'])
ok('filter by text and origin', [s['name'] for s in skills.index(r, 'terse')['skills']] == ['caveman'] and
   [s['name'] for s in skills.index(r, '', 'user')['skills']] == ['mine'], 'filter')
ok('index writes nothing', before == sorted(str(p) for p in BASE.rglob('*')), 'tree changed')


# D3: installed_plugins.json + enabledPlugins, the desktop app's plugins, the account's skills, the built-ins
inst = C / 'plugins' / 'cache' / 'mk2' / 'off' / '2.0.0'
mk(inst / 'skills', 'offskill', 'Installed but not enabled')
(C / 'plugins' / 'installed_plugins.json').write_text(json.dumps({'version': 2, 'plugins': {
    'pl@mk': [{'scope': 'user', 'installPath': str(C / 'plugins/cache/mk/pl/1.10.0'), 'version': '1.10.0'}],
    'off@mk2': [{'scope': 'user', 'installPath': str(inst), 'version': '2.0.0'}]}}), encoding='utf-8')
(C / 'settings.json').write_text(json.dumps({'enabledPlugins': {'pl@mk': True}}), encoding='utf-8')
DD = BASE / 'desktop' / 'claude_x'
pd = DD / 'rpm/a/b/plugin_01'
mk(pd / 'skills', 'deskskill', 'From the desktop app')
(pd / '.claude-plugin').mkdir()
(pd / '.claude-plugin' / 'plugin.json').write_text(json.dumps({'name': 'deskplug'}), encoding='utf-8')
mk(DD / 'local-agent-mode-sessions/skills-plugin/s/t/skills', 'docx', 'Word files')
d3 = {s['id']: s for s in skills.index(r)['skills']}
ok('D3: installed but not enabled plugin is listed with enabled false, an enabled one true',
   d3['plugin:off:offskill']['enabled'] is False and d3['plugin:pl:new']['enabled'] is True, [(k, v['enabled']) for k, v in d3.items() if v['origin'] == 'plugin'])
ok('D3: desktop plugin and account skill found', d3['plugin:deskplug:deskskill']['plugin'] == 'deskplug@desktop' and d3['account:anthropic-skills:docx']['origin'] == 'account', list(d3))
ok('D3: built-in skills have no file and are listed', d3['builtin:-:simplify']['path'] is None and d3['builtin:-:simplify']['origin'] == 'builtin', '')
ok('D3: find works on anthropic-skills:docx and a built-in', skills.find(list(d3.values()), 'anthropic-skills:docx')['id'] == 'account:anthropic-skills:docx' and
   skills.find(list(d3.values()), 'simplify')['origin'] == 'builtin', '')

# advise
n0 = len(r.messages())
res = skills.do(r, {'action': 'advise', 'skill': 'plugin:pl:caveman', 'to': ['UI']})
msgs = r.messages()
ok('advise: one chat message tagging UI', res['ok'] and len(msgs) == n0 + 1 and '@UI' in msgs[-1]['text'] and 'caveman' in msgs[-1]['text'], (res, msgs[-1:]))
ok('advise to all, by bare name', skills.do(r, {'action': 'advise', 'id': 'mine', 'to': '*'})['ok'] and '@all' in r.messages()[-1]['text'], r.messages()[-1])
ok('advise unknown skill / agent are errors, nothing posted', not skills.do(r, {'action': 'advise', 'skill': 'nope', 'to': 'UI'})['ok'] and
   not skills.do(r, {'action': 'advise', 'skill': 'mine', 'to': 'GHOST'})['ok'] and len(r.messages()) == n0 + 2, 'errors')
ok('advised list', next(s for s in skills.index(r)['skills'] if s['name'] == 'caveman')['advised'][0]['to'] == 'UI', 'advised')

# search
res = skills.do(r, {'action': 'search', 'q': 'pdf merge', 'for': ['UI']})
ok('search: request r1 tagged to the searcher with who it is for', res == {'ok': True, 'req': 'r1', 'searcher': 'SEARCHER'} and
   r.messages()[-1]['text'].startswith('SKILLSEARCH r1: pdf merge [for: UI] @SEARCHER'), (res, r.messages()[-1]))
v = skills.index(r)
ok('search: pending and the searcher is busy', v['requests'][0]['state'] == 'pending' and v['requests'][0]['for'] == ['UI'] and v['searcher']['busy'], v['requests'])
(room / 'research').mkdir(exist_ok=True)
(room / 'research' / 'skills-r1.json').write_text(json.dumps({'req': 'r1', 'query': 'pdf merge', 'status': 'done', 'results': [
    {'name': 'foo', 'what': 'Foo', 'source': 's', 'url': 'https://github.com/o/r', 'trust': 't', 'fit': 0.5, 'install_hint': 'h'}]}), encoding='utf-8')
v = skills.index(r)
ok('search: done, cards from the file', v['requests'][0]['state'] == 'done' and v['requests'][0]['cards'][0]['name'] == 'foo' and
   v['requests'][0]['file'] == 'research/skills-r1.json' and not v['searcher']['busy'], v['requests'])
(room / 'research' / 'skills-r1.json').write_text(json.dumps({'status': 'done', 'results': [{'name': 'evil', 'url': 'javascript:alert(1)'}]}), encoding='utf-8')
ok('cards: a non-http url is emptied', skills.index(r)['requests'][0]['cards'][0]['url'] == '', skills.index(r)['requests'][0]['cards'])
(room / 'research' / 'skills-r1.json').write_text(json.dumps({'req': 'r1', 'query': 'pdf merge', 'status': 'done', 'results': [
    {'name': 'foo', 'what': 'Foo', 'source': 's', 'url': 'https://github.com/o/r', 'trust': 't', 'fit': 0.5, 'install_hint': 'h'}]}), encoding='utf-8')
ok('search: poll one request', skills.do(r, {'action': 'request', 'req': 'r1'})['request']['state'] == 'done', 'poll')
ok('search: empty query is an error', not skills.do(r, {'action': 'search', 'q': '  '})['ok'], '')

# paused
skills.do(r, {'action': 'search', 'q': 'video'})
r.append('SEARCHER', 'pausa task T4 per SKILLSEARCH r2', status=True)
ok('search: paused after the searcher says so', skills.index(r)['requests'][-1]['state'] == 'paused', skills.index(r)['requests'][-1])

# no searcher -> temporary one, preview writes nothing
room2 = BASE / 'room2'
subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(room2), '--participants', 'A,B', '--lang', 'it'], capture_output=True)
r2 = chat.Room(room2)
res = skills.do(r2, {'action': 'search', 'q': 'x'})
ok('no searcher: need temp_searcher (translated error)', res['ok'] is False and res['need'] == 'temp_searcher' and 'searcher' in res['error'], res)
n0 = len(r2.messages())
pre = skills.do(r2, {'action': 'temp_searcher', 'q': 'x', 'for': ['A']})
ok('temp_searcher preview: nothing written', pre['ok'] and pre['preview']['name'] == skills.SEARCH_NAME and len(r2.messages()) == n0 and
   not (room2 / 'skills.json').exists(), pre)
class FakeProc:
    def wait(self, timeout=None):
        (room2 / 'research' / 'skills-r1.json').write_text(json.dumps({'status': 'done', 'results': [{'name': 'a'}, {'name': 'b'}]}), encoding='utf-8')


calls = []
skills.launch = lambda cmd, prompt, cwd, log: calls.append((cmd, prompt, str(cwd))) or FakeProc()     # never start a real claude here
res = skills.do(r2, {'action': 'temp_searcher', 'q': 'x', 'for': ['A'], 'confirm': True})
for _ in range(50):
    if any('done' in m['text'] for m in r2.messages()):
        break
    time.sleep(0.1)
cmd, prompt, cwd = calls[0] if calls else ([], '', '')
ok('temp_searcher confirm: claude -p started once, prompt on stdin, only its own file writable', res['ok'] and len(calls) == 1 and cmd[1] == '-p' and
   '--permission-mode' in cmd and 'dontAsk' in cmd and 'Edit(research/skills-r1.json)' in ' '.join(cmd) and 'x [for: A]' in prompt and 'skills-r1.json' in prompt, (res, cmd, prompt[:200]))
ok('temp_searcher: request kept, chat line, and a done line when the process ends', skills.state_of(r2)['requests'][0]['for'] == ['A'] and
   'claude -p' in r2.messages()[-2]['text'] + r2.messages()[-1]['text'] + (r2.messages()[-3]['text'] if len(r2.messages()) > 2 else '') and
   r2.messages()[-1]['from'] == skills.SEARCH_NAME and '(2)' in r2.messages()[-1]['text'], r2.messages()[-3:])

class NoFileProc:
    returncode = 1
    def wait(self, timeout=None): pass


skills.watch(r2, {'req': 'r9'}, NoFileProc(), 'research/skills-r9.json')
ok('watch: no file -> failed line with the exit code and the log, not "done (0)"', 'ended without' in r2.messages()[-1]['text'] and
   'exit 1' in r2.messages()[-1]['text'] and 'skills-temp/r9.log' in r2.messages()[-1]['text'], r2.messages()[-1])

# add
pre = skills.do(r, {'action': 'add', 'path': str(extra)})
ok('add preview: from/to, nothing written', pre['ok'] and pre['preview']['name'] == 'foo' and pre['preview']['from'] == str(extra) and
   skills.state_of(r)['roots'] == [], pre)
ok('add without a skill folder fails', not skills.do(r, {'action': 'add', 'path': str(BASE / 'nothing')})['ok'], '')
res = skills.do(r, {'action': 'add', 'path': str(extra), 'confirm': True})
ok('add confirm: root kept in the room, origin added', res == {'ok': True, 'id': 'added:-:foo'} and
   next(s for s in skills.index(r)['skills'] if s['name'] == 'foo')['origin'] == 'added', res)
ok('add: the card now shows as added', skills.index(r)['requests'][0]['cards'][0]['added'] is True, '')
ok('add card with a repo url is previewed without cloning', skills.do(r, {'action': 'add', 'req': 'r1', 'card': 'foo'})['preview']['downloads'] is True and
   not (BASE / 'dl').exists(), 'preview')
(room / 'research' / 'skills-r1.json').write_text(json.dumps({'status': 'done', 'results': [{'name': 'esc', 'url': 'https://github.com/o/r', 'skill_path': '../../x/SKILL.md'}]}), encoding='utf-8')
pv = skills.do(r, {'action': 'add', 'req': 'r1', 'card': 'esc'})['preview']
ok('add card: a skill_path leaving the clone is ignored', Path(pv['path']).resolve() == (BASE / 'dl' / 'o__r').resolve(), pv)
ok('add card without a github url fails', not skills.do(r, {'action': 'add', 'req': 'r9', 'card': 'x'})['ok'], '')
ok('unknown action', not skills.do(r, {'action': 'zap'})['ok'], '')

# HTTP: the routes of cmd_serve
import socket
with socket.socket() as sk:                    # a free port: a fixed one answered from a server left by an earlier run
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
env = {**os.environ, 'CHATROOM_LIVE': '1'}
p = subprocess.Popen([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'serve', '--room', str(room), '--port', str(port)], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://localhost:{port}/skills.json', timeout=2)
            break
        except OSError:
            time.sleep(0.3)
    got = json.load(urllib.request.urlopen(f'http://localhost:{port}/skills.json?q=terse', timeout=10))
    ok('GET /skills.json?q=', got['v'] == 1 and [s['name'] for s in got['skills']] == ['caveman'], got)
    rq = urllib.request.Request(f'http://localhost:{port}/skills/do', data=json.dumps({'action': 'request', 'req': 'r1'}).encode(),
                                headers={'Content-Type': 'application/json'})
    ok('POST /skills/do', json.load(urllib.request.urlopen(rq, timeout=10))['request']['req'] == 'r1', '')
except Exception as exc:
    ok('http', False, repr(exc))
finally:
    p.terminate()
    # serve re-launches itself under the plugin's python, so the listener is not our child: stop whoever listens on our port
    out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True).stdout if os.name == 'nt' else ''
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 5 and cols[1].endswith(f':{port}') and cols[3] == 'LISTENING':
            subprocess.run(['taskkill', '/F', '/PID', cols[4]], capture_output=True)
print(f'{"FAIL" if fails else "OK"}: {fails} failures')
sys.exit(1 if fails else 0)
