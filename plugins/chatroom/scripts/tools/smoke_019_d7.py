"""D7 of the skill workshop: the lead derives skills from the conversation (request, relay line, done), where each skill comes from and the
update check/apply of skills with an external creator. No network, no real claude or git push: the outside calls of skills_d7 are replaced.
Run: python tools/smoke_019_d7.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke019d7_'))
C = BASE / 'claude'
os.environ['CLAUDE_CONFIG_DIR'] = str(C)
os.environ['CHATROOM_SKILLS_DIR'] = str(BASE / 'dl')
os.environ['CHATROOM_SKILLS_USER_DIR'] = str(C / 'skills')
os.environ['CLAUDE_DATA_DIR'] = str(BASE / 'desktop')
sys.path.insert(0, SCRIPTS)
import chat        # noqa: E402
import skills      # noqa: E402
import skills_d6   # noqa: E402
import skills_d7   # noqa: E402
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def mk(root, name, desc, body='old body\n'):
    d = Path(root) / name
    d.mkdir(parents=True)
    (d / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {desc}\n---\n{body}', encoding='utf-8')
    return d


def jw(p, v):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v), encoding='utf-8')


# skills of every origin: a user folder, a user clone, a project one, a github plugin, a local-directory plugin, an added clone, account
mine = mk(C / 'skills', 'mine', 'Merge pdf files into one document')
cl = mk(C / 'skills', 'cloned', 'A skill cloned from a repo')
(cl / '.git').mkdir()
(cl / '.git' / 'config').write_text('[core]\n\tbare = false\n[remote "origin"]\n\turl = https://github.com/alice/cloned-skill.git\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n', encoding='utf-8')
gp = mk(C / 'plugins/cache/ghmk/gp/1.0.0/skills', 'gpskill', 'A skill of a github plugin')
lp = mk(C / 'plugins/cache/lomk/lp/0.1.0/skills', 'lpskill', 'A skill of my own local plugin')
jw(C / 'plugins' / 'installed_plugins.json', {'version': 2, 'plugins': {
    'gp@ghmk': [{'scope': 'user', 'installPath': str(C / 'plugins/cache/ghmk/gp/1.0.0'), 'version': '1.0.0', 'gitCommitSha': 'a' * 40}],
    'lp@lomk': [{'scope': 'user', 'installPath': str(C / 'plugins/cache/lomk/lp/0.1.0'), 'version': '0.1.0', 'gitCommitSha': 'b' * 40}]}})
jw(C / 'plugins' / 'known_marketplaces.json', {'ghmk': {'source': {'source': 'github', 'repo': 'bob/market'}}, 'lomk': {'source': {'source': 'directory', 'path': 'E:/x'}}})
jw(C / 'settings.json', {'enabledPlugins': {'gp@ghmk': True, 'lp@lomk': True}})
clone = BASE / 'dl' / 'carol__skillrepo'
added = mk(clone, 'addedskill', 'A skill added from a clone')
(clone / '.git').mkdir()
(clone / '.git' / 'config').write_text('[remote "origin"]\n\turl = git@github.com:carol/skillrepo.git\n', encoding='utf-8')
room = BASE / 'room'
subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(room), '--participants', 'CORE,UI', '--lang', 'en'], capture_output=True)
cfg = json.loads((room / 'config.json').read_text(encoding='utf-8'))
cfg['self_names'] = ['LEAD']
jw(room / 'config.json', cfg)
r = chat.Room(room)
jw(room / 'skills.json', {'v': 1, 'seq': 0, 'roots': [str(clone)], 'requests': [], 'advised': []})

# ---- B: where a skill comes from (local files only, no network)
calls = []
skills_d7.http_get = lambda url: calls.append(url) or (_ for _ in ()).throw(OSError('offline'))
skills_d7.git = lambda args, cwd=None: calls.append(args) or (1, '')
idx = skills.index(r)
by = {s['name']: s for s in idx['skills']}
ok('index: no network and no subprocess to tell the sources', calls == [], calls)
ok('source: a user folder without git is "you", no update', by['mine']['source']['kind'] == 'you' and by['mine']['updatable'] is False, by['mine'].get('source'))
ok('source: a user folder that is a clone: repo alice/cloned-skill, updatable', by['cloned']['source']['kind'] == 'repo' and by['cloned']['source']['label'] == 'alice/cloned-skill'
   and by['cloned']['source']['url'] == 'https://github.com/alice/cloned-skill' and by['cloned']['updatable'] is True, by['cloned'].get('source'))
ok('source: a plugin of a github marketplace: label, url, version, updatable', by['gpskill']['source'] == {'kind': 'marketplace', 'label': 'gp@ghmk', 'url': 'https://github.com/bob/market', 'version': '1.0.0'}
   and by['gpskill']['updatable'] is True, by['gpskill'].get('source'))
ok('source: a plugin of a local-directory marketplace is "local", no update', by['lpskill']['source']['kind'] == 'local' and by['lpskill']['updatable'] is False, by['lpskill'].get('source'))
ok('source: an added clone is a repo carol/skillrepo (ssh url)', by['addedskill']['source']['label'] == 'carol/skillrepo' and by['addedskill']['updatable'] is True, by['addedskill'].get('source'))
ok('source: builtin never updatable', all(s['updatable'] is False and s['source']['kind'] == 'builtin' for s in idx['skills'] if s['origin'] == 'builtin'))
ok('every skill has source.kind from the list and a bool updatable', all(s['source']['kind'] in skills_d7.KINDS and isinstance(s['updatable'], bool) for s in idx['skills']))

# ---- B: update_check
GH = 'https://raw.githubusercontent.com/bob/market/HEAD/.claude-plugin/marketplace.json'
web = {GH: json.dumps({'plugins': [{'name': 'gp', 'source': './plugins/gp', 'version': '1.2.0'}]}),
       'https://api.github.com/repos/bob/market/compare/' + 'a' * 40 + '...' + 'c' * 40: json.dumps(
           {'status': 'ahead', 'ahead_by': 3, 'commits': [{'commit': {'message': 'fix a\n\nbody'}}, {'commit': {'message': 'add b'}}],
            'files': [{'filename': 'plugins/gp/skills/x.md'}, {'filename': 'README.md'}]})}
heads = {'https://github.com/bob/market.git': 'c' * 40, 'https://github.com/alice/cloned-skill.git': 'e' * 40}


def fake_http(url):
    if url in web:
        return web[url]
    raise OSError('404')


def fake_git(args, cwd=None):
    if args[:1] == ['ls-remote']:
        return (0, f'{heads[args[-2]]}\tHEAD\n') if args[-2] in heads and args[1] == '--' else (128, '')
    if args == ['rev-parse', 'HEAD']:
        return 0, 'd' * 40 + '\n'
    if args == ['status', '--porcelain']:
        return 0, STATUS[0]
    return 1, ''


STATUS = ['']
skills_d7.http_get, skills_d7.git = fake_http, fake_git
res = skills.do(r, {'action': 'update_check', 'skill': 'plugin:gp:gpskill'})
u = res.get('update') or {}
ok('update_check plugin: installed 1.0.0, available 1.2.0 (the creator\'s marketplace.json), newer', res['ok'] and u['installed'] == '1.0.0' and u['available'] == '1.2.0' and u['newer'] is True
   and u['source'] == 'plugin gp@ghmk' and u['kind'] == 'marketplace' and u['checked_at'] > 0, res)
ok('update_check: what changes is told (commits, files under the plugin only, subjects)', '3 commits' in u['changes'] and '1 files' in u['changes'] and 'fix a' in u['changes'] and 'body' not in u['changes'], u.get('changes'))
web[GH] = json.dumps({'plugins': [{'name': 'gp', 'source': './plugins/gp', 'version': '1.0.0'}]})
res = skills.do(r, {'action': 'update_check', 'skill': 'plugin:gp:gpskill'})
ok('update_check: same version = not newer', res['ok'] and res['update']['newer'] is False, res)
web[GH] = json.dumps({'plugins': [{'name': 'gp', 'source': './plugins/gp'}]})
web['https://raw.githubusercontent.com/bob/market/HEAD/plugins/gp/.claude-plugin/plugin.json'] = json.dumps({'version': '1.0.0'})
res = skills.do(r, {'action': 'update_check', 'skill': 'plugin:gp:gpskill'})
ok('update_check: with no version in the marketplace the plugin.json of the plugin folder counts', res['ok'] and res['update']['available'] == '1.0.0' and res['update']['newer'] is False, res)
res = skills.do(r, {'action': 'update_check', 'skill': 'user:-:cloned'})
u = res.get('update') or {}
ok('update_check repo: local sha d.. vs remote e.., unknown compare = newer null, shas shown', res['ok'] and u['installed'] == 'ddddddd' and u['available'] == 'eeeeeee' and u['newer'] is None
   and u['source'] == 'repo alice/cloned-skill', res)
web['https://api.github.com/repos/alice/cloned-skill/compare/' + 'd' * 40 + '...' + 'e' * 40] = json.dumps({'status': 'ahead', 'ahead_by': 2, 'commits': [], 'files': []})
res = skills.do(r, {'action': 'update_check', 'skill': 'user:-:cloned'})
ok('update_check repo: remote ahead = newer', res['ok'] and res['update']['newer'] is True, res)
for ref, why in (('user:-:mine', 'yours'), ('plugin:lp:lpskill', 'computer'), ('builtin:-:loop', 'built into')):
    res = skills.do(r, {'action': 'update_check', 'skill': ref})
    ok(f'update_check refused for {ref}', res['ok'] is False and why in res['error'], res)
ok('update_check: unknown skill', skills.do(r, {'action': 'update_check', 'skill': 'nope'})['ok'] is False)
skills_d7.http_get, skills_d7.git = lambda url: (_ for _ in ()).throw(OSError('offline')), lambda args, cwd=None: (128, '')
res = skills.do(r, {'action': 'update_check', 'skill': 'user:-:cloned'})
ok('update_check offline: a clear error, no crash', res['ok'] is False and 'creator' in res['error'], res)
skills_d7.http_get, skills_d7.git = fake_http, fake_git

# a hostile remote url (a .git/config out of a zip) never reaches git; the real run() finds programs by their full path (claude.cmd on Windows)
bad = mk(C / 'skills', 'hostile', 'A skill with a hostile clone')
(bad / '.git').mkdir()
(bad / '.git' / 'config').write_text('[remote "origin"]\n\turl = --upload-pack=cmd /c echo pwned\n', encoding='utf-8')
seen = []
skills_d7.git = lambda args, cwd=None: seen.append(args) or (0, 'x\tHEAD\n')
hs = {x['name']: x for x in skills.index(r)['skills']}['hostile']
ok('a hostile remote url: not updatable, never given to git', hs['updatable'] is False and skills_d7.remote_head('--upload-pack=x') is None and skills_d7.remote_head('file:///etc') is None
   and skills_d7.remote_head('ext::sh -c id') is None and seen == [], (hs.get('source'), seen))
skills_d7.git = fake_git
code, out = skills_d7.run([Path(sys.executable).stem, '-c', 'print("hi")'])
ok('run: a bare program name is resolved to its full path', code == 0 and 'hi' in out, (code, out))

# ---- B: update_apply (nothing runs without confirm)
ran = []
skills_d7.run = lambda argv, cwd=None: ran.append((argv, cwd)) or (0, 'Updated gp. Restart to apply.\n')
web[GH] = json.dumps({'plugins': [{'name': 'gp', 'source': './plugins/gp', 'version': '1.2.0'}]})
pv = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill'})
p = pv.get('preview') or {}
ok('update_apply plugin without confirm: a preview, nothing run', pv['ok'] and ran == [] and p['how'] == 'claude plugin update gp@ghmk -s user' and p['installed'] == '1.0.0'
   and p['available'] == '1.2.0' and p['restart'] is True and p['name'] == 'gpskill', pv)
res = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill', 'confirm': True})
ok('update_apply plugin with confirm: runs claude plugin update, says restart', res['ok'] and res['applied'] and res['restart'] and ran[-1][0] == ['claude', 'plugin', 'update', 'gp@ghmk', '-s', 'user']
   and res['installed'] == '1.2.0', (res, ran))
n = len(ran)
res = skills.do(r, {'action': 'update_apply', 'skill': 'user:-:cloned', 'confirm': True})
ok('update_apply repo: git pull --ff-only in the clone, no restart', res['ok'] and ran[n][0][:2] == ['git', '-C'] and ran[n][0][-2:] == ['pull', '--ff-only'] and res['restart'] is False, (res, ran))
STATUS[0] = ' M file.md\n'
n = len(ran)
res = skills.do(r, {'action': 'update_apply', 'skill': 'user:-:cloned', 'confirm': True})
ok('update_apply repo with local changes: refused, nothing run', res['ok'] is False and 'local changes' in res['error'] and len(ran) == n, res)
STATUS[0] = ''
web[GH] = json.dumps({'plugins': [{'name': 'gp', 'source': './plugins/gp', 'version': '1.0.0'}]})
n = len(ran)
res = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill', 'confirm': True})
ok('update_apply when up to date: refused', res['ok'] is False and 'up to date' in res['error'] and len(ran) == n, res)
for ref in ('user:-:mine', 'plugin:lp:lpskill', 'builtin:-:loop'):
    ok(f'update_apply refused for {ref}', skills.do(r, {'action': 'update_apply', 'skill': ref, 'confirm': True})['ok'] is False)
skills_d7.run = lambda argv, cwd=None: (1, 'boom\n')
web[GH] = json.dumps({'plugins': [{'name': 'gp', 'source': './plugins/gp', 'version': '1.2.0'}]})
res = skills.do(r, {'action': 'update_apply', 'skill': 'plugin:gp:gpskill', 'confirm': True})
ok('update_apply: a failing tool is an error with its output', res['ok'] is False and 'boom' in res['error'], res)

# ---- A: derive from the lead's conversation
before = json.loads((room / 'skills.json').read_text(encoding='utf-8'))['seq']
pv = skills.do(r, {'action': 'derive', 'source': {'chat': True}, 'desc': ''})
p = pv.get('preview') or {}
ok('chat derive without confirm: a preview with the lead, no desc needed, no budget, nothing written', pv['ok'] and p['name'] == 'LEAD' and p['kind'] == 'derive' and 'budget_usd' not in p
   and p['reads'] and p['writes'] == ['skills-candidates/**'] and json.loads((room / 'skills.json').read_text(encoding='utf-8'))['seq'] == before and not (room / 'skills-jobs').exists(), pv)
res = skills.do(r, {'action': 'derive', 'source': {'chat': True}, 'desc': 'the pdf merge trick', 'confirm': True})
req = res.get('req')
ok('chat derive confirm: {req, name:lead, via:lead}, nothing started', res['ok'] and req == f'r{before + 1}' and res['name'] == 'LEAD' and res['via'] == 'lead', res)
brief = (room / 'skills-jobs' / f'{req}.brief.md')
txt = brief.read_text(encoding='utf-8') if brief.is_file() else ''
ok('the brief: wish, D6 rules, the closing line to post, the skills that exist (no builtin)', 'the pdf merge trick' in txt and 'meta.json' in txt and f'SKILLDERIVE {req} done' in txt
   and 'user:-:mine' in txt and 'builtin:' not in txt and 'chat.jsonl' in txt, txt[:300])
st = json.loads((room / 'skills.json').read_text(encoding='utf-8'))['requests'][-1]
ok('the request: src chat, searcher is the lead, not announced yet', st['src'] == 'chat' and st['searcher'] == 'LEAD' and st['announced'] is False and st['kind'] == 'derive', st)
ok('a second chat derive while waiting is refused', skills.do(r, {'action': 'derive', 'source': {'chat': True}, 'confirm': True})['ok'] is False)
view = [x for x in skills.index(r)['requests'] if x['req'] == req][0]
ok('requests[]: via lead, pending, not announced, no log', view['state'] == 'pending' and view['via'] == 'lead' and view['announced'] is False and view['log'] is None and view['kind'] == 'derive', view)
lines = chat.skill_lines(r)
ok('the relay line: once, with the brief path, the candidates folder and what to post', len(lines) == 1 and f'SKILLDERIVE {req} (derive)' in lines[0] and f'{req}.brief.md' in lines[0]
   and '/skills-candidates' in lines[0] and 'done: N candidates' in lines[0] and 'the pdf merge trick' in lines[0], lines)
ok('the relay line is not repeated', chat.skill_lines(r) == [])
ok('requests[]: announced now', [x for x in skills.index(r)['requests'] if x['req'] == req][0]['announced'] is True)
ok('still pending with no candidate and no word of the lead', [x for x in skills.index(r)['requests'] if x['req'] == req][0]['state'] == 'pending')
r.append('UI', f'SKILLDERIVE {req} done: 1 candidates')
ok('only the lead\'s word counts: a line by somebody else leaves it pending', [x for x in skills.index(r)['requests'] if x['req'] == req][0]['state'] == 'pending')
r.append('LEAD', f'SKILLDERIVE {req} done: none, nothing repeated twice')
view = [x for x in skills.index(r)['requests'] if x['req'] == req][0]
ok('the lead says done: none -> state done, its words as note', view['state'] == 'done' and 'nothing repeated' in view['note'], view)
# a candidate the lead wrote is a D6 candidate of the request
res = skills.do(r, {'action': 'suggest', 'source': {'chat': True}, 'confirm': True})
req2 = res['req']
d = room / 'skills-candidates' / 'pdf-merge'
d.mkdir(parents=True)
(d / 'SKILL.md').write_text('---\nname: pdf-merge\ndescription: Merge pdf files in page order\n---\n1. run it\n', encoding='utf-8')
(d / 'meta.json').write_text(json.dumps({'v': 1, 'name': 'pdf-merge', 'req': req2, 'kind': 'suggest', 'score': 7, 'why': 'again', 'criteria': {}, 'repeated': [], 'hard': []}), encoding='utf-8')
ix = skills.index(r)
ok('a candidate written for the request makes it done and shows in candidates[]', [x for x in ix['requests'] if x['req'] == req2][0]['state'] == 'done'
   and any(c['name'] == 'pdf-merge' for c in ix['candidates']), ix['requests'][-1])
ok('suggest brief names the existing skills for the overlap', 'SKILLSUGGEST' in (room / 'skills-jobs' / f'{req2}.brief.md').read_text(encoding='utf-8'))
# improve from the conversation: the current text is copied for the lead
res = skills.do(r, {'action': 'improve', 'skill': 'user:-:mine', 'source': {'chat': True}, 'desc': 'add the page order', 'confirm': True})
req3 = res['req']
ok('chat improve: the current SKILL.md is copied next to the brief, brief names id and file', res['ok'] and (room / 'skills-jobs' / f'{req3}.current.md').read_text(encoding='utf-8').startswith('---')
   and 'user:-:mine' in (room / 'skills-jobs' / f'{req3}.brief.md').read_text(encoding='utf-8') and 'improves' in (room / 'skills-jobs' / f'{req3}.brief.md').read_text(encoding='utf-8'), res)
ok('chat improve of a builtin is refused', skills.do(r, {'action': 'improve', 'skill': 'builtin:-:loop', 'source': {'chat': True}, 'confirm': True})['ok'] is False)
lines = chat.skill_lines(r)
ok('the relay prints the two new requests, one line each', len(lines) == 2 and f'SKILLSUGGEST {req2} (suggest)' in lines[0] and f'SKILLIMPROVE {req3} (improve)' in lines[1], lines)
# no answer for an hour = failed
jw(room / 'skills.json', {**json.loads((room / 'skills.json').read_text(encoding='utf-8')), 'requests': [{**x, 'at': int(time.time()) - 4000} if x['req'] == req3 else x
                                                                                                    for x in json.loads((room / 'skills.json').read_text(encoding='utf-8'))['requests']]})
ok('an hour without candidate or word of the lead = failed', [x for x in skills.index(r)['requests'] if x['req'] == req3][0]['state'] == 'failed')
# the relay down: refused
(room / 'relay_alerts_LEAD.owner').write_text('99999999 1', encoding='utf-8')
res = skills.do(r, {'action': 'derive', 'source': {'chat': True}, 'desc': 'x', 'confirm': True})
ok('the lead\'s relay gone: refused with a clear text, nothing written', res['ok'] is False and 'relay' in res['error'], res)
(room / 'relay_alerts_LEAD.owner').unlink()
# no lead
cfg['self_names'] = []
jw(room / 'config.json', cfg)
ok('a room without a lead: refused', skills.do(r, {'action': 'derive', 'source': {'chat': True}, 'desc': 'x', 'confirm': True})['ok'] is False)
# the other sources still work as in D6 (a room source needs a desc)
ok('derive from the room still needs a desc', skills.do(r, {'action': 'derive', 'source': {'room': 'current'}, 'desc': ''})['ok'] is False)
print('OK: 0 failures' if not fails else f'FAILED: {fails}')
sys.exit(1 if fails else 0)
