"""I 10 punti forti di ogni modello, dai punteggi raccolti dalle fonti e dal glossario (scripts/bench_glossary.json).

Per ogni benchmark i modelli misurati vanno in classifica; la frontiera è il migliore. La forza di un punteggio è
0.6 x (vicinanza alla frontiera) + 0.4 x (1 - posizione/modelli misurati), per 1.0 se misurato da una fonte
indipendente (Artificial Analysis, una classifica pubblica) e per 0.7 se dichiarato dal produttore (piano 4.2). I punti
forti di un modello sono i suoi punteggi più forti, al massimo 3 per ambito e 10 in tutto, solo su benchmark con almeno 3
modelli confrontabili (gli altri restano tra i punteggi); gli indici (ambito "index") vanno nel grafico AA, velocità e
prezzo (ambito "efficiency": misure di AA su provider a pagamento) solo nella scheda, non tra i punti forti. Una voce
del glossario con "family" vale per tutti gli id che cominciano col suo (design-arena-website è Design Arena). Trofeo 🏆: primo in uno di questi benchmark. Funzioni pure: niente rete, niente file tranne il glossario."""
import json
import re
from pathlib import Path

GLOSSARY = Path(__file__).resolve().parents[2] / 'bench_glossary.json'
TOP, PER_AREA, MIN_MODELS, DECLARED = 10, 3, 3, 0.7
NOT_STRENGTHS = ('index', 'efficiency')


def norm(name):
    return re.sub(r'[^a-z0-9²τ]+', '', str(name or '').lower())


def extra_path():
    return Path.home() / '.claude' / 'chatroom' / 'spawn' / 'glossary_extra.json'   # i benchmark che il ricercatore ha trovato


def load_glossary(path=GLOSSARY):
    """il glossario; quello del plugin con in coda i benchmark nuovi del ricercatore (stessa forma, senza alias)"""
    g = json.loads(Path(path).read_text(encoding='utf-8'))
    if Path(path) == GLOSSARY:
        try:
            extra = json.loads(extra_path().read_text(encoding='utf-8'))
        except (OSError, ValueError):
            extra = []
        for b in extra if isinstance(extra, list) else []:
            if isinstance(b, dict) and b.get('area') in g['_meta']['areas'] and lookup(b.get('id'), g) is None:
                g['benchmarks'].append({**b, 'aliases': []})
    return g


