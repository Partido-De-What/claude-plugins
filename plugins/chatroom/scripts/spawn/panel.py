"""The Spawn view of the viewer (?view=spawn, the 🛸 button): one full-window panel with three tabs (Keys, Models, Roles)
instead of cards in the chat. This module gives it plain data and runs its clicks; the drawing is spawn-view.js.

  GET  /spawn/state.json            keys and tools, the catalog one row per line, the roles
  GET  /spawn/model.json?c=ID       one model: hosts, its strongest benchmarks first (with what each one measures and who
                                    measured it), every other score, its versions
  POST /spawn/do {action, ...}      save/check/skip a key, log in to OpenRouter, update or study the catalog, create, replace
                                    or stop a role, move a model to another line"""
import json
from pathlib import Path
from urllib.parse import urlparse

from i18n import lang_of, say, use

SOURCES = {'artificialanalysis.ai': 'Artificial Analysis', 'vals.ai': 'Vals AI', 'benchlm.ai': 'BenchLM', 'lmarena.ai': 'LMArena',
           'arena.ai': 'LMArena', 'openrouter.ai': 'OpenRouter', 'designarena.ai': 'Design Arena', 'huggingface.co': 'Hugging Face',
           'swebench.com': 'SWE-bench', 'gorilla.cs.berkeley.edu': 'BFCL', 'eqbench.com': 'EQ-Bench', 'tbench.ai': 'Terminal-Bench',
           'aider.chat': 'Aider', 'arcprize.org': 'ARC Prize', 'scale.com': 'Scale', 'epoch.ai': 'Epoch AI'}


def _lang(room):
    use(lang_of(room.config()), here=True)
    return lang_of(room.config())


def _source(s):
    """who measured a score, in words: the leaderboard's name, or the maker when the maker published it"""
    host = urlparse(str(s.get('source') or '')).netloc.lower().removeprefix('www.')
    if not s.get('independent'):
        return {'kind': 'maker', 'label': say('spawnv.src.maker'), 'url': s.get('source', '')}
    name = next((v for k, v in SOURCES.items() if host == k or host.endswith('.' + k)), host or '?')
    return {'kind': 'measured', 'label': say('spawnv.src.measured', who=name), 'url': s.get('source', '')}


def _bench(s, gl, lang, frontier=None):
    from spawn.bench import strengths
    g = strengths.entry(s.get('bench'), gl) or {}
    name = g.get('name') or s.get('bench')
    if g and g.get('id') != s.get('bench'):            # a family's member (design-arena-3d): the family's name and its part
        name += ' · ' + str(s.get('bench'))[len(g['id']) + 1:].replace('-', ' ')
    return {'bench': s.get('bench'), 'name': name, 'what': g.get(lang) or g.get('en') or '',
            'area': s.get('area') or g.get('area') or 'other', 'value': s.get('value'), 'unit': g.get('unit', ''),
            'better': g.get('better', 'higher'), 'rank': s.get('rank'), 'of': s.get('of'), 'trophy': bool(s.get('trophy')),
            'frontier': s.get('frontier', frontier), 'date': s.get('date', ''), 'source': _source(s)}


def _quotas():
    try:
        from spawn.limiter import LIMITER
        q = LIMITER.routes()
        return q if isinstance(q, dict) else {}
    except (ImportError, AttributeError):
        return {}


def _hosts(m, quotas):
    out = []
    for r in m.get('routes') or []:
        if not r.get('free'):
            continue
        q, ping = quotas.get(f"{r.get('adapter')}:{r.get('model_id')}") or {}, r.get('ping') or {}
        out.append({'adapter': r.get('adapter'), 'model_id': r.get('model_id'), 'ctx': r.get('ctx'), 'tools': r.get('tools'),
                    'ping_ms': ping.get('ms'), 'up': ping.get('ok'), 'quota': q.get('quota'), 'left': q.get('remaining_requests'),
                    'limit': q.get('limit_requests'), 'reset_s': q.get('reset_s'), 'r429': q.get('recent_429'), 'down': bool(q.get('down'))})
    return out


UPPER = {'glm', 'gpt', 'oss', 'vl', 'ai', 'aa', 'lfm', 'r1', 'tts', 'ocr', 'moe'}
MAKERS = {'z-ai': 'Z.ai', 'zai-org': 'Z.ai', 'qwen': 'Qwen', 'deepseek-ai': 'DeepSeek', 'deepseek': 'DeepSeek', 'moonshotai': 'Moonshot',
          'nvidia': 'NVIDIA', 'google': 'Google', 'meta-llama': 'Meta', 'meta': 'Meta', 'mistralai': 'Mistral', 'mistral': 'Mistral',
          'openai': 'OpenAI', 'minimax': 'MiniMax', 'minimaxai': 'MiniMax', 'stepfun-ai': 'StepFun', 'stepfun': 'StepFun',
          'cohere': 'Cohere', 'poolside': 'Poolside', 'liquid': 'Liquid', 'thinkingmachines': 'Thinking Machines', 'xiaomi': 'Xiaomi',
          'tencent': 'Tencent', 'inclusionai': 'inclusionAI', 'microsoft': 'Microsoft', 'ibm': 'IBM', 'ibm-granite': 'IBM'}


