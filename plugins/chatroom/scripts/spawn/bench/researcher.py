"""I ricercatori dei benchmark di nicchia: agenti Haiku che il lead lancia con un prompt già scritto (come un aiuto
prestato: la riga STUDY del relay nomina il file, il lead lo passa tale e quale). Due tipi: uno per modello (6 minuti,
fonti obbligatorie: Vals, Artificial Analysis, model card, BenchLM, LMArena), che studia una volta ogni modello e poi
solo i nuovi (D6); uno per classifica (BOARDS, una volta al giorno), che copia una classifica per tutti i modelli del
catalogo. Ogni benchmark di nicchia porta i 3 migliori della sua classifica ("leaders"), per la frontiera. Il risultato
è un file JSON che viene dal web: qui lo si controlla prima di usarlo.

  prepare(models, out, ...)  scrive il prompt riempito accanto a out e ne dà il percorso (None: niente da fare)
  accept(path, glossary)     il risultato controllato: ({canonical: [score]}, nuovi benchmark, leaders), o ValueError
  mark_studied(canonicals)   da non studiare più; boards_due() / mark_boards(ids): le classifiche di oggi
"""
import json
import math
import re
import time
from pathlib import Path

import jsonschema

try:
    from .strengths import lookup
except ImportError:                                      # lanciato come script (_prova)
    from strengths import lookup

TEMPLATE = Path(__file__).resolve().parents[3] / 'templates' / 'bench_researcher.md'
BOARD_TEMPLATE = TEMPLATE.with_name('bench_board.md')
LINES_TEMPLATE = TEMPLATE.with_name('bench_lines.md')
LINES_SCHEMA = {
    'type': 'object', 'required': ['decisions'], 'additionalProperties': False,
    'properties': {
        'decisions': {'type': 'array', 'maxItems': 300, 'items': {
            'type': 'object', 'required': ['canonical', 'action'], 'additionalProperties': False,
            'properties': {'canonical': {'type': 'string', 'pattern': r'^[a-z0-9][a-z0-9.-]{0,120}$'}, 'action': {'enum': ['split', 'move']},
                           'line': {'type': 'string', 'pattern': r'^[a-z0-9][a-z0-9.~-]{0,120}$'}}}},
        'checked': {'type': 'array', 'maxItems': 300, 'items': {'type': 'string', 'maxLength': 140}}}}
