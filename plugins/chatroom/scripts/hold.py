"""SubagentStop hook of the chatroom: a room agent that ends its turn is held, at no token cost, until a message for it
arrives (a tag, a tag to everyone, the user, the lead, a plan, a vote, a closing, a kernel line naming it), and then goes
on with that message as its next instruction (Claude Code's `decision: block` with a reason). It replaces the idle wait
loop and the lead's SendMessage to a stopped agent. The hold lasts HOLD_WAIT, under the harness's stall watchdog (a hold
of 50 minutes killed the agents on 30/10, limits.py): then one short turn goes through ("nothing for you") and the next
stop holds again; with chatroom:room-agent's one-hour cache that turn reads its cache. The reason carries what the agent
would read (read --focus), so a wake costs no extra read. The room is found by the agent's id in the rosters of the
rooms known to chat.py, with or without a viewer. The agent goes for good when the room is closed, has been silent for
ROOM_IDLE, or the lead retired it. Any fault lets the agent stop, as without this hook."""
import contextlib
import io
import json
import re
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layers
from limits import HOLD_WAIT

POLL = 2
ROOM_IDLE = 6 * 3600           # a room whose chat has not moved for six hours holds nobody
REASON_MAX = 6000              # characters of messages in a reason; past it the agent reads the rest
REPORT_MIN = 200               # last words shorter than this are not a report ("waiting for CLOSED")
HANDBACK_MAX = 2               # reports put off at most this often: the third goes through (a room never closed kept them forever)
EMPTY_MAX = 3                  # turns in a row with nothing new: then it reports and goes (an idle woken every 9 minutes for hours)
TASK_EMPTY_MAX = 12            # the same for an agent that holds a task: its job may take hours, not for ever (12 turns of 9 minutes, 1 h 50 min)
FELL_MAX = 3                   # times in a row the hold resumes an agent whose last turn ended on an API error (a network that stays down)
PROCS_TAIL = 2_000_000         # bytes of a transcript read for the processes an agent leaves running