def _name(m):
    """a readable name: GLM 5.3, Qwen 3.8 Max, Kimi K3, Nemotron 3 Ultra (owner, free tags and sizes like 550b-a55b away)"""
    import re
    n = re.sub(r'(:free|[-_]free|:batch)$', '', str(m.get('name') or m['canonical']).split('/')[-1], flags=re.I)
    n = re.sub(r'^([a-z]+)(\d)', r'\1 \2', n, flags=re.I)                       # qwen3.8 -> qwen 3.8
    parts = [w for w in re.split(r'[-_ ]+', n) if w]
    moe = any(re.fullmatch(r'a\d+(\.\d+)?b', w, re.I) for w in parts)          # 550b-a55b: a mixture's sizes say nothing to a reader
    words = [w.upper() if re.fullmatch(r'\d+(\.\d+)?b', w, re.I) else w for w in parts
             if not re.fullmatch(r'a\d+(\.\d+)?b|bf16|fp8|it|instruct|tee', w, re.I) and not (moe and re.fullmatch(r'\d+(\.\d+)?b', w, re.I))]
    out = ' '.join(w.upper() if w.lower() in UPPER else w if any(ch.isupper() for ch in w[1:]) else w[:1].upper() + w[1:] for w in words)
    return out or m['canonical']


def _maker(m):
    owner = str(m.get('name') or '').split('/')[0].lower() if '/' in str(m.get('name') or '') else ''
    return MAKERS.get(owner, owner.replace('-', ' ').title() if owner else '')


def _probe(m):
    p = m.get('probe') or {}
    return {'ok': p.get('ok'), 'ms': p.get('ms'), 'error': p.get('error'), 'host': p.get('host'), 'at': p.get('at')} if p else None


def _profile(m, lang):
    """the profiler's card in the room's language: what it is, status, level next to known models, free limits per host"""
    p = m.get('profile') or {}
    if not p:
        return None
    other = 'en' if lang == 'it' else 'it'
    return {'what': p.get(lang) or p.get(other) or '', 'status': p.get('status', 'unknown'), 'successor': p.get('successor', ''),
            'level': p.get('level_' + lang) or p.get('level_' + other) or '', 'basis': p.get('basis', ''),
            'limits': p.get('limits') or [], 'sources': p.get('sources') or []}


def _summary(m, quotas, lang='it'):
    hosts = _hosts(m, quotas)
    pings = [h['ping_ms'] for h in hosts if h['ping_ms']]
    return {'c': m['canonical'], 'name': _name(m), 'maker': _maker(m), 'aa': m.get('aa'), 'areas': [a for a in (m.get('areas_best') or []) if a != 'other'][:3],
            'hosts': len(hosts), 'ping_ms': min(pings) if pings else None, 'ctx': max((h['ctx'] or 0) for h in hosts) if hosts else None,
            'tools': any(h['tools'] for h in hosts), 'partial': m.get('state') in ('pending', 'partial'), 'params_b': m.get('params_b'),
            'probe': _probe(m), 'status': (m.get('profile') or {}).get('status'), 'level': (_profile(m, lang) or {}).get('level', '')}


