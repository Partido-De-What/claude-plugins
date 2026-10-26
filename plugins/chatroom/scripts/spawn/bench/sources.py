"""Le fonti veloci dei punteggi (coda benchmark, 30 s): per ora Artificial Analysis, con la chiave gratuita (D2, 100
richieste al giorno: una lettura al giorno basta, la tiene in cache il catalogo).

La forma della risposta (GET /api/v2/data/llms/models, header x-api-key) è scritta dalla documentazione pubblica come la
ricordo: non verificata con una chiave vera. Per questo il parser è tollerante: una chiave di valutazione sconosciuta
entra lo stesso col suo nome (aa-<chiave>), le percentuali scritte come frazioni (0.71) si riconoscono per colonna."""
import math
import re
import time

try:
    from .strengths import lookup
except ImportError:                                      # lanciato come script (_prova)
    from strengths import lookup

AA_URL = 'https://artificialanalysis.ai/api/v2/data/llms/models'
AA_PAGE = 'https://artificialanalysis.ai/models/'
AA_KEYS = {'artificial_analysis_intelligence_index': 'aa-intelligence-index', 'artificial_analysis_coding_index': 'aa-coding-index',
           'artificial_analysis_math_index': 'aa-math-index', 'lcr': 'aa-lcr', 'tau2': 'tau2-telecom', 'terminalbench_hard': 'terminal-bench-hard',
           'aime': 'aime-2024', 'aime_25': 'aime-2025', 'math_500': 'math-500', 'gpqa': 'gpqa-diamond', 'hle': 'hle',
           'terminalbench_v2_1': 'terminal-bench-2-1', 'terminalbench_v4_0': 'terminal-bench-4', 'tau_banking': 'tau2-banking',
           'artificial_analysis_agentic_index': 'aa-agentic-index'}
OR_AA = {'intelligence_index': 'aa-intelligence-index', 'coding_index': 'aa-coding-index', 'agentic_index': 'aa-agentic-index'}
OR_PAGE = 'https://openrouter.ai/'
AA_METRICS = {('median_output_tokens_per_second',): 'aa-output-speed', ('median_time_to_first_token_seconds',): 'aa-ttft',
              ('pricing', 'price_1m_blended_3_to_1'): 'aa-price-blended'}
INDEXES = {'aa-intelligence-index', 'aa-coding-index', 'aa-math-index'}
VARIANT_WORDS = {'reasoning', 'thinking', 'instruct', 'preview', 'non', 'high', 'low', 'medium', 'max', 'it'}


