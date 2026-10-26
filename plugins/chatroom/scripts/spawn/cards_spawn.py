"""The cards of the spawn mode, as data for cards.py: Prepara spawn (keys, Headroom, RTK), Catalogo (every free model,
with its AA value, routes and ping), Scheda modello (scores with their source, the 10 strong points, the routes), Confronto
(the same benchmarks side by side). Each builder reads what the others publish (keys.status() of spawn.keys, the catalog
of spawn.catalog, the glossary bench_glossary.json) and returns {title, icon, blocks}; card_action answers a click.
Texts in the room's language (locales spawn.*); benchmark descriptions from the glossary, in the same language."""
import json
import shutil
import time
from pathlib import Path

from i18n import lang_of, say, use

HERE = Path(__file__).resolve().parent.parent
TOP = 15                                         # models in the catalog card and in the AA chart


def _setup_path():
    return Path.home() / '.claude' / 'chatroom' / 'spawn' / 'setup.json'      # Path.home each time: tests use a fake HOME


def _setup():
    try:
        d = json.loads(_setup_path().read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_setup(d):
    p = _setup_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(d), encoding='utf-8')
    tmp.replace(p)


def glossary():
    """the plugin's glossary with the benchmarks the researcher found (spawn.bench.strengths)"""
    from spawn.bench import strengths
    try:
        g = strengths.load_glossary()
    except (OSError, ValueError, KeyError):
        g = {}
    return {b['id']: b for b in g.get('benchmarks', []) if isinstance(b, dict) and b.get('id')}, (g.get('_meta') or {}).get('areas') or {}


# ------------------------------------------------------------------ Prepara spawn
def tools_state():
    """Headroom importable, RTK on the PATH (or where the plugin keeps it)"""
    import importlib.util
    rtk = shutil.which('rtk') or shutil.which('rtk-oss')
    return {'headroom': importlib.util.find_spec('headroom') is not None, 'rtk': bool(rtk)}


SHOWN = 6                                        # providers still to set up drawn whole; the others behind "N more"


def prepare(keys_status, tools, skipped, full=False):
    """the setup card: every free provider (link, offer, key field, verify, skip), then Headroom and RTK; spawn starts
    only when every provider has a verified (or at least saved) key or was skipped, and Headroom and RTK are there.
    Short on a phone: the ready and the skipped ones in one line each, at most SHOWN to do unless full"""
    rows, missing = [], 0
    for pid, p in keys_status.items():
        states = [k.get('state') for k in p.get('keys', [])]
        state = 'ok' if 'verified' in states else 'warn' if states and 'rejected' not in states else 'bad' if states else 'wait'
        if pid in skipped and state != 'ok':
            state, value = 'warn', say('spawn.prep.skipped')
        else:
            value = p.get('offer', '') + (' · ' + say('spawn.prep.keys', n=len(states)) if states else '')
            missing += state in ('bad', 'wait')
        row = {'key': pid, 'label': p.get('name', pid), 'value': value, 'state': state, 'link': p.get('signup', ''),
               'link_label': say('spawn.prep.signup')}
        if state != 'ok':
            row['fields'] = [{'name': 'key', 'type': 'password', 'placeholder': say('spawn.prep.key')}] + \
                            [{'name': x, 'type': 'text', 'placeholder': x} for x in p.get('extra', [])]
            row['actions'] = ([{'id': 'login', 'label': say('spawn.prep.login')}] if p.get('pkce') else []) + \
                             [{'id': 'save', 'label': say('spawn.prep.save')}] + \
                             ([] if pid in skipped else [{'id': 'skip', 'label': say('spawn.prep.skip'), 'confirm': say('spawn.prep.skipConfirm', name=p.get('name', pid))}])
        else:
            row['actions'] = [{'id': 'check', 'label': say('spawn.prep.check')}]
        rows.append(row)
    trows = [{'key': t, 'label': name, 'state': 'ok' if tools.get(t) else 'bad',
              'value': say('spawn.prep.toolOk') if tools.get(t) else say(f'spawn.prep.{t}Missing')}
             for t, name in (('headroom', 'Headroom'), ('rtk', 'RTK'))]
    if not tools.get('headroom'):
        trows[0]['actions'] = [{'id': 'install_headroom', 'label': say('spawn.prep.install'), 'confirm': say('viewer.hrConfirm')}]
    ready = not missing and all(tools.get(t) for t in ('headroom', 'rtk'))
    done = [r['label'] for r in rows if r['state'] == 'ok']
    away = [r['label'] for r in rows if r['key'] in skipped and r['state'] != 'ok']
    todo = rows if full else [r for r in rows if r['state'] != 'ok' and r['key'] not in skipped]
    more = len(todo) - SHOWN if not full and len(todo) > SHOWN else 0
    blocks = [{'t': 'text', 'text': say('spawn.prep.intro')}]
    if not full:
        blocks += [{'t': 'text', 'text': say(k, names=', '.join(v))} for k, v in (('spawn.prep.done', done), ('spawn.prep.away', away)) if v]
    blocks += [{'t': 'rows', 'rows': todo[:SHOWN] if more else todo}, {'t': 'rows', 'rows': trows},
               {'t': 'actions', 'items': ([] if full else [{'id': 'more', 'label': say('spawn.prep.more', n=more) if more else say('spawn.prep.all')}])
                + [{'id': 'start', 'label': say('spawn.prep.start'), 'disabled': not ready}]}]
    return {'title': say('spawn.prep.title'), 'icon': '🔑', 'blocks': blocks, 'full': full,
            'note': say('spawn.prep.ready') if ready else say('spawn.prep.left', n=missing)}


