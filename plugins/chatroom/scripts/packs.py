"""External packs for the 3D office: furniture models and character looks you add yourself.

A pack is one JSON file in ~/.claude/chatroom/packs/ (the viewer asks for them at /packs.json); a pack that is not valid is
skipped and reported, never half loaded:

    {"format": "chatroom-pack", "version": 1, "id": "my-pack", "name": "My pack", "author": "Name", "license": "CC-BY-4.0",
     "source": "https://...",
     "models": {"Desk/Big": {"s": [16, 16, 16], "p": ["#202020"], "v": "<base64 of x,y,z,colour-index bytes>"}},
     "looks": {"Dev": {"skin": "#c68642", "hair": "#2b1b10", "style": "short", "outfit": "hoodie", "top": "#3a7bd5",
                       "pants": "#1f2230", "glasses": true, "headphones": false}}}

A model has the shape of vendor/office-pack.json (made from MagicaVoxel .vox files by tools/vox_bundle.py); its name in the
office is "<id>/<model>" (an item of the layout says `pack: "my-pack/Desk/Big"`), so a pack never replaces a built-in
model. A look is a preset of your own figure (the 👤 panel). Make a pack from a folder of .vox files:

    python packs.py make SOURCE_DIR OUT.json --id my-pack --name "My pack" --author "Name" --license CC-BY-4.0

Test: python packs.py --prova"""
import argparse
import base64
import binascii
import json
import os
import re
import sys
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')
FORMAT = 'chatroom-pack'
MAX_FILE = 12 * 1024 * 1024                  # bytes of one pack file
MAX_MODELS, MAX_PACKS, MAX_VOXELS = 400, 40, 60000
ID = re.compile(r'[a-z0-9][a-z0-9-]{0,30}')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_ .-]{0,59}(/[A-Za-z0-9][A-Za-z0-9_ .-]{0,59}){0,3}')
HEX = re.compile(r'#[0-9a-fA-F]{6}')
STYLES = ('short', 'spiky', 'bob', 'bun', 'cap', 'beanie', 'long', 'bald')       # the same lists as LOOK in office-voxel.js
OUTFITS = ('suit', 'cardigan', 'hoodie', 'polo')


