"""One question to many free models at once: `chat.py spawn consult PROMPT.md OUT_DIR [--top N] [--ids host:id,id] [--openrouter] [--dry]`.
A room wrote this by hand three times (consulto.py); here it is. One answer per file (OUT_DIR/NN-model.md, written as it comes),
the state in OUT_DIR/stato.json. A model that drips for DEADLINE seconds, or answers with less than MIN_CHARS characters, is
given up and the next route of the same model is tried."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEADLINE = 900            # seconds for one route
MIN_CHARS = 400           # shorter is an empty answer or a refusal
WORKERS = 20


def _routes(m, has_key):
    rs = [r for r in m.get('routes') or [] if r.get('free') and has_key(r['adapter'])]
    return sorted(rs, key=lambda r: r['adapter'] == 'huggingface')      # huggingface last: its quota ends at the ping


def pick(top=60, ids=None, openrouter=False, catalog_models=None, has_key=None, live=None):
    """the models to ask: [(prefix, model)], from the catalog (the best free routes with a key), a host and ids chosen by hand
    (`ids` = 'host:id,id'), or the live list of OpenRouter (`live`: its /models data, stealth models first)"""
    if ids:
        host, _, lst = ids.partition(':')
        return [(host[:2].upper(), {'canonical': i.replace('/', '_').replace(':', '_'), 'aa': None,
                                    'routes': [{'adapter': host, 'model_id': i, 'free': True}]}) for i in lst.split(',') if i]
    if openrouter:
        import research
        return [('OR', {'canonical': m['id'].replace('/', '_').replace(':', '_'), 'aa': None, 'ctx': m.get('context_length'),
                        'routes': [{'adapter': 'open_router', 'model_id': m['id'], 'free': True}]})
                for m in research.panel_models(live or [])[:top]]
    from spawn.catalog import catalog
    models = sorted(catalog_models if catalog_models is not None else catalog.load()['models'], key=catalog.order)
    return [('', m) for m in models if _routes(m, has_key)][:top]


def consult(prompt, out, picked, has_key, complete, deadline=DEADLINE, workers=WORKERS, say=print):
    """ask every picked model; returns the rows [{n, model, host, s, chars, errors}], one line printed for each"""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows, lock = [], threading.Lock()

    def ask(i, prefix, m):
        row = {'n': i + 1, 'model': m['canonical'], 'aa': m.get('aa'), 'host': None, 's': None, 'chars': 0, 'errors': []}
        t0 = time.time()
        for r in _routes(m, has_key):
            stop = threading.Event()
            timer = threading.Timer(deadline, stop.set)
            timer.start()
            try:
                got = complete(r['adapter'], r['model_id'], [{'role': 'user', 'content': prompt}], max_tokens=8192, attempts=2, stop=stop, effort='high')
                text = (got.get('text') or '').strip()
                if len(text) < MIN_CHARS:
                    raise ValueError(f'short answer ({len(text)} characters)')
                row.update(host=r['adapter'], s=round(time.time() - t0), chars=len(text))
                (out / f"{prefix}{i + 1:02d}-{m['canonical']}.md").write_text(f"# {m['canonical']} (host {r['adapter']}, {row['s']} s)\n\n{text}\n", encoding='utf-8')
                break
            except Exception as exc:            # one route failing must not stop the others: the error is kept in the row
                row['errors'].append(f"{r['adapter']}: {type(exc).__name__} {' '.join(str(getattr(exc, 'detail', exc)).split())[:120]}")
            finally:
                timer.cancel()
        with lock:
            rows.append(row)
            (out / 'stato.json').write_text(json.dumps(sorted(rows, key=lambda x: x['n']), indent=1, ensure_ascii=False), encoding='utf-8')

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda x: ask(x[0], *x[1]), enumerate(picked)))
    for r in sorted(rows, key=lambda x: x['n']):
        say(f"{r['n']:>2} {r['model']:<36} {(r['host'] or 'NO ANSWER'):<16} {r['s'] or '':>5} s {r['chars']:>6} chars {'; '.join(r['errors'])[:110]}")
    say(f"{sum(bool(r['host']) for r in rows)}/{len(rows)} answers in {out}")
    return sorted(rows, key=lambda x: x['n'])