# ------------------------------------------------------------------ Catalogo, Scheda, Confronto
def _best_route(m):
    routes = m.get('routes') or []
    up = [r for r in routes if (r.get('ping') or {}).get('ok')]
    return min(up, key=lambda r: (r.get('ping') or {}).get('ms') or 1e9) if up else (routes[0] if routes else {})


def _free(m):
    return any(r.get('free') for r in m.get('routes') or [])


def _ctx(n):
    return f'{round(n / 1000)}k' if n else '—'


def _quotas():
    """what the limiter knows of each route's quota (PORTE, T30): {"adapter:model_id": {...}}; {} before it knows"""
    try:
        from spawn.limiter import LIMITER
        q = LIMITER.routes()
        return q if isinstance(q, dict) else {}
    except (ImportError, AttributeError):
        return {}


def _quota_text(q):
    """quota 37/50 · reset 12 s · 2×429, from what the provider said; '' when it said nothing"""
    q = q or {}
    left, top = q.get('remaining_requests'), q.get('limit_requests')
    bits = [say('spawn.q.left', left=left, top=top) if left is not None and top else
            say('spawn.q.pct', pct=round(q['quota'] * 100)) if q.get('quota') is not None else '',
            say('spawn.q.reset', s=round(q['reset_s'])) if q.get('reset_s') else '',
            f"{q['recent_429']}×429" if q.get('recent_429') else '', say('spawn.q.down') if q.get('down') else '']
    return ' · '.join(b for b in bits if b)


def _lines(models):
    """[(newest, [older, ...])]: one entry per line of models, newest first (CATALOGO's one rule, catalog.lines and
    identity.line_key, T29: glm-5, 5.2, 5.3 are one line, qwen3-coder and qwen3.8 two), in the order of `models`"""
    from spawn.catalog import catalog as c
    return [(g['newest'], g['older']) for g in c.lines(models)]


def _line(canonical):
    from spawn.catalog.identity import line_key
    return line_key(canonical)[0] or canonical


