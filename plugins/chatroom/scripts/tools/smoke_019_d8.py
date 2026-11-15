"""D8 of the skill workshop: executable check and verified state, usage registry, measured tokens, levels, activation test, nearby cases.
No network and no real claude: the command runner of skills_d8 is replaced (one real run at the end of each point).
Run: python tools/smoke_019_d8.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke019d8_'))
C = BASE / 'claude'
os.environ['CLAUDE_CONFIG_DIR'] = str(C)
os.environ['CHATROOM_SKILLS_DIR'] = str(BASE / 'dl')
os.environ['CHATROOM_SKILLS_USER_DIR'] = str(C / 'skills')
os.environ['CLAUDE_DATA_DIR'] = str(BASE / 'desktop')
sys.path.insert(0, SCRIPTS)
import chat        # noqa: E402
import skills      # noqa: E402
import skills_d6   # noqa: E402
import skills_d8   # noqa: E402
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


def cand(base, name, meta, desc='Unrelated sorcery of zebras', body='new body\n'):
    d = Path(base) / 'skills-candidates' / name
    d.mkdir(parents=True)
    (d / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {desc}\n---\n{body}', encoding='utf-8')
    (d / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
    return d


mine = mk(C / 'skills', 'mine', 'Merge pdf files into one document')
room = BASE / 'room'
subprocess.run([sys.executable, str(Path(SCRIPTS) / 'chat.py'), 'init', '--room', str(room), '--participants', 'CORE,UI', '--lang', 'en'], capture_output=True)
jw(room / 'skills.json', {'v': 1, 'seq': 0, 'roots': [], 'requests': [], 'advised': []})
r = chat.Room(room)
ran, script = [], []      # what the fake runner was asked to run; the answers it gives, in order (default: exit 0)


def fake(cmd, cwd, limit):
    ran.append((cmd, str(cwd).replace('\\', '/'), limit))
    return script.pop(0) if script else (0, 'ok\n')


REAL = skills_d8.run_cmd
skills_d8.run_cmd = fake
META = Path(C / 'chatroom' / 'skills-meta.json')


def idx():
    return skills.index(r)


def cand_of(name):
    return {c['name']: c for c in idx()['candidates']}[name]


def skill_of(name):
    return {s['name']: s for s in idx()['skills']}[name]


# ---- 1: the check
cand(room, 'zebra-magic', {'name': 'zebra-magic', 'criteria': {'recurrence': 9, 'error_cost': 9, 'specificity': 9, 'overlap': 0, 'weight': 0}})
cid = cand_of('zebra-magic')['id']
NOCHECK = {'check': None, 'verified': {'state': 'unverified', 'ok': False, 'at': None, 'exit': None, 'hash': None}}
ok('every skill and candidate has check and verified, unverified, even with nothing stored',
   all(s['check'] is None and s['verified']['state'] == 'unverified' for s in idx()['skills']) and
   all(c['check'] is None and c['verified'] == NOCHECK['verified'] for c in idx()['candidates']), idx()['candidates'][0])

res = skills.do(r, {'action': 'check_set', 'id': cid, 'check': {'cmd': ''}})
ok('check_set: an empty command is refused', not res['ok'] and 'cmd' in res['error'], res)
res = skills.do(r, {'action': 'check_set', 'id': cid, 'check': {'cmd': 'pytest -q', 'timeout': 9999}})
ok('check_set: stored, the timeout capped, nothing ran', res['ok'] and res['check'] == {'cmd': 'pytest -q', 'cwd': None, 'timeout': 600} and ran == [], (res, ran))
ok('check_set: the candidate shows it, still unverified', cand_of('zebra-magic')['check']['cmd'] == 'pytest -q' and cand_of('zebra-magic')['verified']['state'] == 'unverified')
ok('check_run without a stored check is refused', not skills.do(r, {'action': 'check_run', 'id': 'user:-:mine'})['ok'])

pv = skills.do(r, {'action': 'check_run', 'id': cid})
p = pv.get('preview') or {}
ok('check_run preview: the whole command, the folder, the limit, the token; nothing ran',
   pv['ok'] and p['cmd'] == 'pytest -q' and p['cwd'].endswith('skills-candidates/zebra-magic') and p['timeout'] == 600 and p['token'] and p['what'] == 'candidate' and ran == [], (pv, ran))
tok = p['token']
res = skills.do(r, {'action': 'check_run', 'id': cid, 'confirm': True})
ok('check_run: confirm without the token runs nothing', not res['ok'] and res['needs'] == 'token' and res['token'] == tok and ran == [], (res, ran))
res = skills.do(r, {'action': 'check_run', 'id': cid, 'confirm': True, 'token': 'f' * 12})
ok('check_run: a wrong token runs nothing', not res['ok'] and ran == [], res)
res = skills.do(r, {'action': 'check_run', 'id': cid, 'confirm': True, 'token': tok, 'cmd': 'rm -rf /'})
ok('check_run: confirm with the token runs the STORED command (a cmd in the call is ignored), in the folder, with the limit',
   res['ok'] and res['passed'] is True and res['exit'] == 0 and len(ran) == 1 and ran[0][0] == 'pytest -q' and ran[0][1].endswith('skills-candidates/zebra-magic') and ran[0][2] == 600, (res, ran))
ok('check_run: verified stored and shown in the index', res['verified']['state'] == 'verified' and cand_of('zebra-magic')['verified']['state'] == 'verified' and
   cand_of('zebra-magic')['verified']['hash'] == res['hash'], res)
(room / 'skills-candidates/zebra-magic/SKILL.md').write_text('---\nname: zebra-magic\ndescription: Unrelated sorcery of zebras\n---\nchanged body\n', encoding='utf-8')
ok('verified goes back to unverified when SKILL.md changes', cand_of('zebra-magic')['verified']['state'] == 'unverified')
script.append((1, 'FAILED test_x\n1 failed'))
res = skills.do(r, {'action': 'check_run', 'id': cid, 'confirm': True, 'token': tok})
ok('a failing check: passed false, the output tail, state failed', res['ok'] and res['passed'] is False and res['exit'] == 1 and 'FAILED' in res['out'] and
   cand_of('zebra-magic')['verified']['state'] == 'failed' and cand_of('zebra-magic')['verified']['ok'] is False, res)
script.append((None, 'still running'))
res = skills.do(r, {'action': 'check_run', 'id': cid, 'confirm': True, 'token': tok})
ok('a check over its limit: exit null, failed', res['ok'] and res['passed'] is False and res['exit'] is None and cand_of('zebra-magic')['verified']['state'] == 'failed', res)
skills.do(r, {'action': 'check_set', 'id': cid, 'check': {'cmd': 'pytest -q tests', 'cwd': str(BASE)}})
ok('a new command clears the old answer and changes the token', cand_of('zebra-magic')['verified']['state'] == 'unverified' and
   not skills.do(r, {'action': 'check_run', 'id': cid, 'confirm': True, 'token': tok})['ok'])
pv = skills.do(r, {'action': 'check_run', 'id': cid})['preview']
ok('a check with its own cwd shows it', pv['cwd'] == str(BASE).replace('\\', '/') and pv['token'] != tok, pv)

# a real skill: the data goes to the sidecar in ~/.claude/chatroom, the skill folder is never touched
before = sorted(p.name for p in mine.iterdir())
ran.clear()
res = skills.do(r, {'action': 'check_set', 'id': 'user:-:mine', 'check': {'cmd': 'node t.js'}})
ok('check_set on a real skill: the sidecar file holds it, the skill folder is the same', res['ok'] and META.is_file() and
   json.loads(META.read_text(encoding='utf-8'))['skills']['user:-:mine']['check']['cmd'] == 'node t.js' and sorted(p.name for p in mine.iterdir()) == before, res)
ok('the index shows the skill check', skill_of('mine')['check']['cmd'] == 'node t.js' and skill_of('mine')['verified']['state'] == 'unverified')
pv = skills.do(r, {'action': 'check_run', 'id': 'user:-:mine'})['preview']
res = skills.do(r, {'action': 'check_run', 'skill': 'mine', 'confirm': True, 'token': pv['token']})
ok('check_run on a real skill (by "skill" too): runs in its folder, verified in the sidecar', res['ok'] and res['passed'] and ran[0][1].endswith('skills/mine') and
   skill_of('mine')['verified']['state'] == 'verified' and sorted(p.name for p in mine.iterdir()) == before, (res, ran))
bi = [s for s in idx()['skills'] if s['origin'] == 'builtin']
ok('a builtin skill has no folder: refused', not bi or not skills.do(r, {'action': 'check_set', 'id': bi[0]['id'], 'check': {'cmd': 'x'}})['ok'])
ok('an unknown id is refused', not skills.do(r, {'action': 'check_set', 'id': 'user:-:nope', 'check': {'cmd': 'x'}})['ok'] and
   not skills.do(r, {'action': 'check_run', 'id': 'cand:deadbeef:nope'})['ok'])

# the real runner (own process group, machine lock): one command that passes, one that fails
skills_d8.run_cmd = REAL
rr = skills_d8.run_one({'cmd': f'"{sys.executable}" -c "print(41+1)"', 'cwd': None, 'timeout': 60}, str(BASE))
ok('the real runner: a passing command', rr['passed'] and '42' in rr['out'] and rr['exit'] == 0, rr)
rr = skills_d8.run_one({'cmd': f'"{sys.executable}" -c "import sys; sys.exit(3)"', 'cwd': None, 'timeout': 60}, str(BASE))
ok('the real runner: a failing command, its exit code', not rr['passed'] and rr['exit'] == 3, rr)
rr = skills_d8.run_one({'cmd': 'x', 'cwd': str(BASE / 'missing'), 'timeout': 5}, str(BASE))
ok('a missing folder is an error text, not a run', isinstance(rr, str) and 'missing' in rr, rr)
skills_d8.run_cmd = fake

# promote: the unverified door and the improvement gate
cand(room, 'plain-new', {'name': 'plain-new'}, body='plain\n')
pid = cand_of('plain-new')['id']
pv = skills.do(r, {'action': 'promote', 'id': pid})
ok('promote preview: unverified true', pv['ok'] and pv['preview']['unverified'] is True and pv['preview']['verified']['state'] == 'unverified', pv)
res = skills.do(r, {'action': 'promote', 'id': pid, 'confirm': True})
ok('promote of an unverified candidate needs unverified_ok: nothing laid', not res['ok'] and res['needs'] == 'unverified_ok' and not (C / 'skills' / 'plain-new').exists(), res)
res = skills.do(r, {'action': 'promote', 'id': pid, 'confirm': True, 'unverified_ok': True})
ok('with unverified_ok it is added, marked unverified', res['ok'] and (C / 'skills' / 'plain-new' / 'SKILL.md').is_file() and skill_of('plain-new')['verified']['state'] == 'unverified', res)

cand(room, 'good-new', {'name': 'good-new', 'check': {'cmd': 'pytest -q'}}, body='good\n')
gid = cand_of('good-new')['id']
tk = skills.do(r, {'action': 'check_run', 'id': gid})['preview']['token']
skills.do(r, {'action': 'check_run', 'id': gid, 'confirm': True, 'token': tk})
ok('a verified candidate: promote preview unverified false', skills.do(r, {'action': 'promote', 'id': gid})['preview']['unverified'] is False)
res = skills.do(r, {'action': 'promote', 'id': gid, 'confirm': True})
ok('a verified candidate is added without unverified_ok; the new skill keeps check and verified', res['ok'] and skill_of('good-new')['verified']['state'] == 'verified' and
   skill_of('good-new')['check']['cmd'] == 'pytest -q', res)

# an improvement of "mine": the candidate carries a check that must pass AFTER the change
ran.clear()
cand(room, 'mine', {'name': 'mine', 'improves': 'user:-:mine', 'check': {'cmd': 'node new.js'}}, desc='Merge pdf files into one document', body='improved body\n')
imp = {c['id'] for c in idx()['candidates'] if c['name'] == 'mine'}.pop()
tk = skills.do(r, {'action': 'check_run', 'id': imp})['preview']['token']
skills.do(r, {'action': 'check_run', 'id': imp, 'confirm': True, 'token': tk})
(room / 'skills-candidates/mine/SKILL.md').write_text('---\nname: mine\ndescription: Merge pdf files into one document\n---\nimproved body\n', encoding='utf-8')
pv = skills.do(r, {'action': 'promote', 'id': imp})['preview']
HERE = str(mine).replace(chr(92), '/')
ok('improvement preview: the gate lists the candidate check AND the one the skill had, whole, with the folder, and a token',
   pv['gate'] == [{'id': 'check', 'cmd': 'node new.js', 'cwd': HERE, 'timeout': 110}, {'id': 'check-old', 'cmd': 'node t.js', 'cwd': HERE, 'timeout': 110}] and pv['token'], pv)
ran.clear()
res = skills.do(r, {'action': 'promote', 'id': imp, 'confirm': True, 'unverified_ok': True})
ok('improvement confirm without the gate token: nothing laid, nothing run', not res['ok'] and res['needs'] == 'token' and 'old body' in (mine / 'SKILL.md').read_text(encoding='utf-8') and ran == [], (res, ran))
script.append((1, 'boom'))
res = skills.do(r, {'action': 'promote', 'id': imp, 'confirm': True, 'unverified_ok': True, 'token': pv['token']})
ok('the check fails after the change: the old skill is put back, reverted true',
   not res['ok'] and res['reverted'] is True and 'old body' in (mine / 'SKILL.md').read_text(encoding='utf-8') and {x[0] for x in ran} == {'node new.js', 'node t.js'} and
   skill_of('mine')['name'] == 'mine', (res, ran))
res = skills.do(r, {'action': 'promote', 'id': imp, 'confirm': True, 'unverified_ok': True, 'token': pv['token']})
ok('the check passes after the change: kept, verified on the new text', res['ok'] and 'improved body' in (mine / 'SKILL.md').read_text(encoding='utf-8') and
   skill_of('mine')['verified']['state'] == 'verified' and skill_of('mine')['check']['cmd'] == 'node new.js', res)

# ---- 3: the usage registry (Skill calls of the agents' transcripts, tied to the task each agent held)
import skills_use  # noqa: E402
import time  # noqa: E402
T0 = 1800000000


def iso(t):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(t)) + '.123Z'


def line(t, tid, ref):
    return json.dumps({'timestamp': iso(t), 'message': {'content': [{'type': 'tool_use', 'name': 'Skill', 'id': tid, 'input': {'skill': ref}}]}}) + '\n'


def agent_file(aid, text):
    p = C / 'projects' / 'proj' / 'sess' / 'subagents' / f'agent-{aid}.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    return p


def hist(owner, taken, closed=None, state='done'):
    h = [{'v': 1, 'ts': taken - 50, 'by': 'LEAD', 'owner': None, 'state': 'open'}, {'v': 2, 'ts': taken, 'by': owner, 'owner': owner, 'state': 'taken'}]
    if closed:
        h.append({'v': 3, 'ts': closed, 'by': owner, 'owner': owner, 'state': state})
    return h


jw(room / 'roster.json', {'CORE': 'aaaa1111', 'UI': 'aaaa2222', 'VERIFY': 'aaaa3333'})
jw(room / 'board.json', {'tasks': [
    {'id': 'T1', 'title': 'first', 'state': 'done', 'owner': 'CORE', 'hist': hist('CORE', T0, T0 + 100)},
    {'id': 'T2', 'title': 'second', 'state': 'taken', 'owner': 'UI', 'hist': hist('UI', T0)},
    {'id': 'T3', 'title': 'third', 'state': 'blocked', 'owner': 'VERIFY', 'hist': hist('VERIFY', T0, T0 + 100, 'blocked')}]})
core_tr = agent_file('aaaa1111', line(T0 + 10, 'tu1', 'mine') + line(T0 + 10, 'tu1', 'mine') + line(T0 + 500, 'tu2', 'mine') + line(T0 + 20, 'tu3', 'nosuchskill') + 'not json\n')
agent_file('aaaa2222', line(T0 + 30, 'tu4', 'mine') + line(T0 + 31, 'tu5', 'plain-new'))
agent_file('aaaa3333', line(T0 + 40, 'tu6', 'mine'))
ok('before any scan every skill has a usage with zeros and unused false',
   all(s['usage'] == skills_use.empty_usage() for s in idx()['skills']) and all(c['usage']['count'] == 0 for c in idx()['candidates']))
res = skills.do(r, {'action': 'usage_scan'})
ok('usage_scan: reads the three transcripts, 6 new calls (a streamed duplicate id and a broken line are not counted)',
   res['ok'] and res['complete'] is True and res['scanned']['transcripts'] == 3 and res['scanned']['new'] == 6 and res['scanned']['rooms'] == 1, res)
u = skill_of('mine')['usage']
ok('usage: count, rooms, last, ok and fail from the task each agent held (done, open, blocked, none)',
   u['count'] == 4 and u['rooms'] == 1 and u['last'] == T0 + 500 and u['ok'] == 1 and u['fail'] == 1 and u['scanned_rooms'] == 1 and u['unused'] is False, u)
res = skills.do(r, {'action': 'usage', 'id': 'user:-:mine'})
by_t = {(e['agent'], e['at']): e for e in res['uses']}
ok('usage action: each use with its task, title and outcome',
   by_t[('CORE', T0 + 10)]['task'] == 'T1' and by_t[('CORE', T0 + 10)]['outcome'] == 'done' and by_t[('CORE', T0 + 10)]['ok'] is True and by_t[('CORE', T0 + 10)]['task_title'] == 'first' and
   by_t[('CORE', T0 + 500)]['outcome'] == 'none' and by_t[('CORE', T0 + 500)]['task'] is None and by_t[('CORE', T0 + 500)]['ok'] is None and
   by_t[('UI', T0 + 30)]['outcome'] == 'open' and by_t[('UI', T0 + 30)]['ok'] is None and by_t[('VERIFY', T0 + 40)]['outcome'] == 'dropped' and by_t[('VERIFY', T0 + 40)]['ok'] is False, res)
ok('a second scan reads nothing new (offsets)', skills.do(r, {'action': 'usage_scan'})['scanned']['new'] == 0)
with open(core_tr, 'a', encoding='utf-8') as f:
    f.write(line(T0 + 60, 'tu7', 'mine').rstrip('\n'))      # a line being written: waits
ok('a line without its newline waits for the next scan', skills.do(r, {'action': 'usage_scan'})['scanned']['new'] == 0 and skill_of('mine')['usage']['count'] == 4)
with open(core_tr, 'a', encoding='utf-8') as f:
    f.write('\n')
ok('...and is read once complete', skills.do(r, {'action': 'usage_scan'})['scanned']['new'] == 1 and skill_of('mine')['usage']['count'] == 5)
ok('unused needs 3 scanned rooms: one room is not enough', skill_of('good-new')['usage']['unused'] is False and skill_of('good-new')['usage']['count'] == 0)
for k in ('a', 'b'):      # two more known rooms with an agent each
    o = BASE / f'room_{k}'
    o.mkdir()
    jw(o / 'roster.json', {'X': f'aaaa9{k}99'})
    agent_file(f'aaaa9{k}99', line(T0 + 5, f'tx{k}', 'plain-new'))
    chat.known_room(o, [f'aaaa9{k}99'])
ok('the scan goes over the known rooms: three rooms now, a never called skill is unused, a used one is not',
   skills.do(r, {'action': 'usage_scan'})['scanned']['rooms'] == 3 and skill_of('good-new')['usage']['unused'] is True and skill_of('good-new')['usage']['unused_rooms'] == 3 and
   skill_of('plain-new')['usage']['rooms'] == 3 and skill_of('plain-new')['usage']['unused'] is False, skill_of('good-new')['usage'])
ok('there is no action that removes a skill (unused is only a flag)', not any('remove' in a or 'delete' in a for a in skills_use.ACTIONS))
with open(core_tr, 'a', encoding='utf-8') as f:
    f.write(line(T0 + 70, 'tu8', 'mine'))
res = skills_use.scan(r, budget=-1)
ok('a scan over its budget says complete false and reads nothing; the next one finishes', res['complete'] is False and res['new'] == 0 and skills_use.scan(r)['new'] == 1, res)
reg = json.loads((C / 'chatroom' / 'skills-usage.json').read_text(encoding='utf-8'))
ok('the registry file: version, offsets, rooms, uses', reg['v'] == 1 and len(reg['offsets']) == 5 and len(reg['rooms']) == 3 and len(reg['uses']) == 10, {k: len(v) if hasattr(v, '__len__') else v for k, v in reg.items()})

# ---- 2: measured tokens and steps (closed tasks with the skill against without it, same rooms; never an estimate)
def aline(t, mid, tool=None, ref=None):
    content = [{'type': 'tool_use', 'name': tool, 'id': 'u' + mid, 'input': {'skill': ref} if ref else {}}] if tool else []
    return json.dumps({'type': 'assistant', 'timestamp': iso(t), 'message': {'id': mid, 'usage': {'input_tokens': 100, 'output_tokens': 20}, 'content': content}}) + '\n'


rm = BASE / 'room_m'
rm.mkdir()
jw(rm / 'roster.json', {'A': 'aaaam001'})
tasks, text = [], ''
for k in range(6):
    t0 = T0 + 1000 * (k + 1)
    tasks.append({'id': f'T{k + 1}', 'title': f'job {k}', 'state': 'done', 'owner': 'A', 'hist': hist('A', t0, t0 + 100)})
    if k < 3:      # with the skill: 2 requests, 2 tool calls (the Skill call and one more)
        text += aline(t0 + 10, f'm{k}a', 'Skill', 'good-new') + aline(t0 + 20, f'm{k}b', 'Bash')
    else:          # without: 3 requests, 3 tool calls
        text += aline(t0 + 10, f'm{k}a', 'Bash') + aline(t0 + 20, f'm{k}b', 'Bash') + aline(t0 + 30, f'm{k}c', 'Bash')
text += aline(T0 + 1010, 'm0a', 'Bash')      # the same streamed message written twice counts once
jw(rm / 'board.json', {'tasks': tasks})
agent_file('aaaam001', text)
chat.known_room(rm, ['aaaam001'])
skills.do(r, {'action': 'usage_scan'})
ok('measure for a skill never measured: null in the index', skill_of('good-new')['measured'] is None and all(c['measured'] is None for c in idx()['candidates']))
res = skills.do(r, {'action': 'measure', 'id': 'user:-:good-new'})
mm = res.get('measured') or {}
ok('measure: 3 tasks with, 3 without: tokens and steps saved are the difference of the means (input-equivalent tokens 200 per request here)',
   res['ok'] and mm['with']['n'] == 3 and mm['without']['n'] == 3 and mm['with']['tokens_mean'] == 400 and mm['without']['tokens_mean'] == 600 and
   mm['tokens_saved'] == 200 and mm['steps_saved'] == 1 and 'not proof' in mm['basis'] and mm['min_n'] == 3, res)
ok('...and it is stored: the index shows it', skill_of('good-new')['measured']['tokens_saved'] == 200 and skill_of('good-new')['measured']['steps_saved'] == 1)
res = skills.do(r, {'action': 'measure', 'id': 'user:-:mine'})
ok('too few tasks: no number, only the reason (need 3 with and 3 without)', res['ok'] and res['measured']['tokens_saved'] is None and res['measured']['steps_saved'] is None and
   'need 3' in res['measured']['basis'], res)
cand(room, 'braggart', {'name': 'braggart', 'tokens_saved': 5000, 'measured': {'tokens_saved': 5000}}, body='b\n')
ok('a candidate never has a measure: what a job writes is ignored', cand_of('braggart')['tokens_saved'] is None and cand_of('braggart')['measured'] is None)
ok('measure of an unknown skill is refused', not skills.do(r, {'action': 'measure', 'id': 'user:-:nope'})['ok'])

# ---- 5: three levels (strategy > function > step) and the tree
ok('every skill and candidate has level null, parent null and children []', all(s['level'] is None and s['parent'] is None and s['children'] == [] for s in idx()['skills']) and
   all(c['level'] is None and c['parent'] is None and c['children'] == [] for c in idx()['candidates']))
ok('level_set: a level that does not exist is refused', not skills.do(r, {'action': 'level_set', 'id': 'user:-:plain-new', 'level': 'epic'})['ok'])
ok('level_set: plain-new is a function, good-new a strategy, mine a step', all(skills.do(r, {'action': 'level_set', 'id': i, 'level': lv})['ok'] for i, lv in
   (('user:-:plain-new', 'function'), ('user:-:good-new', 'strategy'), ('user:-:mine', 'step'))))
res = skills.do(r, {'action': 'level_set', 'id': 'user:-:mine', 'parent': 'plain-new'})
ok('parent by name: stored as the id, the index shows parent and children', res['ok'] and res['parent'] == 'user:-:plain-new' and res['level'] == 'step' and
   skill_of('mine')['parent'] == 'user:-:plain-new' and skill_of('plain-new')['children'] == ['user:-:mine'] and skill_of('mine')['level'] == 'step', res)
ok('a parent of the same level or lower is refused (so there is never a cycle)', not skills.do(r, {'action': 'level_set', 'id': 'user:-:plain-new', 'parent': 'mine'})['ok'] and
   not skills.do(r, {'action': 'level_set', 'id': 'user:-:mine', 'parent': 'mine'})['ok'] and not skills.do(r, {'action': 'level_set', 'id': 'user:-:good-new', 'parent': 'plain-new'})['ok'])
ok('an unknown parent is refused; so is a link when a level is missing', not skills.do(r, {'action': 'level_set', 'id': 'user:-:mine', 'parent': 'nope'})['ok'] and
   not skills.do(r, {'action': 'level_set', 'id': 'user:-:mine', 'level': None, 'parent': 'plain-new'})['ok'] and skill_of('mine')['level'] == 'step')
ok('a level that would break a child is refused (plain-new to step while mine is its child)', not skills.do(r, {'action': 'level_set', 'id': 'user:-:plain-new', 'level': 'step'})['ok'] and
   skill_of('plain-new')['level'] == 'function')
ok('level_set on a candidate: metadata in its meta.json, and a parent null clears it', skills.do(r, {'action': 'level_set', 'id': cand_of('braggart')['id'], 'level': 'step', 'parent': 'good-new'})['ok'] and
   cand_of('braggart')['level'] == 'step' and cand_of('braggart')['parent'] == 'user:-:good-new' and
   skills.do(r, {'action': 'level_set', 'id': cand_of('braggart')['id'], 'parent': None})['ok'] and cand_of('braggart')['parent'] is None)
ok('only metadata: the folders of the skills are untouched', sorted(p.name for p in (C / 'skills' / 'mine').iterdir()) == ['SKILL.md'])

# ---- 4a: the activation check (free, local) and 4b: the activation test (one claude -p, on a click, cost shown first)
mk(C / 'skills', 'pdfa', 'Merge pdf files into one document. Use when the user asks to merge or combine pdf files. Do NOT use when the request is about splitting pdf files.')
mk(C / 'skills', 'pdfb', 'Split pdf files into single pages. Use when the user asks to split pdf files.')
res = skills.do(r, {'action': 'activation_check', 'id': 'user:-:pdfa'})
ck = res.get('check') or {}
ok('activation_check: clauses counted, the exclusion found and compared with the triggers, the neighbours it can be confused with',
   res['ok'] and ck['positives'] >= 1 and ck['negatives'] == 1 and ck['has_exclusion'] is True and ck['closeness'] > 0 and {x['name'] for x in ck['confused_with']} >= {'pdfb', 'mine'} and
   all(set(x) == {'id', 'name', 'overlap'} for x in ck['confused_with']) and ck['suggestion'] is None and ck['advice'], res)
res = skills.do(r, {'action': 'activation_check', 'id': 'user:-:mine'})
ck = res['check']
ok('activation_check: no trigger clause is the first advice; the suggestion adds a "Do NOT use" clause naming the neighbours', ck['positives'] == 0 and ck['has_exclusion'] is False and
   'Use when' in ck['advice'] and ck['suggestion'].startswith('Merge pdf files into one document. Do NOT use when the request is really about') and 'pdfa' in ck['suggestion'], ck)
ok('activation_check: free: nothing launched, nothing written', not (room / 'skills-jobs').exists() or not list((room / 'skills-jobs').glob('*.activation.json')))
ok('activation_check of a candidate works, of an unknown skill is refused', skills.do(r, {'action': 'activation_check', 'id': cand_of('braggart')['id']})['ok'] and
   not skills.do(r, {'action': 'activation_check', 'id': 'user:-:nope'})['ok'])


class Fake:
    """a claude -p that writes what the test says, never a real one"""
    writes = None
    returncode = 0

    def __init__(self, cwd):
        self.cwd = Path(cwd)

    def wait(self, timeout=None):
        if Fake.writes:
            Fake.writes(self.cwd)


launched = []
skills.launch = lambda cmd, prompt, cwd, log: launched.append((cmd, prompt, str(cwd))) or Fake(cwd)


def wait_line(text):
    import time as _t
    for _ in range(60):
        if any(text in m['text'] for m in r.messages()):
            return True
        _t.sleep(0.1)
    return False


pv = skills.do(r, {'action': 'activation_test', 'id': 'user:-:pdfa'})
p = pv.get('preview') or {}
ok('activation_test preview: what it does, the file it writes, the cap in USD, the model writes the prompts; nothing started',
   pv['ok'] and p['kind'] == 'activation' and p['n'] == 6 and p['prompts'] == [] and p['budget_usd'] == 1 and p['writes'][0].endswith('.activation.json') and p['note'] and launched == [], pv)
rq = p['writes'][0].split('/')[1].split('.')[0]


def write_items(cwd):
    items = [{'q': f'merge my pdfs {i}', 'should': True, 'picked': 'pdfa' if i < 2 else 'mine'} for i in range(3)] + \
            [{'q': f'split a pdf {i}', 'should': False, 'picked': 'pdfb' if i < 2 else 'pdfa'} for i in range(3)]
    (cwd / 'skills-jobs' / f'{rq}.activation.json').write_text(json.dumps({'req': rq, 'items': items, 'suggestion': 'Merge pdfs. Use when merging. Do NOT use when splitting (pdfb).'}), encoding='utf-8')


Fake.writes = write_items
res = skills.do(r, {'action': 'activation_test', 'id': 'user:-:pdfa', 'confirm': True})
ok('activation_test confirm: one claude -p with the files it may read and the one it may write, 1 USD cap, the skill list written for it',
   res['ok'] and res['req'] == rq and len(launched) == 1 and '--max-budget-usd' in launched[0][0] and launched[0][0][launched[0][0].index('--max-budget-usd') + 1] == '1' and
   f'Edit(skills-jobs/{rq}.activation.json)' in ' '.join(launched[0][0]) and 'pdfa' in launched[0][1] and (room / 'skills-jobs' / f'{rq}.skills.md').is_file() and
   'pdfb' in (room / 'skills-jobs' / f'{rq}.skills.md').read_text(encoding='utf-8'), (res, launched[:1]))
ok('activation_test: done line in the chat', wait_line(f'activation test {rq} for pdfa done: 4 of 6 right'), r.messages()[-2:])
a = skill_of('pdfa')['activation']
ok('the result is scored here, stored as the activation of the skill: right, wrong, total, the matrix, the suggestion',
   a['right'] == 4 and a['wrong'] == 2 and a['total'] == 6 and (a['tp'], a['fn'], a['fp'], a['tn']) == (2, 1, 1, 2) and 'Do NOT use' in a['suggestion'] and a['at'], a)
q = [x for x in idx()['requests'] if x['req'] == rq][0]
ok('the request is in requests[] with kind activation, done, and the scored result with the items', q['kind'] == 'activation' and q['state'] == 'done' and q['result']['right'] == 4 and
   len(q['result']['items']) == 6 and q['result']['items'][0]['q'] and q['result']['suggestion'], q)
ok('a skill never tested has activation null', skill_of('pdfb')['activation'] is None and all(c['activation'] is None for c in idx()['candidates']))
Fake.writes = None
res = skills.do(r, {'action': 'activation_test', 'id': 'user:-:pdfb', 'confirm': True})
ok('a job that ends without its file: failed, a line with the exit code, no activation stored', res['ok'] and wait_line('ended without a result') and skill_of('pdfb')['activation'] is None and
   [x for x in idx()['requests'] if x['req'] == res['req']][0]['state'] == 'failed')
ok('a candidate can be tested too: the result is stored under its id', skills.do(r, {'action': 'activation_test', 'id': cand_of('braggart')['id']})['ok'])

# ---- 6: nearby cases (1 to 4 executable checks of the same family; an improvement is kept only when no case gets worse)
ok('every skill and candidate has cases [] and cases_run null', all(s['cases'] == [] and s['cases_run'] is None for s in idx()['skills']) and
   all(c['cases'] == [] and c['cases_run'] is None for c in idx()['candidates']))
CS = [{'task': t, 'check': {'cmd': f'case {t}'}} for t in 'abcde']
ok('cases_set: none, five, or one without a command are refused', not skills.do(r, {'action': 'cases_set', 'id': 'user:-:pdfb', 'cases': []})['ok'] and
   not skills.do(r, {'action': 'cases_set', 'id': 'user:-:pdfb', 'cases': CS})['ok'] and not skills.do(r, {'action': 'cases_set', 'id': 'user:-:pdfb', 'cases': [{'task': 'x'}]})['ok'])
res = skills.do(r, {'action': 'cases_set', 'id': 'user:-:pdfb', 'cases': CS[:3]})
ok('cases_set: the server gives the ids c1..c3, metadata only, nothing ran', res['ok'] and [c['id'] for c in res['cases']] == ['c1', 'c2', 'c3'] and
   [c['id'] for c in skill_of('pdfb')['cases']] == ['c1', 'c2', 'c3'] and skill_of('pdfb')['cases'][0]['check']['cmd'] == 'case a', res)
ran.clear()
pv = skills.do(r, {'action': 'cases_run', 'id': 'user:-:pdfb'})
p = pv.get('preview') or {}
ok('cases_run preview: every command whole with its folder, the number of runs, a token; nothing ran',
   pv['ok'] and [c['check']['cmd'] for c in p['cases']] == ['case a', 'case b', 'case c'] and p['runs'] == 3 and p['token'] and p['cases'][0]['check']['cwd'].endswith('skills/pdfb') and ran == [], pv)
ok('cases_run without the token runs nothing', not skills.do(r, {'action': 'cases_run', 'id': 'user:-:pdfb', 'confirm': True})['ok'] and ran == [])
script[:] = [(0, ''), (1, 'x'), (0, '')]
res = skills.do(r, {'action': 'cases_run', 'id': 'user:-:pdfb', 'confirm': True, 'token': p['token']})
ok('cases_run: one result per case, stored with the time', res['ok'] and [x['passed'] for x in res['results']] == [True, False, True] and res['passed'] is False and
   [x[0] for x in ran] == ['case a', 'case b', 'case c'] and skill_of('pdfb')['cases_run']['stale'] is False and skill_of('pdfb')['cases_run']['passed'] is False, (res, ran))
(C / 'skills' / 'pdfb' / 'SKILL.md').write_text('---\nname: pdfb\ndescription: Split pdf files into single pages. Use when the user asks to split pdf files.\n---\nedited\n', encoding='utf-8')
ok('the last run is stale once SKILL.md changed', skill_of('pdfb')['cases_run']['stale'] is True)

# an improvement of pdfb: the gate runs the cases before and after (2*K runs), one worse case refuses, a better one alone is kept
cand(room, 'pdfb', {'name': 'pdfb', 'improves': 'user:-:pdfb'}, desc='Split pdf files into single pages. Use when the user asks to split pdf files.', body='better split\n')
bid = [c['id'] for c in idx()['candidates'] if c['name'] == 'pdfb'][0]
pv = skills.do(r, {'action': 'promote', 'id': bid})['preview']
ok('improvement preview with cases: the gate lists the three cases, and the number of runs is 2*K', [g['id'] for g in pv['gate']] == ['c1', 'c2', 'c3'] and pv['runs'] == 6 and pv['token'], pv)
before_tree = sorted((p.name, p.read_bytes()) for p in (C / 'skills' / 'pdfb').iterdir())
ran.clear()
script[:] = [(0, ''), (1, ''), (0, ''), (0, ''), (0, ''), (1, '')]      # before: pass fail pass; after: pass pass FAIL
res = skills.do(r, {'action': 'promote', 'id': bid, 'confirm': True, 'unverified_ok': True, 'token': pv['token']})
ok('one case that passed before and fails now: refused, reverted, the folder is the same, worse 1, better 1, utility 0 (informative)',
   not res['ok'] and res['reverted'] is True and res['worse'] == 1 and res['better'] == 1 and res['utility'] == 0.0 and
   [(x['id'], x['before'], x['after']) for x in res['cases_result']] == [('c1', True, True), ('c2', False, True), ('c3', True, False)] and
   sorted((p.name, p.read_bytes()) for p in (C / 'skills' / 'pdfb').iterdir()) == before_tree and len(ran) == 6, (res, len(ran)))
script[:] = [(0, ''), (1, ''), (0, ''), (0, ''), (0, ''), (0, '')]      # before: pass fail pass; after: all pass
res = skills.do(r, {'action': 'promote', 'id': bid, 'confirm': True, 'unverified_ok': True, 'token': pv['token']})
ok('a better case and no worse one: kept, with the cases_result, better 1, worse 0, utility 0.33',
   res['ok'] and res['better'] == 1 and res['worse'] == 0 and res['utility'] == 0.33 and 'better split' in (C / 'skills' / 'pdfb' / 'SKILL.md').read_text(encoding='utf-8'), res)
g = skills_d8.gate_of({'cases': [{'task': 'n', 'check': {'cmd': 'x'}}], 'check': {'cmd': 'new'}}, 'user:-:pdfb')
ok('the gate keeps the cases the skill had and the candidate ones, with unique ids', [c['id'] for c in g['cases']] == ['c1', 'c2', 'c3', 'c1+'] and g['checks'] == [('check', {'cmd': 'new', 'cwd': None, 'timeout': 110})], g)
cid_ = cand_of('braggart')['id']
skills.do(r, {'action': 'cases_set', 'id': cid_, 'cases': CS[:2]})
ok('cases on a candidate live in its meta.json and come with it when promoted', len(cand_of('braggart')['cases']) == 2 and
   json.loads((room / 'skills-candidates/braggart/meta.json').read_text(encoding='utf-8'))['cases'][1]['id'] == 'c2')

# a promoted candidate cannot bring a tree that level_set would refuse (VERIFY #332)
cand(room, 'loopy', {'name': 'loopy', 'level': 'function', 'parent': 'user:-:loopy'}, body='l\n')
cand(room, 'upside', {'name': 'upside', 'level': 'strategy', 'parent': 'user:-:mine'}, body='u\n')
for nm in ('loopy', 'upside'):
    skills.do(r, {'action': 'promote', 'id': cand_of(nm)['id'], 'confirm': True, 'unverified_ok': True})
ok('promote: a parent that is itself, or of a lower level, is dropped; the level stays', skill_of('loopy')['level'] == 'function' and skill_of('loopy')['parent'] is None and
   skill_of('upside')['level'] == 'strategy' and skill_of('upside')['parent'] is None, (skill_of('loopy')['parent'], skill_of('upside')['parent']))

# six measures at once give the same, right number (the transcript offsets advance one request at a time)
import threading  # noqa: E402
got = []
ths = [threading.Thread(target=lambda: got.append(skills.do(r, {'action': 'measure', 'id': 'user:-:good-new'}).get('measured', {}).get('tokens_saved'))) for _ in range(6)]
[t.start() for t in ths]
[t.join() for t in ths]
ok('six parallel measures all say 200', got == [200] * 6, got)

# the verdict cannot be forged by a job (it writes meta.json), and a candidate cannot weaken the gate with an easier check
import shutil  # noqa: E402
cand(room, 'forged', {'name': 'forged', 'check': {'cmd': 'exit 0'}}, body='forged\n')
fid = cand_of('forged')['id']
m = json.loads((room / 'skills-candidates/forged/meta.json').read_text(encoding='utf-8'))
m['verified'] = {'ok': True, 'at': 1, 'exit': 0, 'hash': 'x', 'skill_hash': skills_d8.file_hash(room / 'skills-candidates/forged/SKILL.md')}
(room / 'skills-candidates/forged/meta.json').write_text(json.dumps(m), encoding='utf-8')
ok('a "verified" written into meta.json by a job counts for nothing', cand_of('forged')['verified']['state'] == 'unverified' and
   skills.do(r, {'action': 'promote', 'id': fid})['preview']['unverified'] is True)
shutil.rmtree(room / 'skills-candidates/mine')
cand(room, 'mine', {'name': 'mine', 'improves': 'user:-:mine', 'check': {'cmd': 'exit 0'}}, desc='Merge pdf files into one document', body='weaker\n')
wid = [c['id'] for c in idx()['candidates'] if c['name'] == 'mine' and c['status'] == 'new'][0]
pv = skills.do(r, {'action': 'promote', 'id': wid})['preview']
ran.clear()
script[:] = [(0, 'easy'), (1, 'the old check fails')]
res = skills.do(r, {'action': 'promote', 'id': wid, 'confirm': True, 'unverified_ok': True, 'token': pv['token']})
ok('an easier check of the candidate does not replace the old one: the old one fails after, the change is reverted',
   not res['ok'] and res['reverted'] is True and 'improved body' in (mine / 'SKILL.md').read_text(encoding='utf-8') and [x[0] for x in ran] == ['exit 0', 'node new.js'], (res, ran))

# a busy machine: the answer is at once, not a wait inside the request
import machine  # noqa: E402
real_holder = machine.holder
machine.holder = lambda: {'pid': -5, 'label': 'a long build'}
skills_d8.run_cmd = REAL
rr = skills_d8.run_one({'cmd': 'x', 'cwd': None, 'timeout': 5}, str(BASE))
machine.holder = real_holder
skills_d8.run_cmd = fake
ok('a machine busy with another job: an error naming it, nothing waits', isinstance(rr, str) and 'a long build' in rr, rr)

# a corrupt JSON file counts as absent: one bad job output or meta.json must not take the whole panel down
bad = BASE / 'bad.json'
bad.write_text('{not json', encoding='utf-8')
bad2 = BASE / 'bad2.json'
bad2.write_bytes(b'\xff\xfe\x00bad')
ok('a corrupt JSON file (bad json, bad utf-8) reads as empty, not as an error', skills.read_json_file(bad) == {} and skills.read_json_file(bad2) == {}, 'raised or not empty')

# an accepted improvement keeps the cases the skill already had and adds the candidate's (the gate ran them all)
ck = lambda w: {'cmd': 'x ' + w, 'cwd': None, 'timeout': 30}
kept = BASE / 'carrykeep.md'
kept.write_text('x', encoding='utf-8')
skills_d8.carry({'cases': [{'task': 'new', 'check': ck('b')}]}, 'user:-:carrykeep', kept, None, None,
                {'checks': [], 'cases': [{'id': 'c1', 'task': 'old', 'check': ck('a')}, {'id': 'c1+', 'task': 'new', 'check': ck('b')}]})
got = skills_d8.sidecar().get('user:-:carrykeep', {}).get('cases') or []
ok('carry keeps the old cases and adds the new one (ids from the gate)', [c['id'] for c in got] == ['c1', 'c1+'], got)

print(f'\n{fails} failure(s)')
sys.exit(1 if fails else 0)