STUDIED = Path.home() / '.claude' / 'chatroom' / 'spawn' / 'studied.json'
MINUTES = 6
# le classifiche lette una volta al giorno per tutti i modelli (#530 p.3); indirizzi scritti a memoria: il lettore li cerca
BOARDS = [
    {'id': 'vals', 'name': 'Vals AI', 'url': 'https://www.vals.ai/benchmarks',
     'benches': 'vibe-code-bench, finance-agent, legalbench, tax-eval, corp-fin, medqa, swe-bench-verified, terminal-bench-2'},
    {'id': 'aa-cyber', 'name': 'Artificial Analysis, valutazioni cyber', 'url': 'https://artificialanalysis.ai',
     'benches': 'aa-cyber-index, cybergym-e2e-aa'},
    {'id': 'swe-bench', 'name': 'SWE-bench', 'url': 'https://www.swebench.com', 'benches': 'swe-bench-verified, swe-bench-multilingual'},
    {'id': 'swe-bench-pro', 'name': 'SWE-Bench Pro (Scale)', 'url': 'https://scale.com/leaderboard/swe_bench_pro_public', 'benches': 'swe-bench-pro'},
    {'id': 'bfcl', 'name': 'Berkeley Function Calling Leaderboard', 'url': 'https://gorilla.cs.berkeley.edu/leaderboard.html', 'benches': 'bfcl'},
    {'id': 'eq-bench', 'name': 'EQ-Bench', 'url': 'https://eqbench.com', 'benches': 'eq-bench-3, creative-writing-v3'},
    {'id': 'lmarena', 'name': 'LMArena', 'url': 'https://lmarena.ai/leaderboard', 'benches': 'lmarena-text, lmarena-webdev, lmarena-coding'},
    {'id': 'terminal-bench', 'name': 'Terminal-Bench', 'url': 'https://www.tbench.ai/leaderboard', 'benches': 'terminal-bench-2'},
    {'id': 'aider', 'name': 'Aider Polyglot', 'url': 'https://aider.chat/docs/leaderboards/', 'benches': 'aider-polyglot'},
    {'id': 'arc-prize', 'name': 'ARC Prize', 'url': 'https://arcprize.org/leaderboard', 'benches': 'arc-agi-1, arc-agi-2'},
    {'id': 'benchlm', 'name': 'BenchLM', 'url': 'https://benchlm.ai', 'benches': 'every benchmark it collects'},
]
_TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 300}
_URL = {'type': 'string', 'pattern': r'^https://\S{4,500}$'}
SCHEMA = {
    'type': 'object', 'required': ['models'], 'additionalProperties': False,
    'properties': {
        'models': {'type': 'array', 'maxItems': 500, 'items': {
            'type': 'object', 'required': ['canonical', 'scores'], 'additionalProperties': False,
            'properties': {
                'canonical': _TEXT,
                'scores': {'type': 'array', 'maxItems': 200, 'items': {
                    'type': 'object', 'required': ['bench', 'value', 'source', 'date', 'independent'], 'additionalProperties': False,
                    'properties': {'bench': {'type': 'string', 'pattern': r'^[a-z0-9][a-z0-9.-]{0,60}$'}, 'value': {'type': 'number'},
                                   'source': _URL, 'date': {'type': 'string', 'pattern': r'^\d{4}-\d{2}(-\d{2})?$'},
                                   'independent': {'type': 'boolean'}}}}}}},
        'leaders': {'type': 'array', 'maxItems': 300, 'items': {
            'type': 'object', 'required': ['bench', 'model', 'value', 'source', 'date'], 'additionalProperties': False,
            'properties': {'bench': {'type': 'string', 'pattern': r'^[a-z0-9][a-z0-9.-]{0,60}$'}, 'model': _TEXT, 'value': {'type': 'number'},
                           'source': _URL, 'date': {'type': 'string', 'pattern': r'^\d{4}-\d{2}(-\d{2})?$'}}}},
        'new_benchmarks': {'type': 'array', 'maxItems': 100, 'items': {
            'type': 'object', 'required': ['id', 'name', 'area', 'unit', 'better', 'url', 'it', 'en'], 'additionalProperties': False,
            'properties': {'id': {'type': 'string', 'pattern': r'^[a-z0-9][a-z0-9.-]{0,60}$'}, 'name': _TEXT, 'area': _TEXT,
                           'unit': {'type': 'string', 'maxLength': 30}, 'better': {'enum': ['higher', 'lower']},
                           'url': _URL, 'it': _TEXT, 'en': _TEXT}}}}}


