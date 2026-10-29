"""SubagentStop hook of the chatroom: a room agent that ends its turn is held, at no token cost, until a message for it
arrives (a tag, a tag to everyone, the user, the lead, a plan, a vote, a closing), and then goes on with that message as
its next instruction (Claude Code's `decision: block` with a reason). It replaces the idle wait loop and the lead's
SendMessage to a stopped agent, and the agent's long report back to the lead at every stop. After WAIT seconds with
nothing for it, it is let through once more with a one-line reason, which costs one cached turn (its cache lives an
hour with chatroom:room-agent). It is let go for good when the room is closed, its viewer is down, or the lead retired it.
Any fault lets the agent stop, as without this hook. Checked live: Claude Code delivers each reason, any number of times."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
WAIT, POLL = 3000, 2            # 50 minutes under the one-hour cache; hooks.json gives the hook 3300 s


def registry():
    path = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'chatroom' / 'rooms.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def find(aid):
    """(room folder, name) of a live room whose roster has this agent id, or (None, None)"""
    for key, info in registry().items():
        if aid in info.get('ids', []) and time.time() - float(info.get('ts', 0)) < 60:
            import chat
            name = next((n for n, v in chat.Room(key).roster().items() if v == aid), None)
            if name:
                return key, name
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
    import chat
    chat.use(room.config().get('lang'))
    lines = [f"#{m['n']} {m['from']}: {' '.join(m.get('text', '').split())[:300]}" for m in new[-4:]]
    return chat.say('chat.say.hold.new_for_you', name=name, n=len(new), lines='\n'.join(lines))


def decide(ev, wait=WAIT, poll=POLL):
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
    mark = room.dir / f'waiting_{name}.txt'           # held like a wait: a message for it needs no ping (print_alert)
    try:
        mark.write_text(f'{end + 5:.0f}')
    except OSError:
        pass
    try:
        return _hold(room, aid, key, name, end, wait, poll)
    finally:
        mark.unlink(missing_ok=True)


def _hold(room, aid, key, name, end, wait, poll):
    import chat
    while True:
        if closed(room) or find(aid) != (key, name):      # closed, the viewer gone, or retired meanwhile
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
            return {'decision': 'block', 'reason': chat.say('chat.say.hold.nothing', name=name, minutes=wait // 60)}
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
    (room / 'roster.json').write_text(json.dumps({'A': 'aaaa1111', 'B': 'bbbb2222'}))
    (base / 'c' / 'chatroom' / 'rooms.json').write_text(json.dumps({str(room): {'ts': time.time(), 'ids': ['aaaa1111', 'bbbb2222']}}))
    r = chat.Room(room)
    assert decide({'agent_id': 'zzzz'}) is None                                   # not a room agent: it stops
    threading.Timer(1.0, lambda: r.append('B', '@A your turn')).start()
    t0 = time.time()
    got = decide({'agent_id': 'aaaa1111'}, wait=20, poll=0.2)
    assert got and got['decision'] == 'block' and '@A your turn' in got['reason'] and time.time() - t0 < 10, got
    assert int((room / 'delivered_A.txt').read_text()) >= 1
    r.set_cursor('A', 1)
    got = decide({'agent_id': 'aaaa1111'}, wait=1, poll=0.2)
    assert got and 'nothing' in got['reason'].lower(), got                        # nothing in the window: one quiet turn
    r.append('LEAD', 'CLOSED v1: done')
    assert decide({'agent_id': 'aaaa1111'}, wait=5, poll=0.2) is None             # closed: it stops for good
    print('hold prova ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
        sys.exit(0)
    sys.exit(main())