def candidates():
    """room folders worth looking in: the served ones and the ones chat.py met lately"""
    base = layers.chatroom_dir()
    out = []
    for f in ('rooms.json', 'known_rooms.json'):
        try:
            out += list(json.loads((base / f).read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError):
            pass
    return list(dict.fromkeys(out))


def find(aid):
    """(room folder, name) of a live room whose roster has this agent id, or (None, None)"""
    for key in candidates():
        d = Path(key)
        try:
            if aid not in (d / 'roster.json').read_text(encoding='utf-8') or time.time() - (d / 'chat.jsonl').stat().st_mtime > ROOM_IDLE:
                continue                                  # cheap first: most rooms do not have this agent
        except OSError:
            continue
        import chat
        name = next((n for n, v in chat.Room(d).roster().items() if v == aid), None)
        if name:
            return str(d), name
    return None, None


def closed(room):
    """a CLOSED was posted (chat.py lets a participant's through only with every vote in) and the lead did not reopen"""
    import chat
    return chat.is_shut(room, room.messages()[-50:])


def done_closing(room, name):
    """the lead called the closing and this agent has answered it: it stays for nobody, its idle or its task included"""
    import chat
    items = room.messages()
    n = chat.winding(room, items)
    return bool(n) and any(m['from'] == name and m['n'] > n and not m.get('kind') for m in items)


def device_hold(room, name):
    """minutes left of the research hold this agent has on the shared device (research hold), 0 when it has none. A worker
    that waits for its own measurement on the device has work going: it is neither asked for its report nor counted as gone
    (a worker released a 100-minute hold with three tests left, because its turn ended while the first one ran)"""
    try:
        h = json.loads((room.dir / 'research' / 'gpu.hold').read_text(encoding='utf-8'))
        left_s = float(h.get('until', 0)) - time.time()
    except (OSError, ValueError, TypeError):
        return 0
    return max(1, int(left_s // 60)) if h.get('by') == name and left_s > 0 else 0


def waits(room, name):
    """why this agent has to stay: it declared an idle (it waits for someone), holds a task, or has a run queued or going.
    '' when it has none: its work is finished, it reports and goes, and nothing keeps it. A shared lock it holds or queues
    for counts too: its turn comes with a tag, and it needs no turn before that"""
    import chat
    if chat.is_paused(room):                              # the user stopped the room: nobody goes, nobody reports, until resume
        return 'pause'
    if device_hold(room, name):
        return 'hold'
    if room.idle_entry(name, room.messages()):
        return 'idle'
    if chat.waits_for_lead(room, only=name):          # B4: "I wait for your ok" without --idle: it stays until the lead answers
        return 'lead'
    if any(t.get('owner') == name and t['state'] == 'taken' for t in chat.Board(room).load()['tasks']):
        return 'task'
    if chat.Locks(room).involves(name):
        return 'lock'
    d = room.dir / 'research'
    try:
        if any(x.get('by') == name for x in json.loads((d / 'queue.json').read_text(encoding='utf-8'))):
            return 'run'
    except (OSError, ValueError):
        pass
    try:
        if (json.loads((d / 'state.json').read_text(encoding='utf-8')).get('pending') or {}).get('by') == name:
            return 'run'
    except (OSError, ValueError):
        pass
    return ''


END_RE = re.compile(r'(?im)^\W*END\s*:\s*(completed|partial|blocked|error)\b(.*)$')


def keep_report(room, name, inp):
    """the END line of a final report (END: completed|partial|blocked|error; files: a, b; gaps: ...) as ROOM/reports/NAME.json"""
    import chat
    text = '\n'.join(str(v) for v in (inp.values() if isinstance(inp, dict) else [inp]) if isinstance(v, str))
    m = END_RE.search(text)
    if not m:
        return False
    rest = m.group(2)
    part = lambda k: (re.search(rf'{k}\s*:\s*([^;\n]*)', rest, re.I) or [None, ''])[1].strip()[:300]
    try:
        (room.dir / 'reports').mkdir(exist_ok=True)
        chat.write_atomic(room.dir / 'reports' / f'{name}.json', json.dumps({'end': m.group(1).lower(), 'files': part('files'), 'gaps': part('gaps'),
                                                                           'at': time.time()}, ensure_ascii=False))
    except OSError:
        pass
    return True


def handback(ev):
    """PreToolUse of SubagentHandback, the tool that ends an agent's run (auto mode): an agent that still waits in an open
    room reports later, so that a run in queue or a tag can still reach it; one with nothing left passes. The report is
    only put off: it still goes through SubagentHandback, and its review, when the agent has finished"""
    key, name = find(str(ev.get('agent_id') or ''))
    if not key:
        return None
    import chat
    room = chat.Room(key)
    if not keep_report(room, name, ev.get('tool_input') or {}) and bump(room, f'endask_{name}') == 1:   # idea 5 (Hermes): one correction turn
        chat.use(room.config().get('lang'))
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                       'permissionDecisionReason': chat.say('chat.say.hold.add_end')}}
    why = waits(room, name)
    if closed(room) or done_closing(room, name) or chat.voted_latest(room, name) or gone_now(room, name):   # D3: the hold let it go: its report goes through
        return None
    if not why:
        left(room, name)
        return None
    if bump(room, f'handback_{name}') > HANDBACK_MAX:
        return None
    chat.use(room.config().get('lang'))
    chat.note_event(room, 'hold', 'report_put_off', name, detail=why)
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': chat.say('chat.say.hold.report_later', why={
                                       'idle': chat.say('chat.say.hold.why_idle'), 'task': chat.say('chat.say.hold.why_task'),
                                       'run': chat.say('chat.say.hold.why_run'), 'hold': chat.say('chat.say.hold.why_hold'), 'pause': chat.say('chat.say.hold.why_pause'),
                                       'lock': chat.say('chat.say.hold.why_lock'), 'lead': chat.say('chat.say.hold.why_lead')}[why])}}