def fetch_aa(key, timeout=30):
    """la lista dei modelli di Artificial Analysis (una richiesta); la chiave va solo nell'header, mai in un URL o in un log"""
    import httpx
    r = httpx.get(AA_URL, headers={'x-api-key': key}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _bench(key, glossary):
    return AA_KEYS.get(key) or lookup(key.replace('_', '-'), glossary) or 'aa-' + re.sub(r'[^a-z0-9]+', '-', key.lower()).strip('-')[:57]


def parse_aa(payload, glossary, date=None):
    """{slug: {'name', 'aa', 'scores': [{'bench', 'value', 'source', 'date', 'independent': True}]}} dalla risposta di AA"""
    date = date or time.strftime('%Y-%m-%d')
    rows = [m for m in (payload or {}).get('data') or [] if isinstance(m, dict) and isinstance(m.get('slug'), str) and m['slug'].strip()]
    num = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None
    fraction = {}                                         # una colonna di valutazione tutta tra 0 e 1 è in frazioni
    for m in rows:
        for k, v in (m.get('evaluations') or {}).items():
            if num(v) is not None and _bench(k, glossary) not in INDEXES:
                fraction[k] = fraction.get(k, True) and 0 <= num(v) <= 1
    out = {}
    for m in rows:
        slug = m['slug'].strip()[:120]
        src = AA_PAGE + re.sub(r'[^A-Za-z0-9._-]', '', slug)
        scores = []
        for k, v in (m.get('evaluations') or {}).items():
            if num(v) is not None:
                scores.append({'bench': _bench(k, glossary), 'value': round(num(v) * (100 if fraction.get(k) else 1), 4)})
        for path, bench in AA_METRICS.items():
            v = m
            for p in path:
                v = v.get(p) if isinstance(v, dict) else None
            if num(v) is not None and num(v) > 0:         # 0 = non misurato
                scores.append({'bench': bench, 'value': num(v)})
        scores = [{**s, 'source': src, 'date': date, 'independent': True} for s in scores]
        aa = next((s['value'] for s in scores if s['bench'] == 'aa-intelligence-index'), None)
        out[slug] = {'name': str(m.get('name') or slug)[:120], 'aa': aa, 'scores': scores}
    return out


def parse_openrouter(benchmarks, model_id, date=None):
    """i punteggi che OpenRouter scrive nella sua lista dei modelli (benchmarks di /models, gratis: arrivano con la lista):
    gli indici di Artificial Analysis e Design Arena per categoria (design-arena-<categoria>, o design-arena-agents-<...>
    per l'arena degli agenti). Tutti indipendenti: li misurano AA e i voti di Design Arena, non il produttore"""
    date = date or time.strftime('%Y-%m-%d')
    b = benchmarks if isinstance(benchmarks, dict) else {}
    src = OR_PAGE + re.sub(r'[^A-Za-z0-9._/-]', '', str(model_id).split(':')[0])
    num = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None
    out = [{'bench': bench, 'value': num(v)} for k, bench in OR_AA.items()
           for v in [(b.get('artificial_analysis') or {}).get(k) if isinstance(b.get('artificial_analysis'), dict) else None] if num(v) is not None]
    for d in b.get('design_arena') if isinstance(b.get('design_arena'), list) else []:
        cat = re.sub(r'[^a-z0-9]+', '-', str(d.get('category', '')).lower()).strip('-')[:30] if isinstance(d, dict) else ''
        if cat and num(d.get('elo')) is not None:
            arena = 'design-arena-agents-' if d.get('arena') == 'agents' else 'design-arena-'
            out.append({'bench': arena + cat, 'value': num(d['elo'])})
    return [{**x, 'source': src, 'date': date, 'independent': True} for x in out]


OR_BENCH_URL = 'https://openrouter.ai/api/v1/benchmarks'
OR_BENCH_SOURCES = ('artificial-analysis', 'openrouter', 'design-arena')
OR_TYPES = {'gpqa_diamond': 'gpqa-diamond', 'tau_bench_verified_airline': 'tau-bench-verified-airline'}


def fetch_or_benchmarks(key, timeout=30):
    """le tre fonti di /benchmarks di OpenRouter (con la chiave Bearer; senza risponde 401; 30 al minuto, 500 al giorno)"""
    import httpx
    out = {}
    for src in OR_BENCH_SOURCES:
        r = httpx.get(OR_BENCH_URL, params={'source': src}, headers={'Authorization': f'Bearer {key}'}, timeout=timeout)
        r.raise_for_status()
        out[src] = r.json()
    return out


def parse_or_benchmarks(payloads, glossary):
    """{slug: {'name', 'aa', 'scores'}} dalle risposte di /benchmarks (source -> {data, meta}), come parse_aa, da
    accoppiare al catalogo con match(). Lo slug è model_permaslug senza la data in coda (google/gemini-4-argon-20261013)"""
    num = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None
    out = {}
    for src, payload in (payloads or {}).items():
        meta = (payload or {}).get('meta') or {}
        date = str(meta.get('as_of') or '')[:10] or time.strftime('%Y-%m-%d')
        page = meta.get('source_url') if str(meta.get('source_url', '')).startswith('https://') else 'https://openrouter.ai/rankings'
        for r in (payload or {}).get('data') or []:
            if not isinstance(r, dict) or not isinstance(r.get('model_permaslug'), str):
                continue
            slug = re.sub(r'-\d{8}$', '', r['model_permaslug'].strip().lower())[:120]
            rows = []
            if src == 'artificial-analysis':
                rows = [(bench, num(r.get(k))) for k, bench in OR_AA.items()]
            elif src == 'openrouter' and num(r.get('accuracy')) is not None:
                t = str(r.get('benchmark_type', ''))
                rows = [(OR_TYPES.get(t) or lookup(t.replace('_', '-'), glossary) or 'or-' + re.sub(r'[^a-z0-9]+', '-', t.lower())[:50],
                         num(r['accuracy']) * 100)]
            elif src == 'design-arena' and r.get('category'):
                cat = re.sub(r'[^a-z0-9]+', '-', str(r['category']).lower()).strip('-')[:30]
                rows = [(('design-arena-agents-' if r.get('arena') == 'agents' else 'design-arena-') + cat, num(r.get('elo')))]
            m = out.setdefault(slug, {'name': str(r.get('display_name') or slug)[:120], 'aa': None, 'scores': []})
            for bench, v in rows:
                if v is not None and not any(x['bench'] == bench for x in m['scores']):   # la prima riga (la più recente) vince
                    m['scores'].append({'bench': bench, 'value': round(v, 4), 'source': page, 'date': date, 'independent': True})
                    if bench == 'aa-intelligence-index':
                        m['aa'] = v
    return out


def or_bench_scores(key, canonicals, glossary, payloads=None):
    """la fonte /benchmarks per la coda veloce: {canonical: [score]}"""
    ob = parse_or_benchmarks(fetch_or_benchmarks(key) if payloads is None else payloads, glossary)
    return {c: ob[slug]['scores'] for c, slug in match(ob, canonicals).items()}


def _tokens(name):
    return frozenset(t for t in re.split(r'[^a-z0-9]+', str(name).lower()) if t and t not in VARIANT_WORDS)


def match(aa, canonicals):
    """{canonical: slug di AA} per i modelli del catalogo che AA conosce. Prima la chiave uguale, poi le stesse parole in
    qualsiasi ordine (AA scrive claude-4-5-sonnet, i provider claude-sonnet-4-5) senza le parole di variante; tra due
    varianti dello stesso modello vince quella con l'indice più alto"""
    from_identity = {}
    try:
        from ..catalog.identity import canonical_id
    except ImportError:                                  # lanciato come script (_prova)
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'catalog'))
        from identity import canonical_id
    for slug in aa:
        from_identity.setdefault(canonical_id(slug), []).append(slug)
    by_tokens = {}
    for slug in aa:
        by_tokens.setdefault(_tokens(canonical_id(slug)), []).append(slug)
    best = lambda slugs: max(slugs, key=lambda s: (aa[s]['aa'] is not None, aa[s]['aa'] or 0, s))
    out = {}
    for c in canonicals:
        hit = from_identity.get(c) or by_tokens.get(_tokens(c))
        if hit:
            out[c] = best(hit)
    return out


