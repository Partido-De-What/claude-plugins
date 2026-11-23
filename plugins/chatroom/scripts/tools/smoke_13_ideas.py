"""1.3: seven ideas from DeepSeek Harness and Qwen Code. Synthetic rooms only. Run: python -X utf8 smoke_13_ideas.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
BASE = Path(tempfile.mkdtemp(prefix='smoke13_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
CHAT = str(SCRIPTS / 'chat.py')
sys.path.insert(0, str(SCRIPTS))
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


def run(room, *args, stdin=''):
    r = subprocess.run([sys.executable, CHAT, *args, '--room', str(room)], input=stdin.encode('utf-8'), capture_output=True, timeout=300,
                       env=dict(os.environ), cwd=str(BASE))
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', errors='replace')


def new_room(name, parts='A,B'):
    room = BASE / name
    run(room, 'init', '--participants', parts, '--lang', 'en')
    run(room, 'post', '--as', 'LEAD', stdin='hello, I lead')
    return room


import chat  # noqa: E402
import fit  # noqa: E402
import hold  # noqa: E402

# 1: the gate
ok('1 no gate: the timed wake goes as before', chat.gate_says(None) is None)
ok('1 a gate that prints nothing: no wake', chat.gate_says(f'"{sys.executable}" -c "pass"') == '')
ok('1 a gate that prints: the wake carries its words', chat.gate_says(f'"{sys.executable}" -c "print(\'render done\')"') == 'render done')

# 2: the END line of a final report, in the closing
room = new_room('report')
r = chat.Room(room)
hold.keep_report(r, 'A', {'result': 'END: partial; files: out/a.mp4, out/b.mp4; gaps: the audio mix\nthe rest of the report'})
got = chat.final_reports(r)
ok('2 the END line is kept: stop reason, files, gaps', got.get('A') == {**got.get('A', {}), 'end': 'partial', 'files': 'out/a.mp4, out/b.mp4', 'gaps': 'the audio mix'}, got)
hold.keep_report(r, 'B', {'result': 'no end line here'})
ok('2 a report without END is not invented', 'B' not in chat.final_reports(r))
c, o = run(room, 'close-steps', '--as', 'LEAD')
ok('2 close-steps lists the final reports', 'FINAL REPORTS' in o and 'A: partial' in o, o[-500:])

# 3: a run of reads
room = new_room('reads')
r = chat.Room(room)
r.update_roster(lambda ro: ro.update(A='abcdef1234567890'))
known = BASE / 'claude' / 'chatroom' / 'known_rooms.json'
known.write_text(json.dumps({str(room): {'ts': time.time(), 'ids': ['abcdef1234567890']}}), encoding='utf-8')
small = BASE / 'small.txt'
small.write_text('x\n', encoding='utf-8')
ev = {'tool_name': 'Read', 'agent_id': 'abcdef1234567890', 'tool_input': {'file_path': str(small)}}
outs = [fit.answer(ev) for _ in range(fit.READ_STREAK)]
ok('3 the 15th read in a row tells the agent to conclude', outs[-1] and 'reads in a row' in json.dumps(outs[-1]) and not any(outs[:-1]), outs[-2:])
fit.answer({'tool_name': 'Edit', 'agent_id': 'abcdef1234567890', 'tool_input': {'file_path': str(small)}})
ok('3 an Edit ends the run', not (room / 'reads_abcdef1234567890.txt').exists())
fit.answer(ev)
run(room, 'post', '--as', 'A', stdin='found it: the bug is in parse()')
ok('3 a message ends the run too', not (room / 'reads_abcdef1234567890.txt').exists())

# 4: an agent that leaves releases what it held
room = new_room('release')
r = chat.Room(room)
run(room, 'lock', 'acquire', 'bench', '--as', 'A')
ok('4 A holds the bench', r.dir.joinpath('locks.json').exists() and chat.Locks(r).involves('A'))
hold.left(r, 'A', 'lock')
ok('4 when A leaves, its lock is released and the room is told', not chat.Locks(r).involves('A') and 'released bench' in (room / 'chat.jsonl').read_text(encoding='utf-8'), chat.Locks(r).load())

# 5: the same refusal three times in a row
room = new_room('loop')
run(room, 'read', '--as', 'A')
for _ in range(3):
    run(room, 'task', 'done', 'T9', '--proof', 'x', '--as', 'A')
c, o = run(room, 'check', '--as', 'LEAD')
ok('5 three refusals in a row: a CHECK for the lead', 'same refusal' in o and 'A' in o, o[-500:])

# 6: rotate carries the last messages
room = new_room('rotate', 'ALFA,BETA')
run(room, 'post', '--as', 'ALFA', stdin='working on the parser')
run(room, 'post', '--as', 'BETA', stdin='@ALFA use the new grammar in g.txt')
run(room, 'rotate', 'ALFA', '--now', '--as', 'LEAD')
p = (room / 'prompts' / 'ALFA-rotated.md').read_text(encoding='utf-8')
ok('6 the fresh prompt carries the last messages that concern it', 'THE LAST MESSAGES THAT CONCERN YOU' in p and 'use the new grammar in g.txt' in p, p[-600:])

# 7: a refused post keeps what was tried
room = new_room('attempt')
run(room, 'post', '--as', 'A', stdin='first')
run(room, 'read', '--as', 'A')
run(room, 'post', '--as', 'B', stdin='@A look at this')
run(room, 'post', '--as', 'A', stdin='my text that crossed')
evs = [json.loads(x) for x in (room / 'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
ok('7 the refusal event carries the attempted text', any(e.get('kind') == 'refusal' and 'my text that crossed' in e.get('attempt', '') for e in evs), evs[-3:])

print(f'fails {fails}')
sys.exit(1 if fails else 0)