def running_procs(room, name):
    """the background processes of this agent's transcript that still run (a viewer, an http.server left up for hours):
    their commands, for the lead's CHECK. The tail of the transcript only: [] when it is not here or not readable"""
    import chat
    import activity
    path = chat.agent_file(room.roster().get(name))
    if not path:
        return []
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, f.seek(0, 2) - PROCS_TAIL))
            lines = f.read().decode('utf-8', errors='replace').splitlines()[1:]
        act, agent = activity.Activity(room), activity.Agent(name, room.roster().get(name))
        for line in lines:
            try:
                act.record(agent, json.loads(line))
            except (ValueError, AttributeError, TypeError):
                pass
    except OSError:
        return []
    return [q['cmd'][:120] for q in agent.procs.values() if q['state'] == 'running'][:6]


def left(room, name, why=''):
    """it goes while the room is open. gone.json keeps what it still held when it went: `why` (idle, task, lock or run: what
    waits() said; '' when nothing), its taken tasks and the background processes it left running. 0.19.0 kept only the message
    number, and the CHECK said "no idle and nothing taken" of an agent that went holding T6. Only the lead can tell a finished
    job from one left half way: the relay tells it (CHECK), unless the agent comes back and writes"""
    import chat
    try:
        if gone_now(room, name):                         # D4: the same exit, seen again (the report turn after it): one entry, one event
            return
        got = chat.read_json(room.dir / 'gone.json', {})
        got[name] = {'n': last_n(room, name), 'why': why, 'aid': room.roster().get(name),
                     'tasks': [t['id'] for t in chat.Board(room).load()['tasks'] if t.get('owner') == name and t['state'] == 'taken'],
                     'procs': running_procs(room, name)}
        chat.write_atomic(room.dir / 'gone.json', json.dumps(got))
        chat.write_atomic(room.dir / f'letgo_{name}.json', json.dumps({'n': got[name]['n'], 'aid': got[name]['aid']}))   # gone.json goes at its next command: this stays for its report turn
        chat.release_all(room, name)                     # idea 4: what it held goes back to the others
        if got[name]['tasks'] or got[name]['procs'] or why not in ('', 'idle'):   # B3: nothing in hand, or only waiting: its job is done, no event, no lesson
            chat.note_event(room, 'hold', 'left', name, ','.join(got[name]['tasks']), why or 'nothing in hand')
        elif why == 'idle':                              # D4: an idle agent nobody needed goes: a fact of the room, not a fault
            chat.note_event(room, 'flow', 'left_idle', name)
    except (OSError, ValueError, KeyError):
        pass


def last_n(room, name):
    return max((m['n'] for m in room.messages() if m['from'] == name), default=0)


def gone_now(room, name):
    """the hold already let this agent go and it has written nothing since (same agent id): its report turn, not a new stretch"""
    import chat
    e = chat.read_json(room.dir / f'letgo_{name}.json', None)
    return isinstance(e, dict) and e.get('n') == last_n(room, name) and e.get('aid') == room.roster().get(name)


def demo_kept(room):
    """D1: config demo=on and someone looks at this room's viewer: an idle agent stays at its desk, however long nothing comes"""
    if room.config().get('demo') != 'on':
        return False
    try:
        import procs
        here = room.dir.resolve()
        return any(e.get('kind') == 'serve' and e.get('room') and Path(e['room']).resolve() == here and e.get('clients')
                   for e in procs.running())
    except Exception:
        return False


def bump(room, key, reset=False):
    """a counter of this agent in the room folder: +1 (or back to 0) and its value"""
    p = room.dir / f'{key}.txt'
    try:
        n = 0 if reset else int(p.read_text() or 0) + 1
    except (OSError, ValueError):
        n = 0 if reset else 1
    try:
        p.write_text(str(n))
    except OSError:
        pass
    return n


def draft_note(room, name):
    """a message of the agent stopped as crossed and never posted again: said once, with its text"""
    import chat
    d = room.dir / 'drafts' / f'{name}.txt'
    if not d.is_file():
        return None
    text = d.read_text(encoding='utf-8', errors='replace')
    d.replace(d.with_suffix('.seen'))
    chat.use(room.config().get('lang'))
    return {'decision': 'block', 'reason': chat.say('chat.say.hold.draft', name=name, text=text[:1500])}