def _model_row(m, quotas):
    r = _best_route(m)
    ping = r.get('ping') or {}
    q = quotas.get(f"{r.get('adapter')}:{r.get('model_id')}") or {}
    state = 'bad' if q.get('down') else 'ok' if ping.get('ok') else 'bad' if ping and not ping.get('ok') else 'wait'
    bits = [f"AA {m['aa']:g}" if m.get('aa') is not None else 'AA n.d.', say('spawn.cat.routes', n=len(m.get('routes') or [])),
            f"{ping['ms']} ms" if ping.get('ms') else '', 'ctx ' + _ctx(r.get('ctx')), _quota_text(q)]
    if m.get('areas_best'):
        bits.append(say('spawn.cat.best') + ' ' + ', '.join(m['areas_best'][:3]))
    if m.get('state') in ('pending', 'partial'):
        bits.append(say('spawn.cat.partial'))
    return {'key': m['canonical'], 'label': m.get('name') or m['canonical'], 'value': ' · '.join(b for b in bits if b), 'state': state,
            'actions': [{'id': 'sheet', 'label': say('spawn.cat.sheet')}, {'id': 'compare', 'label': say('spawn.cat.compare')},
                        {'id': 'role', 'label': say('spawn.cat.role')}]}


def catalog(cat):
    """the free models (D12: the 0.13 uses only free ones), one row per line with its newest version, best AA first (AA,
    routes, best ping, context, quota left); the older versions of a line under "older versions (N)", still choosable;
    the AA chart of the top lines"""
    models = [m for m in cat.get('models', []) if _free(m)]
    models.sort(key=lambda m: (m.get('aa') is None, -(m.get('aa') or 0), m.get('name') or m.get('canonical', '')))
    lines, quotas = _lines(models)[:60], _quotas()
    lines.sort(key=lambda l: (l[0].get('aa') is None, -(l[0].get('aa') or 0), l[0].get('name') or l[0]['canonical']))
    blocks = [{'t': 'text', 'text': say('spawn.cat.intro', n=len(lines))}]
    bars = [{'label': m.get('name') or m['canonical'], 'value': m['aa'], 'max': 100} for m, _ in lines if m.get('aa') is not None][:TOP]
    if bars:
        blocks.append({'t': 'bars', 'title': say('spawn.cat.aaChart'), 'unit': '', 'items': bars})
    for newest, older in lines:
        blocks.append({'t': 'rows', 'rows': [_model_row(newest, quotas)]})
        if older:
            blocks.append({'t': 'more', 'label': say('spawn.cat.older', n=len(older)), 'rows': [_model_row(m, quotas) for m in older]})
    blocks.append({'t': 'actions', 'items': [{'id': 'update', 'label': say('spawn.cat.update')}, {'id': 'study', 'label': say('spawn.cat.study')}]})
    return {'title': say('spawn.cat.title'), 'icon': '📚', 'blocks': blocks}


def _score_line(s, gl, lang):
    b = gl.get(s.get('bench'), {})
    who = say('spawn.sheet.independent') if s.get('independent') else say('spawn.sheet.declared')
    return f"{s.get('source', '?')} · {s.get('date', '')} · {who}" + (f" · {b.get(lang) or b.get('en')}" if b else '')


