"""0.19.9, area A (auto-harness): one test per bug of BUG-0.19.5.md, each failing on 0.19.0 and passing here.
Run: python -X utf8 smoke_0199_a.py   (ONLY=A1 runs one). HOME is a fake config dir: nothing is written in ~/.claude"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke0199a_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import chat  # noqa: E402

CHAT = str(Path(SCRIPTS) / 'chat.py')
ONLY = os.environ.get('ONLY')
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def section(key):
    if ONLY and ONLY != key:
        return False
    print(f'-- {key}', flush=True)
    return True


def run(room, *args, stdin=b'', timeout=180):
    r = subprocess.run([sys.executable, '-X', 'utf8', CHAT, *args, '--room', str(room)], input=stdin, capture_output=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def post(room, who, text, *extra):
    return run(room, 'post', '--as', who, *extra, stdin=text.encode('utf-8'))


def plain(name, participants='A,B,C', lang='en'):
    room = BASE / f'room-{name}'
    subprocess.run([sys.executable, CHAT, 'init', '--room', str(room), '--participants', participants, '--lang', lang], capture_output=True)
    return room


def events(room):
    try:
        return [json.loads(x) for x in (room / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    except OSError:
        return []


if section('A1'):      # ground=1: the held done must come back with something checked
    room = plain('a1', 'A,B')
    run(room, 'brief', 'goal=g', 'ground=1', 'max=20')
    run(room, 'task', 'add', 't1', '--as', 'A'); run(room, 'task', 'take', 'T1', '--as', 'A')
    c1, o1 = run(room, 'task', 'done', 'T1', '--proof', 'pytest: 3 passed, exit 0', '--as', 'A')
    ok('A1 the first done is held', c1 != 0 and 'held once' in o1, o1)
    c2, o2 = run(room, 'task', 'done', 'T1', '--proof', 'pytest -q: 3 passed, exit 0', '--as', 'A')
    ok('A1 the same proof, reworded, is held again', c2 != 0 and 'held again' in o2, o2)
    c3, o3 = run(room, 'task', 'done', 'T1', '--proof', 'pytest: 3 passed, exit 0; callers read in chat.py:2156 and smoke_017.py:368, no other spelling', '--as', 'A')
    ok('A1 a proof that names what was checked after the hold goes through', c3 == 0 and 'done by A' in o3, o3)
    ev = [e for e in events(room) if e['kind'] == 'guard']
    ok('A1 both holds are events with task and agent', [(e['key'], e.get('task'), e['name']) for e in ev] == [('ground', 'T1', 'A'), ('ground_same', 'T1', 'A')], ev)
    run(room, 'task', 'add', 't2', '--as', 'A'); run(room, 'task', 'take', 'T2', '--as', 'A')
    b = json.loads((room / 'board.json').read_text(encoding='utf-8'))
    b['tasks'][1]['grounded'] = True                  # a board of 0.19.0 held it once already
    (room / 'board.json').write_text(json.dumps(b), encoding='utf-8')
    c, o = run(room, 'task', 'done', 'T2', '--proof', 'pytest: 3 passed, exit 0', '--as', 'A')
    ok('A1 a board of 0.19.0 (grounded true) still passes the second done', c == 0 and 'done by A' in o, o)

def agent_log(aid, *recs):
    """a Claude Code subagent's transcript where chat.py looks for it (CLAUDE_CONFIG_DIR/projects/*/*/subagents/agent-ID.jsonl)"""
    d = BASE / 'claude' / 'projects' / 'p' / 's' / 'subagents'
    d.mkdir(parents=True, exist_ok=True)
    (d / f'agent-{aid}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in recs), encoding='utf-8')
    chat._AGENT_FILES.clear()


def iso(sec):
    return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(sec))