def add_extra(news):
    """aggiunge al glossario esteso i benchmark nuovi (già controllati da researcher.accept); un id già noto non entra"""
    g = load_glossary()
    fresh = [{k: b[k] for k in ('id', 'name', 'area', 'unit', 'better', 'url', 'it', 'en')} for b in news if lookup(b['id'], g) is None]
    if fresh:
        try:
            old = json.loads(extra_path().read_text(encoding='utf-8'))
        except (OSError, ValueError):
            old = []
        extra_path().parent.mkdir(parents=True, exist_ok=True)
        tmp = extra_path().with_suffix('.tmp')
        tmp.write_text(json.dumps((old if isinstance(old, list) else []) + fresh, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(extra_path())
    return len(fresh)


def check_glossary(d):
    """gli errori del glossario ([] se va bene): campi, ambiti noti, verso, testi, url, nomi e alias unici"""
    areas, seen, errs = d.get('_meta', {}).get('areas', {}), {}, []
    for b in d.get('benchmarks', []):
        missing = [k for k in ('id', 'name', 'area', 'unit', 'better', 'aliases', 'url', 'it', 'en') if k not in b]
        if missing:
            errs.append(f"{b.get('id')}: manca {', '.join(missing)}")
            continue
        if b['area'] not in areas:
            errs.append(f"{b['id']}: ambito sconosciuto {b['area']}")
        if b['better'] not in ('higher', 'lower'):
            errs.append(f"{b['id']}: better è higher o lower")
        if not str(b['it']).strip() or not str(b['en']).strip():
            errs.append(f"{b['id']}: testo vuoto")
        if not str(b['url']).startswith('https://'):
            errs.append(f"{b['id']}: url non https")
        for n in {norm(x) for x in [b['id'], b['name'], *b['aliases']]}:
            if seen.get(n, b['id']) != b['id']:
                errs.append(f"{b['id']}: il nome {n} è già di {seen[n]}")
            seen[n] = b['id']
    return errs


def lookup(name, glossary):
    """l'id del glossario per un nome come lo scrive una fonte ("GPQA", "τ²-Bench Telecom"), o None"""
    key = norm(name)
    for b in glossary['benchmarks']:
        if key in {norm(x) for x in [b['id'], b['name'], *b['aliases']]}:
            return b['id']
    return None


def entry(bench, glossary):
    """la voce del glossario di un id: la sua, o quella della famiglia di cui è parte (design-arena-website), o {}"""
    return next((b for b in glossary['benchmarks'] if b['id'] == bench), None) or next(
        (b for b in glossary['benchmarks'] if b.get('family') and str(bench).startswith(b['id'] + '-')), {})


def _best(scores):
    """un punteggio per benchmark: prima l'indipendente, poi il più recente"""
    out = {}
    for s in scores:
        old = out.get(s['bench'])
        if old is None or (bool(s.get('independent')), str(s.get('date') or '')) > (bool(old.get('independent')), str(old.get('date') or '')):
            out[s['bench']] = s
    return out


def _frontier(value, values, better):
    """quanto value è vicino al migliore, da 0 a 1: rapporto sui valori positivi, altrimenti tra peggiore e migliore"""
    best, worst = (max(values), min(values)) if better == 'higher' else (min(values), max(values))
    if best > 0 and worst > 0:
        f = value / best if better == 'higher' else best / value
    else:
        f = 1.0 if best == worst else (value - worst) / (best - worst)
    return round(max(0.0, min(1.0, f)), 4)


def annotate(scores_by_model, glossary, leaders=None):
    """{canonical: [{'bench', 'value', 'source', 'date', 'independent'}]} -> {canonical: {'scores', 'strengths', 'areas_best'}}.
    bench è un id del glossario (lookup) o il nome della fonte se il glossario non lo conosce: ambito "other".
    leaders: {bench: [valori]} dei migliori di una classifica che non sono nel catalogo: contano in posizione, numero di
    modelli e frontiera, così una nicchia misurata su un solo modello nostro ha comunque la sua gara"""
    gl = {b['id']: b for b in glossary['benchmarks']}
    best = {m: _best(s) for m, s in scores_by_model.items()}
    columns = {}
    for m, by in best.items():
        for bench, s in by.items():
            columns.setdefault(bench, []).append((m, float(s['value'])))
    for bench, values in (leaders or {}).items():
        if bench in columns:                              # un leader conta solo dove un modello nostro è misurato
            columns[bench] += [(None, float(v)) for v in values]
    out = {}
    for m, by in best.items():
        scores, items = [], []
        for bench, s in by.items():
            g = gl.get(bench) or entry(bench, glossary)
            better, col = g.get('better', 'higher'), columns[bench]
            vals = [v for _, v in col]
            value = float(s['value'])
            rank = 1 + sum(1 for _, v in col if (v > value if better == 'higher' else v < value))
            f = _frontier(value, vals, better)
            scores += [{**x, 'frontier': _frontier(float(x['value']), vals, better)} for x in scores_by_model[m] if x['bench'] == bench]
            area = g.get('area', 'other')
            if area not in NOT_STRENGTHS and len(col) >= MIN_MODELS:
                items.append({'bench': bench, 'area': area, 'value': value, 'source': s.get('source', ''), 'rank': rank,
                              'of': len(col), 'trophy': rank == 1,
                              'weight': round((0.6 * f + 0.4 * (1 - rank / len(col))) * (1.0 if s.get('independent') else DECLARED), 4)})
        items.sort(key=lambda x: (-x['trophy'], -x['weight'], x['bench']))
        picked, per = [], {}
        for it in items:
            if len(picked) < TOP and per.get(it['area'], 0) < PER_AREA:
                picked.append(it)
                per[it['area']] = per.get(it['area'], 0) + 1
        mean = {a: sum(x['weight'] for x in picked if x['area'] == a) / n for a, n in per.items()}
        out[m] = {'scores': scores, 'strengths': picked, 'areas_best': sorted(mean, key=lambda a: (-mean[a], a))[:3]}
    return out


def _prova():
    g = load_glossary()
    assert check_glossary(g) == [], check_glossary(g)
    assert lookup('GPQA', g) == 'gpqa-diamond' and lookup('τ²-Bench Telecom', g) == 'tau2-telecom' and lookup('nope', g) is None
    bad = {'_meta': {'areas': {'code': {}}}, 'benchmarks': [
        {'id': 'a', 'name': 'A', 'area': 'code', 'unit': '%', 'better': 'up', 'aliases': ['x'], 'url': 'http://a', 'it': 'a', 'en': ''},
        {'id': 'b', 'name': 'B', 'area': 'nope', 'unit': '%', 'better': 'higher', 'aliases': ['X'], 'url': 'https://b', 'it': 'b', 'en': 'b'},
        {'id': 'c'}]}
    errs = ' | '.join(check_glossary(bad))
    for want in ('better', 'testo vuoto', 'non https', 'ambito sconosciuto', 'già di a', 'manca'):
        assert want in errs, (want, errs)
    s = lambda b, v, ind=True, date='2026-10-01', src='artificialanalysis': {'bench': b, 'value': v, 'independent': ind, 'date': date, 'source': src}
    code = ['livecodebench', 'swe-bench-verified', 'terminal-bench-2', 'aider-polyglot', 'humaneval']
    data = {
        'alfa': [s(b, 90) for b in code] + [s('gpqa-diamond', 80), s('aa-intelligence-index', 70), s('aa-ttft', 0.5),
                                              s('aa-omniscience', -10), s('niche-bench', 3)],
        'beta': [s(b, 60) for b in code] + [s('gpqa-diamond', 85, False, '2026-10-10', 'vendor'), s('gpqa-diamond', 79),
                                              s('aa-ttft', 2.0), s('aa-omniscience', 20)],
        'gamma': [s(b, 30) for b in code] + [s('gpqa-diamond', 40), s('aa-ttft', 1.0), s('aa-omniscience', 5), s('niche-bench', 1)],
        'delta': [s('niche-bench', 2), s('swe-bench-pro', 50)],
    }
    out = annotate(data, g)
    a, b = out['alfa'], out['beta']
    assert len([x for x in a['strengths'] if x['area'] == 'code']) == 3, a['strengths']             # al massimo 3 per ambito
    assert not any(x['bench'] == 'aa-intelligence-index' for x in a['strengths'])                    # gli indici no
    assert any(x['bench'] == 'aa-intelligence-index' for x in a['scores'])                           # ma restano tra i punteggi
    assert not any(x['area'] == 'efficiency' for m in out for x in out[m]['strengths'])              # #506 p.3: velocità e prezzo no
    ft = {m: next(x for x in out[m]['scores'] if x['bench'] == 'aa-ttft')['frontier'] for m in ('alfa', 'beta')}
    assert ft == {'alfa': 1.0, 'beta': 0.25}, ft                                                     # lower è meglio
    lcb = next(x for x in a['strengths'] if x['bench'] == 'livecodebench')
    assert lcb['trophy'] and lcb['of'] == 3
    assert not any(x['bench'] == 'swe-bench-pro' for x in out['delta']['strengths'])                # 1 modello solo: non è un punto forte
    assert any(x['bench'] == 'swe-bench-pro' for x in out['delta']['scores'])                         # ma resta tra i punteggi
    w = {x['bench']: x['weight'] for x in b['strengths']}
    assert w['aa-omniscience'] == round(0.6 * 1.0 + 0.4 * (1 - 1 / 3), 4), w                          # 0.6 x frontiera + 0.4 x (1 - rank/N)
    cg = annotate({'mistral-large-4': [s('cybergym-e2e-aa', 82)]}, g, leaders={'cybergym-e2e-aa': [79, 78], 'other': [1]})
    x = cg['mistral-large-4']['strengths'][0]
    assert (x['rank'], x['of'], x['trophy'], x['area']) == (1, 3, True, 'security'), x            # CyberGym 82 davanti a 79 e 78 (#530)
    assert not annotate({'m': [s('cybergym-e2e-aa', 70)]}, g, leaders={'cybergym-e2e-aa': [82, 79]})['m']['strengths'][0]['trophy']
    da = annotate({k: [s('design-arena-website', v)] for k, v in (('a', 1300), ('b', 1200), ('c', 1100))}, g)
    assert da['a']['strengths'][0]['area'] == 'design' and da['a']['strengths'][0]['trophy']          # famiglia Design Arena
    sw = lambda f, rank, n, ind: round((0.6 * f + 0.4 * (1 - rank / n)) * (1.0 if ind else DECLARED), 4)
    assert DECLARED == 0.7 and sw(1.0, 1, 3, False) == round(0.7 * (0.6 + 0.4 * 2 / 3), 4)
    gp = next(x for x in b['strengths'] if x['bench'] == 'gpqa-diamond')
    assert gp['value'] == 79                                                                         # indipendente prima del dichiarato
    assert sorted(x['value'] for x in b['scores'] if x['bench'] == 'gpqa-diamond') == [79, 85]       # ma tutte le fonti restano
    om = {m: next(x for x in out[m]['scores'] if x['bench'] == 'aa-omniscience')['frontier'] for m in ('alfa', 'beta', 'gamma')}
    assert om == {'alfa': 0.0, 'beta': 1.0, 'gamma': 0.5}, om                                        # valori negativi: tra peggiore e migliore
    assert next(x for x in a['strengths'] if x['bench'] == 'niche-bench')['area'] == 'other'         # fuori glossario: ambito other
    assert len(a['strengths']) <= TOP and a['areas_best'][0] in ('code', 'efficiency', 'science'), a['areas_best']
    assert all(x['source'] for m in out for x in out[m]['scores'])                                   # la fonte sempre presente (#117)
    print('strengths ok')


if __name__ == '__main__':
    _prova()
