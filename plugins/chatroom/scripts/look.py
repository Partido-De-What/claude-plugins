"""chat.py vision FILE --ask "...": a picture, a long log or a page read by a free model with vision among the spawn hosts
(OpenRouter, the key of the spawn mode), which answers in a few lines; the agent keeps the verdict, not the pixels (141
frames read as images were about 8% of a night room, kept in context for good). The answer is kept by the file's and the
question's hash, so the same look costs once. Off unless the room turns it on (config vision=1): the file leaves the
machine; never for a research room's sealed files. When no host answers, the agent reads the picture as before."""
import base64
import hashlib
import json
import mimetypes
import os
import urllib.request
from pathlib import Path

PICTURES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
TEXT_MAX = 60_000
ASK = ('Answer in at most five short lines, facts only, about this file. Question: ')


def models(key):
    """free models with image input on OpenRouter, the largest context first"""
    req = urllib.request.Request('https://openrouter.ai/api/v1/models', headers={'Authorization': f'Bearer {key}'})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())['data']
    free = [m for m in data if str(m.get('id', '')).endswith(':free') and 'image' in ((m.get('architecture') or {}).get('input_modalities') or [])]
    return sorted(free, key=lambda m: -int(m.get('context_length') or 0))


def _sealed(room, path):
    try:
        c = json.loads((room.dir / 'research' / 'contract.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    p = Path(path).resolve().as_posix().lower()
    return any(p.endswith('/' + rel.lower()) for rel in (c.get('sealed') or {})) or bool(c.get('final') and Path(path).name in c['final'])


def look(room, path, ask, pick=models, call=None):
    """the verdict (a few lines), from the cache or a free model; ValueError when it cannot be asked"""
    src = Path(path)
    if str(room.config().get('vision', 0)) != '1':
        raise ValueError('look is off in this room: config vision=1 turns it on (the file leaves this machine)')   # shortcut: English until F8
    if not src.is_file():
        raise ValueError(f'no file {path}')
    if _sealed(room, src):
        raise ValueError(f'{src.name} is sealed in this research: it never leaves the machine')
    digest = hashlib.sha256(src.read_bytes() + (ask or '').encode()).hexdigest()[:16]
    cache = room.dir / 'look' / f'{digest}.md'
    if cache.is_file():
        return cache.read_text(encoding='utf-8')
    if src.suffix.lower() in PICTURES:
        import thumbs
        small = Path(thumbs.shrink(room.dir, src))          # a smaller upload; the answer does not need the full pixels
        mime = mimetypes.guess_type(small.name)[0] or 'image/png'
        content = [{'type': 'text', 'text': ASK + ask},
                   {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{base64.b64encode(small.read_bytes()).decode()}'}}]
    else:
        import squeeze
        text = src.read_text(encoding='utf-8', errors='replace')
        content = ASK + ask + '\n\n' + (squeeze.short(text, str(src)) if len(text) > TEXT_MAX else text)
    from spawn import keys
    key = os.environ.get('OPENROUTER_API_KEY') or (keys.load('open_router') or {}).get('key')
    if not key:
        raise ValueError('vision needs the OpenRouter key of the spawn mode (the Prepara spawn card)')
    if call is None:
        from spawn.providers import complete
        call = lambda model, msgs: (complete('open_router', model, msgs, key=key, max_tokens=600)['text'] or '').strip()
    errors = []
    for m in pick(key)[:3]:
        try:
            answer = call(m['id'], [{'role': 'user', 'content': content}])
        except Exception as exc:                          # the next model; none: the agent reads the file itself
            errors.append(f"{m['id']}: {str(exc)[:80]}")
            continue
        if answer:
            out = f"{answer}\n(look: {m['id']})"
            cache.parent.mkdir(exist_ok=True)
            cache.write_text(out, encoding='utf-8')
            return out
    raise ValueError('no free vision model answered (' + '; '.join(errors)[:300] + '): read the file itself')


def _prova():
    import sys
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import chat
    from PIL import Image
    d = Path(tempfile.mkdtemp(prefix='look_'))
    (d / 'config.json').write_text('{"vision": 1}')
    room = chat.Room(d)
    Image.new('RGB', (1920, 1080), 'red').save(d / 'frame.png')
    seen = []
    fake_pick = lambda key: [{'id': 'm1:free'}, {'id': 'm2:free'}]

    def fake_call(model, msgs):
        seen.append(model)
        if model == 'm1:free':
            raise RuntimeError('busy')
        return 'The frame is all red. No text.'
    os.environ['OPENROUTER_API_KEY'] = 'test-key'
    out = look(room, d / 'frame.png', 'what is in it?', fake_pick, fake_call)
    assert out.startswith('The frame is all red') and seen == ['m1:free', 'm2:free'], (out, seen)
    assert look(room, d / 'frame.png', 'what is in it?', fake_pick, lambda m, x: 1 / 0) == out   # cached: no second call
    (d / 'config.json').write_text('{}')
    try:
        look(room, d / 'frame.png', 'x', fake_pick, fake_call)
        raise AssertionError('look ran in a room that did not turn it on')
    except ValueError:
        pass
    print('look prova ok')


if __name__ == '__main__':
    _prova()
