"""Il catalogo della modalità spawn: tutti i modelli di tutti i provider configurati, una scheda per modello con le sue
strade (provider e id), i punteggi con la fonte, i 10 punti forti. Si salva in ~/.claude/chatroom/spawn/catalog.json
e il viewer lo serve com'è (GET /catalog.json, contratto #112 della stanza 0.13).

  refresh(cat, provider_ids, list_models)   rilegge le liste dei provider (una volta ogni 12 ore per provider, salvo force)
  add_scores(cat, scores, glossary)         unisce punteggi nuovi e ricalcola aa, punti forti, ambiti migliori, stato
  fast_scores(sources, timeout)             le fonti veloci in parallelo: allo scadere dà ciò che ha, segnato parziale
  load(), save(cat)                         il file, scritto intero o per niente

list_models(provider_id) è quella di PORTE (spawn.providers.list_models, firma #130): una lista di dict
{id, name, ctx, max_out, tools, reasoning, free, price_in, price_out, modalities}, o un'eccezione. Il "ping" della
lista è la richiesta della lista stessa: tempo e riuscita per provider, mai una completion (quella è del runner allo spawn).
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

try:
    from .identity import canonical_id
except ImportError:                                      # lanciato come script (_prova)
    from identity import canonical_id
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research import _params_b                            # noqa: E402  la taglia dall'id ('550b-a55b' -> 550), come il panel

MAX_AGE = 12 * 3600
FAST_TIMEOUT = 30
ROUTE_KEYS = ('ctx', 'max_out', 'tools', 'reasoning', 'free', 'price_in', 'price_out')


def order(m):
    """prima chi ha l'indice AA più alto, poi i modelli n.d. dal più grande (parametri dall'id), poi per nome"""
    return (-(m['aa'] if m.get('aa') is not None else -1), -(m.get('params_b') or 0), m['canonical'])


def catalog_path():
    return Path.home() / '.claude' / 'chatroom' / 'spawn' / 'catalog.json'   # Path.home a ogni chiamata: i test usano una HOME finta


def load():
    try:
        d = json.loads(catalog_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    return {'updated': d.get('updated'), 'providers': d.get('providers') or {}, 'models': d.get('models') or []}


def save(cat):
    path = catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'catalog.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(cat, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def refresh(cat, provider_ids, list_models, now=None, force=False):
    """le liste dei provider dovuti (mai letti, letti più di 12 ore fa, o force); un provider che fallisce tiene le sue
    strade di prima e segna l'errore. Le strade di un provider riletto sono sostituite dalla lista nuova"""
    now = now or time.time()
    models = {m['canonical']: m for m in cat['models']}
    for pid in provider_ids:
        st = cat['providers'].get(pid) or {}
        if not force and st.get('ok') and now - st.get('at', 0) < MAX_AGE:
            continue
        t0 = time.time()
        try:
            listed = list_models(pid)
        except Exception as exc:                           # un provider giù non ferma gli altri
            cat['providers'][pid] = {**st, 'at': now, 'ok': False, 'error': f'{type(exc).__name__}: {str(exc)[:160]}'}
            continue
        ms = int((time.time() - t0) * 1000)
        cat['providers'][pid] = {'at': now, 'ok': True, 'ms': ms, 'count': len(listed)}
        for m in models.values():
            m['routes'] = [r for r in m['routes'] if r['adapter'] != pid]
        for item in listed:
            key = canonical_id(item.get('id'))
            if not key:
                continue
            m = models.setdefault(key, {'canonical': key, 'name': str(item.get('name') or item['id'])[:120], 'routes': [],
                                        'scores': [], 'aa': None, 'strengths': [], 'areas_best': [], 'state': 'pending',
                                        'params_b': _params_b({'id': item['id'], 'description': item.get('description')})})
            m['routes'].append({'adapter': pid, 'model_id': item['id'], **{k: item.get(k) for k in ROUTE_KEYS},
                                'ping': {'ok': True, 'ms': ms, 'at': now}})
    cat['models'] = sorted((m for m in models.values() if m['routes']), key=order)
    cat['updated'] = now
    return cat


def add_scores(cat, scores, glossary, partial=False, studied=()):
    """scores: {canonical: [score]} (dalle fonti o dal ricercatore). Un punteggio della stessa fonte per lo stesso
    benchmark sostituisce il vecchio. Stato: complete quando le fonti veloci hanno finito e il ricercatore lo ha
    studiato, partial se manca una delle due, pending senza punteggi"""
    try:
        from ..bench.strengths import annotate
    except ImportError:
        from strengths import annotate
    models = {m['canonical']: m for m in cat['models']}
    for c, new in scores.items():
        if c not in models:
            continue
        keep = {(s['bench'], s['source']) for s in new}
        models[c]['scores'] = [s for s in models[c]['scores'] if (s['bench'], s['source']) not in keep] + list(new)
    raw = {c: [{k: s[k] for k in ('bench', 'value', 'source', 'date', 'independent')} for s in m['scores']] for c, m in models.items() if m['scores']}
    notes = annotate(raw, glossary)
    for c, m in models.items():
        n = notes.get(c)
        if n:
            m['scores'], m['strengths'], m['areas_best'] = n['scores'], n['strengths'], n['areas_best']
            m['aa'] = next((s['value'] for s in n['scores'] if s['bench'] == 'aa-intelligence-index'), None)
        if c in scores or m['state'] != 'pending':
            m['state'] = 'partial' if partial or c not in studied else 'complete'
    cat['models'] = sorted(models.values(), key=order)
    return cat