def sheet(cat, canonical, lang='en'):
    """one model: its routes, its 10 strong points (🏆 when first), every score with source, date and who measured it"""
    m = next((x for x in cat.get('models', []) if x.get('canonical') == canonical), None)
    if not m:
        raise ValueError(say('spawn.err.noModel', model=canonical))
    gl, areas = glossary()
    quotas = _quotas()
    name = lambda bid: gl.get(bid, {}).get('name', bid)
    routes = [{'key': f"{r.get('adapter')}:{r.get('model_id')}", 'label': r.get('adapter', '?'),
               'value': ' · '.join(x for x in [r.get('model_id', ''), say('spawn.sheet.free') if r.get('free') else '', 'ctx ' + _ctx(r.get('ctx')),
                                                say('spawn.sheet.tools') if r.get('tools') else '', f"{(r.get('ping') or {}).get('ms')} ms" if (r.get('ping') or {}).get('ms') else '',
                                                _quota_text(quotas.get(f"{r.get('adapter')}:{r.get('model_id')}"))] if x),
               'state': 'ok' if (r.get('ping') or {}).get('ok') else 'wait' if not r.get('ping') else 'bad'} for r in m.get('routes') or []]
    strong = [{'label': ('🏆 ' if s.get('trophy') else '') + name(s.get('bench')), 'value': s.get('value'),
               'note': ' · '.join(x for x in [(areas.get(s.get('area')) or {}).get(lang, s.get('area', '')),
                                             say('spawn.sheet.rank', rank=s.get('rank'), of=s.get('of')) if s.get('rank') else '',
                                             s.get('source', '')] if x)} for s in (m.get('strengths') or [])[:10]]
    scores = [{'key': s.get('bench', ''), 'label': name(s.get('bench')), 'value': f"{s.get('value')} — {_score_line(s, gl, lang)}"}
              for s in m.get('scores') or []]
    blocks = [{'t': 'text', 'text': ' · '.join(x for x in [f"AA {m['aa']:g}" if m.get('aa') is not None else 'AA n.d.',
                                                          say('spawn.cat.partial') if m.get('state') in ('pending', 'partial') else ''] if x)},
              {'t': 'rows', 'rows': routes}]
    if strong:
        blocks.append({'t': 'bars', 'title': say('spawn.sheet.strong'), 'items': strong})
    if scores:
        blocks.append({'t': 'rows', 'rows': scores})
    same = [x for x in cat.get('models', []) if x['canonical'] != canonical and _line(x['canonical']) == _line(canonical)]
    if same:                                           # the other versions of its line, each with its own sheet
        blocks.append({'t': 'more', 'label': say('spawn.sheet.versions', n=len(same)),
                       'rows': [{'key': x['canonical'], 'label': x.get('name') or x['canonical'], 'value': f"AA {x['aa']:g}" if x.get('aa') is not None else 'AA n.d.',
                                 'actions': [{'id': 'sheet', 'label': say('spawn.cat.sheet')}]} for x in same]})
    return {'title': m.get('name') or canonical, 'icon': '🧾', 'blocks': blocks}


def compare(cat, canonicals, lang='en'):
    """2-4 models on the benchmarks they share, one group of bars per benchmark"""
    ms = [m for m in cat.get('models', []) if m.get('canonical') in canonicals][:4]
    if len(ms) < 2:
        raise ValueError(say('spawn.err.compareTwo'))
    gl, _ = glossary()
    by = [{s.get('bench'): s for s in m.get('scores') or []} for m in ms]
    shared = [b for b in by[0] if all(b in x for x in by[1:])]
    blocks = []
    for b in shared[:12]:
        g = gl.get(b, {})
        blocks.append({'t': 'bars', 'title': f"{g.get('name', b)}" + (f" — {g.get(lang) or g.get('en')}" if g else ''),
                       'items': [{'label': m.get('name') or m['canonical'], 'value': x[b].get('value'), 'note': x[b].get('source', '')}
                                 for m, x in zip(ms, by)]})
    if not blocks:
        blocks = [{'t': 'text', 'text': say('spawn.cmp.none')}]
    return {'title': say('spawn.cmp.title', names=' · '.join(m.get('name') or m['canonical'] for m in ms)), 'icon': '⚖️', 'blocks': blocks}


# ------------------------------------------------------------------ roles: Crea ruolo, Stato ruoli, Sostituisci
def _label(m):
    return (m.get('name') or m['canonical']) + (f" · AA {m['aa']:g}" if m.get('aa') is not None else '')


def _usable(cat):
    """the models a role can run on now: a free host with tools, best AA first"""
    from spawn.runner import routes_of
    ms = [m for m in cat.get('models', []) if routes_of(m['canonical'], cat)]
    return sorted(ms, key=lambda m: (m.get('aa') is None, -(m.get('aa') or 0)))


