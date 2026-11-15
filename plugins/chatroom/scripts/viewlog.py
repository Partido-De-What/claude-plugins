"""POST /viewlog: the 3D office page (opened with ?viewlog=1) sends what turned its view by itself, so the user need not open the
console. Write only: one JSON line per event in ROOM/viewlog.jsonl, nothing is ever read back. Local programs only (chat.py checks
the peer), at most MAX_EVENTS events and MAX_BODY bytes a call, the file stops growing at MAX_FILE."""
import json
import time

MAX_EVENTS, MAX_BODY, MAX_LINE, MAX_FILE = 200, 64 * 1024, 4000, 2 * 1024 * 1024
LOCAL = ('127.0.0.1', '::1', '::ffff:127.0.0.1')


def append(room, body, ip):
    """(status, answer) for a body already parsed; the caller has checked the length of the request"""
    events = body.get('events') if isinstance(body, dict) else None
    if not isinstance(events, list) or len(events) > MAX_EVENTS or not all(isinstance(e, dict) for e in events):
        return 400, {'ok': False, 'error': 'events: a list of at most %d objects' % MAX_EVENTS}
    f = room.dir / 'viewlog.jsonl'
    if f.is_file() and f.stat().st_size >= MAX_FILE:
        return 200, {'ok': True, 'n': 0, 'full': True}
    now = round(time.time(), 3)
    lines = []
    for e in events:
        line = json.dumps({**e, 'ip': ip, 'at': now})      # ascii only: a lone surrogate of the page cannot break the write
        lines.append(line if len(line) <= MAX_LINE else json.dumps({'cut': True, 'n': len(line), 'head': line[:3000], 'ip': ip, 'at': now}))      # still one valid JSON line
    if lines:
        with open(f, 'a', encoding='utf-8') as fh:
            fh.write('\n'.join(lines) + '\n')
    return 200, {'ok': True, 'n': len(lines)}