def fast_scores(sources, timeout=FAST_TIMEOUT):
    """sources: {nome: funzione() -> {canonical: [score]}}, tutte insieme. Allo scadere: ciò che è arrivato, e partial
    True se una fonte non ha finito o ha fallito (la coda non aspetta oltre: i thread rimasti finiscono da soli)"""
    pool = ThreadPoolExecutor(max_workers=max(1, len(sources)))
    futures = {pool.submit(fn): name for name, fn in sources.items()}
    done, late = wait(futures, timeout=timeout)
    pool.shutdown(wait=False, cancel_futures=True)
    out, partial = {}, bool(late)
    for f in done:
        try:
            for c, s in (f.result() or {}).items():
                out.setdefault(c, []).extend(s)
        except Exception:
            partial = True
    return out, partial


def _prova():
    import tempfile
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bench'))
    import strengths
    g = strengths.load_glossary()
    real_home = Path.home()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['USERPROFILE'] = os.environ['HOME'] = tmp       # mai la ~/.claude vera
        assert Path.home() == Path(tmp) and catalog_path().is_relative_to(Path(tmp))
        lists = {'open_router': [{'id': 'z-ai/glm-5.3:free', 'name': 'GLM 5.3 (free)', 'ctx': 200000, 'tools': True, 'free': True, 'price_in': 0, 'price_out': 0},
                                 {'id': 'z-ai/glm-5.3', 'name': 'GLM 5.3', 'ctx': 200000, 'tools': True, 'free': False, 'price_in': 0.5, 'price_out': 2}],
                 'siliconflow': [{'id': 'zai-org/GLM-5.3', 'name': 'GLM-5.3', 'ctx': 131072, 'tools': True, 'free': False}],
                 'nvidia_nim': [{'id': 'moonshotai/kimi-k3', 'name': 'Kimi K3', 'ctx': None, 'tools': None, 'free': True},
                                {'id': 'deepseek-ai/deepseek-v4-flash', 'name': 'DeepSeek V4 Flash', 'free': True}]}
        calls = []

        def list_models(pid):
            calls.append(pid)
            if pid == 'groq':
                raise ConnectionError('giù')
            return lists[pid]
        cat = refresh(load(), ['open_router', 'siliconflow', 'nvidia_nim', 'groq'], list_models, now=1000.0)
        glm = next(m for m in cat['models'] if m['canonical'] == 'glm-5-3')
        assert len(glm['routes']) == 3 and {r['adapter'] for r in glm['routes']} == {'open_router', 'siliconflow'}, glm['routes']
        assert next(r for r in glm['routes'] if r['model_id'].endswith(':free'))['free'] is True and glm['state'] == 'pending'
        assert cat['providers']['groq']['ok'] is False and 'giù' in cat['providers']['groq']['error'] and cat['providers']['nvidia_nim']['ok']
        save(cat)
        cat = refresh(load(), ['open_router', 'groq'], list_models, now=1000.0 + 3600)
        assert calls.count('open_router') == 1 and calls.count('groq') == 2                       # 12 ore: non riletto; un errore sì
        lists['open_router'] = lists['open_router'][1:]                                            # la :free sparisce
        cat = refresh(cat, ['open_router'], list_models, now=1000.0 + MAX_AGE + 1)
        glm = next(m for m in cat['models'] if m['canonical'] == 'glm-5-3')
        assert [r['model_id'] for r in glm['routes'] if r['adapter'] == 'open_router'] == ['z-ai/glm-5.3']
        s = lambda b, v: {'bench': b, 'value': v, 'source': 'https://artificialanalysis.ai/models/x', 'date': '2026-10-26', 'independent': True}
        slow = lambda: time.sleep(3) or {'kimi-k3': [s('gpqa-diamond', 99)]}
        got, partial = fast_scores({'aa': lambda: {'glm-5-3': [s('aa-intelligence-index', 61), s('gpqa-diamond', 78)], 'kimi-k3': [s('gpqa-diamond', 70)],
                                           'deepseek-v4-flash': [s('gpqa-diamond', 60)]},
                                    'slow': slow, 'broken': lambda: 1 / 0}, timeout=1)
        assert partial and set(got) == {'glm-5-3', 'kimi-k3', 'deepseek-v4-flash'} and len(got['kimi-k3']) == 1, got
        cat = add_scores(cat, got, g, partial=partial)
        glm = next(m for m in cat['models'] if m['canonical'] == 'glm-5-3')
        assert glm['aa'] == 61 and glm['state'] == 'partial' and glm['strengths'] and cat['models'][0]['canonical'] == 'glm-5-3'
        cat = add_scores(cat, {'glm-5-3': [s('gpqa-diamond', 80)]}, g, studied={'glm-5-3'})
        glm = next(m for m in cat['models'] if m['canonical'] == 'glm-5-3')
        assert [x['value'] for x in glm['scores'] if x['bench'] == 'gpqa-diamond'] == [80] and glm['state'] == 'complete'
        assert all('frontier' in x and x['source'] for x in glm['scores'])
        save(cat)
        assert load()['models'][0]['canonical'] == 'glm-5-3' and not list(catalog_path().parent.glob('*.tmp'))
        big = {'canonical': 'nemotron-3-ultra-550b-a55b', 'aa': None, 'params_b': 550.0}
        small = {'canonical': 'lfm-2-5-2-6b', 'aa': None, 'params_b': 2.6}
        assert sorted([small, big, {'canonical': 'x', 'aa': 1, 'params_b': None}], key=order)[1:] == [big, small]
        assert _params_b({'id': 'nvidia/nemotron-3-ultra-550b-a55b:free'}) == 550
    assert not (real_home / '.claude' / 'chatroom' / 'spawn' / 'catalog.json').exists()
    print('catalog ok')


if __name__ == '__main__':
    _prova()