def aa_scores(key, canonicals, glossary, payload=None):
    """la fonte AA per la coda veloce (catalog.fast_scores): {canonical: [score]} dei modelli del catalogo che AA conosce"""
    aa = parse_aa(fetch_aa(key) if payload is None else payload, glossary)
    return {c: aa[slug]['scores'] for c, slug in match(aa, canonicals).items()}


def _prova():
    import strengths
    g = strengths.load_glossary()
    payload = {'status': 200, 'data': [
        {'id': 'u1', 'name': 'GLM-5.3 (Reasoning)', 'slug': 'glm-5-3-reasoning', 'model_creator': {'slug': 'zai'},
         'evaluations': {'artificial_analysis_intelligence_index': 61.2, 'mmlu_pro': 0.842, 'gpqa': 0.781, 'lcr': 0.66,
                         'tau2': 0.9, 'some_new_eval': 0.5, 'hle': None},
         'pricing': {'price_1m_blended_3_to_1': 0.0}, 'median_output_tokens_per_second': 88.5, 'median_time_to_first_token_seconds': 0.9},
        {'id': 'u2', 'name': 'GLM-5.3', 'slug': 'glm-5-3', 'evaluations': {'artificial_analysis_intelligence_index': 48.0, 'mmlu_pro': 0.8},
         'median_output_tokens_per_second': 0},
        {'id': 'u3', 'name': 'Claude 4.5 Sonnet', 'slug': 'claude-4-5-sonnet', 'evaluations': {'artificial_analysis_intelligence_index': 63,
         'mmlu_pro': 0.87, 'some_new_eval': 2.5}, 'pricing': {'price_1m_blended_3_to_1': 6.0}},
        {'id': 'u4', 'name': 'bad', 'slug': '', 'evaluations': {}}, 'junk',
        {'id': 'u5', 'name': 'NaN', 'slug': 'nan-model', 'evaluations': {'gpqa': float('nan'), 'mmlu_pro': True}}]}
    aa = parse_aa(payload, g, date='2026-10-26')
    assert set(aa) == {'glm-5-3-reasoning', 'glm-5-3', 'claude-4-5-sonnet', 'nan-model'}, set(aa)
    r = {s['bench']: s['value'] for s in aa['glm-5-3-reasoning']['scores']}
    assert r['mmlu-pro'] == 84.2 and r['gpqa-diamond'] == 78.1 and r['aa-lcr'] == 66.0 and r['tau2-telecom'] == 90.0, r
    assert r['aa-intelligence-index'] == 61.2 and r['aa-output-speed'] == 88.5 and r['aa-ttft'] == 0.9 and 'aa-price-blended' not in r
    assert r['aa-some-new-eval'] == 0.5 and 'hle' not in r                     # una colonna con 2.5: non è in frazioni
    assert 'aa-output-speed' not in {s['bench'] for s in aa['glm-5-3']['scores']} and aa['nan-model']['scores'] == []
    s0 = aa['glm-5-3-reasoning']['scores'][0]
    assert s0['independent'] and s0['date'] == '2026-10-26' and s0['source'] == 'https://artificialanalysis.ai/models/glm-5-3-reasoning'
    assert aa['glm-5-3-reasoning']['aa'] == 61.2 and aa['nan-model']['aa'] is None
    m = match(aa, ['glm-5-3', 'claude-sonnet-4-5', 'kimi-k3'])
    assert m == {'glm-5-3': 'glm-5-3', 'claude-sonnet-4-5': 'claude-4-5-sonnet'}, m
    m = match({k: v for k, v in aa.items() if k != 'glm-5-3'}, ['glm-5-3'])
    assert m == {'glm-5-3': 'glm-5-3-reasoning'}, m                             # solo la variante: la prende
    orb = {'design_arena': [{'arena': 'models', 'category': 'Website', 'elo': 1322, 'rank': 6}, {'arena': 'agents', 'category': 'agenticslides(html)', 'elo': 1200},
                            {'arena': 'models', 'category': 'x', 'elo': None}, 'junk'],
           'artificial_analysis': {'intelligence_index': 55.1, 'coding_index': None, 'agentic_index': float('nan')}}
    o = {x['bench']: x['value'] for x in parse_openrouter(orb, 'moonshotai/kimi-k3.1-pro:free', '2026-10-26')}
    assert o == {'aa-intelligence-index': 55.1, 'design-arena-website': 1322.0, 'design-arena-agents-agenticslides-html': 1200.0}, o
    assert parse_openrouter(orb, 'a/b:free')[0]['source'] == 'https://openrouter.ai/a/b' and parse_openrouter(None, 'x') == []
    import json
    from pathlib import Path
    real = Path(r'E:\claudecode pesante\claude-plugins-dev-tools\cantiere013\prove\payload')   # risposte vere salvate dal LEAD (#548)
    if real.is_dir():
        pl = {s: json.loads((real / f"or_benchmarks_{s.replace('artificial-analysis', 'aa').replace('-', '_')}.json").read_text(encoding='utf-8'))
              for s in OR_BENCH_SOURCES}
        ob = parse_or_benchmarks(pl, g)
        argon = ob['google/gemini-4-argon']
        assert {x['bench'] for x in argon['scores']} >= {'gpqa-diamond'} and all(0 < x['value'] <= 100 for x in argon['scores'] if x['bench'] == 'gpqa-diamond')
        assert any(x['bench'].startswith('design-arena-') for v in ob.values() for x in v['scores'])
        assert ob['anthropic/claude-opus-5.5']['aa'] == 57.6 and argon['scores'][0]['date'].startswith('2026-10-')
        got = or_bench_scores(None, ['claude-opus-5-5', 'gemini-4-argon', 'nessuno'], g, payloads=pl)
        assert set(got) == {'claude-opus-5-5', 'gemini-4-argon'}, set(got)
        aa_real = parse_aa(json.loads((real / 'aa_models.json').read_text(encoding='utf-8')), g)
        assert len(aa_real) > 600 and aa_real['claude-opus-5-5']['aa'] == 57.6
    got = aa_scores(None, ['glm-5-3', 'kimi-k3'], g, payload=payload)
    assert list(got) == ['glm-5-3'] and got['glm-5-3'] == aa['glm-5-3']['scores']
    print('sources ok')


if __name__ == '__main__':
    _prova()