ERR = lambda sec: {'type': 'assistant', 'timestamp': iso(sec), 'isApiErrorMessage': True, 'apiError': 'connection_failed', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'API Error'}]}}
TEXT = lambda sec, t: {'type': 'assistant', 'timestamp': iso(sec), 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': t}]}}


def with_board(room, tasks):
    p = room / 'board.json'
    b = json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {'tasks': [], 'facts': [], 'decisions': []}
    b['tasks'] = tasks
    p.write_text(json.dumps(b), encoding='utf-8')


def task(tid, owner, state='taken', **kw):
    return {'id': tid, 'title': f'task {tid}', 'owner': owner, 'state': state, 'files': [], 'deps': [], 'notes': [], 'ts': time.time(), **kw}


if section('A2'):      # events say who and on which task
    room = plain('a2', 'A,B')
    run(room, 'task', 'add', 't1', '--as', 'A'); run(room, 'task', 'take', 'T1', '--as', 'A')
    run(room, 'task', 'done', 'T1', '--as', 'A')      # no proof: refused
    ev = [e for e in events(room) if e['key'] == 'noproof']
    ok('A2 a refusal carries the task', ev and ev[0].get('task') == 'T1' and ev[0]['name'] == 'A', events(room))
    r = chat.Room(room)
    r.append('A', 'working on T1'); r.append('B', 'ok')
    last = max(m['n'] for m in r.messages() if m['from'] == 'A')
    (room / 'gone.json').write_text(json.dumps({'A': {'n': last, 'why': 'idle', 'tasks': ['T1'], 'procs': []}}))
    c, o = run(room, 'alerts', '--as', 'LEAD', '--messages')
    ev = [e for e in events(room) if e['kind'] == 'check' and e['key'] == 'gone']
    ok('A2 a check carries the agent, the task and its whole key', ev and ev[0]['name'] == 'A' and ev[0].get('task') == 'T1' and ev[0].get('detail') == f'gone:A:{last}', (ev, o))
    o = run(room, 'lessons')[1]
    ok('A2 lessons counts the agent of a check', '1 agent' in o.split('check:gone')[1].split('\n')[0], o)

if section('A7'):      # gone: what the agent still held, and what it left running
    room = plain('a7', 'A,B')
    r = chat.Room(room)
    r.append('A', 'start'); r.append('B', 'ok')
    with_board(room, [task('T6', 'A')])
    (room / 'gone.json').write_text(json.dumps({'A': {'n': 1, 'why': 'task', 'tasks': ['T6'], 'procs': ['python -m http.server 8797']}}))
    o = run(room, 'check')[1]
    ok('A7 an agent that left with a task is not said to have nothing taken', 'T6' in o and 'nothing taken' not in o and 'http.server 8797' in o, o)
    c, o = run(room, 'status')
    ok('A7 status reads the new gone.json too: A is closed', c == 0 and json.loads(o)['turn']['A'] == 'closed', o)
    (room / 'gone.json').write_text(json.dumps({'A': 1}))
    o = run(room, 'check')[1]
    ok('A7 a gone.json of 0.19.0 (the number alone) still reads', 'ended its run with the room open' in o, o)

if section('A8'):      # "waiting for you" counts only what is for the lead
    room = plain('a8', 'UI,DESIGN')
    r = chat.Room(room)
    r.append('UI', '@DESIGN T16 reviewed, no defect. Note: I cleared localStorage on the viewer of LEAD by mistake, can you tell me if it matters?')
    ok('A8 a message to another agent that only names the lead is not a wait for the lead', not chat.waits_for_lead(r), chat.waits_for_lead(r))
    r.append('UI', '@LEAD can you decide this, A or B?')
    ok('A8 a question tagged to the lead is', [x[0] for x in chat.waits_for_lead(r)] == ['UI'], chat.waits_for_lead(r))
    r2 = chat.Room(plain('a8b', 'UI,DESIGN'))
    r2.append('UI', 'LEAD, can I close this?')
    ok('A8 a question that names the lead without a tag still is', [x[0] for x in chat.waits_for_lead(r2)] == ['UI'])

if section('A5'):      # an agent ended by an API error is not an agent that waits
    import hold
    room = plain('a5', 'A,B')
    r = chat.Room(room)
    r.update_roster(lambda ro: ro.update(A='aaaa1111aaaa', B='bbbb2222bbbb'))
    r.append('A', 'start'); r.append('B', 'ok')
    with_board(room, [task('T6', 'A')])
    now = time.time()
    agent_log('aaaa1111aaaa', TEXT(now - 400, 'working'), ERR(now - 300))
    e = chat.fell(r, 'A')
    ok('A5 the last record is an API error', e and e[0] == 'connection_failed' and abs(e[1] - (now - 300)) < 2, e)
    o = run(room, 'check')[1]
    ok('A5 the relay says it fell, with its tasks and how to resume it', 'API error' in o and 'T6' in o and 'aaaa1111aaaa' in o, o)
    got = hold.decide({'agent_id': 'aaaa1111aaaa'}, wait=3, poll=0.2)
    ok('A5 the hold resumes it with what happened', got and got['decision'] == 'block' and 'connection_failed' in got['reason'], got)
    for _ in range(hold.FELL_MAX):
        got = hold.decide({'agent_id': 'aaaa1111aaaa'}, wait=1, poll=0.2)
    ok('A5 a network that stays down does not resume it forever', not (got and 'connection_failed' in got.get('reason', '')), got)
    agent_log('aaaa1111aaaa', TEXT(now - 400, 'working'), ERR(now - 300), TEXT(now - 100, 'back'))
    ok('A5 an agent that went on after the error did not fall', chat.fell(r, 'A') is None)
    ok('A5 and the relay is quiet about it', 'API error' not in run(room, 'check')[1])

if section('B1'):      # exits with the room open: the report once for each stretch of silence, and a task holder stays
    import hold
    room = plain('b1', 'A,B')
    r = chat.Room(room)
    r.update_roster(lambda ro: ro.update(A='cccc3333cccc', B='dddd4444dddd'))
    r.append('LEAD', 'start'); r.append('A', 'idle')
    agent_log('cccc3333cccc', TEXT(time.time() - 50, 'resto in idle'))
    first = hold.report(r, 'A')
    again = hold.report(r, 'A')
    r.append('A', 'back and gone again')
    third = hold.report(r, 'A')
    ok('B1 the report is asked once for a stretch of silence, and again after the agent wrote', first and again is None and third, (first, again, third))
    with_board(room, [task('T6', 'A')])
    r.set_cursor('A', 99)
    held = [hold.decide({'agent_id': 'cccc3333cccc'}, wait=1, poll=0.2) for _ in range(hold.EMPTY_MAX + 3)]
    ok('B1 an agent that holds a task is held, not let go after the empty windows', all(held), held)
    (room / 'empty_A.txt').write_text('0')
    held = [hold.decide({'agent_id': 'cccc3333cccc'}, wait=1, poll=0.2) for _ in range(hold.TASK_EMPTY_MAX + 1)]
    g = json.loads((room / 'gone.json').read_text()) if (room / 'gone.json').exists() else {}
    ok('B1 a task holder is held through the long cap, then goes with its task named', all(held[:-1]) and g.get('A', {}).get('why') == 'task' and g['A'].get('tasks') == ['T6'], (held[-1], g))
    with_board(room, [])
    r.append('A', '40%: waiting for @B', 'idle')
    r.set_cursor('A', 99)
    (room / 'empty_A.txt').write_text('0')
    held = [hold.decide({'agent_id': 'cccc3333cccc'}, wait=1, poll=0.2) for _ in range(hold.EMPTY_MAX + 1)]
    g = json.loads((room / 'gone.json').read_text())
    ok('B1 an idle agent goes after the empty windows, asked for its report, and gone.json says why', 'report' in held[-1]['reason'] and g['A']['why'] == 'idle' and g['A']['tasks'] == [], (held[-1], g))

if section('B1c'):     # a task holder held with nothing new for 3 turns: the lead is told once for the stretch, with the minutes (T36)
    import hold
    room = plain('b1c', 'A,B')
    r = chat.Room(room)
    r.update_roster(lambda ro: ro.update(A='eeee5555eeee', B='ffff6666ffff'))
    r.append('LEAD', 'start'); r.append('A', 'taking T6')
    with_board(room, [task('T6', 'A')])
    r.set_cursor('A', max(m['n'] for m in r.messages()))
    settings = BASE / 'claude' / 'chatroom' / 'settings.json'
    hold_turn = lambda: hold.decide({'agent_id': 'eeee5555eeee'}, wait=1, poll=0.2)
    idle_checks = lambda: [(k, t) for k, t in chat.failures(r) if k.startswith('taskidle:')]
    for _ in range(2):
        hold_turn()
    ok('B1c two empty turns: nothing yet', not idle_checks(), idle_checks())
    hold_turn()
    got = idle_checks()
    ok('B1c the third empty turn: the lead is told who holds what, and for how many minutes', len(got) == 1 and 'A holds T6' in got[0][1] and 'nothing for 27 minutes' in got[0][1], got)
    key = got[0][0] if got else ''
    for _ in range(2):
        hold_turn()
    ok('B1c more empty turns: the same key, so the relay says it once', [k for k, _ in idle_checks()] == [key], idle_checks())
    r.append('B', '@A are you there?')
    hold_turn()
    ok('B1c something for it arrives: nothing to say any more', not idle_checks(), idle_checks())
    r.append('A', 'yes, on T6'); r.set_cursor('A', max(m['n'] for m in r.messages()))
    for _ in range(3):
        hold_turn()
    again = idle_checks()
    ok('B1c a new stretch of silence is a new key', len(again) == 1 and again[0][0] != key, (key, again))
    settings.write_text(json.dumps({'task_idle_turns': 'x', 'task_empty_max': 0}), encoding='utf-8')
    ok('B1c a junk value in the user settings is ignored', chat.settings().get('task_idle_turns') is None and chat.settings().get('task_empty_max') is None, chat.settings())
    r.append('A', 'still on T6'); r.set_cursor('A', max(m['n'] for m in r.messages()))
    settings.write_text(json.dumps({'task_idle_turns': 1, 'task_empty_max': 2}), encoding='utf-8')
    (room / 'empty_A.txt').write_text('0')
    hold_turn()
    ok('B1c the user settings move the threshold: after 1 turn', len(idle_checks()) == 1, idle_checks())
    hold_turn(); hold_turn()
    g = json.loads((room / 'gone.json').read_text()) if (room / 'gone.json').exists() else {}
    ok('B1c and the cap: it goes after 2 empty turns, naming its task', g.get('A', {}).get('why') == 'task' and g['A'].get('tasks') == ['T6'], g)
    ok('B1c an agent that went is not said to do nothing: the gone check says it', not idle_checks() and any(k.startswith('gone:A:') for k, _ in chat.failures(r)), chat.failures(r))
    settings.unlink()


def usage(sec, ctx, mid):
    """an assistant record with the usage a context is read from"""
    return {'type': 'assistant', 'timestamp': iso(sec), 'message': {'id': mid, 'role': 'assistant', 'content': [{'type': 'text', 'text': 'x'}],
                                                                'usage': {'input_tokens': 10, 'cache_read_input_tokens': ctx, 'cache_creation_input_tokens': 0, 'output_tokens': 5}}}


if section('A10'):     # the rotate line comes at the delivery of the task, not in the middle of it
    room = plain('a10', 'A,B')
    r = chat.Room(room)
    r.update_roster(lambda ro: ro.update(A='eeee5555eeee', B='ffff6666ffff'))
    r.append('LEAD', 'start'); r.append('A', 'on it')
    agent_log('eeee5555eeee', usage(time.time(), 200_000, 'm1'))
    with_board(room, [task('T6', 'A')])
    o = run(room, 'check')[1]
    ok('A10 in the middle of a task: it says to rotate at the delivery of T6, with no command to run now', 'T6' in o and 'delivery' in o and ' rotate A --room' not in o, o)
    with_board(room, [task('T6', 'A', state='done')])
    o = run(room, 'check')[1]
    ok('A10 after the delivery: rotate it now, the command ready with the room and the lead', 'delivered T6' in o and 'rotate A --room' in o and '--as LEAD' in o and room.resolve().as_posix() in o, o)
    with_board(room, [])
    o = run(room, 'check')[1]
    ok('A10 an agent with no task on the board keeps the plain line', 'carries 200k tokens' in o and 'rotate A --room' not in o, o)

if section('T13'):     # the lead's context: the user is told to compact, with the line ready and the state file named
    for name, research in (('t13', False), ('t13r', True)):
        room = plain(name, 'A,B')
        if research:
            (room / 'research').mkdir()
            (room / 'research' / 'contract.json').write_text('{}', encoding='utf-8')
            run(room, 'config', 'mode=research')
        (BASE / 'claude' / 'projects' / 'p').mkdir(parents=True, exist_ok=True)
        (BASE / 'claude' / 'projects' / 'p' / f'sess-{name}.jsonl').write_text(json.dumps(usage(time.time(), 400_000, 'l1')) + '\n', encoding='utf-8')
        (room / 'sessions.json').write_text(json.dumps({f'sess-{name}': 'LEAD'}), encoding='utf-8')
        chat.Room(room).append('LEAD', 'start')
        o = run(room, 'check')[1]
        state = (room.resolve() / 'LEAD.md').as_posix()
        ok(f'T13 {name}: the check tells the lead to ask the user to compact, with the line ready', '/compact keep only what ' in o and 'user' in o, o)
        ok(f'T13 {name}: and names the state file by its whole path', state in o, o)

def age_idles(room, seconds):
    """the idle messages of a room written `seconds` ago (the chat file is one JSON per line)"""
    f = room / 'chat.jsonl'
    rows = [json.loads(x) for x in f.read_text(encoding='utf-8').splitlines()]
    for m in rows:
        if m.get('kind') == 'idle':
            m['ts'] -= seconds
    f.write_text(''.join(json.dumps(m, ensure_ascii=False) + '\n' for m in rows), encoding='utf-8')
    chat._PARSED.clear()


if section('A3'):      # idle agents next to a free task: the harness gives them the task, it does not only say it
    room = plain('a3', 'A,B,C,D')
    r = chat.Room(room)
    run(room, 'task', 'add', 't one', '--as', 'LEAD'); run(room, 'task', 'add', 't two', '--as', 'LEAD'); run(room, 'task', 'add', 't three', '--as', 'LEAD')
    r.append('LEAD', 'go')
    r.append('A', '100%: T0 delivered, nothing left for me', 'idle'); r.append('B', '60%: waiting for @C to finish the parser', 'idle')
    r.append('D', '100%: nothing to do', 'idle')
    ok('A3 a fresh idle is left alone', chat.dissolve_idlefree(r) == [], chat.dissolve_idlefree(r))
    out = chat.dissolve_idlefree(r, now=time.time() + 300)
    b = json.loads((room / 'board.json').read_text(encoding='utf-8'))['tasks']
    ok('A3 the idle that waits for nobody gets a free task each, the one that waits for C does not',
       [(t['id'], t.get('assigned_to')) for t in b] == [('T1', 'A'), ('T2', 'D'), ('T3', None)] and len(out) == 2, (b, out))
    msgs = [m for m in r.messages() if 'assigned to' in m['text']]
    ok('A3 the lead is told and the line tags only its agent', len(msgs) == 2 and msgs[0]['text'].startswith('@A ') and chat.Room(room).wakes(msgs[0], 'A') and not chat.Room(room).wakes(msgs[0], 'D'), msgs)
    ev = [e for e in events(room) if e['key'] == 'idlefree']
    ok('A3 each hand-out is an event with agent and task', [(e['name'], e['task']) for e in ev] == [('A', 'T1'), ('D', 'T2')], ev)
    ok('A3 it does not repeat for the same idle', chat.dissolve_idlefree(r, now=time.time() + 600) == [])
    run(room, 'task', 'decline', 'T1', '--as', 'A', '--note', 'not mine')
    ok('A3 a declined task is not thrown at the same idle again', chat.dissolve_idlefree(r, now=time.time() + 900) == [] and
       json.loads((room / 'board.json').read_text(encoding='utf-8'))['tasks'][0].get('assigned_to') is None)
    c, o = run(room, 'task', 'accept', 'T2', '--as', 'D')
    ok('A3 the agent accepts it as any assignment', c == 0, o)
    room2 = plain('a3b', 'A,B')
    r2 = chat.Room(room2)
    run(room2, 'task', 'add', 't one', '--as', 'LEAD'); run(room2, 'task', 'add', 't two', '--as', 'LEAD'); run(room2, 'task', 'take', 'T1', '--as', 'A')
    r2.append('LEAD', 'go'); r2.append('A', '100%: waiting', 'idle'); r2.append('B', '50%: the run', 'idle', flags={'external': True})
    ok('A3 an agent that holds a task, or waits for an outside run, is left alone', chat.dissolve_idlefree(r2, now=time.time() + 300) == [], chat.dissolve_idlefree(r2, now=time.time() + 300))
    room3 = plain('a3c', 'A,B')
    r3 = chat.Room(room3)
    (room3 / 'research').mkdir(); (room3 / 'research' / 'contract.json').write_text('{}', encoding='utf-8')
    run(room3, 'task', 'add', 't one', '--as', 'LEAD'); r3.append('LEAD', 'go'); r3.append('A', '100%: free', 'idle'); r3.append('B', '100%: free', 'idle')
    ok('A3 a research room is left to its kernel', chat.dissolve_idlefree(r3, now=time.time() + 300) == [])
    room5 = plain('a3e', 'A,B')
    r5 = chat.Room(room5)
    run(room5, 'config', 'idlefree=off'); run(room5, 'task', 'add', 't one', '--as', 'LEAD'); r5.append('LEAD', 'go'); r5.append('A', '100%: free', 'idle')
    ok('A3 config idlefree=off keeps the lead in charge of the tasks', chat.dissolve_idlefree(r5, now=time.time() + 300) == [])
    room4 = plain('a3d', 'A,B')
    r4 = chat.Room(room4)
    run(room4, 'task', 'add', 't one', '--as', 'LEAD'); r4.append('LEAD', 'go'); r4.append('A', '100%: free', 'idle'); r4.append('B', '100%: free', 'idle')
    age_idles(room4, 300)
    c, o = run(room4, 'alerts', '--as', 'LEAD', '--messages')
    b = json.loads((room4 / 'board.json').read_text(encoding='utf-8'))['tasks']
    ok('A3 the relay of the lead does it by itself and tells the lead', b[0].get('assigned_to') in ('A', 'B') and 'gave T1' in o, (b, o))

if section('A6'):      # an existing test changed outside the worktree (no diff sees it) must be named at the delivery
    tests = BASE / 'tests-a6'
    tests.mkdir()
    (tests / 'smoke_one.py').write_text('print(1)' + '\n', encoding='utf-8')
    (tests / 'smoke_two.py').write_text('print(2)' + '\n', encoding='utf-8')
    room = plain('a6', 'A,B')
    run(room, 'brief', f'tests={tests}')
    run(room, 'task', 'add', 't1', '--as', 'A'); run(room, 'task', 'take', 'T1', '--as', 'A')
    c, o = run(room, 'task', 'done', 'T1', '--proof', 'pytest: 3 passed, exit 0', '--as', 'A')
    ok('A6 nothing changed in the tests folder: it closes', c == 0, o)
    run(room, 'task', 'add', 't2', '--as', 'A'); run(room, 'task', 'take', 'T2', '--as', 'A')
    (tests / 'smoke_one.py').write_text('print("changed")' + '\n', encoding='utf-8')
    (tests / 'smoke_new.py').write_text('print(3)' + '\n', encoding='utf-8')
    c, o = run(room, 'task', 'done', 'T2', '--proof', 'pytest: 3 passed, exit 0', '--as', 'A')
    ok('A6 an existing test changed and not named: refused, with its name; a new file is not asked', c != 0 and 'smoke_one.py' in o and 'smoke_new.py' not in o and 'smoke_two.py' not in o, o)
    ok('A6 the refusal is an event with agent, task and file', any(e['key'] == 'tests_changed' and e['task'] == 'T2' and e['name'] == 'A' and 'smoke_one.py' in e.get('detail', '') for e in events(room)), events(room))
    c, o = run(room, 'task', 'done', 'T2', '--proof', 'pytest: 3 passed, exit 0; changed smoke_one.py: its expected text moved with the new locale key', '--as', 'A')
    ok('A6 named with the reason it closes', c == 0 and 'done by A' in o, o)
    ok('A6 the prompt tells the agents', str(tests) in run(room, 'prompt', 'A')[1])
    run(room, 'task', 'add', 't3', '--as', 'LEAD'); run(room, 'task', 'assign', 'T3', 'A', '--as', 'LEAD'); run(room, 'task', 'accept', 'T3', '--as', 'A')
    (tests / 'smoke_two.py').write_text('print("by an assignment")', encoding='utf-8')
    c, o = run(room, 'task', 'done', 'T3', '--proof', 'pytest: 3 passed, exit 0', '--as', 'A')
    ok('A6 a task taken by accepting an assignment is checked too', c != 0 and 'smoke_two.py' in o, o)
    room2 = plain('a6b', 'A,B')
    run(room2, 'task', 'add', 't1', '--as', 'A'); run(room2, 'task', 'take', 'T1', '--as', 'A')
    (tests / 'smoke_two.py').write_text('print("again")' + '\n', encoding='utf-8')
    c, o = run(room2, 'task', 'done', 'T1', '--proof', 'pytest: 3 passed, exit 0', '--as', 'A')
    ok('A6 a room without brief tests= is not checked', c == 0, o)
    ok('A6 and it does not look at the folder it runs in', chat.tests_snapshot(chat.Room(room2)) == {}, chat.tests_snapshot(chat.Room(room2)))
    gone_tests = BASE / 'tests-a6d'
    gone_tests.mkdir()
    (gone_tests / 'smoke_del.py').write_text('print(1)' + '\n', encoding='utf-8')
    room3 = plain('a6d', 'A,B')
    run(room3, 'brief', f'tests={gone_tests}')
    run(room3, 'task', 'add', 't1', '--as', 'A'); run(room3, 'task', 'take', 'T1', '--as', 'A')
    (gone_tests / 'smoke_del.py').unlink()
    c, o = run(room3, 'task', 'done', 'T1', '--proof', 'pytest: 3 passed, exit 0', '--as', 'A')
    ok('A6 a test deleted since the task was taken is refused, with its name', c != 0 and 'smoke_del.py' in o and 'deleted' in o, o)
    c, o = run(room3, 'task', 'done', 'T1', '--proof', 'pytest: 3 passed, exit 0; smoke_del.py: not mine, deleted by the cleanup', '--as', 'A')
    ok('A6 and named with its reason it closes', c == 0 and 'done by A' in o, o)

if section('A4'):      # the score rule: 4 and 5 apply by themselves, 1 to 3 wait for the creator, and local / general go apart (A4, A4-bis)
    home = BASE / 'claude' / 'chatroom'
    room = plain('a4', 'A,B')
    P = lambda *x: run(room, 'lessons', 'propose', *x, '--as', 'LEAD')
    c, o = P('Give the free task to who waits for nobody', '--score', '5', '--reach', 'local', '--scope', 'a room with idle agents and free tasks', '--note', 'idle chains of a night room')
    ok('A4 a 5 is applied by itself as an active lesson', c == 0 and 'applied by itself' in o and 'L1' in o, o)
    c, o = P('Name the changed test in the proof', '--score', '4', '--reach', 'general', '--scope', 'a room with tests kept outside git')
    ok('A4 a 4 too', c == 0 and 'applied by itself' in o and 'L2' in o, o)
    lessons = json.loads((home / 'lessons.json').read_text(encoding='utf-8'))['lessons']
    ok('A4 they are active, scored and carry their reach', [(x['status'], x['score'], x['reach']) for x in lessons] == [('active', 5, 'local'), ('active', 4, 'general')], lessons)
    ok('A4 and they go into the prompt of every agent', 'Give the free task to who waits for nobody' in run(room, 'prompt', 'A')[1])
    c, o = P('A rule about T12 only', '--score', '5', '--reach', 'local', '--scope', 'x')
    ok('A4 the gate still stops a rule that holds in one room only', c != 0 and 'T12' in o, o)
    c, o = P('Reword the closing card', '--score', '3', '--reach', 'local')
    ok('A4 a 3 is not kept for anyone but the creator, and not applied', c == 0 and 'Not kept' in o and not (room / 'proposals.json').read_text(encoding='utf-8').count('Reword'), o)
    c, o = P('A bug of the plugin', '--score', '5', '--reach', 'general', '--kind', 'plugin')
    ok('A4 a bug of the plugin is not kept for them either', c == 0 and 'Not kept' in o and 'Bug of' not in (room / 'proposals.json').read_text(encoding='utf-8'), o)
    c, o = P('No score here', '--reach', 'local')
    ok('A4 a proposal without a score is refused with the usage', c != 0 and '--score' in o, o)
    c, o = P('No reach here', '--score', '4', '--scope', 'x')
    ok('A4 and one without a reach', c != 0 and '--reach' in o, o)
    c, o = run(room, 'lessons', 'close')
    ok('A4 the closing of another user: part a only, local and general apart', 'a. Auto-harness' in o and 'b. ' not in o and 'c. ' not in o and o.index('local') < o.index('Give the free task') < o.index('general') < o.index('Name the changed test'), o)
    ok('A4 a 5 the gate refused is still in the closing, with its reason', 'A rule about T12 only' in o and 'T12' in o[o.index('Not applied'):], o)
    ok('A4 the closing of another user says why scores 1 to 3 are not kept and how to keep them', 'Not kept on this machine' in o and 'CHATROOM_CREATOR=1' in o, o)
    c, o2 = P('A rule with no when', '--score', '5', '--reach', 'general')
    ok('A4 a 5 without its conditions is refused and listed too', c != 0 and 'A rule with no when' in run(room, 'lessons', 'close')[1], o2)
    (home / 'creator').write_text('', encoding='utf-8')
    P('Reword the closing card', '--score', '3', '--reach', 'local', '--note', 'seen in the closing of a room')
    P('Hardware note: the card needs a pause', '--score', '2', '--reach', 'general')
    P('The relay dies when the shell closes', '--score', '4', '--reach', 'general', '--kind', 'plugin')
    c, o = run(room, 'lessons', 'close')
    a, b, cc = o.index('a. Auto-harness'), o.index('b. '), o.index('c. ')
    ok('A4 the creator gets the three parts, in order', a < b < cc, o)
    ok('A4 and the creator is not told that scores are not kept', 'Not kept on this machine' not in o and 'A rule about T12 only' in o[:b], o)
    ok('A4 b holds the 1 to 3 of the session, local and general apart', 'Reword the closing card' in o[b:cc] and 'Hardware note' in o[b:cc] and o[b:cc].index('Reword') < o[b:cc].index('general') < o[b:cc].index('Hardware'), o)
    ok('A4 c holds the plugin bug, apart from the session', 'relay dies' in o[cc:] and 'relay dies' not in o[:cc], o)
    c, o = run(room, 'lessons')
    ok('A4 lessons lists the kept ones in two lists, local then general', o.index('local') < o.index('L1') < o.index('general (') < o.index('L2'), o)
    procs = [subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'lessons', 'propose', f'Seen together number {i}', '--score', '2', '--reach', 'local', '--as', 'LEAD', '--room', str(room)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(6)]
    [x.wait() for x in procs]
    ids = [x['id'] for x in json.loads((room / 'proposals.json').read_text(encoding='utf-8'))]
    ok('A4 six proposals made together get six ids', len(ids) == 13 and len(set(ids)) == 13, ids)
    run(room, 'lessons', 'add', 'Old style rule without a reach', '--scope', 'when old', '--as', 'LEAD')
    (home / 'creator').unlink()
    ok('A4 a lesson added without --reach is local', json.loads((home / 'lessons.json').read_text(encoding='utf-8'))['lessons'][-1]['reach'] == 'local')
    rroom = plain('a4r', 'A,B')                    # the same rule in a research room: a 5 is applied and the agents of the research carry it
    (rroom / 'research').mkdir(); (rroom / 'research' / 'contract.json').write_text(json.dumps({'work': 'w', 'program': 'program.py', 'evaluate': 'ev.sh', 'metric': 'score', 'direction': 'min', 'budget_s': 60, 'max_evals': 5, 'sealed': []}), encoding='utf-8')
    c, o = run(rroom, 'lessons', 'propose', 'Stop a run that repeats the last one', '--score', '5', '--reach', 'general', '--scope', 'a research room', '--as', 'LEAD')
    ok('A4 a 5 proposed in a research room is applied', c == 0 and 'applied by itself' in o, o)
    c, o = run(rroom, 'prompt', 'A')
    ok('A4 and the agents of a research room carry it', c == 0 and 'Stop a run that repeats the last one' in o, o[-300:])

if section('A4L'):     # T19d: lessons.json is the user's, shared by every room and process: lessons added together are all kept
    home = BASE / 'claude' / 'chatroom'
    (home / 'lessons.json').unlink(missing_ok=True)       # the cap of 8 live lessons: those the A4 sections left would refuse the fifth add, and the one that waits for the lock
    room = plain('a4l', 'A,B')
    procs = [subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'lessons', 'add', f'Together rule number {"abcde"[i]}', '--scope', 'a test room', '--room', str(room)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for i in range(5)]
    why = [(x.communicate()[1].decode('utf-8', errors='replace')[-200:], x.returncode) for x in procs]      # a lost add says why
    got = [x for x in json.loads((home / 'lessons.json').read_text(encoding='utf-8'))['lessons'] if x['text'].startswith('Together rule')]
    ok('A4L five lessons added together are all kept, with their own ids', len(got) == 5 and len({x['id'] for x in got}) == 5, ([x['id'] for x in got], why))
    ok('A4L and no lock or temporary file is left behind', not (home / 'lessons.lock').exists() and not list(home.glob('lessons.json.*tmp')), list(home.iterdir()))
    (home / 'lessons.lock').write_text('', encoding='utf-8')               # a holder that is alive: the add waits for it
    waiting = subprocess.Popen([sys.executable, '-X', 'utf8', CHAT, 'lessons', 'add', 'Waits for the lock', '--scope', 'a test room', '--room', str(room)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    held = waiting.poll() is None and 'Waits for the lock' not in (home / 'lessons.json').read_text(encoding='utf-8')
    (home / 'lessons.lock').unlink()
    waiting.wait(timeout=30)
    ok('A4L an add waits while another process holds lessons.json, then goes in', held and 'Waits for the lock' in (home / 'lessons.json').read_text(encoding='utf-8'), held)
    gone = subprocess.Popen([sys.executable, '-c', 'pass']); gone.wait()      # a holder that died: its pid is free, its lock goes at once
    (home / 'lessons.lock').write_text(str(gone.pid), encoding='utf-8')
    import lessons
    t0 = time.time()
    with lessons.lessons_lock():                      # in this process: a command line also counts its python start, 11 to 17 s with every core busy
        pass
    took = time.time() - t0
    ok('A4L the lock of a dead pid is taken over without waiting 20 s', took < 5 and not (home / 'lessons.lock').exists(), round(took, 1))
    (home / 'lessons.lock').write_text(str(gone.pid), encoding='utf-8')
    c, o = run(room, 'lessons', 'retire', 'L2')
    ok('A4L and the command goes through it', c == 0 and 'retired' in o and not (home / 'lessons.lock').exists(), (c, o))
    (home / 'lessons.lock').write_text('', encoding='utf-8')
    os.utime(home / 'lessons.lock', (time.time() - 60, time.time() - 60))
    c, o = run(room, 'lessons', 'retire', 'L1')
    ok('A4L the lock of a holder that died is taken over', c == 0 and 'retired' in o and not (home / 'lessons.lock').exists(), o)
    real, calls = os.replace, []
    def flaky(a, b):                                  # Windows refuses the swap while a reader has the file open: a lesson must not be lost to it
        calls.append(1)
        if len(calls) < 4:
            raise PermissionError(5, 'Access is denied')
        return real(a, b)
    data, err = lessons.load(), None
    data['lessons'].append({'id': 'L99', 'text': 'Saved after a refused swap', 'status': 'retired'})
    os.replace = flaky
    try:
        lessons.save(data)
    except PermissionError as e:
        err = e
    finally:
        os.replace = real
    ok('A4L a swap refused for a moment is tried again, the lesson is kept', err is None and len(calls) == 4 and 'Saved after a refused swap' in (home / 'lessons.json').read_text(encoding='utf-8')
       and not list(home.glob('lessons.json.*tmp')), (err, len(calls)))

if section('R1'):      # rotation: the ask tells the old agent to stop, --now says when the state is older than the ask, the refusal tells the new agent its name
    room = plain('r1', 'A,B')
    notes = room / 'notes'
    c, o = run(room, 'rotate', 'A', '--as', 'LEAD')
    ask = [m['text'] for m in chat.Room(room).messages() if 'ROTATE' in m['text']]
    ok('R1 the ask tells the agent to stop after its state line, and why', c == 0 and ask and 'STOP' in ask[0] and 'no report' in ask[0] and 'refused and lost' in ask[0], (c, ask))
    run(room, 'notebook', '--state', 'old state | next: x', '--as', 'A')
    past = time.time() - 120                       # a state older than the ask: the agent did not write after it
    os.utime(notes / 'A.state.md', (past, past))
    c, o = run(room, 'rotate', 'A', '--now', '--as', 'LEAD')
    ok('R1 rotate --now says the state is older than the ask, and goes on', c == 0 and 'has not written its state since you asked' in o and (room / 'prompts' / 'A-rotated.md').is_file(), o)
    run(room, 'rotate', 'B', '--as', 'LEAD')
    run(room, 'notebook', '--state', 'fresh state | next: y', '--as', 'B')       # written after the ask
    c, o = run(room, 'rotate', 'B', '--now', '--as', 'LEAD')
    ok('R1 a state written after the ask: no note', c == 0 and 'has not written' not in o and 'left no state' not in o, o)
    c, o = run(room, 'notebook', '--state', 'late state', '--as', 'A')
    ok('R1 the retired name is refused, and the refusal tells the new agent its name', c != 0 and '--as A~1' in o and 'your prompt says you are A~1' in o, o)
    c, o = run(room, 'notebook', '--state', 'new state | next: z', '--as', 'A~1')
    ok('R1 and under that name it writes', c == 0, o)

print(f'\n{fails} FAIL' if fails else '\nALL PASS')
sys.exit(1 if fails else 0)
