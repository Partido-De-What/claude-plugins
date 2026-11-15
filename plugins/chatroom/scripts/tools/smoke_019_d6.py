"""D6 of the skill workshop (skills_d6.py): candidates, derive/suggest/improve jobs (never a real claude), diff, promote with backup,
dismiss. Nothing outside a temp folder is touched. Run: python tools/smoke_019_d6.py"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke019d6_'))
C = BASE / 'claude'
os.environ['CLAUDE_CONFIG_DIR'] = str(C)
os.environ['CHATROOM_SKILLS_DIR'] = str(BASE / 'dl')
os.environ['CHATROOM_SKILLS_USER_DIR'] = str(C / 'skills')
os.environ['CLAUDE_DATA_DIR'] = str(BASE / 'desktop')
sys.path.insert(0, SCRIPTS)
import chat        # noqa: E402
import skills      # noqa: E402
import skills_d6   # noqa: E402
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


def tree(p):
    return sorted((str(x.relative_to(p)), hashlib.md5(x.read_bytes()).hexdigest()) for x in Path(p).rglob('*') if x.is_file())


mine = mk(C / 'skills', 'mine', 'Merge pdf files into one document in page order')
(mine / 'old.txt').write_text('only in the old version', encoding='utf-8')
plug = mk(C / 'plugins/cache/mk/pl/1.0.0/skills', 'plugskill', 'A plugin skill about kernels')
(plug / 'scripts').mkdir()
(plug / 'scripts' / 'run.py').write_text('print(1)', encoding='utf-8')
(C / 'plugins' / 'installed_plugins.json').write_text(json.dumps({'version': 2, 'plugins': {'pl@mk': [
    {'scope': 'user', 'installPath': str(C / 'plugins/cache/mk/pl/1.0.0'), 'version': '1.0.0'}]}}), encoding='utf-8')
(C / 'settings.json').write_text(json.dumps({'enabledPlugins': {'pl@mk': True}}), encoding='utf-8')
room = BASE / 'room'
subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(room), '--participants', 'CORE,UI', '--lang', 'en'], capture_output=True)
r = chat.Room(room)
r.append('UI', 'SECRET-CHAT-LINE must never reach a job')
(room / 'board.json').write_text(json.dumps({'tasks': [{'id': 'T3', 'title': 'Build the kernel', 'owner': 'CORE', 'state': 'done', 'proof': 'pytest: 3 passed',
                                                         'gaps': 'no gpu', 'notes': []}], 'decisions': [{'text': 'DECISION-ONE'}], 'facts': [{'text': 'FACT-ONE'}]}), encoding='utf-8')
(room / 'notes').mkdir(exist_ok=True)
(room / 'notes' / 'CORE.state.md').write_text('STATE-NOTE of core', encoding='utf-8')


def cand(base, name, meta, desc='Unrelated sorcery of zebras', body='step one\n'):
    d = Path(base) / 'skills-candidates' / name
    d.mkdir(parents=True)
    (d / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {desc}\n---\n{body}', encoding='utf-8')
    (d / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
    return d


# candidates in the index: server recomputes score, tokens, covered_by; no body
cand(room, 'zebra-magic', {'name': 'zebra-magic', 'score': 10, 'req': 'r0', 'kind': 'derive', 'tasks': ['T3'], 'why': 'because',
                           'criteria': {'recurrence': 10, 'error_cost': 10, 'specificity': 10, 'overlap': 0, 'weight': 0}})
cand(room, 'pdf-twin', {'name': 'pdf-twin', 'criteria': {'recurrence': 5, 'error_cost': 5, 'specificity': 5, 'overlap': 0, 'weight': 0}},
     desc='Merge pdf files into one document in page order please')
cand(room, 'Bad Name', {'name': 'x'})
cand(room, 'heavy', {'name': 'heavy', 'criteria': {'recurrence': 10, 'error_cost': 10, 'specificity': 10, 'overlap': 0, 'weight': 0}}, body='word ' * 900)
idx = skills.index(r)
cs = {c['name']: c for c in idx['candidates']}
ok('candidates: bad folder name dropped, three listed', set(cs) == {'zebra-magic', 'pdf-twin', 'heavy'}, list(cs))
ok('candidates: heavy body -> weight raised by the server, score lower than the job said, sorted by score', cs['heavy']['criteria']['weight'] >= 7 and cs['heavy']['score'] == 9 and
   cs['zebra-magic']['score'] == 10 and [c['name'] for c in idx['candidates']][0] == 'zebra-magic', (cs['heavy']['criteria'], cs['heavy']['score']))
ok('candidates: covered_by finds the existing skill, overlap raised by the server', cs['pdf-twin']['covered_by'] == 'user:-:mine' and
   cs['pdf-twin']['criteria']['overlap'] >= 6 and cs['zebra-magic']['covered_by'] is None, cs['pdf-twin'])
ok('candidates: no body in the index, rooms listed', 'step one' not in json.dumps(idx) and idx['rooms'][0]['current'] and idx['rooms'][0]['n'] == 3, idx['rooms'])
cid = cs['zebra-magic']['id']
res = skills.do(r, {'action': 'candidate', 'id': cid})
ok('candidate action: the body', res['ok'] and 'step one' in res['candidate']['body'], res)
ok('candidate: unknown id and a path in the id are refused', not skills.do(r, {'action': 'candidate', 'id': 'cand:../x:y'})['ok'] and
   not skills.do(r, {'action': 'candidate', 'id': 'cand:deadbeef:zebra-magic'})['ok'], '')
ok('derive without a description: its own message, not the search one', 'skill you want' in skills.do(r, {'action': 'derive', 'desc': ''})['error'], '')
for bad in ({'action': 'derive', 'desc': ''}, {'action': 'derive', 'desc': 'x', 'source': {'folder': str(BASE / 'nothing')}},
            {'action': 'derive', 'desc': 'x', 'source': {'repo': 'https://evil.example/o/r'}}, {'action': 'improve', 'skill': 'nope'}):
    ok(f"refused: {bad}", skills.do(r, bad)['ok'] is False, bad)

# job previews write nothing
before = tree(BASE)
pv = skills.do(r, {'action': 'derive', 'desc': 'kernel routes'})
ok('derive preview: nothing written, nothing started', pv['ok'] and pv['preview']['kind'] == 'derive' and pv['preview']['writes'] == ['skills-candidates/**'] and
   pv['preview']['budget_usd'] == 1 and pv['preview']['reads'] == ['skills-jobs/r1.input.md'] and before == tree(BASE) and skills.state_of(r)['requests'] == [], pv)
pv = skills.do(r, {'action': 'improve', 'skill': 'plugskill'})
ok('improve preview of a plugin skill: a user copy', pv['ok'] and pv['preview']['target']['copy'] is True and pv['preview']['target']['origin'] == 'plugin' and
   pv['preview']['target']['path'].endswith('/skills/plugskill') and pv['preview']['budget_usd'] == 2, pv)


class Fake:
    """a claude -p that writes what the test says, never a real one"""
    writes = None
    returncode = 0

    def __init__(self, cwd):
        self.cwd = Path(cwd)

    def wait(self, timeout=None):
        if Fake.writes:
            Fake.writes(self.cwd)


calls = []
skills.launch = lambda cmd, prompt, cwd, log: calls.append((cmd, prompt, str(cwd))) or Fake(cwd)


def wait_line(text):
    for _ in range(60):
        if any(text in m['text'] for m in r.messages()):
            return True
        time.sleep(0.1)
    return False


def dmeta(req, name, kind, **kv):
    return {'v': 1, 'name': name, 'req': req, 'kind': kind, 'at': int(time.time()), 'why': 'w',
            'criteria': {'recurrence': 8, 'error_cost': 6, 'specificity': 8, 'overlap': 1, 'weight': 2}, **kv}


# derive from the current room
Fake.writes = lambda cwd: cand(cwd, 'kernel-routes', dmeta('r1', 'kernel-routes', 'derive', tasks=['T3']), 'Build kernels the way T3 did')
res = skills.do(r, {'action': 'derive', 'desc': 'kernel routes', 'confirm': True})
ok('derive confirm: started once, claude -p, own folder only', res['ok'] and res['req'] == 'r1' and len(calls) == 1 and calls[0][0][1] == '-p' and
   'Edit(skills-candidates/**)' in ' '.join(calls[0][0]) and 'dontAsk' in calls[0][0] and 'skills-jobs/r1.input.md' in ' '.join(calls[0][0]), (res, calls))
inp = (room / 'skills-jobs' / 'r1.input.md').read_text(encoding='utf-8')
ok('digest: board, decisions, facts, state notes; never the chat', all(x in inp for x in ('T3', 'pytest: 3 passed', 'no gpu', 'DECISION-ONE', 'FACT-ONE', 'STATE-NOTE'))
   and 'SECRET-CHAT-LINE' not in inp and 'SECRET-CHAT-LINE' not in calls[0][1], inp[:300])
ok('derive: done line in the chat, request done with its kind', wait_line('SKILLDERIVE r1 done') and
   [q for q in skills.index(r)['requests'] if q['req'] == 'r1'][0]['state'] == 'done', r.messages()[-2:])
ok('derive: the room is told, a prompt names the candidate files', 'SKILLDERIVE r1: kernel routes' in ' '.join(m['text'] for m in r.messages()) and
   'skills-candidates/<slug>' in calls[0][1] and 'kernel routes' in calls[0][1], calls[0][1][:200])

# a job that ends without a candidate is failed, said in the chat, not pending forever
Fake.writes = None
Fake.returncode = 3
res = skills.do(r, {'action': 'suggest', 'confirm': True})
ok('suggest without a result: failed line with the exit code, state failed', wait_line('SKILLSUGGEST r2 ended without a candidate (exit 3)') and
   [q for q in skills.index(r)['requests'] if q['req'] == 'r2'][0]['state'] == 'failed', r.messages()[-1:])
Fake.returncode = 0
req = skills_d6.new_job(r, 'derive', 'q', {'label': 'room:room', 'kind': 'room', 'folder': room}, None)
ok('the same job twice at once is refused', skills.do(r, {'action': 'derive', 'desc': 'again', 'confirm': True})['ok'] is False, '')
skills.change(r, lambda s: [x.update(failed=1) for x in s['requests'] if x['req'] == req['req']])

# improve a user skill: current copy, candidate, diff, promote with backup, old folder replaced
Fake.writes = lambda cwd: cand(cwd, 'mine', dmeta('r4', 'mine', 'improve', improves='user:-:mine'), 'Merge pdf files into one document in page order',
                               body='new body\n')
res = skills.do(r, {'action': 'improve', 'skill': 'mine', 'desc': 'learned', 'confirm': True})
ok('improve confirm: the current text is handed over as a file', res['ok'] and (room / 'skills-jobs' / 'r4.current.md').read_text(encoding='utf-8').count('old body') == 1 and
   'Read(skills-jobs/r4.current.md)' in ' '.join(calls[-1][0]) and '--max-budget-usd' in calls[-1][0] and '2' in calls[-1][0], (res, calls[-1][0]))
ok('improve: done', wait_line('SKILLIMPROVE r4 done'), r.messages()[-1:])
mc = [c for c in skills.index(r)['candidates'] if c['name'] == 'mine'][0]
d = skills.do(r, {'action': 'diff', 'id': mc['id']})
ok('diff: unified, counts, target is the user skill in place', d['ok'] and '-old body' in d['diff'] and '+new body' in d['diff'] and d['added'] >= 1 and
   d['target']['copy'] is False and d['target']['origin'] == 'user', d)
before = tree(mine)
pv = skills.do(r, {'action': 'promote', 'id': mc['id']})
ok('promote preview: backup path and diff, nothing written', pv['ok'] and pv['preview']['replaces'] and '-old body' in pv['preview']['diff'] and
   '/skills-backup/mine/' in pv['preview']['backup'] and before == tree(mine) and not (C / 'skills-backup').exists(), pv)
res = skills.do(r, {'action': 'promote', 'id': mc['id'], 'confirm': True, 'unverified_ok': True})
bk = Path(res['backup'])
ok('promote: old copied to the dated backup, SKILL.md replaced, the other files of the skill kept, no meta.json', res['ok'] and (bk / 'SKILL.md').read_text(encoding='utf-8').count('old body') == 1 and
   (bk / 'old.txt').is_file() and (mine / 'old.txt').is_file() and 'new body' in (mine / 'SKILL.md').read_text(encoding='utf-8') and
   'old body' not in (mine / 'SKILL.md').read_text(encoding='utf-8') and not (mine / 'meta.json').exists(), res)
ok('promote: candidate marked added, backup is outside the skills root', [c for c in skills.index(r)['candidates'] if c['name'] == 'mine'][0]['status'] == 'added' and
   bk.parts[-2] == 'mine' and not str(bk).startswith(str(C / 'skills') + os.sep), bk)

# a second promote in the same second (a double click): its own backup folder, no crash
res2 = skills.do(r, {'action': 'promote', 'id': mc['id'], 'confirm': True, 'unverified_ok': True})
ok('double promote: second backup beside the first, answered', res2['ok'] and res2['backup'] != res['backup'] and Path(res2['backup']).is_dir(), res2)

# improve a plugin skill: a user copy, the plugin file is never touched
ptree = tree(C / 'plugins')
Fake.writes = lambda cwd: cand(cwd, 'plugskill', dmeta('r5', 'plugskill', 'improve', improves='plugin:pl:plugskill'), 'A plugin skill about kernels', body='better\n')
skills.do(r, {'action': 'improve', 'skill': 'plugin:pl:plugskill', 'confirm': True})
wait_line('SKILLIMPROVE r5 done')
pc = [c for c in skills.index(r)['candidates'] if c['name'] == 'plugskill'][0]
res = skills.do(r, {'action': 'promote', 'id': pc['id'], 'confirm': True, 'unverified_ok': True})
ok('plugin skill: promoted as a user copy, plugin folder untouched', res['ok'] and res['id'] == 'user:-:plugskill' and res['backup'] is None and
   (C / 'skills' / 'plugskill' / 'SKILL.md').is_file() and (C / 'skills' / 'plugskill' / 'scripts' / 'run.py').is_file() and ptree == tree(C / 'plugins'), res)

# a new skill: refused when the name is taken, ok otherwise; dismiss
zid = cs['zebra-magic']['id']
res = skills.do(r, {'action': 'promote', 'id': zid, 'confirm': True, 'unverified_ok': True})
ok('new skill promoted into the user skills', res['ok'] and res['id'] == 'user:-:zebra-magic' and (C / 'skills' / 'zebra-magic' / 'SKILL.md').is_file(), res)
again = skills.do(r, {'action': 'promote', 'id': zid, 'confirm': True, 'unverified_ok': True})
ok('the same new name again is refused (use improve), nothing overwritten', again['ok'] is False and 'improve' in again['error'], again)
res = skills.do(r, {'action': 'dismiss', 'id': [c for c in skills.index(r)['candidates'] if c['name'] == 'pdf-twin'][0]['id']})
ok('dismiss: status in meta, folder stays', res['ok'] and json.loads((room / 'skills-candidates/pdf-twin/meta.json').read_text(encoding='utf-8'))['status'] == 'dismissed', res)

# another known room: its candidates are listed, and it can be a source
other = BASE / 'other'
subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(other), '--participants', 'A', '--lang', 'en'], capture_output=True)
cand(other, 'other-skill', dmeta('r0', 'other-skill', 'derive'))
(C / 'chatroom').mkdir(exist_ok=True)
(C / 'chatroom' / 'known_rooms.json').write_text(json.dumps({str(other): {'ts': 1, 'ids': []}, str(BASE / 'gone'): {'ts': 1, 'ids': []}}), encoding='utf-8')
idx = skills.index(r)
oid = skills_d6.rid(other)
ok('known rooms: listed with their candidates, a missing one skipped', {x['id'] for x in idx['rooms']} == {skills_d6.rid(room), oid} and
   'cand:%s:other-skill' % oid in {c['id'] for c in idx['candidates']}, idx['rooms'])
Fake.writes = lambda cwd: cand(cwd, 'from-other', dmeta('r6', 'from-other', 'derive'))
skills.do(r, {'action': 'derive', 'desc': 'x', 'source': {'room': oid}, 'confirm': True})
ok('room source: the job runs in that room, its digest is there, the candidate lands there', wait_line('SKILLDERIVE r6 done') and calls[-1][2] == str(other.resolve()) and
   (other / 'skills-jobs' / 'r6.input.md').is_file() and (other / 'skills-candidates' / 'from-other').is_dir(), calls[-1][2])

print(f'OK: {fails} failures' if not fails else f'FAIL: {fails} failures')
sys.exit(1 if fails else 0)
