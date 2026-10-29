"""Smaller pictures for the room's agents: an image an agent reads costs about (width/28) x (height/28) tokens and stays
in its context, read again at every turn (a 1920x1080 frame 2.691 tokens, at 1000 px 1.296). The chatroom mod asks the
viewer (POST /thumb) before an agent's Read of a picture wider or taller than MAX, and the agent reads the copy instead.
Pillow is in the room's environment (pyproject.toml); without it the picture passes as it is. Copies live in
ROOM/thumbs, by the source's path, size and time, so the same picture is shrunk once and reads the same bytes every time
(the prompt cache holds)."""
import hashlib
import os
from pathlib import Path

MAX = 1000
TYPES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')


def shrink(room_dir, path, limit=MAX):
    """the path an agent should read: a copy at most `limit` px on its longer side, or the picture itself"""
    src = Path(path)
    if src.suffix.lower() not in TYPES or not src.is_file():
        return str(path)
    try:
        from PIL import Image
        st = src.stat()
        key = hashlib.sha256(f'{src.resolve()}|{st.st_size}|{st.st_mtime_ns}|{limit}'.encode()).hexdigest()[:16]
        out = Path(room_dir) / 'thumbs' / f'{key}.png'
        if out.is_file():
            return str(out)
        with Image.open(src) as im:
            if max(im.size) <= limit:
                return str(path)
            im.thumbnail((limit, limit), Image.Resampling.LANCZOS)
            out.parent.mkdir(exist_ok=True)
            tmp = out.with_name(f'{key}.{os.getpid()}.png')
            im.save(tmp, 'PNG')
        os.replace(tmp, out)
        return str(out)
    except Exception:                                     # no Pillow, a broken file: the agent reads the original, as before
        return str(path)


def _prova():
    import tempfile
    from PIL import Image
    d = Path(tempfile.mkdtemp(prefix='thumbs_'))
    Image.new('RGB', (400, 300), 'gray').save(d / 'small.png')
    Image.new('RGB', (2000, 1000), 'gray').save(d / 'big.jpg')
    assert shrink(d, d / 'small.png') == str(d / 'small.png')
    out = shrink(d, d / 'big.jpg')
    with Image.open(out) as im:
        assert im.size == (1000, 500), im.size
    assert shrink(d, d / 'big.jpg') == out                # cached: the same bytes next time
    assert shrink(d, d / 'missing.png') == str(d / 'missing.png')
    print('thumbs prova ok')


if __name__ == '__main__':
    _prova()