def check_model(m):
    """the model as it will be served, or ValueError"""
    if not isinstance(m, dict) or not (isinstance(m.get('s'), list) and len(m['s']) == 3 and all(isinstance(n, int) and 0 < n <= 256 for n in m['s'])):
        raise ValueError('s must be three sizes')
    pal = m.get('p')
    if not isinstance(pal, list) or not 0 < len(pal) <= 256 or not all(isinstance(c, str) and HEX.fullmatch(c) for c in pal):
        raise ValueError('p must be 1-256 colours #rrggbb')
    try:
        raw = base64.b64decode(str(m.get('v', '')), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('v is not base64') from None
    if not raw or len(raw) % 4 or len(raw) // 4 > MAX_VOXELS:
        raise ValueError(f'v must be 1-{MAX_VOXELS} voxels of four bytes')
    if max(raw[3::4]) >= len(pal):
        raise ValueError('a voxel uses a colour that is not in p')
    return {'s': m['s'], 'p': [c.lower() for c in pal], 'v': base64.b64encode(raw).decode('ascii')}


def check_look(look):
    if not isinstance(look, dict):
        raise ValueError('a look is an object')
    out = {}
    for k, v in look.items():
        if k in ('skin', 'hair', 'top', 'pants') and isinstance(v, str) and HEX.fullmatch(v):
            out[k] = v.lower()
        elif k == 'style' and v in STYLES or k == 'outfit' and v in OUTFITS:
            out[k] = v
        elif k in ('glasses', 'headphones') and isinstance(v, bool):
            out[k] = v
        else:
            raise ValueError(f'look {k}: not an accepted value')
    return out


def check_pack(d):
    """(info, models, looks) of a pack read from JSON, or ValueError"""
    if not isinstance(d, dict) or d.get('format') != FORMAT or d.get('version') != 1:
        raise ValueError(f'not a {FORMAT} version 1')
    pid = str(d.get('id', ''))
    if not ID.fullmatch(pid):
        raise ValueError('id: lower case letters, digits and dashes')
    models, looks = {}, {}
    for name, m in (d.get('models') or {}).items():
        if not NAME.fullmatch(str(name)) or len(models) >= MAX_MODELS:
            raise ValueError(f'model name {str(name)[:40]!r} refused')
        models[f'{pid}/{name}'] = check_model(m)
    for name, look in (d.get('looks') or {}).items():
        if not re.fullmatch(r'[A-Za-z0-9_ .-]{1,40}', str(name)):
            raise ValueError(f'look name {str(name)[:40]!r} refused')
        looks[f'{name}'] = check_look(look)
    text = lambda k, n: str(d.get(k, ''))[:n]
    info = {'id': pid, 'name': text('name', 80) or pid, 'author': text('author', 80), 'license': text('license', 40), 'source': text('source', 200),
            'models': len(models), 'looks': len(looks)}
    return info, models, looks


def load(folder=None):
    """every pack of the folder: {'models': {id/name: model}, 'looks': {name: look}, 'packs': [info], 'errors': [text]}"""
    folder = Path(folder) if folder else CLAUDE_DIR / 'chatroom' / 'packs'
    out = {'models': {}, 'looks': {}, 'packs': [], 'errors': []}
    for path in sorted(folder.glob('*.json'))[:MAX_PACKS]:
        try:
            if path.stat().st_size > MAX_FILE:
                raise ValueError('file too big')
            info, models, looks = check_pack(json.loads(path.read_text(encoding='utf-8')))
            if any(p['id'] == info['id'] for p in out['packs']):
                raise ValueError(f"id {info['id']} already loaded")
        except (OSError, ValueError, TypeError, UnicodeDecodeError) as exc:
            out['errors'].append(f'{path.name}: {exc}')
            continue
        out['models'].update(models)
        out['looks'].update({f'{k} ({info["id"]})': v for k, v in looks.items()})
        out['packs'].append(info)
    return out


def make(source, out, pid, name, author, license_, source_url=''):
    """a pack file from a folder of MagicaVoxel .vox files"""
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
    import vox_bundle
    models = {}
    for p in sorted(Path(source).rglob('*.vox')):
        models[p.relative_to(source).with_suffix('').as_posix()] = vox_bundle.pack(*vox_bundle.read_vox(p.read_bytes()))
    pack = {'format': FORMAT, 'version': 1, 'id': pid, 'name': name, 'author': author, 'license': license_, 'source': source_url, 'models': models, 'looks': {}}
    check_pack(pack)                                        # what is written loads
    Path(out).write_text(json.dumps(pack, separators=(',', ':')), encoding='utf-8')
    return len(models)


def _prova():
    """self-check: a good pack loads with prefixed names; every kind of bad pack is refused with a reason and the others still load"""
    import tempfile
    model = {'s': [2, 1, 1], 'p': ['#AA0000', '#00aa00'], 'v': base64.b64encode(bytes([0, 0, 0, 0, 1, 0, 0, 1])).decode()}
    good = {'format': FORMAT, 'version': 1, 'id': 'my-pack', 'name': 'Mine', 'author': 'A', 'license': 'CC0', 'models': {'Desk/Big': model},
            'looks': {'Dev': {'skin': '#C68642', 'style': 'bun', 'outfit': 'hoodie', 'glasses': True}}}
    bad = {
        'wrong-format': {**good, 'format': 'x'}, 'bad-id': {**good, 'id': 'My Pack'}, 'bad-name': {**good, 'id': 'b1', 'models': {'../x': model}},
        'bad-colour': {**good, 'id': 'b2', 'models': {'M': {**model, 'p': ['red']}}},
        'index': {**good, 'id': 'b3', 'models': {'M': {**model, 'v': base64.b64encode(bytes([0, 0, 0, 5])).decode()}}},
        'b64': {**good, 'id': 'b4', 'models': {'M': {**model, 'v': '!!'}}},
        'look': {**good, 'id': 'b5', 'looks': {'X': {'style': 'mohawk'}}},
        'dup': {**good, 'name': 'again'},
    }
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / '1-good.json').write_text(json.dumps(good))
        for k, v in bad.items():
            (Path(tmp) / f'2-{k}.json').write_text(json.dumps(v))
        (Path(tmp) / '3-broken.json').write_text('{not json')
        r = load(tmp)
        assert [p['id'] for p in r['packs']] == ['my-pack'] and list(r['models']) == ['my-pack/Desk/Big'], r['packs']
        assert r['models']['my-pack/Desk/Big']['p'] == ['#aa0000', '#00aa00'] and r['looks'] == {'Dev (my-pack)': {'skin': '#c68642', 'style': 'bun', 'outfit': 'hoodie', 'glasses': True}}
        assert len(r['errors']) == len(bad) + 1 and all(e.split(':')[0].endswith('.json') for e in r['errors']), r['errors']
        assert load(Path(tmp) / 'nothing') == {'models': {}, 'looks': {}, 'packs': [], 'errors': []}
        src = Path(tmp) / 'src'; src.mkdir()                                            # make: a .vox in, a pack out that loads
        sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
        import struct
        chunk = lambda cid, body: cid + struct.pack('<ii', len(body), 0) + body
        kids = chunk(b'SIZE', struct.pack('<iii', 2, 1, 1)) + chunk(b'XYZI', struct.pack('<i', 2) + bytes([0, 0, 0, 5, 1, 0, 0, 9]))
        (src / 'Lamp.vox').write_bytes(b'VOX ' + struct.pack('<i', 150) + b'MAIN' + struct.pack('<ii', 0, len(kids)) + kids)
        assert make(src, Path(tmp) / 'made.json', 'made', 'Made', 'Me', 'CC0') == 1
        (Path(tmp) / 'made.json').rename(Path(tmp) / '0-made.json')
        assert 'made/Lamp' in load(tmp)['models']
    print('packs.py: prova ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
    elif len(sys.argv) > 1 and sys.argv[1] == 'make':
        ap = argparse.ArgumentParser(prog='packs.py make')
        ap.add_argument('make'); ap.add_argument('source'); ap.add_argument('out')
        ap.add_argument('--id', required=True); ap.add_argument('--name', required=True); ap.add_argument('--author', default='')
        ap.add_argument('--license', default=''); ap.add_argument('--source-url', default='')
        a = ap.parse_args()
        print(f'{make(a.source, a.out, a.id, a.name, a.author, a.license, a.source_url)} models -> {a.out}')
    else:
        print(json.dumps(load(), ensure_ascii=False)[:2000])
