"""Life in idle (experimental; off unless the user turns it on, never in a research room): where an idle agent spends
its break, chosen by the server so that everyone sees the same thing.

- The places come from idle_spots.json (office-layout.js idleSpots): the user's own office when the viewer published it
  (~/.claude/chatroom/idle_spots.json), else the default office's list next to this file.
- A place is a pure function of (room, name, 20-minute slot), with a fixed character per agent (a zone it prefers); two
  agents never share a place. An agent may choose (`go`): its choice holds 40 minutes.
- `look` tells an agent where it is, who is near, where the others and the user are, and which places are free; with
  `--map` it adds a 24x14 map. The diary ("while you slept: ...") is told once per break of 10 minutes or more.
Nothing here wakes an agent: it reads these only when it is awake anyway."""
import hashlib
import json
import os
import time
from pathlib import Path

from i18n import lang_of, say

HERE = Path(__file__).resolve().parent
USER_SPOTS = Path.home() / '.claude' / 'chatroom' / 'idle_spots.json'     # the user's own office, published by the viewer
SLOT = 1200                                           # a place is kept 20 minutes
CHOICE = 2400                                         # an agent's own choice holds 40 minutes
DIARY_MIN = 600                                       # a break shorter than this has nothing to tell
USER_FRESH = 180                                      # the user's position is "here" this long after the viewer sent it


def spots():
    """{size, zones, spots, grid}: the user's office if published and sound, else the default one"""
    for f in (USER_SPOTS, HERE / 'idle_spots.json'):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get('spots') and d.get('grid') and d.get('zones'):
            return d
    return {'size': [30, 20], 'zones': [], 'spots': [], 'grid': []}


def clean_spots(d):
    """the list the viewer sends (POST /idle_spots), checked: at most 200 places, numbers in the office, a 24x14 grid"""
    if not isinstance(d, dict):
        raise ValueError('not an object')
    size = [float(v) for v in d.get('size', [])][:2]
    zones = [{'key': str(z.get('key', ''))[:1].upper(), 'it': str(z.get('it', ''))[:40], 'en': str(z.get('en', ''))[:40]}
             for z in d.get('zones', [])[:30] if isinstance(z, dict)]
    keys = {z['key'] for z in zones if z['key'].isalpha()}
    out = []
    for s in d.get('spots', [])[:200]:
        x, z = float(s['x']), float(s['z'])
        if len(size) != 2 or abs(x) > size[0] or abs(z) > size[1]:
            raise ValueError('a place outside the office')
        out.append({'id': len(out) + 1, 'x': round(x, 2), 'z': round(z, 2), 'rot': round(float(s.get('rot', 0)), 3),
                    'pose': str(s.get('pose', 'sit'))[:8], 'tag': 'common' if s.get('tag') == 'common' else 'coffee',
                    'zone': str(s.get('zone', ''))[:1].upper() if str(s.get('zone', ''))[:1].upper() in keys else ''})
    grid = [''.join(ch if ch.isalpha() or ch == '.' else '.' for ch in str(row)[:24]).lower() for row in d.get('grid', [])[:14]]
    if len(size) != 2 or not out or len(grid) != 14 or any(len(r) != 24 for r in grid):
        raise ValueError('incomplete list')
    return {'size': size, 'zones': zones, 'spots': out, 'grid': grid}


def is_on(room, settings):
    """the user turned it on, and the room is not a research room"""
    return settings.get('idle_life') is True and (room.config().get('mode') or '') != 'research'


def _h(*parts):
    return int(hashlib.sha256('|'.join(map(str, parts)).encode('utf-8')).hexdigest(), 16)


def _key(room):
    return str(room.dir.resolve()).lower()              # the room in the seed: one name in two rooms makes different choices


