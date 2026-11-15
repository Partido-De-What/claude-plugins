"""0.19.9 BRIO: B2 roster written by the PreToolUse hook, B4 `post "text"`, B5 status turn 'stopped', B6 inbox marks of a lead.
Fake CLAUDE_CONFIG_DIR, a temp room: nothing real is read or written. Run: python smoke_0199_b.py
(CHATROOM_SCRIPTS = the scripts folder, default: this file's parent; against an older one the new checks FAIL)"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199b_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['HOME'] = os.environ['USERPROFILE'] = str(BASE)
os.environ['CHATROOM_RELAUNCHED'] = '1'               # no uv environment built under the fake folder at every run (1-2 minutes)
sys.path.insert(0, SCRIPTS)
import chat      # noqa: E402
import inbox     # noqa: E402
fails = 0
CHAT = str(Path(SCRIPTS) / 'chat.py')


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def run(*args, stdin=None):
    given = {'input': stdin} if stdin is not None else {'stdin': subprocess.DEVNULL}       # no stdin at all: a shell that gives none
    return subprocess.run([sys.executable, '-X', 'utf8', CHAT, *args], capture_output=True, text=True, encoding='utf-8', timeout=60, **given)


def log(room):
    p = room / 'chat.jsonl'
    return p.read_text(encoding='utf-8') if p.is_file() else ''


def mkroom(name):
    room = BASE / name
    run('init', '--room', str(room), '--participants', 'A,B', '--lang', 'en')
    return room


# ---- B4: post "text" as an argument (it answered "empty message": it wanted stdin)
room = mkroom('r4')
r = run('post', '--as', 'A', '--room', str(room), 'hello from an argument')
ok('B4: post --as A "text" posts the text', 'empty message' not in r.stdout + r.stderr and 'hello from an argument' in log(room), r.stdout + r.stderr)
r = run('post', '--as', 'B', 'second one', '--room', str(room))
ok('B4: the words may come before --room too', 'second one' in log(room), r.stdout + r.stderr)
r = run('post', '--as', 'A', '--room', str(room), stdin='from stdin\nsecond line')
ok('B4: stdin still works', 'from stdin' in log(room), r.stdout + r.stderr)
r = run('post', '--as', 'A', '--room', str(room))
ok('B4: neither text nor stdin is still refused', 'empty message' in r.stdout + r.stderr, r.stdout + r.stderr)

# ---- B2: the roster writes itself from an agent's first chat call (the desktop app has no mod)
room = mkroom('r2')
hook = Path(SCRIPTS) / 'roster_hook.py'
AID, BID = 'a0123456789abcdef', 'a1111111111111111'


def fire(ev):
    return subprocess.run([sys.executable, '-S', '-E', str(hook), ], input=json.dumps(ev), capture_output=True, text=True, timeout=60)


def roster():
    p = room / 'roster.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {}


ok('B2: the hook script exists', hook.is_file())
if hook.is_file():
    fire({'agent_id': AID, 'tool_name': 'mcp__chatroom__chat_read', 'tool_input': {'room': str(room), 'as': 'A'}})
    ok('B2: an MCP chat call of a participant writes name = agent id', roster() == {'A': AID}, roster())
    fire({'agent_id': BID, 'tool_name': 'Bash', 'tool_input': {'command': f'python "{CHAT}" read --as B --room "{room}"'}})
    ok('B2: a chat.py call in a shell writes it too', roster() == {'A': AID, 'B': BID}, roster())
    before = roster()
    fire({'tool_name': 'mcp__chatroom__chat_read', 'tool_input': {'room': str(room), 'as': 'LEAD'}})                 # the lead: no agent id
    fire({'agent_id': 'a2222222222222222', 'tool_name': 'mcp__chatroom__chat_read', 'tool_input': {'room': str(room), 'as': 'LEAD'}})   # not a participant
    fire({'agent_id': 'a3333333333333333', 'tool_name': 'mcp__chatroom__chat_read', 'tool_input': {'room': str(room), 'as': 'A'}})    # the name is taken
    fire({'agent_id': AID, 'tool_name': 'mcp__chatroom__chat_read', 'tool_input': {'room': str(BASE / 'nowhere'), 'as': 'B'}})   # another room
    fire({'agent_id': 'not an id', 'tool_name': 'mcp__chatroom__chat_read', 'tool_input': {'room': str(room), 'as': 'B'}})
    ok('B2: the lead, a stranger, a taken name, another room, a bad id: nothing written', roster() == before, roster())
    cmd = next((h['command'] for g in json.loads((Path(SCRIPTS).parent / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))['hooks']['PreToolUse']
                for h in g['hooks'] if 'roster_hook.py' in h['command']), None)
    ok('B2: hooks.json runs the hook before Bash and chatroom MCP calls', cmd is not None)
    bash = shutil.which('bash')
    if cmd and bash:
        room2 = mkroom('r2b')
        ev = {'agent_id': AID, 'tool_name': 'mcp__chatroom__chat_post', 'tool_input': {'room': str(room2), 'as': 'A', 'text': 'x'}}
        subprocess.run([bash, '-c', cmd], input=json.dumps(ev), text=True, capture_output=True, timeout=60,
                       env={**os.environ, 'CLAUDE_PLUGIN_ROOT': str(Path(SCRIPTS).parent)})
        ok('B2: the hooks.json command, run by bash, writes the roster', json.loads((room2 / 'roster.json').read_text(encoding='utf-8')) == {'A': AID}
           if (room2 / 'roster.json').is_file() else False)
        t0 = time.time()
        subprocess.run([bash, '-c', cmd], input=json.dumps({'agent_id': AID, 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}), text=True,
                       capture_output=True, timeout=60, env={**os.environ, 'CLAUDE_PLUGIN_ROOT': str(Path(SCRIPTS).parent)})
        ok('B2: a Bash call that is not a chat call costs no python (under 3 s)', time.time() - t0 < 3, time.time() - t0)
    # what the lead sees: its first post now names the agents to ping instead of "the roster is not written yet"
    r = run('post', '--as', 'LEAD', '--room', str(room), '@all first message')
    ok('B2: the lead\'s first post pings the agents', AID in r.stdout and 'roster is not written' not in r.stdout, r.stdout)

# ---- B5: status says 'stopped' for an agent whose run ended, 'working' for one at work
room = mkroom('r5')
sub = BASE / 'claude' / 'projects' / 'p' / 's' / 'subagents'
sub.mkdir(parents=True)


def transcript(aid, *lines):
    (sub / f'agent-{aid}.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in lines), encoding='utf-8')


asst = lambda reason, *content: {'type': 'assistant', 'message': {'role': 'assistant', 'stop_reason': reason, 'content': list(content)}}
user = {'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'x'}]}}
tool = {'type': 'tool_use', 'name': 'Bash', 'input': {}}
transcript(AID, user, asst('end_turn', {'type': 'text', 'text': 'done'}))                                  # A: its last turn ended
transcript(BID, user, asst('tool_use', {'type': 'text', 'text': 'running'}, tool), {'type': 'system'})      # B: a command is running
run('roster', f'A={AID}', f'B={BID}', '--room', str(room))
turn = lambda: json.loads(run('status', '--room', str(room)).stdout)['turn']
ok('B5: an ended run is stopped, a running command is working', (turn()['A'], turn()['B']) == ('stopped', 'working'), turn())
transcript(AID, asst('end_turn', {'type': 'text', 'text': 'done'}), user)                                  # a message woke A again
ok('B5: a transcript that goes on after the end is working again', turn()['A'] == 'working', turn())
transcript(AID, asst('tool_use', {'type': 'tool_use', 'name': 'SubagentHandback', 'input': {}}))          # A handed its report back
ok('B5: the hand-back of the report is stopped too', turn()['A'] == 'stopped', turn())
(room / 'waiting_A.txt').write_text(f'{time.time() + 60:.0f} {os.getpid()}')                                # held by the hook: waiting wins
ok('B5: an agent held in a wait is waiting, not stopped', turn()['A'] == 'waiting', turn())

# ---- B6: the lead's inbox does not hand over again what it was already given or read
room = mkroom('r6')
for i in range(3):
    chat.Room(room).append('A', f'@LEAD message {i}')
ok('B6: control: nothing marked, three pending', len(inbox.pending(room, 'LEAD')[0]) == 3)
(room / 'delivered_LEAD.txt').write_text('')                                                              # a mark caught half written reads as 0
(room / 'cursor__alerts_LEAD.txt').write_text('3')                                                         # the relay's cursor knows better
ok('B6: a half-written delivered mark does not bring them back (the relay cursor holds)', inbox.pending(room, 'LEAD')[0] == [], inbox.pending(room, 'LEAD')[0])
(room / 'cursor__alerts_LEAD.txt').unlink()
(room / 'cursor_COORDINATOR.txt').write_text('3')                                                          # the lead read under another of its names
ok('B6: what the lead read under another name is not handed again', inbox.pending(room, 'LEAD')[0] == [], inbox.pending(room, 'LEAD')[0])
(room / 'cursor_COORDINATOR.txt').unlink()
chat.Room(room).append('A', '@LEAD message 3')
ok('B6: a newer message is still handed', [m['n'] for m in inbox.pending(room, 'LEAD')[0]] == [1, 2, 3, 4], [m['n'] for m in inbox.pending(room, 'LEAD')[0]])
ok('B6: another agent does not read the lead\'s marks', [m['n'] for m in inbox.pending(room, 'A')[0]] == [], 'A tags nobody here')

# ---- B7: rotate makes the prompt `prompt` made (its tools), carries rules + state under a cap, not the whole notebook
room = mkroom('r7')
base = room / 'prompts' / 'A.md'
run('prompt', 'A', '--room', str(room), '--tools', 'mcp', '--out', str(base))
mcp_len = len(base.read_text(encoding='utf-8'))
notes = room / 'notes'
notes.mkdir(exist_ok=True)
(notes / 'A.rules.md').write_text('- RULE-KEEP-ONE word for word\n', encoding='utf-8')
(notes / 'A.md').write_text(''.join(f'- 10:0{i % 10} OLDNOTE-{i} ' + 'x' * 180 + '\n' for i in range(120)), encoding='utf-8')    # about 23k of notebook
run('notebook', '--state', '--as', 'A', '--room', str(room), 'goal: finish T3 | done: the first half | next: write the test')
asked = run('rotate', 'A', '--as', 'LEAD', '--room', str(room))
ok('B7: the ask names the state command and its parts', '--state' in log(room) and 'what is left' in log(room), asked.stdout + asked.stderr)
r = run('rotate', 'A', '--now', '--as', 'LEAD', '--room', str(room))
rot = (room / 'prompts' / 'A-rotated.md').read_text(encoding='utf-8') if (room / 'prompts' / 'A-rotated.md').is_file() else ''
ok('B7: rotate --now ran', r.returncode == 0 and rot, r.stdout + r.stderr)
cap = getattr(chat, 'ROTATE_STATE_MAX', 4000) + 1500
ok('B7: the rotated prompt is the first prompt plus a bounded tail, not 23k', len(rot) <= mcp_len + cap, f'{len(rot)} vs {mcp_len} + {cap}')
head = rot.find('YOU GO ON FROM')
ok('B7: it keeps the tools of the first prompt (mcp, not both: 7k longer)', head > 0 and abs(head - mcp_len) < 500, f'{head} vs {mcp_len}')
ok('B7: the state is in it, and the rules word for word', 'goal: finish T3' in rot and 'next: write the test' in rot and 'RULE-KEEP-ONE word for word' in rot)
ok('B7: the notebook is a pointer, not copied', 'OLDNOTE-' not in rot and 'A~1' in rot and '120 lines' in rot, rot[-400:])
ok('B7: one name: ready says the room name A~1, and the retire line does not tell to make the prompt again',
   'A~1' in r.stdout and 'generate the new prompt' not in r.stdout, r.stdout)
ok('B7: with a state, no warning', 'left no state' not in r.stdout, r.stdout)
r = run('rotate', 'B', '--now', '--as', 'LEAD', '--room', str(room))
ok('B7: rotate --now warns (and goes on) when the state is missing', 'left no state' in r.stdout and (room / 'prompts' / 'B-rotated.md').is_file(), r.stdout + r.stderr)
room2 = mkroom('r7b')                                                                                   # a retired name is refused: a fresh room for the long state
run('notebook', '--state', '--as', 'B', '--room', str(room2), 'goal: START-MARK ' + 'y' * 5000 + ' | next: END-MARK')
r = run('rotate', 'B', '--now', '--as', 'LEAD', '--room', str(room2))
rot_b = (room2 / 'prompts' / 'B-rotated.md').read_text(encoding='utf-8')
ok('B7: a state over the cap warns and keeps its end', 'START-MARK' not in rot_b and 'END-MARK' in rot_b and 'characters' in r.stdout, r.stdout)
r = run('rotate', 'A', '--now', '--tools', 'shell', '--out', str(room / 'prompts' / 'A-shell.md'), '--as', 'LEAD', '--room', str(room))
ok('B7: --tools overrides what the first prompt used', (room / 'prompts' / 'A-shell.md').is_file() and len((room / 'prompts' / 'A-shell.md').read_text(encoding='utf-8')) > len(rot) + 3000, r.stdout + r.stderr)

# ---- B8: a decision can be retired; task amend corrects --preview
room = mkroom('r8')
for t in ('render the clip', 'storyboard', 'frame'):
    run('task', 'add', t, '--as', 'LEAD', '--room', str(room), *(['--costly'] if t.startswith('render') else []))
tasks = lambda: {t['id']: t for t in json.loads((room / 'board.json').read_text(encoding='utf-8'))['tasks']}
r = run('task', 'amend', 'T1', '--preview', 'T2', '--as', 'LEAD', '--room', str(room))
ok('B8: task amend --preview sets the task approved first', tasks()['T1'].get('preview') == 'T2', r.stdout + r.stderr)
r = run('task', 'amend', 'T1', '--preview', 'T3', '--as', 'LEAD', '--room', str(room))
ok('B8: and corrects it', tasks()['T1'].get('preview') == 'T3', r.stdout + r.stderr)
r = run('task', 'amend', 'T2', '--preview', 'T3', '--as', 'LEAD', '--room', str(room))
ok('B8: a task that is not costly is refused', 'preview' not in tasks()['T2'] and r.returncode != 0, r.stdout + r.stderr)
r = run('task', 'amend', 'T1', '--preview', 'T9', '--as', 'LEAD', '--room', str(room))
ok('B8: an unknown task is refused, the old preview stays', tasks()['T1'].get('preview') == 'T3' and r.returncode != 0, r.stdout + r.stderr)
for text in ('rule one', 'rule two'):
    run('task', 'decide', text, '--as', 'LEAD', '--room', str(room))
r = run('task', 'retire', 'D1', '--note', 'it was wrong', '--as', 'LEAD', '--room', str(room))
shown = run('board', '--room', str(room)).stdout
ok('B8: a retired decision leaves the board, the others stay', r.returncode == 0 and 'rule one' not in shown and 'rule two' in shown, r.stdout + r.stderr + shown)
ok('B8: CONVENZIONI.md says it was retired, on a line of the same shape as the decision',
   any(x.startswith('- D1 ') and 'RETIRED' in x for x in (room / 'CONVENZIONI.md').read_text(encoding='utf-8').splitlines()))
ok('B8: it is kept in the history', [d['k'] for d in json.loads((room / 'board.json').read_text(encoding='utf-8'))['decisions']] == [1, 2])
ok('B8: retiring twice is refused', run('task', 'retire', 'D1', '--as', 'LEAD', '--room', str(room)).returncode != 0)
ok('B8: an unknown decision is refused', run('task', 'retire', 'D9', '--as', 'LEAD', '--room', str(room)).returncode != 0)
ok('B8: an agent cannot retire the lead\'s decision', run('task', 'retire', 'D2', '--as', 'A', '--room', str(room)).returncode != 0)
run('task', 'decide', 'rule of A', '--as', 'A', '--room', str(room))
ok('B8: its author can retire it', run('task', 'retire', 'D3', '--as', 'A', '--room', str(room)).returncode == 0)
ok('B8: the numbers are not reused', run('task', 'decide', 'rule four', '--as', 'LEAD', '--room', str(room)).stdout.count('D4') >= 1)

# ---- B3: the browser panel is one for all: a lock named "browser", short by default, in the prompt and the help
room = mkroom('r3')
held = lambda: json.loads((room / 'locks.json').read_text(encoding='utf-8'))
r = run('lock', 'acquire', 'browser', '--as', 'A', '--room', str(room))
ok('B3: lock acquire browser is A\'s, for 10 minutes by default', r.returncode == 0 and held()['browser']['ttl'] == 10, r.stdout + r.stderr)
r = run('lock', 'acquire', 'bench', '--as', 'A', '--room', str(room))
ok('B3: another resource keeps the 30 minutes', held()['bench']['ttl'] == 30, r.stdout + r.stderr)
r = run('lock', 'acquire', 'browser', '--as', 'B', '--room', str(room))
ok('B3: B finds the panel taken and is queued (exit 3)', r.returncode == 3 and [q['name'] for q in held()['browser']['queue']] == ['B'], r.stdout + r.stderr)
run('lock', 'release', 'browser', '--as', 'A', '--room', str(room))
ok('B3: at the release the panel passes to B, still for 10 minutes', held()['browser']['owner'] == 'B' and held()['browser']['ttl'] == 10, held())
r = run('lock', 'acquire', 'browser', '--as', 'A', '--ttl', '25', '--room', str(room))
ok('B3: --ttl still decides when it is given', r.returncode == 3 and run('lock', 'release', 'browser', '--as', 'B', '--room', str(room)).returncode == 0 and held()['browser']['ttl'] == 25, held())
help_lock = run('help', 'lock', '--as', 'A', '--room', str(room)).stdout
ok('B3: the lock help names the browser panel', 'browser' in help_lock, help_lock)
ok('B3: the agent prompt names it too', 'browser panel' in run('prompt', 'A', '--room', str(room)).stdout)

# ---- T19a: the user's layer (CLAUDE_CONFIG_DIR/chatroom/user) is read before the core; one place says where the user's data lives
try:
    import layers
except ImportError:                                  # the old code: nothing of this exists
    layers = None
ok('T19a: scripts/layers.py exists', layers is not None)
mine = BASE / 'claude' / 'chatroom'
user = mine / 'user'
room = mkroom('r19')
roomit = BASE / 'r19i'
run('init', '--room', str(roomit), '--participants', 'A,B', '--lang', 'it')
put = lambda rel, text: ((user / rel).parent.mkdir(parents=True, exist_ok=True), (user / rel).write_text(text, encoding='utf-8'))
helptext = lambda r: run('help', 'lock', '--as', 'A', '--room', str(r)).stdout
ok('T19a: with no override the core page is read', 'a shared resource' in helptext(room) and 'risorsa condivisa' in helptext(roomit))
put('templates/help_lock.md', 'OVERRIDE {{AS}}\n')
ok('T19a: an override of a template wins over the core (and is filled)', helptext(room).startswith('OVERRIDE A'), helptext(room))
ok('T19a: an English override does not replace the Italian core page', 'risorsa condivisa' in helptext(roomit), helptext(roomit))
put('templates/it/help_lock.md', 'SOVRASCRITTO {{AS}}\n')
ok('T19a: an Italian override wins in an Italian room', helptext(roomit).startswith('SOVRASCRITTO A') and helptext(room).startswith('OVERRIDE A'), helptext(roomit))
(user / 'templates' / 'help_lock.md').unlink()
(user / 'templates' / 'it' / 'help_lock.md').unlink()
ok('T19a: take the override away and the core is back', 'a shared resource' in helptext(room))
put('guides/lead-normal.md', 'MY GUIDE\n')
ok('T19a: a guide is overridden too, the other one is not', run('guide', 'normal', '--room', str(room)).stdout.startswith('MY GUIDE')
   and not run('guide', 'research', '--room', str(room)).stdout.startswith('MY GUIDE'))
put('templates/agent_prompt.md', 'I AM {{NAME}} IN {{ROOM}}\n')
ok('T19a: the agent prompt can be overridden', run('prompt', 'A', '--room', str(room)).stdout.startswith('I AM A IN '), run('prompt', 'A', '--room', str(room)).stdout[:200])
put('locales/en.json', json.dumps({'chat.say.lock.free': 'FREE-X {lock}'}))
r = run('lock', 'check', 'browser', '--as', 'A', '--room', str(room))
ok('T19a: a key of the user\'s locale overrides one text, not the others', 'FREE-X browser' in r.stdout and 'is held by' not in r.stdout and 'Usage' not in r.stdout, r.stdout + r.stderr)
put('locales/en.json', '{oops')
r = run('lock', 'check', 'browser', '--as', 'A', '--room', str(room))
ok('T19a: a locale file that is not JSON is ignored, the core text is used', r.returncode == 0 and 'is free for you' in r.stdout, r.stdout + r.stderr)
ok('T39: ...and one line on stderr names the file (it was ignored in silence)', r.stderr.count('en.json') == 1 and 'cannot be used' in r.stderr, r.stderr[-300:])
(user / 'locales' / 'en.json').write_bytes('{"chat.say.lock.free": "caffè"}'.encode('cp1252'))      # Notepad ANSI
r = run('lock', 'check', 'browser', '--as', 'A', '--room', str(room))
ok('T39: a locale saved in cp1252 is ignored with the same line, and an empty one too', r.returncode == 0 and 'is free for you' in r.stdout and r.stderr.count('en.json') == 1, r.stdout + r.stderr[-300:])
(user / 'locales' / 'en.json').write_bytes(b'')
r = run('lock', 'check', 'browser', '--as', 'A', '--room', str(room))
ok('T39: an empty locale file gets the line too', r.returncode == 0 and r.stderr.count('en.json') == 1, r.stdout + r.stderr[-300:])
(user / 'locales' / 'en.json').write_text('{"chat.say.lock.free": "FREE-X {lock}"}', encoding='utf-8')      # back to what the tests below expect
r = run('lock', 'check', 'browser', '--as', 'A', '--room', str(room))
ok('T39: a good locale file says nothing on stderr', 'en.json' not in r.stderr, r.stderr[-300:])
r = run('prompt', 'A', '--room', str(room), '--template', '../guides/lead-normal.md')
ok('T19a: a template name that leaves the folder is refused', r.returncode != 0 or 'MY GUIDE' not in r.stdout, r.stdout + r.stderr)
if layers:
    ok('T19a: chatroom_dir() follows CLAUDE_CONFIG_DIR', layers.chatroom_dir() == mine and layers.user_root() == user, layers.chatroom_dir())
    ok('T19a: find() says which layer, and a name that leaves its folder finds nothing',
       layers.find('guides', 'lead-normal.md')[1] == 'user' and layers.find('guides', 'lead-research.md')[1] == 'core'
       and layers.find('templates', '../guides/lead-research.md') == (None, None))
    (BASE / 'crlf.txt').write_bytes(b'a\r\nb\r\n')
    (BASE / 'lf.txt').write_bytes(b'a\nb\n')
    ok('T19a: sha() of a CRLF file is the one of its LF text', layers.sha(BASE / 'crlf.txt') == layers.sha(BASE / 'lf.txt') and layers.sha(BASE / 'none') is None)
    rel = 'guides/lead-normal.md'
    layers.base_path(rel).unlink(missing_ok=True)       # a read saved it (T29 below); here is an override that has none
    ok('T19a: an override with no base is not stale', rel in layers.overrides() and rel not in layers.stale())
    layers.base_save(rel)
    ok('T19a: base_save copies the core file in .base, then it is not stale', layers.sha(layers.base_path(rel)) == layers.sha(layers.core_root() / rel) and layers.stale() == [])
    layers.base_path(rel).write_text('an older core', encoding='utf-8')
    ok('T19a: a core file that is not the base any more makes the override stale', layers.stale() == [rel], layers.stale())
    for other in ('.pristine/guides/x.md', 'recovered/0.18.0/templates/x.md', 'guides/lead-normal.md.merged', 'templates/x.tmp', 'hooks/x.py'):
        put(other, 'x')
    ok('T19a: .base, other .folders, recovered/ and the drafts of a merge are not overrides', layers.overrides() == ['guides/lead-normal.md', 'locales/en.json', 'templates/agent_prompt.md'], layers.overrides())
    # T29: an override made by hand has no base; the first time it is read, the core file it is read instead of becomes its base
    # (the merge of the next update needs the core it was written against, and by then the core is already the new one)
    layers.base_path(rel).unlink(missing_ok=True)
    same = lambda r: layers.sha(layers.base_path(r)) is not None and layers.sha(layers.base_path(r)) == layers.sha(layers.core_root() / r)
    ok('T29: the first read of an override saved the core file as its base (guide, template, locale)',
       same('templates/agent_prompt.md') and same('locales/en.json') and not layers.base_path(rel).exists(), [r for r in layers.overrides() if not same(r)])
    layers.find('guides', 'lead-normal.md')
    ok('T29: find() of an override saves the base when there is none', same(rel) and layers.stale() == [])
    layers.base_path(rel).write_text('the core of a version before', encoding='utf-8')
    layers.find('guides', 'lead-normal.md')
    ok('T29: a base that is there is never rewritten by a read', layers.base_path(rel).read_text(encoding='utf-8') == 'the core of a version before')
    put('templates/my_own.md', 'a file of the user with no twin in the core')
    ok('T29: an override with no core file gets no base', layers.find('templates', 'my_own.md')[1] == 'user' and not layers.base_path('templates/my_own.md').exists())
    (user / 'templates' / 'my_own.md').unlink()
    ok('T29: a core file read as such gets no base', layers.find('guides', 'lead-research.md')[1] == 'core' and not layers.base_path('guides/lead-research.md').exists())
    layers.base_save(rel)
    import i18n
    time.sleep(1.1)
    put('locales/en.json', json.dumps({'chat.say.lock.free': 'FREE-Y {lock}'}))
    ok('T19a: i18n.catalog() carries the user\'s keys on the core ones', i18n.catalog('en')['chat.say.lock.free'] == 'FREE-Y {lock}' and i18n.catalog('en')['chat.say.lock.busy'].startswith('lock {lock}'))
    # a value of the user's locale that is not a text would break every command that says the key (fill() wants a string)
    time.sleep(1.1)
    put('locales/en.json', json.dumps({'chat.say.lock.free': 'FREE-Z {lock}', 'chat.say.lock.busy': 5, 'chat.say.lock.held': ['a'], 'chat.say.lock.none': {}}))
    ok('T28: locale_overlay keeps texts and plurals, not numbers, lists or empty ones', layers.locale_overlay('en') == {'chat.say.lock.free': 'FREE-Z {lock}'}, layers.locale_overlay('en'))
    ok('T28: a key of the user that is not a text leaves the core text, and saying it does not fail',
       i18n.catalog('en')['chat.say.lock.free'] == 'FREE-Z {lock}' and i18n.tr('en', 'chat.say.lock.busy', lock='L', owner='h').startswith('lock L is held by h'),
       i18n.tr('en', 'chat.say.lock.busy', lock='L', owner='h'))
    # T35: an override that is not UTF-8 (Notepad saves ANSI) or is empty is skipped, and a line says which file; a BOM is not text
    hl = user / 'templates' / 'help_lock.md'
    hl.parent.mkdir(parents=True, exist_ok=True)
    hl.write_bytes('caffè {{AS}}\n'.encode('cp1252'))
    r = run('help', 'lock', '--as', 'A', '--room', str(room))
    ok('T35: an override saved in cp1252 is skipped: the core page is read and a line names the file',
       r.returncode == 0 and 'a shared resource' in r.stdout and 'help_lock.md' in r.stderr and 'UTF-8' in r.stderr, r.stdout[:80] + r.stderr[-300:])
    hl.write_bytes(b'  \r\n')
    r = run('help', 'lock', '--as', 'A', '--room', str(room))
    ok('T35: an empty (blank) override is skipped, with a line', r.returncode == 0 and 'a shared resource' in r.stdout and 'help_lock.md' in r.stderr and 'empty' in r.stderr, r.stdout[:80] + r.stderr[-300:])
    hl.write_bytes(b'\xef\xbb\xbfOVERRIDE {{AS}}\r\n')
    r = run('help', 'lock', '--as', 'A', '--room', str(room))
    ok('T35: a BOM at the start of an override is not part of the page', r.stdout.startswith('OVERRIDE A') and 'help_lock.md' not in r.stderr, repr(r.stdout[:20]) + r.stderr[-200:])
    hl.write_text('perché {{AS}}\n', encoding='utf-8')
    r = run('help', 'lock', '--as', 'A', '--room', str(room))
    ok('T35: an override in UTF-8 with accents is used, with no line', r.stdout.startswith('perché A') and 'help_lock.md' not in r.stderr, repr(r.stdout[:20]) + r.stderr[-200:])
    (user / 'templates' / 'zz_only_user.md').write_bytes(b'caff\xe8\n')
    ok('T35: an unreadable override with no core page finds nothing', layers.find('templates', 'zz_only_user.md') == (None, None))
    hl.unlink()
    (user / 'templates' / 'zz_only_user.md').unlink()
    layers.base_path('templates/help_lock.md').unlink(missing_ok=True)
    from spawn.bench import strengths
    import idle_life
    ok('T19a: the files of the user\'s data are under chatroom_dir(), not under HOME/.claude',
       chat.SETTINGS_FILE.parent == mine and chat.OFFICE_FILE.parent == mine and idle_life.USER_SPOTS.parent == mine and strengths.extra_path() == mine / 'spawn' / 'glossary_extra.json',
       (chat.SETTINGS_FILE, idle_life.USER_SPOTS, strengths.extra_path()))
else:
    from spawn.bench import strengths
    ok('T19a: the files of the user\'s data follow CLAUDE_CONFIG_DIR', strengths.extra_path() == mine / 'spawn' / 'glossary_extra.json', strengths.extra_path())

# ---- T27: nobody builds the Claude folder by hand: CLAUDE_CONFIG_DIR is honoured by every module or by none
here = Path(SCRIPTS)
STANDALONE = ('layers.py', 'mcp_launch.py')            # layers.py says where it is; mcp_launch.py is copied next to Claude's folder and cannot import it
hand = [str(p.relative_to(here)) for p in here.rglob('*.py')
        if p.name not in STANDALONE and not p.name.startswith(('smoke_', 'test_'))
        and re.search(r"Path\.home\(\)\s*/\s*['\"]\.claude['\"]", p.read_text(encoding='utf-8', errors='replace'))]
ok('T27: no module of the plugin rebuilds ~/.claude by hand (it asks layers)', not hand, hand)
if layers is not None:
    import doctor, lessons, machine, packs, skills
    from spawn import limiter
    ok('T27: the modules that had their own copy now follow CLAUDE_CONFIG_DIR through layers',
       lessons.home() == mine and machine.lock_path() == mine / 'machine.lock' and doctor.claude_dir() == mine.parent and skills.claude_dir() == mine.parent
       and packs.CLAUDE_DIR == mine.parent and limiter.out_path() == mine / 'spawn' / 'out.json',
       (lessons.home(), machine.lock_path(), doctor.claude_dir(), skills.claude_dir(), packs.CLAUDE_DIR, limiter.out_path()))

shutil.rmtree(BASE, ignore_errors=True)
print('FAIL' if fails else 'ALL PASS', fails, flush=True)
sys.exit(1 if fails else 0)