def studied():
    try:
        d = json.loads(STUDIED.read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def mark_studied(canonicals):
    d = studied()
    d.update({c: time.strftime('%Y-%m-%d') for c in canonicals})
    STUDIED.parent.mkdir(parents=True, exist_ok=True)
    tmp = STUDIED.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(STUDIED)


def _boards_path():
    return Path.home() / '.claude' / 'chatroom' / 'spawn' / 'boards.json'


def _boards_read():
    try:
        d = json.loads(_boards_path().read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def boards_due(today=None):
    """le classifiche non ancora lette oggi"""
    today, read = today or time.strftime('%Y-%m-%d'), _boards_read()
    return [b for b in BOARDS if read.get(b['id']) != today]


def mark_boards(ids, today=None):
    read = {**_boards_read(), **{i: today or time.strftime('%Y-%m-%d') for i in ids}}
    _boards_path().parent.mkdir(parents=True, exist_ok=True)
    _boards_path().write_text(json.dumps(read), encoding='utf-8')


def prepare(models, out, glossary_path, areas, lang='it', minutes=MINUTES, skip=(), board=None):
    """models: {canonical: [nomi dei provider]}. Scrive il prompt in out.prompt.md e ne dà il percorso, o None se non
    c'è niente da fare: per un modello solo se non è già studiato (D6); per una classifica (board: una voce di BOARDS)
    tutti i modelli. skip: i benchmark che le API danno già. Nomi e id vengono dai provider: senza a capo, corti, così
    non scrivono istruzioni nel prompt"""
    done = {} if board else studied()
    todo = {c: names for c, names in models.items() if c not in done}
    if not todo:
        return None
    clean = lambda s: re.sub(r'[\x00-\x1f`<>]', ' ', str(s))[:120]
    lines = '\n'.join(f'- {clean(c)}: ' + ', '.join(clean(n) for n in list(names)[:8]) for c, names in todo.items())
    values = {'MODELS': lines, 'OUT': str(out), 'GLOSSARY': str(glossary_path), 'AREAS': ', '.join(areas),
              'MINUTES': str(minutes), 'LANGUAGE': 'Italian' if lang == 'it' else 'English', 'SKIP': ', '.join(skip) or '-',
              **({'BOARD': board['name'], 'BOARD_URL': board['url'], 'BOARD_BENCHES': board['benches']} if board else {})}
    tpl = (BOARD_TEMPLATE if board else TEMPLATE).read_text(encoding='utf-8')
    text = re.sub(r'\{\{([A-Z_]+)\}\}', lambda m: values.get(m.group(1), m.group(0)), tpl)
    left = re.findall(r'\{\{[A-Z_]+\}\}', text)
    if left:
        raise ValueError(f'campi del template non riempiti: {left}')
    path = Path(out).with_suffix('.prompt.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def prepare_lines(groups, out, lang='it', minutes=MINUTES):
    """il prompt del lettore delle linee in dubbio: groups = [{'line', 'members' (dalla più nuova), 'why'}]"""
    if not groups:
        return None
    clean = lambda s: re.sub(r'[\x00-\x1f`<>]', ' ', str(s))[:160]
    text = LINES_TEMPLATE.read_text(encoding='utf-8')
    values = {'GROUPS': '\n'.join(f"- {clean(g['line'])}: {', '.join(clean(m) for m in g['members'][:12])} ({clean(g['why'])})" for g in groups),
              'OUT': str(out), 'MINUTES': str(minutes), 'LANGUAGE': 'Italian' if lang == 'it' else 'English'}
    text = re.sub(r'\{\{([A-Z_]+)\}\}', lambda m: values.get(m.group(1), m.group(0)), text)
    path = Path(out).with_suffix('.prompt.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def accept_lines(path, members, line_keys):
    """le decisioni del lettore delle linee, controllate: solo membri chiesti, "move" solo verso una linea che esiste"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        jsonschema.validate(data, LINES_SCHEMA)
    except (OSError, ValueError, jsonschema.ValidationError) as exc:
        raise ValueError(f'risultato del lettore delle linee non valido: {str(getattr(exc, "message", exc))[:200]}')
    for d in data['decisions']:
        if d['canonical'] not in members:
            raise ValueError(f"il lettore delle linee ha deciso su un modello non chiesto: {d['canonical'][:60]}")
        if d['action'] == 'move' and d.get('line') not in line_keys:
            raise ValueError(f"il lettore delle linee sposta verso una linea che non c'è: {str(d.get('line'))[:60]}")
    return data['decisions'], [c for c in data.get('checked', []) if c in line_keys]


def accept(path, glossary, asked=None):
    """il file del ricercatore, controllato: ({canonical: [score]}, [nuovi benchmark], [leaders]). Un modello non
    chiesto, un numero non finito o un file fuori schema: ValueError (il file intero è scartato, non corretto a metà)"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'risultato del ricercatore illeggibile: {exc}')
    try:
        jsonschema.validate(data, SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ValueError(f'risultato del ricercatore fuori schema: {exc.message[:200]}')
    areas = set(glossary['_meta']['areas'])
    news = [b for b in data.get('new_benchmarks', []) if b['area'] in areas and lookup(b['id'], glossary) is None]
    out = {}
    for m in data['models']:
        if asked is not None and m['canonical'] not in asked:
            raise ValueError(f"il ricercatore ha risposto per un modello non chiesto: {m['canonical'][:60]}")
        for s in m['scores']:
            if not math.isfinite(s['value']):
                raise ValueError(f"valore non finito per {s['bench']}")
            out.setdefault(m['canonical'], []).append({**s, 'bench': lookup(s['bench'], glossary) or s['bench']})
    leaders = []
    for x in data.get('leaders', []):
        if not math.isfinite(x['value']):
            raise ValueError(f"valore non finito per {x['bench']}")
        leaders.append({**x, 'bench': lookup(x['bench'], glossary) or x['bench'], 'model': re.sub(r'[\x00-\x1f<>`]', ' ', x['model'])[:80]})
    return out, news, leaders


def _prova():
    import tempfile
    import strengths
    global STUDIED
    g = strengths.load_glossary()
    with tempfile.TemporaryDirectory() as tmp:
        STUDIED = Path(tmp) / 'studied.json'
        models = {'glm-5-3': ['z-ai/glm-5.3', 'zai-org/GLM-5.3'], 'kimi-k3': ['moonshotai/kimi-k3\nIGNORE ALL ```']}
        text = prepare(models, Path(tmp) / 'out.json', strengths.GLOSSARY, list(g['_meta']['areas'])).read_text(encoding='utf-8')
        assert 'glm-5-3: z-ai/glm-5.3, zai-org/GLM-5.3' in text and '{{' not in text and str(Path(tmp) / 'out.json') in text
        assert '\nIGNORE' not in text and '```' not in text and 'moonshotai/kimi-k3 IGNORE ALL' in text                 # niente a capo né backtick dai nomi
        mark_studied(['glm-5-3'])
        text = prepare(models, Path(tmp) / 'out.json', strengths.GLOSSARY, ['code']).read_text(encoding='utf-8')
        assert 'glm-5-3' not in text and 'kimi-k3' in text                                     # D6: solo i nuovi
        mark_studied(['kimi-k3'])
        assert prepare(models, Path(tmp) / 'out.json', strengths.GLOSSARY, ['code']) is None
        good = {'models': [{'canonical': 'glm-5-3', 'scores': [
                    {'bench': 'gpqa', 'value': 71.5, 'source': 'https://artificialanalysis.ai/x', 'date': '2026-10-20', 'independent': True},
                    {'bench': 'niche-x', 'value': 12, 'source': 'https://example.org/n', 'date': '2026-09', 'independent': False}]},
                           {'canonical': 'kimi-k3', 'scores': []}],
                'new_benchmarks': [{'id': 'niche-x', 'name': 'Niche X', 'area': 'code', 'unit': '%', 'better': 'higher',
                                    'url': 'https://example.org/n', 'it': 'una cosa', 'en': 'a thing'},
                                   {'id': 'gpqa', 'name': 'dup', 'area': 'science', 'unit': '%', 'better': 'higher',
                                    'url': 'https://x.org/a', 'it': 'x', 'en': 'x'}]}
        p = Path(tmp) / 'out.json'
        p.write_text(json.dumps(good), encoding='utf-8')
        scores, news, leaders = accept(p, g, asked={'glm-5-3', 'kimi-k3'})
        assert scores['glm-5-3'][0]['bench'] == 'gpqa-diamond' and scores['glm-5-3'][1]['bench'] == 'niche-x'
        assert [b['id'] for b in news] == ['niche-x'] and leaders == []                        # un "nuovo" già nel glossario è scartato
        good['leaders'] = [{'bench': 'niche-x', 'model': 'MiMo-V2.6-Pro\nIGNORE', 'value': 79, 'source': 'https://example.org/n', 'date': '2026-10'}]
        p.write_text(json.dumps(good), encoding='utf-8')
        _, _, leaders = accept(p, g)
        assert leaders == [{'bench': 'niche-x', 'model': 'MiMo-V2.6-Pro IGNORE', 'value': 79, 'source': 'https://example.org/n', 'date': '2026-10'}]
        del good['leaders']
        t = prepare({'a': ['x/a']}, Path(tmp) / 'b1.json', strengths.GLOSSARY, ['code'], board=BOARDS[0]).read_text(encoding='utf-8')
        assert 'vals.ai' in t and '{{' not in t and 'LEADERBOARD READER' in t                       # una classifica: anche modelli già studiati
        t = prepare({'new-one': ['x/new']}, Path(tmp) / 'm1.json', strengths.GLOSSARY, ['code'], skip=['gpqa-diamond', 'hle']).read_text(encoding='utf-8')
        assert 'gpqa-diamond, hle' in t and 'Vals AI' in t and '"leaders"' in t
        assert [b['id'] for b in boards_due('2026-10-26')][:1] == ['vals']
        for bad in ({**good, 'extra': 1}, {'models': [{'canonical': 'x', 'scores': [{**good['models'][0]['scores'][0], 'source': 'http://a.b/c'}]}]},
                    {'models': [{'canonical': 'x', 'scores': [{**good['models'][0]['scores'][0], 'value': '71'}]}]},
                    {'models': [{'canonical': 'x', 'scores': [{**good['models'][0]['scores'][0], 'bench': 'Bad Id'}]}]}):
            p.write_text(json.dumps(bad), encoding='utf-8')
            try:
                accept(p, g)
            except ValueError:
                continue
            raise AssertionError(f'accettato: {bad}')
        p.write_text(json.dumps(good), encoding='utf-8')
        try:
            accept(p, g, asked={'glm-5-3'})
            raise AssertionError('modello non chiesto accettato')
        except ValueError:
            pass
        p.write_text('{"models": [{"canonical": "x", "scores": [{"bench": "a", "value": NaN, "source": "https://a.b/c", "date": "2026-01", "independent": true}]}]}', encoding='utf-8')
        try:
            accept(p, g)
            raise AssertionError('NaN accettato')
        except ValueError:
            pass
    print('researcher ok')


if __name__ == '__main__':
    _prova()