def last_words(room, name):
    """the text of the agent's last turn, '' if that turn handed its report over (the tool), None with no transcript here"""
    import chat
    path = chat.agent_file(room.roster().get(name))
    if not path:
        return None
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, f.seek(0, 2) - 262144))
            lines = f.read().decode('utf-8', errors='replace').splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            msg = json.loads(line).get('message') or {}
        except ValueError:
            continue
        if msg.get('role') == 'assistant' and isinstance(msg.get('content'), list):
            if any(c.get('name') == 'SubagentHandback' for c in msg['content'] if isinstance(c, dict)):
                return None
            return ' '.join(c.get('text', '') for c in msg['content'] if isinstance(c, dict) and c.get('type') == 'text')
    return None


def report(room, name):
    """the agent goes. A run that ends on "waiting for CLOSED" leaves its lead with no report (two agents of three, 1/11):
    asked once, in any permission mode, and only when its last words are not one. None lets it stop"""
    import chat
    mark = room.dir / f'report_asked_{name}.txt'
    words = last_words(room, name)
    n = max((m['n'] for m in room.messages() if m['from'] == name), default=0)
    try:
        asked = mark.read_text().strip() == str(n)      # asked once for each stretch of silence: 0.19.0 asked once for the room, and the 2nd and 3rd exit of an agent went without a report
    except OSError:
        asked = False
    if words is None or len(words) >= REPORT_MIN or asked:
        return None
    try:
        mark.write_text(str(n))
    except OSError:
        return None
    chat.use(room.config().get('lang'))
    chat.note_event(room, 'hold', 'report_asked', name)
    return {'decision': 'block', 'reason': chat.say('chat.say.hold.report_now', name=name)}


def news(room, name):
    """the messages that would wake this agent, not yet read by it"""
    users = room.user_names()
    return [m for m in room.messages() if m['n'] > room.cursor(name) and m['from'] != name and room.wakes(m, name, users)]


def reason(room, name, new):
    """what the agent would read now (read --focus: whole what concerns it, the rest as a digest), its cursor moved on"""
    import chat
    chat.use(room.config().get('lang'))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        room.read(name, True)
    text = out.getvalue().strip()
    if len(text) > REASON_MAX:
        text = text[:REASON_MAX] + '\n' + chat.say('chat.say.hold.more', n=new[-1]['n'])
    return chat.say('chat.say.hold.new_for_you', name=name, n=len(new), lines=text)


def decide(ev, wait=HOLD_WAIT, poll=POLL):
    """the hook's answer: {'decision': 'block', 'reason': ...}, or None to let the agent stop"""
    aid = str(ev.get('agent_id') or '')
    if not aid:
        return None
    key, name = find(aid)
    if not key:
        return None
    import chat
    room = chat.Room(key)
    end = time.time() + wait
    mark = room.dir / f'waiting_{name}.txt'           # held like a wait: no ping for it while this process lives (print_alert)
    try:
        mark.write_text(f'{end + 5:.0f} {os.getpid()}')
    except OSError:
        pass
    try:
        return _hold(room, aid, key, name, end, wait, poll)
    finally:
        mark.unlink(missing_ok=True)