def create_role(cat, picked=()):
    """the form of a new role: name, mission, model (the picked ones first), shell only if the user gives it (D1)"""
    ms = _usable(cat)
    ms = [m for m in ms if m['canonical'] in picked] + [m for m in ms if m['canonical'] not in picked]
    return {'title': say('spawn.role.createTitle'), 'icon': '🧑‍🚀', 'blocks': [
        {'t': 'text', 'text': say('spawn.role.createIntro')},
        {'t': 'form', 'key': 'new', 'fields': [
            {'name': 'name', 'label': say('spawn.role.name'), 'type': 'text', 'placeholder': 'ARCH'},
            {'name': 'mission', 'label': say('spawn.role.mission'), 'type': 'text'},
            {'name': 'model', 'label': say('spawn.role.model'), 'type': 'select', 'options': [{'value': m['canonical'], 'label': _label(m)} for m in ms[:80]]},
            {'name': 'shell', 'label': say('spawn.role.shell'), 'type': 'select', 'value': 'no',
             'options': [{'value': 'no', 'label': say('spawn.role.shellNo')}, {'value': 'yes', 'label': say('spawn.role.shellYes')}]}],
         'submit': {'id': 'create', 'label': say('spawn.role.create')}}]}


STATE_DOT = {'service': 'ok', 'switch': 'warn', 'notokens': 'bad', 'stopped': 'bad'}


def role_state(roles):
    """every role: its model and host, its state, the tokens it used; Sostituisci on each"""
    rows = []
    for name, r in sorted(roles.items()):
        u, route = r.get('usage') or {}, r.get('route') or {}
        bits = [r.get('canonical') or route.get('model_id', ''), route.get('adapter', ''), say(f"spawn.role.st.{r.get('state', 'service')}"),
                say('spawn.role.usage', i=u.get('in', 0), o=u.get('out', 0)) if u else '', r.get('error') or '']
        rows.append({'key': name, 'label': ('📟 ' if r.get('state') == 'notokens' else '') + name, 'value': ' · '.join(b for b in bits if b),
                     'state': STATE_DOT.get(r.get('state'), 'wait'), 'actions': [{'id': 'replace', 'label': say('spawn.role.replace')}]})
    return {'title': say('spawn.role.stateTitle'), 'icon': '🛰', 'blocks': [{'t': 'rows', 'rows': rows} if rows else {'t': 'text', 'text': say('spawn.role.none')},
                                                                         {'t': 'actions', 'items': [{'id': 'refresh', 'label': say('spawn.role.refresh')}]}]}


def replace_card(cat, role):
    """the models to replace a role with: enough context and tools first (the ones whose host fits its current window),
    then the Artificial Analysis value; each with its best areas and its price (free)"""
    now = (role.get('route') or {}).get('ctx') or 0
    ms = _usable(cat)
    from spawn.runner import routes_of
    fits = lambda m: (routes_of(m['canonical'], cat)[0].get('ctx') or 0) >= now
    ms = [m for m in ms if fits(m)] + [m for m in ms if not fits(m)]
    rows = [{'key': m['canonical'], 'label': _label(m), 'state': 'ok' if fits(m) else 'warn',
             'value': ' · '.join(b for b in [say('spawn.cat.routes', n=len(routes_of(m['canonical'], cat))), 'ctx ' + _ctx(routes_of(m['canonical'], cat)[0].get('ctx')),
                                              (say('spawn.cat.best') + ' ' + ', '.join(m['areas_best'][:3])) if m.get('areas_best') else '',
                                              '' if fits(m) else say('spawn.role.smallCtx')] if b),
             'actions': [{'id': 'choose', 'label': say('spawn.role.choose')}, {'id': 'sheet', 'label': say('spawn.cat.sheet')}]}
            for m in ms[:30] if m['canonical'] != role.get('canonical')]
    bars = [{'label': m.get('name') or m['canonical'], 'value': m['aa'], 'max': 100} for m in ms if m.get('aa') is not None][:10]
    return {'title': say('spawn.role.replaceTitle', name=role['name']), 'icon': '📟', 'role': role['name'],
            'blocks': [{'t': 'text', 'text': say('spawn.role.replaceIntro', name=role['name'], model=role.get('canonical', '?'))}]
            + ([{'t': 'bars', 'title': say('spawn.cat.aaChart'), 'items': bars}] if bars else []) + [{'t': 'rows', 'rows': rows}]}


def _speak(room):
    """this thread speaks the room's language (the runner and the server call these from threads of their own)"""
    use(lang_of(room.config()), here=True)
    return lang_of(room.config())