def _state(room):
    try:
        d = json.loads((room.dir / 'idle_life.json').read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(room, d):
    path = room.dir / 'idle_life.json'
    tmp = path.with_name(f'.idle_life.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def _allowed(room, name):
    """the common room only for the agents the user let in (the 🛋 panel)"""
    c = room.config().get('common') or {}
    common = bool(c.get('all')) or name in (c.get('who') or [])
    return lambda s: s['tag'] != 'common' or common


def places(room, t=None, items=None, data=None):
    """{name: place} for every agent idle at time t: its own choice while it holds, else the place of the slot"""
    t = time.time() if t is None else t
    data = data or spots()
    items = room.messages() if items is None else items
    names = sorted(n for n in room.config().get('participants', []) if room.idle_entry(n, items))
    if not data['spots'] or not names:
        return {}
    by_id = {s['id']: s for s in data['spots']}
    choices = _state(room).get('choices', {})
    out, taken = {}, set()
    for n in names:                                       # first the choices still holding
        ch = choices.get(n) or {}
        s = by_id.get(ch.get('spot'))
        if s and ch.get('until', 0) > t and _allowed(room, n)(s) and s['id'] not in taken:
            out[n] = s; taken.add(s['id'])
    zones = sorted({s['zone'] for s in data['spots'] if s['zone']})
    slot, key = int(t // SLOT), _key(room)
    for n in names:
        if n in out:
            continue
        ok = _allowed(room, n)
        pool = [s for s in data['spots'] if ok(s)]
        if not pool:
            continue
        liked = zones[_h(key, n, 'zone') % len(zones)] if zones else ''     # the character: a zone it likes
        weighted = [s for s in pool for _ in range(3 if s['zone'] == liked else 1)]
        i = _h(key, n, slot) % len(weighted)
        for k in range(len(weighted)):
            s = weighted[(i + k) % len(weighted)]
            if s['id'] not in taken:
                out[n] = s; taken.add(s['id'])
                break
    return out


def zone_name(data, key, lang):
    z = next((z for z in data['zones'] if z['key'] == key), None)
    return (z.get(lang) or z.get('en')) if z else '?'


def zone_at(data, x, z):
    sx, sz = data['size']
    col, row = int((x + sx / 2) / sx * 24), int((z + sz / 2) / sz * 14)
    return data['grid'][row][col].upper() if 0 <= row < 14 and 0 <= col < 24 and data['grid'][row][col] != '.' else ''


def user_place(room):
    """where the user is (x, z) if the viewer said so in the last 3 minutes, else None"""
    try:
        d = json.loads((room.dir / 'idle_user.json').read_text(encoding='utf-8'))
        return (float(d['x']), float(d['z'])) if time.time() - float(d['ts']) < USER_FRESH else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_user(room, body):
    x, z = float(body['x']), float(body['z'])
    if not (abs(x) < 60 and abs(z) < 60):
        raise ValueError('out of the office')
    path = room.dir / 'idle_user.json'
    tmp = path.with_name(f'.idle_user.{os.getpid()}.tmp')
    tmp.write_text(json.dumps({'x': round(x, 2), 'z': round(z, 2), 'ts': time.time()}), encoding='utf-8')
    os.replace(tmp, path)


def go(room, name, target):
    """the agent chooses: a place number, or a zone (its letter or its name): the first free place there"""
    data, now = spots(), time.time()
    current = places(room, now, data=data)
    taken = {s['id'] for n, s in current.items() if n != name}
    ok = _allowed(room, name)
    target = str(target or '').strip()
    if target.isdigit():
        pick = next((s for s in data['spots'] if s['id'] == int(target)), None)
        if not pick or not ok(pick):
            raise ValueError(say('idle.no_such_place', target=target))
        if pick['id'] in taken:
            raise ValueError(say('idle.place_taken', id=pick['id']))
    else:
        t = target.lower()
        zone = next((z['key'] for z in data['zones'] if t in (z['key'].lower(), z['it'].lower(), z['en'].lower())), None)
        pick = next((s for s in data['spots'] if zone and s['zone'] == zone and ok(s) and s['id'] not in taken), None)
        if not pick:
            raise ValueError(say('idle.no_free_place', target=target))

    def write():
        d = _state(room)
        d.setdefault('choices', {})[name] = {'spot': pick['id'], 'until': now + CHOICE}
        _save(room, d)
    room.locked(write)
    return say('idle.went', id=pick['id'], zone=zone_name(data, pick['zone'], lang_of(room.config())), minutes=CHOICE // 60)


def _initials(names):
    out, used = {}, {'@'}
    for n in names:
        ch = next((c for c in n.upper() + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if c.isalpha() and c not in used), '?')
        used.add(ch); out[n] = ch
    return out


def look(room, name, with_map=False):
    data, lang, items = spots(), lang_of(room.config()), room.messages()
    here = places(room, items=items, data=data)
    zn = lambda key: zone_name(data, key, lang)
    lines = []
    me = here.get(name)
    lines.append(say('idle.you_at', id=me['id'], zone=zn(me['zone'])) if me else say('idle.you_working'))
    others = [n for n in room.config().get('participants', []) if n != name]
    where = [say('idle.other_at', name=n, zone=zn(here[n]['zone'])) if n in here else say('idle.other_working', name=n) for n in others]
    u = user_place(room)
    user = room.config().get('user_name', 'USER')
    where.append(say('idle.user_at', name=user, zone=zn(zone_at(data, *u))) if u else say('idle.user_away', name=user))
    lines.append('; '.join(where))
    taken = {s['id'] for s in here.values()}
    ok = _allowed(room, name)
    free = {}
    for s in data['spots']:
        if s['id'] not in taken and ok(s):
            free.setdefault(s['zone'], []).append(s['id'])
    lines.append(say('idle.free', places='; '.join(f"{zn(k)} {_ranges(v)}" for k, v in free.items())) + ' · ' + say('idle.how_to_go'))
    if with_map:
        lines += _map(data, here, u, _initials(room.config().get('participants', [])), name, lang, user, taken, ok)
    return '\n'.join(lines)


def _ranges(ids):
    out, start = [], None
    for i, v in enumerate(ids):
        if start is None:
            start = v
        if i + 1 == len(ids) or ids[i + 1] != v + 1:
            out.append(str(start) if start == v else f'{start}-{v}')
            start = None
    return ','.join(out)


def _map(data, here, u, ini, name, lang, user, taken, ok):
    """the 24x14 map: zone letters in lower case, free places '·', the agents' initials, the user '@'"""
    sx, sz = data['size']
    cell = lambda x, z: (min(13, max(0, int((z + sz / 2) / sz * 14))), min(23, max(0, int((x + sx / 2) / sx * 24))))
    rows = [list(r) for r in data['grid']]
    for s in data['spots']:
        if s['id'] not in taken and ok(s):           # only the places this agent may take
            r, c = cell(s['x'], s['z']); rows[r][c] = '·'
    for n, s in here.items():
        r, c = cell(s['x'], s['z']); rows[r][c] = ini.get(n, '?')
    if u:
        r, c = cell(*u); rows[r][c] = '@'
    legend = [f"{'@'} {user}"] + [f"{ini[n]} {n}" + (' ←' if n == name else '') for n in ini if n in here] + \
             [f"{z['key'].lower()} {z.get(lang) or z['en']}" for z in data['zones'] if any(z['key'].lower() in r for r in data['grid'])]
    return ['+' + '-' * 24 + '+'] + ['|' + ''.join(r) + '|' for r in rows] + ['+' + '-' * 24 + '+', say('idle.map_north'), '  '.join(legend)]


def diary(room, name, now=None):
    """the line told once per break of 10 minutes or more: the places of the slots it slept through, merged"""
    now = time.time() if now is None else now
    items = room.messages()
    entry = room.idle_entry(name, items)
    if not entry or now - entry.get('ts', now) < DIARY_MIN:
        return ''
    st = _state(room)
    if st.get('told', {}).get(name) == entry['n']:
        return ''
    data, lang = spots(), lang_of(room.config())
    start, parts = entry['ts'], []
    t = start
    while t < now:
        end = min(now, (int(t // SLOT) + 1) * SLOT)
        s = places(room, (t + end) / 2, items=items, data=data).get(name)
        if s:
            if parts and parts[-1][0] == s['id']:
                parts[-1][2] += end - t
            else:
                parts.append([s['id'], s['zone'], end - t])
        t = end
    parts = parts[-5:]

    def write():
        d = _state(room)
        d.setdefault('told', {})[name] = entry['n']
        _save(room, d)
    room.locked(write)
    if not parts:
        return ''
    return say('idle.diary', minutes=int((now - start) // 60),
               places=', '.join(say('idle.diary_part', minutes=max(1, int(p[2] // 60)), zone=zone_name(data, p[1], lang), id=p[0]) for p in parts))