def state(room):
    """everything the three tabs show, in one answer (the page polls it every few seconds while the view is open)"""
    lang = _lang(room)
    from spawn import cards_spawn, keys, runner
    from spawn.bench import strengths
    from spawn.catalog import catalog as c
    skipped = set(cards_spawn._setup().get('skipped', []))
    provs, ready = [], 0
    for pid, p in keys.status().items():
        ks = p.get('keys', [])
        sts, saved = [k.get('state') for k in ks], any(k.get('why') == 'no_probe' for k in ks)
        st = ('ok' if 'verified' in sts else 'saved' if saved and 'rejected' not in sts else 'bad' if 'rejected' in sts
              else 'skipped' if pid in skipped else 'none' if not ks else 'saved')
        ready += st in ('ok', 'saved')
        provs.append({'id': pid, 'name': p.get('name', pid), 'offer': p.get('offer', ''), 'signup': p.get('signup', ''), 'state': st,
                      'pkce': p.get('pkce'), 'extra': p.get('extra', []), 'can_verify': p.get('can_verify')})
    cat, quotas = c.load(), _quotas()
    models = [m for m in cat.get('models', []) if any(r.get('free') for r in m.get('routes') or [])]
    lines = []
    for g in c.lines(models):
        row = _summary(g['newest'], quotas, lang)
        row['older'] = [_summary(o, quotas, lang) for o in g['older']]
        row['doubt'] = bool(g.get('doubt'))
        lines.append(row)
    lines.sort(key=lambda r: (r['aa'] is None, -(r['aa'] or 0), r['name']))
    areas = {k: (v.get(lang) or v.get('en') or k) for k, v in (strengths.load_glossary().get('_meta', {}).get('areas') or {}).items()}
    roles = [{'name': n, 'mission': r.get('mission', ''), 'model': r.get('canonical') or (r.get('route') or {}).get('model_id', ''),
              'host': (r.get('route') or {}).get('adapter', ''), 'state': r.get('state', 'service'), 'usage': r.get('usage') or {},
              'compact': bool(r.get('compact')), 'error': r.get('error') or '', 'shell': 'shell' in (r.get('tools') or [])}
             for n, r in sorted(runner.roles(room).items())]
    return {'lang': lang, 'tools': cards_spawn.tools_state(), 'providers': provs, 'ready': ready,
            'catalog': {'updated': cat.get('updated'), 'sources': {k: {'ok': v.get('ok'), 'count': v.get('count'), 'error': v.get('error')}
                                                                   for k, v in (cat.get('providers') or {}).items()},
                        'lines': lines, 'updating': bool(getattr(state, 'updating', False)), 'error': getattr(state, 'error', ''),
                        'probing': dict(c.PROBE)},
            'areas': areas, 'roles': roles}


def model(room, canonical):
    """one model, strongest benchmarks first: each with what it measures, the value, the rank among the models measured,
    a bar against the best, and who measured it (a leaderboard, or the maker)"""
    lang = _lang(room)
    from spawn.bench import strengths
    from spawn.catalog import catalog as c
    from spawn.catalog.identity import line_key
    cat = c.load()
    m = next((x for x in cat.get('models', []) if x.get('canonical') == canonical), None)
    if not m:
        raise ValueError(say('spawn.err.noModel', model=canonical))
    gl = strengths.load_glossary()
    front = {s.get('bench'): s.get('frontier') for s in m.get('scores') or []}
    full = {s.get('bench'): s for s in m.get('scores') or []}        # a strength carries rank and weight; source and date are in its score
    strong = sorted(({**full.get(s.get('bench'), {}), **s} for s in m.get('strengths') or []),
                    key=lambda s: (-bool(s.get('trophy')), -(s.get('weight') or 0)))
    picked = {s.get('bench') for s in strong}
    others = sorted([s for s in m.get('scores') or [] if s.get('bench') not in picked and not str(s.get('bench', '')).endswith('-index')
                     and s.get('bench') not in ('aa-output-speed', 'aa-price-blended', 'aa-ttft')],
                    key=lambda s: -(s.get('frontier') or 0))
    idx = {s['bench']: s['value'] for s in m.get('scores') or [] if str(s.get('bench', '')).endswith('-index')}
    speed = {s['bench']: s['value'] for s in m.get('scores') or [] if s.get('bench') in ('aa-output-speed', 'aa-ttft')}
    line = line_key(canonical)[0]
    versions = [{'c': x['canonical'], 'name': _name(x), 'aa': x.get('aa')}
                for x in cat.get('models', []) if x['canonical'] != canonical and line_key(x['canonical'])[0] == line]
    maker = canonical.split('/')[0]
    near = sorted({line_key(x['canonical'])[0] for x in cat.get('models', []) if x['canonical'].split('/')[0] == maker} - {line})
    return {'c': canonical, 'name': _name(m), 'maker': _maker(m), 'aa': m.get('aa'), 'indexes': idx, 'speed': speed,
            'areas': [a for a in (m.get('areas_best') or []) if a != 'other'], 'partial': m.get('state') in ('pending', 'partial'),
            'hosts': _hosts(m, _quotas()), 'strong': [_bench(s, gl, lang, front.get(s.get('bench'))) for s in strong[:10]],
            'others': [_bench(s, gl, lang) for s in others], 'versions': versions, 'line': line, 'near': near,
            'profile': _profile(m, lang), 'probe': _probe(m)}