def _viewer_url(room):
    """the address of this room's viewer, from the registry it stamps every 5 s (the OpenRouter login comes back there)"""
    from activity import REGISTRY
    try:
        return json.loads(REGISTRY.read_text(encoding='utf-8'))[str(Path(room.dir).resolve())]['url']
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(say('spawn.err.noViewer'))


def post_prepare(room, author='SPAWN'):
    """the Prepara spawn card in the chat (/spawn, chat.py spawn): (n, id)"""
    import cards
    _speak(room)
    from spawn import keys
    return cards.post(room, author, 'prepare_spawn', prepare(keys.status(), tools_state(), set(_setup().get('skipped', []))), say('spawn.prep.plain'))


def post_create(room, author='SPAWN', picked=()):
    """the Crea ruolo card in the chat: (n, id)"""
    import cards
    _speak(room)
    return cards.post(room, author, 'create_role', create_role(_load_catalog(), picked), say('spawn.role.createPlain'))


def post_replace(room, name):
    """the Sostituisci card of a role, in the chat (the runner calls it when a role runs out of tokens)"""
    import cards
    from spawn import runner
    _speak(room)
    role = runner.roles(room).get(name)
    if not role:
        raise ValueError(say('spawn.err.noRole', name=name))
    return cards.post(room, 'SPAWN', 'replace', replace_card(_load_catalog(), role), say('spawn.role.replacePlain', name=name))


def refresh_catalog(room, cid, force=False):
    """the catalog's round (network: the lists of the providers with a key, AA once a day, the researcher's results) in a
    thread; when it ends the card shows the new catalog (cards.json, read by the page within 3 s), or why it failed"""
    import threading
    import cards

    def run():
        from spawn.catalog import catalog as c
        try:
            cat = c.update(room.dir, force)
        except Exception as exc:                   # a network or a file error: the card says it, the room goes on
            _speak(room)
            try:
                return cards._save(room, cid, {**(cards.states(room).get(cid) or {}), 'error': say('spawn.cat.updateFailed', why=str(exc)[:200])})
            except ValueError:                     # the error's text held something like a key: said without it
                return cards._save(room, cid, {**(cards.states(room).get(cid) or {}), 'error': say('spawn.cat.updateFailed', why=type(exc).__name__)})
        _speak(room)
        cards._save(room, cid, {**catalog(cat), 'note': say('spawn.cat.updated', n=sum(1 for m in cat.get('models', []) if _free(m)))})
    threading.Thread(target=run, daemon=True).start()


def _host(runner, room, canonical, routes, name=None):
    """the host a role starts on: REGIA's choice by quota (best_route, T31) when it is there, else the fastest free one"""
    pick = getattr(runner, 'best_route', None)
    return (pick(room, canonical, name=name) if pick else None) or routes[0]


