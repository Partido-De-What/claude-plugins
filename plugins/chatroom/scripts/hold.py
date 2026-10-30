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
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from limits import HOLD_WAIT

POLL = 2
ROOM_IDLE = 6 * 3600           # a room whose chat has not moved for six hours holds nobody
REASON_MAX = 6000              # characters of messages in a reason; past it the agent reads the rest


def candidates():
    """room folders worth looking in: the served ones and the ones chat.py met lately"""
    base = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'chatroom'
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
    """a CLOSED was posted (chat.py lets a participant's through only with every vote in)"""
    import chat
    return any(chat.closing(m.get('text', ''))[0] for m in room.messages()[-50:] if not m.get('kind'))


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
    while True:
        if closed(room) or find(aid) != (key, name):      # closed, gone quiet for hours, or retired meanwhile
            return None
        new = news(room, name)
        if new:
            try:
                import inbox
                inbox.mark_delivered(room.dir, name, new[-1]['n'])
            except Exception:
                pass
            return {'decision': 'block', 'reason': reason(room, name, new)}
        if time.time() >= end:
            chat.use(room.config().get('lang'))
            return {'decision': 'block', 'reason': chat.say('chat.say.hold.nothing', name=name, minutes=max(1, wait // 60))}
        time.sleep(poll)


def main():
    try:
        got = decide(json.load(sys.stdin))
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
    (room / 'config.json').write_text(json.dumps({'user_name': 'Adrian', 'self_names': ['LEAD'], 'participants': ['A', 'B'], 'lang': 'en'}))
    r = chat.Room(room)
    r.update_roster(lambda ro: ro.update(A='aaaa1111', B='bbbb2222'))       # chat.py records the room: no viewer needed
    r.append('LEAD', 'start')
    r.set_cursor('A', 1)
    assert decide({'agent_id': 'zzzz'}) is None                                   # not a room agent: it stops
    threading.Timer(1.0, lambda: r.append('B', '@A your turn')).start()
    t0 = time.time()
    got = decide({'agent_id': 'aaaa1111'}, wait=20, poll=0.2)
    assert got and got['decision'] == 'block' and '@A your turn' in got['reason'] and time.time() - t0 < 10, got
    assert int((room / 'delivered_A.txt').read_text()) >= 1 and r.cursor('A') >= 2   # read for it: no extra read
    got = decide({'agent_id': 'aaaa1111'}, wait=1, poll=0.2)
    assert got and 'nothing' in got['reason'].lower(), got                        # nothing in the window: one quiet turn
    (room / 'waiting_A.txt').write_text(f'{time.time() + 500:.0f} 999999')
    assert not r.in_wait('A')                                                     # a dead holder's mark does not count
    r.append('LEAD', 'CLOSED v1: done')
    assert decide({'agent_id': 'aaaa1111'}, wait=5, poll=0.2) is None             # closed: it stops for good
    print('hold prova ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
        sys.exit(0)
    sys.exit(main())