def do(room, body):
    """one click of the view; returns {'ok': True, 'note': text} or raises ValueError with the reason to show"""
    _lang(room)
    from spawn import cards_spawn, keys, runner
    from spawn.catalog import catalog as c
    act, pid = body.get('action', ''), body.get('provider', '')
    setup = cards_spawn._setup()
    skipped = set(setup.get('skipped', []))
    note, extra = '', {}
    if act == 'save_key':
        k = str(body.get('key') or '').strip()
        if not k:
            raise ValueError(say('spawn.err.noKey'))
        slot = keys.save(pid, k, {x: str(v).strip() for x, v in (body.get('extra') or {}).items() if str(v).strip()} or None)
        st, _ = keys.check(pid, slot)
        skipped.discard(pid)
        note = say(f'spawn.prep.{st}')
    elif act == 'check_key':
        note = say(f'spawn.prep.{keys.check(pid)[0]}')
    elif act == 'skip':
        skipped.add(pid)
    elif act == 'unskip':
        skipped.discard(pid)
    elif act == 'skip_rest':
        skipped |= {p for p, v in keys.status().items() if not v.get('keys')}
    elif act == 'login':
        extra['open'] = keys.pkce_start(cards_spawn._viewer_url(room) + '/spawn/oauth')[0]
    elif act == 'install_headroom':
        import chat
        chat.start_headroom_install()
        note = say('viewer.hrBusy')
    elif act == 'update':
        _update(room, bool(body.get('force')))
        note = say('spawn.cat.updating')
    elif act == 'probe':
        if not c.PROBE['running']:
            import threading
            c.PROBE['running'] = True                       # set here, so a second click before the thread starts does nothing
            threading.Thread(target=c.probe, kwargs={'only': body.get('only')}, daemon=True).start()
        note = say('spawnv.probing')
    elif act == 'study':
        asked = c.study(room.dir, lang_of(room.config()))
        note = (say('spawn.cat.studyAsked', k=len(asked), n=sum(len(e['models']) for e in asked if e['kind'] == 'model'))
                if asked else say('spawn.cat.studyNone'))
    elif act == 'create':
        name, canonical = str(body.get('name') or '').strip().upper(), str(body.get('model') or '')
        routes = runner.routes_of(canonical)
        if not routes:
            raise ValueError(say('spawn.err.noRoute', model=canonical))
        route = cards_spawn._host(runner, room, canonical, routes)
        runner.create(room, name, str(body.get('mission') or '').strip() or name, canonical, route,
                      tools=('shell',) if body.get('shell') else ())
        note = say('spawn.role.created', name=name, model=canonical, provider=route['adapter'])
    elif act == 'replace':
        name, canonical = str(body.get('role') or ''), str(body.get('model') or '')
        routes = runner.routes_of(canonical)
        if not routes:
            raise ValueError(say('spawn.err.noRoute', model=canonical))
        route = cards_spawn._host(runner, room, canonical, routes, name)
        runner.replace(room, name, canonical, route)
        note = say('spawn.role.replaced', name=name, model=canonical, provider=route['adapter'])
    elif act == 'stop':
        runner.stop(room, str(body.get('role') or ''))
        note = say('spawnv.stopped', name=body.get('role', ''))
    elif act in ('move', 'split'):
        canonical = str(body.get('model') or '')
        c.move_line(canonical, str(body.get('line') or '')) if act == 'move' else c.split_line(canonical)
        note = say('spawn.sheet.moved' if act == 'move' else 'spawn.sheet.splitDone', model=canonical, line=body.get('line', ''))
    else:
        raise ValueError(say('spawn.err.action', action=act))
    cards_spawn._save_setup({**setup, 'skipped': sorted(skipped)})
    return {'ok': True, 'note': note, **extra}


def _update(room, force=False):
    """the catalog's round in a thread (network); the view sees `updating` until it ends, then the new catalog"""
    import threading
    if getattr(state, 'updating', False):
        return

    def run():
        from spawn.catalog import catalog as c
        try:
            from spawn import keys
            from spawn.limiter import LIMITER
            k = keys.load('open_router')
            if k:
                LIMITER.refresh_openrouter(k['key'])
        except Exception:
            pass
        try:
            c.update(room.dir, force)
            state.error = ''
        except Exception as exc:                          # a network or file error: the view says it, never with a key in it
            state.error = type(exc).__name__
        finally:
            state.updating = False
    state.updating = True
    threading.Thread(target=run, daemon=True).start()


def _prova():
    """offline: the source labels and the order of the strengths"""
    use('it', here=True)
    assert _source({'source': 'https://artificialanalysis.ai/models/x', 'independent': True})['label'].endswith('Artificial Analysis')
    assert _source({'source': 'https://mistral.ai/news/x', 'independent': False})['kind'] == 'maker'
    assert _source({'source': 'https://www.vals.ai/benchmarks/x', 'independent': True})['label'].endswith('Vals AI')
    print('panel ok')


if __name__ == '__main__':
    _prova()
