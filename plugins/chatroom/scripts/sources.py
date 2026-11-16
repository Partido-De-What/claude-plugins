"""The register of sources of a room: what each research read, with a line of summary and the link. `chat.py sources add URL "summary"`
adds (or updates, the URL is the key), `chat.py sources` lists. It lives in the room (ROOM/sources.jsonl), or, when the room is bound
to a topic profile, in that topic's folder, so the next room of the topic starts with what the others read."""
import json
import time
from pathlib import Path


def path(room):
    import lessons
    slug = lessons.topic_of(room)
    return (lessons.topic_dir(slug) if slug else Path(room.dir)) / 'sources.jsonl'


def rows(room):
    try:
        lines = path(room).read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:                      # a line being written right now
            pass
    return out


def add(room, by, url, note=''):
    """one row for each URL: a second add of the same URL replaces its note. Returns 'new' or 'updated'"""
    import chat
    url = (url or '').strip()
    if not url:
        raise ValueError('no URL')

    def write():
        got = rows(room)
        found = [r for r in got if r.get('url') == url]
        row = {'ts': int(time.time()), 'by': by, 'url': url, 'note': ' '.join((note or '').split())[:400]}
        got = [r for r in got if r.get('url') != url] + [row]
        p = path(room)
        p.parent.mkdir(parents=True, exist_ok=True)
        chat.write_atomic(p, ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in got))
        return 'updated' if found else 'new'
    return room.locked(write)


def lines(room):
    return [f"- {r['url']} - {r.get('note') or '-'} ({r.get('by', '?')}, {time.strftime('%Y-%m-%d', time.localtime(r.get('ts', 0)))})" for r in rows(room)]
