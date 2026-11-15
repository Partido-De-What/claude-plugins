"""Live preview of what an agent builds (an html page, an animation, a texture, a video, a local server) without spending tokens.

The agent declares it ONCE: `chat.py preview PATH_OR_URL --as NAME`. The server only watches the disk: GET /preview.json lists
each agent's preview with the mtime of what it shows, GET /preview/NAME/REL serves the files of the declared folder. The viewer
reloads a tile when its mtime changes. No picture ever goes through an agent's context. Declarations live in ROOM/previews.json.

Safe by shape: files come only from the declared folder (no `..`, no links out of it), localhost only (chat.py's trusted()), and
every served file carries `Content-Security-Policy: sandbox allow-scripts`, so a page can run but not touch the viewer."""
import json
import mimetypes
import re
import time
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from i18n import say

KINDS = {'html': ('.html', '.htm'), 'image': ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp'),
         'video': ('.mp4', '.webm', '.mov', '.m4v'), 'audio': ('.mp3', '.wav', '.ogg', '.m4a')}
LOCAL = {'127.0.0.1', 'localhost', '::1'}
SIBLINGS, NAME = 200, re.compile(r'[A-Za-z0-9_-]{1,40}\Z')
SANDBOX = 'sandbox allow-scripts'
MAX_BYTES = 64 * 1024 * 1024                  # shortcut: a file is read whole; a bigger video needs Range support (not in v1)


def kind_of(path):
    ext = Path(path).suffix.lower()
    return next((k for k, exts in KINDS.items() if ext in exts), None)


def store(room):
    import chat
    d = chat.read_json(room.dir / 'previews.json', {})
    return d if isinstance(d, dict) else {}


def save(room, fn):
    import chat

    def run():
        d = store(room)
        out = fn(d)
        chat.write_atomic(room.dir / 'previews.json', json.dumps(d, indent=1, ensure_ascii=False))
        return out
    return room.locked(run)


def declare(room, name, target, title=''):
    """one preview for an agent (a new one replaces it); ValueError with the text to show when the target is not allowed"""
    if not NAME.match(name or ''):
        raise ValueError(say('preview.core.err_name'))
    target = str(target or '').strip()
    if re.match(r'https?://', target, re.I):
        u = urlparse(target)
        if (u.hostname or '').lower() not in LOCAL:
            raise ValueError(say('preview.core.err_url_local', url=target))
        entry = {'kind': 'url', 'url': target}
    else:
        p = Path(target).expanduser()
        if p.is_dir():
            p = p / 'index.html'
        if not p.is_file():
            raise ValueError(say('preview.core.err_no_file', path=str(p)))
        kind = kind_of(p)
        if not kind:
            raise ValueError(say('preview.core.err_kind', ext=p.suffix or '-'))
        entry = {'kind': kind, 'file': str(p.resolve()).replace('\\', '/')}
    entry.update(title=str(title or Path(entry.get('file') or target).name)[:80], at=int(time.time()))
    save(room, lambda d: d.__setitem__(name, entry))
    return entry


def off(room, name):
    return save(room, lambda d: d.pop(name, None)) is not None


def newest(page):
    """the newest mtime among the page and the files next to it (what it loads; not recursive, at most SIBLINGS: the page itself
    always counts, so a folder with more files never hides its change)"""
    m = 0.0
    try:
        m = page.stat().st_mtime if page.is_file() else 0.0
        for i, f in enumerate(page.parent.iterdir()):
            if i >= SIBLINGS:
                break
            if f.is_file():
                m = max(m, f.stat().st_mtime)
    except OSError:
        pass
    return m


def listing(room):
    out = []
    for name, e in sorted(store(room).items()):
        if not isinstance(e, dict):
            continue
        item = {'agent': name, 'kind': e.get('kind'), 'title': e.get('title', ''), 'at': e.get('at', 0), 'missing': False}
        if e.get('kind') == 'url':
            item.update(src=e.get('url'), mtime=float(e.get('at', 0)))
        else:
            f = Path(e.get('file', ''))
            item.update(src=f'preview/{name}/{quote(f.name)}', mtime=newest(f), missing=not f.is_file())
            if item['missing']:
                item['mtime'] = 0.0
        out.append(item)
    return {'v': 1, 'at': int(time.time()), 'previews': out}


def serve(room, name, rel):
    """(code, body, content type) of GET /preview/NAME/REL: the declared file for an empty REL, else a file of its folder"""
    e = store(room).get(name)
    if not isinstance(e, dict) or e.get('kind') == 'url':
        return 404, b'no such preview', 'text/plain'
    f = Path(e.get('file', ''))
    base = f.parent.resolve()
    rel = unquote(rel).replace('\\', '/').strip('/')
    p = (base / rel).resolve() if rel else f.resolve()
    if '..' in rel.split('/') or not p.is_relative_to(base) or not p.is_file():
        return 404, b'no such file', 'text/plain'
    if p.stat().st_size > MAX_BYTES:
        return 413, b'too big', 'text/plain'
    ctype = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    if ctype.startswith(('text/', 'application/javascript', 'application/json')) or ctype == 'image/svg+xml':
        ctype += '; charset=utf-8' if 'charset' not in ctype else ''
    return 200, p.read_bytes(), ctype