# ------------------------------------------------------------------ clicks
def card_action(room, card, action, key, values):
    """the answer to a click on a spawn card: the card's new data (cards.py saves it as its state)"""
    import cards
    lang = _speak(room)
    if card['type'] == 'prepare_spawn':
        from spawn import keys
        setup = _setup()
        skipped = set(setup.get('skipped', []))
        full = bool((card.get('state') or {}).get('full') or (card.get('data') or {}).get('full')) or action == 'more'
        note = ''
        if action == 'more':
            return prepare(keys.status(), tools_state(), skipped, True)
        if action == 'save':
            if not values.get('key', '').strip():
                raise ValueError(say('spawn.err.noKey'))
            extra = {k: v.strip() for k, v in values.items() if k != 'key' and v.strip()}
            slot = keys.save(key, values['key'].strip(), extra or None)
            state, _ = keys.check(key, slot)
            note = say(f'spawn.prep.{state}')
            skipped.discard(key)
        elif action == 'check':
            note = say(f'spawn.prep.{keys.check(key)[0]}')
        elif action == 'skip':
            skipped.add(key)
        elif action == 'login':
            url = keys.pkce_start(_viewer_url(room) + '/spawn/oauth')[0]
            return {**prepare(keys.status(), tools_state(), skipped, full), 'open': url}
        elif action == 'install_headroom':
            import chat
            chat.start_headroom_install()
            note = say('viewer.hrBusy')
        elif action == 'start':
            n, cid = cards.post(room, 'SPAWN', 'catalog', catalog(_load_catalog()), say('spawn.cat.plain'))
            refresh_catalog(room, cid)
            note = say('spawn.prep.started', n=n)
        else:
            raise ValueError(say('spawn.err.action', action=action))
        _save_setup({**setup, 'skipped': sorted(skipped)})
        return {**prepare(keys.status(), tools_state(), skipped, full), 'note': note} if note else prepare(keys.status(), tools_state(), skipped, full)
    if card['type'] == 'catalog':
        cat = _load_catalog()
        if action == 'sheet':
            d = sheet(cat, key, lang)
            cards.post(room, 'SPAWN', 'model_sheet', d, say('spawn.sheet.plain', name=d['title']))
            return {**(card.get('state') or {}), 'note': say('spawn.cat.opened', name=d['title'])}
        if action == 'compare':
            picked = list(dict.fromkeys([*(card.get('state') or {}).get('picked', []), key]))[-4:]
            if len(picked) >= 2:
                d = compare(cat, picked, lang)
                cards.post(room, 'SPAWN', 'compare', d, d['title'])
                return {**(card.get('state') or {}), 'picked': [], 'note': ''}
            return {**(card.get('state') or {}), 'picked': picked, 'note': say('spawn.cat.pickMore')}
        if action == 'update':
            refresh_catalog(room, card['id'], force=True)
            return {**(card.get('state') or {}), 'note': say('spawn.cat.updating'), 'error': ''}
        if action == 'study':
            from spawn.catalog import catalog as c
            asked = c.study(room.dir, lang)
            return {**(card.get('state') or {}), 'note': say('spawn.cat.studyAsked', id=asked['id'], n=len(asked['models'])) if asked else say('spawn.cat.studyNone')}
        if action == 'role':
            picked = list(dict.fromkeys([*(card.get('state') or {}).get('picked', []), key]))
            cards.post(room, 'SPAWN', 'create_role', create_role(cat, picked), say('spawn.role.createPlain'))
            return {**(card.get('state') or {}), 'note': say('spawn.role.formPosted')}
    from spawn import runner
    if card['type'] == 'create_role' and action == 'create':
        name, canonical = values.get('name', '').strip().upper(), values.get('model', '')
        routes = runner.routes_of(canonical)
        if not routes:
            raise ValueError(say('spawn.err.noRoute', model=canonical))
        route = _host(runner, room, canonical, routes)
        runner.create(room, name, values.get('mission', '').strip() or name, canonical, route, tools=('shell',) if values.get('shell') == 'yes' else ())
        cards.post(room, 'SPAWN', 'role_state', role_state(runner.roles(room)), say('spawn.role.statePlain'))
        return {**create_role(_load_catalog()), 'note': say('spawn.role.created', name=name, model=canonical, provider=route['adapter'])}
    if card['type'] == 'role_state':
        if action == 'replace':
            post_replace(room, key)
            return {**role_state(runner.roles(room)), 'note': say('spawn.role.replacePosted', name=key)}
        if action == 'refresh':
            return role_state(runner.roles(room))
    if card['type'] == 'replace':
        name = (card.get('data') or {}).get('role', '')
        if action == 'choose':
            routes = runner.routes_of(key)
            if not routes:
                raise ValueError(say('spawn.err.noRoute', model=key))
            route = _host(runner, room, key, routes, name)
            runner.replace(room, name, key, route)
            return {**replace_card(_load_catalog(), runner.roles(room)[name]), 'note': say('spawn.role.replaced', name=name, model=key, provider=route['adapter'])}
        if action == 'sheet':
            d = sheet(_load_catalog(), key, lang)
            cards.post(room, 'SPAWN', 'model_sheet', d, say('spawn.sheet.plain', name=d['title']))
            return {**(card.get('state') or {}), 'note': say('spawn.cat.opened', name=d['title'])}
    raise ValueError(say('spawn.err.action', action=action))


def _load_catalog():
    from spawn.catalog import catalog as c
    return c.load()
