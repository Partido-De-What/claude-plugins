"""Il catalogo della modalità spawn: tutti i modelli gratis (D12: la 0.13 usa solo modelli free) di tutti i provider configurati, una scheda per modello con le sue
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
    from .identity import canonical_id, line_key
except ImportError:                                      # lanciato come script (_prova)
    from identity import canonical_id, line_key
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research import _params_b                            # noqa: E402  la taglia dall'id ('550b-a55b' -> 550), come il panel

MAX_AGE = 12 * 3600
FAST_TIMEOUT = 30
ROUTE_KEYS = ('ctx', 'max_out', 'tools', 'reasoning', 'free', 'price_in', 'price_out')


def order(m):
    """prima chi ha l'indice AA più alto, poi i modelli n.d. dal più grande (parametri dall'id), poi per nome"""
    return (-(m['aa'] if m.get('aa') is not None else -1), -(m.get('params_b') or 0), m['canonical'])


def lines(models):
    """le schede per linea (identity.line_key): [{'line', 'newest': scheda, 'older': [schede, dalla più nuova]}], nell'ordine
    in cui arriva la versione più nuova di ogni linea (models già in ordine). Le card mostrano newest e, chiuse,
    le older come "versioni precedenti (N)": restano tutte sceglibili"""
    groups = {}
    for m in models:
        key, version = line_key(m['canonical'])
        groups.setdefault(key or m['canonical'], []).append((version, m))
    out = []
    for key, ms in groups.items():
        ms.sort(key=lambda x: x[0], reverse=True)
        out.append({'line': key, 'newest': ms[0][1], 'older': [m for _, m in ms[1:]]})
    pos = {id(m): i for i, m in enumerate(models)}
    return sorted(out, key=lambda g: pos[id(g['newest'])])


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
            if not key or item.get('free') is not True:  # D12: la 0.13 usa solo modelli gratis
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


AA_MAX_AGE = 24 * 3600                                    # D2: 100 richieste al giorno, una basta


def _studies(room_dir):
    try:
        lines = (Path(room_dir) / 'spawn' / 'study.jsonl').read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    return [json.loads(x) for x in lines if x.strip()]


def study(room_dir, lang='it'):
    """il tasto "Studia": il prompt del ricercatore per i modelli del catalogo non ancora studiati (D6), e una riga in
    ROOM/spawn/study.jsonl ({id, prompt, out, models}) che il relay del lead mostra come STUDY. None se non c'è nulla da
    studiare. Il risultato in out lo accetta il prossimo update(room_dir)"""
    from spawn.bench import researcher, strengths
    cat = load()
    models = {m['canonical']: [r['model_id'] for r in m['routes']] for m in cat['models']}
    n = len(_studies(room_dir)) + 1
    out = Path(room_dir) / 'spawn' / 'study' / f'{n}.json'
    g = strengths.load_glossary()
    prompt = researcher.prepare(models, out, strengths.GLOSSARY, list(g['_meta']['areas']), lang)
    if prompt is None:
        return None
    entry = {'id': n, 'prompt': str(prompt), 'out': str(out), 'models': sorted(set(models) - set(researcher.studied()))}
    with (Path(room_dir) / 'spawn' / 'study.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


def update(room_dir=None, force=False, list_models=None, load_key=None, aa_payload=None):
    """il giro completo, da chiamare in un thread (la card Catalogo, Prepara spawn): le liste dei provider che hanno una
    chiave, la fonte veloce Artificial Analysis una volta al giorno (con la sua chiave, D2), i risultati del ricercatore
    arrivati nella stanza; poi punti forti e stato, e il file. Il risultato di un ricercatore fuori schema è messo da
    parte (.bad.json) con il motivo nel catalogo, mai usato a metà"""
    from spawn.bench import researcher, sources, strengths
    from spawn.providers import catalog as providers
    if list_models is None:
        from spawn.providers import list_models
    if load_key is None:
        from spawn.keys import load as load_key
    g, now = strengths.load_glossary(), time.time()
    cat = refresh(load(), [p for p in providers.FREE if load_key(p)], list_models, now=now, force=force)
    canon = [m['canonical'] for m in cat['models']]
    aa, st = load_key('artificial_analysis'), cat['providers'].get('artificial_analysis') or {}
    scores, partial = {}, False
    if aa and canon and (force or not st.get('ok') or now - st.get('at', 0) > AA_MAX_AGE):
        scores, partial = fast_scores({'aa': lambda: sources.aa_scores(aa['key'], canon, g, payload=aa_payload)})
        cat['providers']['artificial_analysis'] = {'at': now, 'ok': not partial, 'count': len(scores)}
    for e in _studies(room_dir) if room_dir else []:
        out = Path(e['out'])
        if not out.is_file():
            continue
        try:
            got, news = researcher.accept(out, g, asked=set(e['models']))
            researcher.mark_studied(e['models'])
            if strengths.add_extra(news):
                g = strengths.load_glossary()             # i benchmark nuovi col loro ambito e la loro descrizione
            for c, s in got.items():
                scores.setdefault(c, []).extend(s)
            out.replace(out.with_suffix('.done.json'))
            cat['providers']['researcher'] = {'at': now, 'ok': True, 'count': len(got)}
        except ValueError as exc:
            out.replace(out.with_suffix('.bad.json'))
            cat['providers']['researcher'] = {'at': now, 'ok': False, 'error': str(exc)[:200]}
    cat = add_scores(cat, scores, g, partial=partial, studied=set(researcher.studied()))
    save(cat)
    return cat


def _prova_update(tmp):
    """update e study con provider, chiavi e AA finti, nella HOME finta di _prova"""
    room = Path(tmp) / 'stanza'
    lists = {'open_router': [{'id': 'z-ai/glm-5.3:free', 'name': 'GLM', 'free': True, 'tools': True},
                             {'id': 'moonshotai/kimi-k3:free', 'name': 'Kimi', 'free': True, 'tools': True},
                             {'id': 'deepseek/deepseek-v4-flash:free', 'name': 'DS', 'free': True}],
             'groq': [{'id': 'qwen/qwen3.8-27b', 'name': 'Q', 'free': True}]}
    keys = {'open_router': {'key': 'k'}, 'artificial_analysis': {'key': 'a'}}
    payload = {'data': [{'slug': s, 'evaluations': {'artificial_analysis_intelligence_index': v, 'gpqa': v / 100}}
                        for s, v in (('glm-5-3', 61), ('kimi-k3', 64), ('deepseek-v4-flash', 50))]}
    asked = []
    cat = update(room, list_models=lambda p: asked.append(p) or lists[p], load_key=keys.get, aa_payload=payload)
    assert asked == ['open_router'] and len(cat['models']) == 3                                  # groq senza chiave: non letto
    assert cat['models'][0]['canonical'] == 'kimi-k3' and cat['models'][0]['aa'] == 64 and cat['models'][0]['state'] == 'partial'
    assert cat['providers']['artificial_analysis']['ok'] and cat['models'][0]['strengths']
    e = study(room)
    assert e['models'] == ['deepseek-v4-flash', 'glm-5-3', 'kimi-k3'] and Path(e['prompt']).is_file()
    res = {'models': [{'canonical': 'glm-5-3', 'scores': [{'bench': 'swe-bench-pro', 'value': 40, 'source': 'https://example.org/a',
                                                           'date': '2026-10-01', 'independent': True},
                                                          {'bench': 'niche-x', 'value': 7, 'source': 'https://example.org/n',
                                                           'date': '2026-10-01', 'independent': True}]}],
           'new_benchmarks': [{'id': 'niche-x', 'name': 'Niche X', 'area': 'code', 'unit': '%', 'better': 'higher',
                               'url': 'https://example.org/n', 'it': 'una prova di nicchia', 'en': 'a niche test'}]}
    Path(e['out']).write_text(json.dumps(res), encoding='utf-8')
    cat = update(room, list_models=lambda p: lists[p], load_key=keys.get, aa_payload={'data': []})
    glm = next(m for m in cat['models'] if m['canonical'] == 'glm-5-3')
    assert any(s['bench'] == 'swe-bench-pro' for s in glm['scores']) and glm['state'] == 'complete' and glm['aa'] == 61
    assert Path(e['out']).with_suffix('.done.json').is_file() and cat['providers']['researcher']['ok']
    from spawn.bench import strengths
    g = strengths.load_glossary()
    assert strengths.lookup('niche-x', g) == 'niche-x' and strengths.check_glossary(g) == [] and strengths.extra_path().is_relative_to(Path(tmp))
    assert strengths.add_extra([{'id': 'niche-x', 'name': 'n', 'area': 'code', 'unit': '%', 'better': 'higher', 'url': 'https://a.b/c', 'it': 'x', 'en': 'x'}]) == 0
    assert cat['providers']['artificial_analysis']['count'] == 3                               # AA non riletto nelle 24 ore
    assert study(room) is None                                                                   # D6: tutti studiati
    lists['open_router'].append({'id': 'thinkingmachines/inkling:free', 'name': 'Inkling', 'free': True})
    cat = update(room, force=True, list_models=lambda p: lists[p], load_key=keys.get, aa_payload={'data': []})
    e2 = study(room)
    assert e2['id'] == 2 and e2['models'] == ['inkling']                                          # solo il nuovo
    Path(e2['out']).write_text('{"models": [{"canonical": "glm-5-3", "scores": []}]}', encoding='utf-8')
    cat = update(room, list_models=lambda p: lists[p], load_key=keys.get)
    assert not cat['providers']['researcher']['ok'] and 'non chiesto' in cat['providers']['researcher']['error']
    assert Path(e2['out']).with_suffix('.bad.json').is_file()


def _prova():
    import tempfile
    ms = [{'canonical': c} for c in ('glm-5-2', 'qwen3-8-flash', 'glm-5-3', 'qwen3-coder', 'glm-5', 'qwen3-8', 'gemma-4-31b-it', 'gemma-4-26b-a4b-it')]
    got = {g['line']: (g['newest']['canonical'], [m['canonical'] for m in g['older']]) for g in lines(ms)}
    assert got == {'glm': ('glm-5-3', ['glm-5-2', 'glm-5']), 'qwen-flash': ('qwen3-8-flash', []), 'qwen-coder': ('qwen3-coder', []),
                   'qwen': ('qwen3-8', []), 'gemma-31b-it': ('gemma-4-31b-it', []), 'gemma-26b-a4b-it': ('gemma-4-26b-a4b-it', [])}, got
    assert [g['line'] for g in lines(ms)][:2] == ['qwen-flash', 'glm']              # l'ordine del catalogo, per la versione nuova
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
        assert len(glm['routes']) == 1 and glm['routes'][0]['model_id'] == 'z-ai/glm-5.3:free', glm['routes']     # D12: solo free
        assert next(r for r in glm['routes'] if r['model_id'].endswith(':free'))['free'] is True and glm['state'] == 'pending'
        assert cat['providers']['groq']['ok'] is False and 'giù' in cat['providers']['groq']['error'] and cat['providers']['nvidia_nim']['ok']
        save(cat)
        cat = refresh(load(), ['open_router', 'groq'], list_models, now=1000.0 + 3600)
        assert calls.count('open_router') == 1 and calls.count('groq') == 2                       # 12 ore: non riletto; un errore sì
        lists['siliconflow'][0]['free'] = True                                                   # una seconda strada free
        cat = refresh(cat, ['siliconflow'], list_models, now=1000.0 + MAX_AGE + 1)
        assert len(next(m for m in cat['models'] if m['canonical'] == 'glm-5-3')['routes']) == 2
        lists['open_router'] = lists['open_router'][1:]                                            # la :free sparisce
        cat = refresh(cat, ['open_router'], list_models, now=1000.0 + MAX_AGE + 1)
        glm = next(m for m in cat['models'] if m['canonical'] == 'glm-5-3')
        assert [r['adapter'] for r in glm['routes']] == ['siliconflow'], glm['routes']
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
        catalog_path().unlink()
        _prova_update(tmp)
        big = {'canonical': 'nemotron-3-ultra-550b-a55b', 'aa': None, 'params_b': 550.0}
        small = {'canonical': 'lfm-2-5-2-6b', 'aa': None, 'params_b': 2.6}
        assert sorted([small, big, {'canonical': 'x', 'aa': 1, 'params_b': None}], key=order)[1:] == [big, small]
        assert _params_b({'id': 'nvidia/nemotron-3-ultra-550b-a55b:free'}) == 550
    assert not (real_home / '.claude' / 'chatroom' / 'spawn' / 'catalog.json').exists()
    print('catalog ok')


if __name__ == '__main__':
    _prova()