def _hold(room, aid, key, name, end, wait, poll):
    import chat
    first = True
    while True:
        if find(aid) != (key, name):                      # gone quiet for hours, or retired meanwhile
            return None
        if closed(room):
            return report(room, name)
        chat.Locks(room).tick()
        new = news(room, name)
        note = None if new else draft_note(room, name)
        if note:
            return note
        if first and not new:                                  # the stop itself: did its last turn end on an API error (a network down)? nothing else resumes it
            err, first = chat.fell(room, name), False
            if err and bump(room, f'fell_{name}') <= FELL_MAX:
                chat.use(room.config().get('lang'))
                return {'decision': 'block', 'reason': chat.say('chat.say.hold.fell', err=err[0], minutes=max(0, int((time.time() - err[1]) // 60)))}
            if not err:
                bump(room, f'fell_{name}', reset=True)
        if not new and gone_now(room, name):              # D3, D4: it was let go and turned for its report: no second hold of 9 minutes
            return report(room, name)
        why = waits(room, name)
        if not new and (not why or done_closing(room, name)):   # nothing it waits for: its work is done, it goes
            left(room, name, why)
            return report(room, name)
        if new:
            bump(room, f'empty_{name}', reset=True)
            try:
                import inbox
                inbox.mark_delivered(room.dir, name, new[-1]['n'])
            except Exception:
                pass
            return {'decision': 'block', 'reason': reason(room, name, new)}
        if time.time() >= end:
            cap = None if why in ('run', 'hold', 'pause') else (chat.settings()['task_empty_max'] or TASK_EMPTY_MAX) if why in ('task', 'lead') else EMPTY_MAX   # a queued run of the kernel wakes it; a task holder stays longer (B1: it left with T6 "in corso"), and when it goes gone.json names its tasks and the relay tells the lead; the rest goes
            if why in ('idle', 'lead') and demo_kept(room):
                cap = None
            if cap and bump(room, f'empty_{name}') > cap:
                left(room, name, why)
                return report(room, name)
            chat.use(room.config().get('lang'))
            if why == 'pause':
                return {'decision': 'block', 'reason': chat.say('chat.say.hold.nothing_pause', name=name)}
            if why == 'hold':                             # its measurement runs on the device: it checks it, it does not end here
                return {'decision': 'block', 'reason': chat.say('chat.say.hold.nothing_hold', name=name, left=device_hold(room, name))}
            return {'decision': 'block', 'reason': chat.say('chat.say.hold.nothing', name=name, minutes=max(1, wait // 60))}
        time.sleep(poll)


def main():
    try:
        ev = json.load(sys.stdin)
        got = handback(ev) if ev.get('tool_name') == 'SubagentHandback' else decide(ev)
    except Exception:                                 # a fault here never keeps an agent
        return 0
    if got:
        sys.stdout.reconfigure(encoding='utf-8')
        print(json.dumps(got, ensure_ascii=False))
    return 0


def _prova():
    import tempfile
    import threading
    import chat
    base = Path(tempfile.mkdtemp(prefix='hold_'))
    os.environ['CLAUDE_CONFIG_DIR'] = str(base / 'c')
    (base / 'c' / 'chatroom').mkdir(parents=True)
    room = base / 'room'
    room.mkdir()
    (room / 'config.json').write_text(json.dumps({'user_name': 'USER', 'self_names': ['LEAD'], 'participants': ['A', 'B'], 'lang': 'en'}))
    r = chat.Room(room)
    r.update_roster(lambda ro: ro.update(A='aaaa1111', B='bbbb2222'))       # chat.py records the room: no viewer needed
    r.append('LEAD', 'start')
    r.set_cursor('A', 1)
    assert decide({'agent_id': 'zzzz'}) is None                                   # not a room agent: it stops
    assert decide({'agent_id': 'aaaa1111'}, wait=5, poll=0.2) is None             # no reason to stay: its work is done, it goes
    assert handback({'agent_id': 'aaaa1111', 'tool_input': {'result': 'END: completed; files: -; gaps: -'}}) is None                             # and its report passes
    r.append('A', '40%: waiting for @B', 'idle')
    r.set_cursor('A', 2)
    assert handback({'agent_id': 'aaaa1111', 'tool_input': {'result': 'END: completed; files: -; gaps: -'}})['hookSpecificOutput']['permissionDecision'] == 'deny'   # it waits: the report comes later
    threading.Timer(1.0, lambda: r.append('B', '@A your turn')).start()
    t0 = time.time()
    got = decide({'agent_id': 'aaaa1111'}, wait=20, poll=0.2)
    assert got and got['decision'] == 'block' and '@A your turn' in got['reason'] and time.time() - t0 < 10, got
    assert int((room / 'delivered_A.txt').read_text()) >= 1 and r.cursor('A') >= 2   # read for it: no extra read
    got = decide({'agent_id': 'aaaa1111'}, wait=1, poll=0.2)
    assert got and 'nothing' in got['reason'].lower(), got                        # nothing in the window: one quiet turn
    for _ in range(EMPTY_MAX - 1):
        assert decide({'agent_id': 'aaaa1111'}, wait=1, poll=0.2)
    assert decide({'agent_id': 'aaaa1111'}, wait=1, poll=0.2) is None             # then it goes: no endless empty turns
    (room / 'empty_A.txt').write_text('0')
    (room / 'handback_A.txt').write_text('0')
    t0 = time.time()
    assert decide({'agent_id': 'aaaa1111'}, wait=5, poll=0.2) is None and time.time() - t0 < 3   # D3: let go already: no second hold
    assert handback({'agent_id': 'aaaa1111', 'tool_input': {'result': 'END: completed; files: -; gaps: -'}}) is None                                   # D3: and its report passes, not put off again
    left_rows = [x for x in (room / 'events.jsonl').read_text(encoding='utf-8').splitlines() if '"left' in x]
    assert len(left_rows) == 1 and '"flow"' in left_rows[0], left_rows   # D4: one exit, one event, not a fault
    (room / 'letgo_A.json').unlink()
    assert all(handback({'agent_id': 'aaaa1111', 'tool_input': {'result': 'END: completed; files: -; gaps: -'}}) for _ in range(HANDBACK_MAX))
    assert handback({'agent_id': 'aaaa1111', 'tool_input': {'result': 'END: completed; files: -; gaps: -'}}) is None                             # the third report goes through
    (room / 'research').mkdir()
    (room / 'research' / 'gpu.hold').write_text(json.dumps({'by': 'A', 'reason': 'bench', 'until': time.time() + 600}))
    (room / 'empty_A.txt').write_text('0')
    (room / 'gone.json').unlink(missing_ok=True)
    (room / 'letgo_A.json').unlink(missing_ok=True)
    assert waits(r, 'A') == 'hold'
    for _ in range(EMPTY_MAX + 2):                                                # it holds the device: never asked to report, never gone
        got = decide({'agent_id': 'aaaa1111'}, wait=1, poll=0.2)
        assert got and got['decision'] == 'block' and 'do not release the hold' in got['reason'], got
    assert 'A' not in chat.read_json(room / 'gone.json', {})
    (room / 'research' / 'gpu.hold').write_text(json.dumps({'by': 'A', 'reason': 'bench', 'until': time.time() - 5}))
    assert waits(r, 'A') == 'idle'                                                # the hold ran out: back to the usual rules
    (room / 'research' / 'gpu.hold').unlink()
    (room / 'paused.json').write_text(json.dumps({'ts': time.time(), 'by': 'LEAD', 'why': 'night'}))
    (room / 'empty_A.txt').write_text('0')
    (room / 'gone.json').unlink(missing_ok=True)
    assert chat.is_paused(r) and waits(r, 'A') == 'pause'
    for _ in range(EMPTY_MAX + 2):                                                # a paused room keeps its agents: no report, no fall
        got = decide({'agent_id': 'aaaa1111'}, wait=1, poll=0.2)
        assert got and got['decision'] == 'block' and 'paused' in got['reason'].lower(), got
    assert 'A' not in chat.read_json(room / 'gone.json', {})
    (room / 'paused.json').unlink()
    assert waits(r, 'A') == 'idle'
    (room / 'waiting_A.txt').write_text(f'{time.time() + 500:.0f} 999999')
    assert not r.in_wait('A')                                                     # a dead holder's mark does not count
    r.append('LEAD', 'CLOSED v1: done')
    assert decide({'agent_id': 'aaaa1111'}, wait=5, poll=0.2) is None             # closed: it stops for good
    ag = base / 'c' / 'projects' / 'p' / 's' / 'subagents'
    ag.mkdir(parents=True)
    (ag / 'agent-aaaa1111.jsonl').write_text(json.dumps({'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'waiting for CLOSED'}]}}) + '\n')
    chat._AGENT_FILES.clear()
    got = decide({'agent_id': 'aaaa1111'}, wait=5, poll=0.2)
    assert got and got['decision'] == 'block' and 'SubagentHandback' in got['reason'], got    # short last words: its report, once
    assert decide({'agent_id': 'aaaa1111'}, wait=5, poll=0.2) is None
    print('hold prova ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
        sys.exit(0)
    sys.exit(main())
