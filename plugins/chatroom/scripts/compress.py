"""Headroom at the source: what the room hands back to its agents (chat messages, the board, notebooks) is compressed
when it is long, by the room's viewer server, where Headroom stays loaded (importing it costs about a second, its first
compression about ten). Texts under 1500 tokens and every message of the user or the lead pass untouched. A compressed
text ends with a mark ⟨compressed: ID⟩, and `chat.py expand ID` (or the MCP tool chat_expand) gives the original back.
The same text always becomes the same bytes (kept by its hash in ROOM/compressed/), so what an agent has read once
never changes and the provider's prompt cache holds. No Headroom, no viewer running, or the room's switch off
(config compress=0): everything passes as before."""
import hashlib
import json
import os
import threading
import time
import urllib.request
from pathlib import Path

THRESHOLD = 1500                      # tokens (D9)
CHARS = 4 * THRESHOLD                 # about 4 characters a token: a shorter text never leaves the agent's process
MARK = '⟨compressed: {id} · chat.py expand {id}⟩'
_lock = threading.Lock()              # one compression at a time in the server: Headroom's pipeline is shared


def _dir(room):
    return Path(room.dir) / 'compressed'


def key(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def _headroom(text):
    """(compressed text, tokens saved) from Headroom, or (None, 0)"""
    os.environ.setdefault('HEADROOM_TELEMETRY', 'off')
    from headroom import compress
    with _lock:
        r = compress([{'role': 'tool', 'tool_call_id': 'chatroom', 'content': text}], model='gpt-4o', protect_recent=0,
                     min_tokens_to_compress=THRESHOLD, kompress_model='disabled')
    out = r.messages[0].get('content') if r.messages else None
    return (out, r.tokens_saved) if isinstance(out, str) and r.tokens_saved > 0 else (None, 0)


def warm():
    """the server's start: Headroom loaded and its pipeline built once, in the background"""
    try:
        _headroom('2026-01-01 00:00:00 INFO warm\n' * 1200)
    except Exception:                 # no Headroom: the room works as before
        pass


def shrink(room, text):
    """server side: the text compressed with its mark, or the text itself. A result is kept by the text's hash, a text
    that does not compress too, so it is computed once"""
    if len(text) < CHARS:
        return text
    k, d = key(text), _dir(room)
    try:
        return json.loads((d / f'{k}.json').read_text(encoding='utf-8'))['out']
    except (OSError, ValueError, KeyError):
        pass
    try:
        out, saved = _headroom(text)
    except Exception:
        return text                   # no Headroom: nothing kept, it is tried again once installed
    out = f'{out}\n{MARK.format(id=k)}' if out else text
    d.mkdir(exist_ok=True)
    tmp = d / f'{k}.{os.getpid()}.{threading.get_ident()}.tmp'
    tmp.write_text(json.dumps({'orig': text, 'out': out, 'saved': saved}, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, d / f'{k}.json')
    return out


def viewer_url(room):
    """the address of the room's running viewer, from the registry the viewers stamp every 5 s"""
    from activity import REGISTRY
    try:
        v = json.loads(REGISTRY.read_text(encoding='utf-8')).get(str(Path(room.dir).resolve()))
    except (OSError, ValueError):
        return None
    return v['url'] if v and time.time() - float(v.get('ts', 0)) < 60 else None


def texts(room, items):
    """client side (chat.py read, wait, board, notebook): the same list, the long ones compressed by the viewer"""
    if not any(len(t) >= CHARS for t in items) or not room.config().get('compress', 1):
        return items
    url = viewer_url(room)
    if not url:
        return items
    req = urllib.request.Request(url + '/compress', data=json.dumps({'texts': items}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode('utf-8')).get('texts')
    except (OSError, ValueError):
        return items
    return out if isinstance(out, list) and len(out) == len(items) and all(isinstance(t, str) for t in out) else items


def expand(room, k):
    """the original of a compressed text"""
    if not (isinstance(k, str) and len(k) == 12 and all(c in '0123456789abcdef' for c in k)):
        raise ValueError(f'{k!r}: an id is the 12 letters after "compressed:"')
    try:
        return json.loads((_dir(room) / f'{k}.json').read_text(encoding='utf-8'))['orig']
    except (OSError, ValueError, KeyError):
        raise ValueError(f'no compressed text {k} in this room')


def stats(room, window=10):
    """{saved: tokens saved in this room, recent: compressions in the last `window` seconds} (the Hangar's press)"""
    saved = recent = 0
    now = time.time()
    for f in _dir(room).glob('*.json'):
        try:
            saved += int(json.loads(f.read_text(encoding='utf-8')).get('saved', 0))
            recent += now - f.stat().st_mtime < window
        except (OSError, ValueError):
            pass
    return {'saved': saved, 'recent': recent}


def _prova():
    import tempfile
    import types
    with tempfile.TemporaryDirectory() as tmp:
        room = types.SimpleNamespace(dir=Path(tmp), config=lambda: {})
        short = 'ok ' * 100
        assert shrink(room, short) == short and texts(room, [short]) == [short]
        log = ''.join(f'2026-10-26 01:{i % 60:02d}:00 INFO worker{i % 3} batch {i} ok\n' for i in range(900)) + \
            '2026-10-26 02:00:00 ERROR worker1 batch 901 failed: KeyError participants\n'
        t0 = time.time()
        out = shrink(room, log)
        k = key(log)
        assert out.endswith(MARK.format(id=k)) and 'ERROR worker1' in out and len(out) < len(log) / 10, out[-300:]
        assert expand(room, k) == log and shrink(room, log) == out
        assert stats(room)['saved'] > 1000 and stats(room)['recent'] == 1
        prose = 'The agent read the file and changed the parser because the tests failed on empty input. ' * 120
        assert shrink(room, prose) == prose                     # prose without the ML model: unchanged, kept as such
        for bad in ('../x', 'zz', 12):
            try:
                expand(room, bad)
            except ValueError:
                continue
            raise AssertionError(bad)
        print(f'compress ok ({time.time() - t0:.1f} s)')


if __name__ == '__main__':
    _prova()
