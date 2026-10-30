"""Smaller pictures for the room's agents: an image an agent reads costs about (width/28) x (height/28) tokens and stays
in its context, read again at every turn (a 1920x1080 frame 2.691 tokens, at 1000 px 1.296). The chatroom mod asks the
viewer (POST /thumb) before an agent's Read of a picture wider or taller than MAX, and the agent reads the copy instead.
The agent is told (squeeze.py adds a line after the Read: the copy's size, the original's, the factor for coordinates),
and the same Read again within AGAIN seconds gets the original. `config thumbs=0` turns it off for a room (grounding,
games, pixel work). Pillow is in the room's environment (pyproject.toml); without it the picture passes as it is. Copies
live in ROOM/thumbs, by the source's path, size and time, so the same picture is shrunk once and reads the same bytes
every time (the prompt cache holds)."""
import hashlib
import json
import os
import time
from pathlib import Path

MAX = 1000
AGAIN = 300                    # a second Read of the same picture within 5 minutes: the original
TYPES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')


def _served(room_dir):
    try:
        return json.loads((Path(room_dir) / 'thumbs' / 'served.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _save_served(room_dir, served):
    p = Path(room_dir) / 'thumbs' / 'served.json'
    tmp = p.with_name(f'served.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(dict(sorted(served.items(), key=lambda kv: kv[1]['ts'])[-200:])), encoding='utf-8')
    os.replace(tmp, p)


def note_of(room_dir, path):
    """the copy's record when `path` is a copy this room handed out: {'orig', 'w', 'h', 'ow', 'oh', 'ts'}, else None"""
    return _served(room_dir).get(str(Path(path)))


def shrink(room_dir, path, limit=MAX):
    """the path an agent should read: a copy at most `limit` px on its longer side, or the picture itself"""
    src = Path(path)
    if src.suffix.lower() not in TYPES or not src.is_file():
        return str(path)
    try:
        cfg = json.loads((Path(room_dir) / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        cfg = {}
    if str(cfg.get('thumbs', 1)) == '0':
        return str(path)
    try:
        from PIL import Image
        served = _served(room_dir)
        again = next((k for k, v in served.items() if v.get('orig') == str(src) and time.time() - v['ts'] < AGAIN), None)
        if again:                                         # read again right after its copy: the agent wants the pixels
            served.pop(again)
            _save_served(room_dir, served)
            return str(path)
        st = src.stat()
        key = hashlib.sha256(f'{src.resolve()}|{st.st_size}|{st.st_mtime_ns}|{limit}'.encode()).hexdigest()[:16]
        out = Path(room_dir) / 'thumbs' / f'{key}.png'
        if not out.is_file():
            with Image.open(src) as im:
                if max(im.size) <= limit:
                    return str(path)
                im.thumbnail((limit, limit), Image.Resampling.LANCZOS)
                out.parent.mkdir(exist_ok=True)
                tmp = out.with_name(f'{key}.{os.getpid()}.png')
                im.save(tmp, 'PNG')
            os.replace(tmp, out)
        with Image.open(src) as a, Image.open(out) as b:
            served[str(out)] = {'orig': str(src), 'w': b.size[0], 'h': b.size[1], 'ow': a.size[0], 'oh': a.size[1], 'ts': time.time()}
        _save_served(room_dir, served)
        return str(out)
    except Exception:                                     # no Pillow, a broken file: the agent reads the original, as before
        return str(path)


def note_text(n):
    """the line the agent gets after reading a copy"""
    f = n['ow'] / n['w']
    tok = lambda w, h: -(-w // 28) * -(-h // 28)
    return (f"[chatroom: this picture is a {n['w']}x{n['h']} copy of {n['orig']} ({n['ow']}x{n['oh']}); coordinates on it "
            f"times {f:.2f} give the original's. Read the same file again within {AGAIN // 60} minutes for the original "
            f"(about {tok(n['ow'], n['oh'])} tokens instead of {tok(n['w'], n['h'])}).]")


def _prova():
    import tempfile
    from PIL import Image
    d = Path(tempfile.mkdtemp(prefix='thumbs_'))
    (d / 'config.json').write_text('{}')
    Image.new('RGB', (400, 300), 'gray').save(d / 'small.png')
    Image.new('RGB', (2560, 1440), 'gray').save(d / 'big.jpg')
    assert shrink(d, d / 'small.png') == str(d / 'small.png')
    out = shrink(d, d / 'big.jpg')
    with Image.open(out) as im:
        assert im.size == (1000, 562) or im.size == (1000, 563), im.size
    n = note_of(d, out)
    assert n and n['ow'] == 2560 and '2.56' in note_text(n), n
    assert shrink(d, d / 'big.jpg') == str(d / 'big.jpg')    # read again at once: the original
    assert shrink(d, d / 'big.jpg') == out                     # and then the copy again
    (d / 'config.json').write_text('{"thumbs": 0}')
    assert shrink(d, d / 'big.jpg') == str(d / 'big.jpg')    # off for this room
    assert shrink(d, d / 'missing.png') == str(d / 'missing.png')
    print('thumbs prova ok')


if __name__ == '__main__':
    _prova()
