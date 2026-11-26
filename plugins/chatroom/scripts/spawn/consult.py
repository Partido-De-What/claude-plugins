"""One question to many free models at once, and the model council built on it.

    chat.py spawn consult PROMPT.md OUT_DIR [--top N | --per-host N] [--stealth] [--new-since DATE] [--ids host:id,id] [--openrouter]
                          [--attach FILE ...] [--web] [--deadline S] [--max-tokens N] [--retry-failed] [--retry-dead] [--claude MODEL] [--dry]
    chat.py spawn council "the situation" [OUT_DIR] [--n 10] [--attach FILE ...] [--web]

A room wrote the consult by hand five times (consulto.py, chiedi.py); here it is, with what those scripts patched from outside.
No budget of our own: the output asked is the most the host takes (correct() lowers it at the host's 400), there is no deadline
unless one is given, a route waits an hour for a byte, searching is not counted. What still cuts an answer (the host's quota, a
gateway's duration limit, a truncated or empty answer) is written in the outcome, never silent, and never saved as an answer.

OUT_DIR/<model>.md is one answer, with its outcome in the head; OUT_DIR/stato.json is the state, written while the models think
(seconds, characters of thought and of answer, searches, the route in use) and at the end with every route tried and why it
fell. The same command again asks only the models that have no answer yet. What each route did is remembered across runs
(<config>/chatroom/spawn/consult_memory.json): a route that asked money or is not a chat model is skipped next time, the ones
that answered long questions are tried first."""
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAX_OUT = 65536           # output asked of a host that does not say its own maximum
MAX_CAP = 262144          # a truncated answer is asked again with twice the output, up to this
READ_LONG = 3600          # seconds without a byte before a route is given up: a model that thinks, a host that does not stream
MIN_CHARS = 400           # shorter is an empty answer or a refusal
WORKERS = 20
TOOL_ROUNDS = 40          # a guard, not a budget: past this many rounds of searching the next one is asked without tools, and said
GATEWAY_S = {'kilo': 600}  # gateways that close a request after so many seconds; more are learnt from their error text
PERMANENT = {'not_free', 'not_chat', 'not_found', 'paid_only', 'no_free'}   # what a route did that will not change tomorrow
LIVE_EVERY = 5            # seconds between two writes of the live state
TEXT_CALL = re.compile(r'<tool_call\b|<\|tool_call|<function[=\s>]|\binvoke name=|\bfunction=\w+|"name"\s*:\s*"(?:search_web|search_arxiv|read_page|cerca\w*)"', re.I)
_GATEWAY = re.compile(r'(\d{2,5})[- ]second', re.I)
_TPM = re.compile(r'limit\s+(\d{1,9})\s*,\s*requested\s+(\d{1,9})', re.I)

COUNCIL = """You are one of {n} independent advisers, each a different AI model, asked the same thing at the same time. The user describes a
situation, a problem or some information below. Answer in the language the user writes in, with exactly three sections:

1. Improvements: concrete changes that would make the result better, the most valuable first, each with why.
2. Constructive fact-check: statements in the user's text that are wrong, outdated or unverified; for each, what is true instead and
   how sure you are (a source when you have one). Say plainly when everything checks out.
3. Brilliant ideas: non-obvious moves with high leverage that the user has probably not considered.

Be specific to this situation: no generic advice, no restating the question. If something essential is missing, say what and why.

=== THE USER'S REQUEST ===
{question}"""


# ------------------------------------------------------------------ memory of the routes, across runs
def mem_path():
    import layers
    return layers.chatroom_dir() / 'spawn' / 'consult_memory.json'


def load_mem(path):
    try:
        got = json.loads(Path(path).read_text(encoding='utf-8'))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def save_mem(path, mem):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(path).with_suffix('.tmp')
        tmp.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(path)
    except OSError:
        pass


# ------------------------------------------------------------------ what to ask
def with_files(prompt, attach=()):
    """the prompt and the files to read with it, each under its name"""
    parts = [prompt.rstrip()]
    for f in attach or ():
        p = Path(f)
        parts.append(f"===== FILE: {p.name} =====\n{p.read_text(encoding='utf-8', errors='replace').rstrip()}")
    return '\n\n'.join(parts) + '\n'


def _free(r, has_key):
    return r.get('free') and has_key(r['adapter'])


def _routes(m, has_key):
    rs = [r for r in m.get('routes') or [] if _free(r, has_key)]
    return sorted(rs, key=lambda r: r['adapter'] == 'huggingface')      # huggingface last: its quota ends at the ping


def pick(top=60, ids=None, openrouter=False, catalog_models=None, has_key=None, live=None, per_host=None, stealth=False,
         new_since=None, mem=None):
    """the models to ask: [(prefix, model)]. From the catalog, smartest first: the first `top`, or the first `per_host` of every
    host with a key (a model picked for a host is asked there first); `stealth` adds the stealth models of OpenRouter's live list;
    `new_since` (YYYY-MM-DD) adds the models the consult never asked, or first asked since that day. Or a host and ids chosen by
    hand (`ids` = 'host:id,id'), or the live list of OpenRouter (`openrouter`)."""
    if ids:
        host, _, lst = ids.partition(':')
        return [(host[:2].upper(), {'canonical': i.replace('/', '_').replace(':', '_'), 'aa': None,
                                    'routes': [{'adapter': host, 'model_id': i, 'free': True}]}) for i in lst.split(',') if i]
    live_rows = lambda rows: [('OR', {'canonical': m['id'].replace('/', '_').replace(':', '_'), 'aa': None, 'ctx': m.get('context_length'),
                                      'routes': [{'adapter': 'open_router', 'model_id': m['id'], 'free': True, 'ctx': m.get('context_length')}]})
                              for m in rows]
    if openrouter:
        import research
        return live_rows(research.panel_models(live or [])[:top])
    from spawn.catalog import catalog
    models = [m for m in sorted(catalog_models if catalog_models is not None else catalog.load()['models'], key=catalog.order)
              if _routes(m, has_key)]
    if per_host:
        hosts, out, seen = {}, [], set()
        for m in models:
            for r in _routes(m, has_key):
                if len(hosts.setdefault(r['adapter'], [])) < per_host and m['canonical'] not in seen:
                    hosts[r['adapter']].append(m['canonical'])
                    seen.add(m['canonical'])
                    first = [x for x in m['routes'] if x is r] + [x for x in m['routes'] if x is not r]
                    out.append(('', {**m, 'routes': first}))
                    break
    else:
        out = [('', m) for m in models][:top]
    if new_since:
        seen_at = (mem or {}).get('seen', {})
        since = time.mktime(time.strptime(new_since, '%Y-%m-%d'))
        have = {m['canonical'] for _, m in out}
        out += [('', m) for m in models if m['canonical'] not in have and seen_at.get(m['canonical'], since) >= since]
    if stealth and live:
        have = {m['canonical'] for _, m in out}
        out += [x for x in live_rows([m for m in live if 'stealth' in (str(m.get('name', '')) + str(m.get('description', ''))).lower()])
                if x[1]['canonical'] not in have]
    return out


def quota_note(host, left, tokens_in, models):
    """the line said before a round when a host gives so many free tokens a day (xKiro): how many of its models the question fits"""
    each = tokens_in + 8000                          # shortcut: the answer counted at 8k tokens; a long thinker spends more
    fits = int(left // each) if left else 0
    return (f"{host}: {int(left or 0):,} free tokens left today; the question (~{tokens_in:,} tokens in) fits about {fits} of its "
            f"{models} models, the smartest are asked first" + (' (the others will find the quota over)' if fits < models else ''))


# ------------------------------------------------------------------ one route
def estimate(text):
    return int(len(text) / 3.2) + 1                  # as openai_compat.estimate_tokens: 3.2 characters a token, prudently


def looks_like_call(text):
    """a tool call written as text (Kilo, NVIDIA): short, or the call right at the start; an answer that talks about tool calls is not one"""
    t = (text or '').strip()
    return bool(TEXT_CALL.search(t)) and (len(t) < 2000 or bool(TEXT_CALL.search(t[:300])))


def _kind_of(exc):
    """the error's kind, with what the catalog knows of the service's own answers (paid only, not a chat model, no free tier)"""
    from spawn.catalog import catalog
    kind, detail = getattr(exc, 'kind', type(exc).__name__), str(getattr(exc, 'detail', ''))
    if kind == 'forbidden' and catalog._PAID.search(detail):
        return 'paid_only'
    if kind == 'bad_request' and catalog._NOT_CHAT.search(detail):
        return 'not_chat'
    if kind == 'quota' and re.search(r'limit:\s*0\b', detail):
        return 'no_free'
    return kind


class Consult:
    def __init__(self, prompt, out, has_key, complete, deadline=None, workers=WORKERS, say=print, web=False, max_tokens=None,
                 retry_dead=False, mem=None, limiter=None, catalog_mod=None, tools_impl=None, read=READ_LONG):
        self.prompt, self.out, self.has_key, self.complete = prompt, Path(out), has_key, complete
        self.deadline, self.workers, self.say, self.web, self.max_tokens = deadline, workers, say, web, max_tokens
        self.retry_dead, self.read, self.tools_impl = retry_dead, read, tools_impl
        self.mem_file = mem if mem is not None else mem_path()
        self.mem = load_mem(self.mem_file)
        self.mem.setdefault('routes', {})
        self.mem.setdefault('gateway', {})
        self.mem.setdefault('seen', {})
        self.limiter, self.catalog_mod = limiter, catalog_mod
        self.rows, self.lock, self.tokens_in = {}, threading.Lock(), estimate(prompt)
        self.out.mkdir(parents=True, exist_ok=True)
        self.state = self.out / 'stato.json'

    # ---- files
    def write_state(self):
        with self.lock:
            rows = sorted(self.rows.values(), key=lambda x: x['n'])
            data = json.dumps(rows, indent=1, ensure_ascii=False, default=str)
        try:
            tmp = self.state.with_suffix('.tmp')
            tmp.write_text(data, encoding='utf-8')
            tmp.replace(self.state)
        except OSError:
            pass

    def previous(self):
        try:
            return {r['model']: r for r in json.loads(self.state.read_text(encoding='utf-8')) if isinstance(r, dict) and r.get('model')}
        except (OSError, ValueError):
            return {}

    def head(self, m, row):
        bits = [f"host {row['host']}", row['route'], f"{row['s']} s", f"finish {row['finish']}", f"{row['searches']} searches",
                f"tools {row['tools']}"]
        u = row.get('usage') or {}
        if u:
            bits.append(f"usage in {u.get('prompt_tokens', '?')} out {u.get('completion_tokens', '?')}")
        notes = ''.join(f'\n> {x}' for x in row['notes'])
        return f"# {m['canonical']}\n\n{' · '.join(bits)}{notes}\n\n"

    # ---- memory
    def remember(self, r, **what):
        with self.lock:
            self.mem['routes'][f"{r['adapter']}|{r['model_id']}"] = {**what, 'at': time.time(), 'tokens_in': self.tokens_in}

    def order(self, m):
        """the routes to try, the ones that answered a long question before first; a route that will not change is left out"""
        rs, skipped = [], []
        dead = ((m.get('probe') or {}).get('tries') or {})
        for r in _routes(m, self.has_key):
            last = self.mem['routes'].get(f"{r['adapter']}|{r['model_id']}") or {}
            gone = last.get('kind') if last.get('kind') in PERMANENT else dead.get(r['adapter']) if dead.get(r['adapter']) in PERMANENT else None
            if gone and not self.retry_dead:
                skipped.append({'host': r['adapter'], 'model_id': r['model_id'], 'kind': gone, 'detail': 'skipped: remembered from an earlier try (--retry-dead to try it)'})
            else:
                rs.append((0 if last.get('ok') else 1 if not last else 2, r))
        return [r for _, r in sorted(rs, key=lambda x: x[0])], skipped

    # ---- one model
    def ask_model(self, n, prefix, m):
        row = {'n': n, 'model': m['canonical'], 'aa': m.get('aa'), 'status': 'asking', 'host': None, 'route': None, 's': None,
               'chars': 0, 'finish': None, 'searches': 0, 'tools': 'web' if self.web else 'none', 'usage': None, 'notes': [],
               'tries': [], 'live': {}, 'file': None}
        with self.lock:
            self.rows[m['canonical']] = row
            self.mem['seen'].setdefault(m['canonical'], time.time())
        routes, skipped = self.order(m)
        row['tries'] += skipped
        for r in routes:
            if self.limiter is not None and self.limiter.is_out(r['adapter'], r['model_id']):
                until = max((u for p, _, mm, u in self.limiter.blocks() if p == r['adapter'] and mm in (r['model_id'], '*')), default=0)
                row['tries'].append({'host': r['adapter'], 'model_id': r['model_id'], 'kind': 'quota',
                                     'detail': 'not tried: blocked by the limiter until ' + time.strftime('%Y-%m-%d %H:%M', time.localtime(until))})
                continue
            ctx = r.get('ctx') or m.get('ctx')
            if ctx and self.tokens_in > ctx * 0.95:
                row['tries'].append({'host': r['adapter'], 'model_id': r['model_id'], 'kind': 'too_large',
                                     'detail': f'not sent: question of ~{self.tokens_in} tokens, context {ctx}'})
                continue
            if self.ask_route(m, r, row, prefix):
                break
        if row['status'] != 'ok':
            row['status'] = 'truncated' if any(t.get('kind') == 'truncated' for t in row['tries']) else 'failed'
        row['live'] = {}
        self.write_state()
        return row

    def ask_route(self, m, r, row, prefix):
        host, mid = r['adapter'], r['model_id']
        cap = self.max_tokens or r.get('max_out') or MAX_OUT
        gateway = self.mem['gateway'].get(host) or GATEWAY_S.get(host)
        limit = min(x for x in (self.deadline, gateway and gateway - 15) if x) if (self.deadline or gateway) else None
        if gateway and not self.deadline:
            row['notes'].append(f'{host} closes a request after {gateway} s: what came by then is kept')
        tools = __import__('spawn.web', fromlist=['TOOLS']).TOOLS if self.web else None
        msgs = [{'role': 'user', 'content': self.prompt}]
        t0, retried, rounds, seen_calls = time.time(), set(), 0, set()
        live = row['live']
        live.update(route=f'{host}:{mid}', think=0, text=0, searches=row['searches'], started=t0)

        def on_delta(kind, t):
            live['think' if kind == 'reasoning' else 'text'] = live.get('think' if kind == 'reasoning' else 'text', 0) + len(t)

        while True:
            stop, fired = threading.Event(), threading.Event()
            timer = threading.Timer(limit, lambda: (fired.set(), stop.set())) if limit else None
            if timer:
                timer.start()
            try:
                got = self.complete(host, mid, msgs, tools=tools, max_tokens=cap, attempts=2, stop=stop, effort='high',
                                    on_delta=on_delta, read=self.read, tokens=self.tokens_in + min(cap, 8192))
            except Exception as exc:                  # one route failing must not stop the others: why it fell is kept
                kind, detail = _kind_of(exc), ' '.join(str(getattr(exc, 'detail', exc)).split())
                if fired.is_set():
                    kind, detail = 'deadline', f'deadline of {int(limit)} s reached' + (f' ({host} gateway limit)' if gateway and limit < (self.deadline or 1e9) else '')
                    part = (getattr(exc, 'partial', None) or {}).get('text') or ''
                    if part.strip():
                        self.save(m, row, prefix, part, partial=True)
                elif 'duration limit' in detail.lower() and _GATEWAY.search(detail):
                    with self.lock:
                        self.mem['gateway'][host] = int(_GATEWAY.search(detail)[1])
                    kind = 'gateway'
                elif kind == 'no_output' and cap < MAX_CAP and 'cap' not in retried:
                    retried.add('cap')                  # it thought until the output ended: once more with twice the room
                    cap = min(cap * 2, MAX_CAP)
                    row['notes'].append(f'{host}: the thought used the whole output; asked again with max_tokens {cap}')
                    continue
                elif kind in ('payment', 'paid_only'):
                    kind = 'not_free'
                    try:
                        (self.catalog_mod or __import__('spawn.catalog.catalog', fromlist=['mark_not_free'])).mark_not_free(m['canonical'], host)
                    except Exception:
                        pass
                elif kind in ('too_large', 'context'):
                    t = _TPM.search(detail)
                    detail = (f'question of {t[2]} tokens, limit {t[1]}: ' if t else f'question of ~{self.tokens_in} tokens: ') + detail
                elif tools and kind == 'bad_request' and re.search(r'tool|function', detail, re.I) and 'notools' not in retried:
                    retried.add('notools')              # M2: this host takes no tools; the question again without them, said
                    tools, row['tools'] = None, 'refused by the host'
                    msgs = [{'role': 'user', 'content': self.prompt + '\n\n(Web search is not available on this host: answer from what you know.)'}]
                    row['notes'].append(f'{host} refused the tools: asked without web search')
                    continue
                row['tries'].append({'host': host, 'model_id': mid, 'kind': kind, 'status': getattr(exc, 'status', None),
                                     'detail': detail[:300], 's': round(time.time() - t0)})
                self.remember(r, ok=False, kind=kind, s=round(time.time() - t0))
                return False
            finally:
                if timer:
                    timer.cancel()
            calls = got.get('tool_calls') or []
            text, finish = (got.get('text') or '').strip(), got.get('finish')
            row['usage'], row['finish'] = got.get('usage'), finish
            if calls and tools:                       # M1: the searches it asked for, then the answer
                rounds += 1
                msgs.append(got['message'])
                from spawn import web
                for c in calls:
                    key = json.dumps([c['function'].get('name'), c['function'].get('arguments')], sort_keys=True)
                    if key in seen_calls:
                        result = 'already done above: use those results, or answer'
                    else:
                        seen_calls.add(key)
                        result = web.run(c, self.tools_impl)
                        row['searches'] += 1
                        live['searches'] = row['searches']
                    msgs.append({'role': 'tool', 'tool_call_id': c.get('id') or 'call', 'content': result})
                if rounds >= TOOL_ROUNDS:              # B6: a guard against searching forever, said in the outcome
                    tools = None
                    msgs.append({'role': 'user', 'content': f'You have searched {rounds} rounds: write your answer now, without more searches.'})
                    row['notes'].append(f'{rounds} rounds of searching: the last one was asked without tools')
                continue
            if looks_like_call(text) and 'textcall' not in retried:
                retried.add('textcall')               # B2: a call written as text is not an answer
                row['notes'].append(f'{host} wrote a tool call as text; asked again without tools, in prose')
                tools, row['tools'] = None, ('text calls, asked without' if self.web else row['tools'])
                msgs = [{'role': 'user', 'content': self.prompt + '\n\n(Do not call tools: write the answer itself, in prose.)'}]
                continue
            if looks_like_call(text):
                kind, detail = 'tool_text', f'the answer is a tool call written as text ({len(text)} characters)'
            elif finish == 'length':
                self.save(m, row, prefix, text, partial=True)
                if cap < MAX_CAP and 'length' not in retried:
                    retried.add('length')
                    row['notes'].append(f'{host}: cut at max_tokens {cap}; asked again with {min(cap * 2, MAX_CAP)}')
                    cap = min(cap * 2, MAX_CAP)
                    continue
                kind, detail = 'truncated', f'cut by the output limit (max_tokens {cap}): {len(text)} characters kept as .partial.md'
            elif len(text) < MIN_CHARS:              # B9: was it thinking without writing, or a refusal?
                kind = 'short'
                detail = (f'{len(text)} characters of answer after {round(time.time() - t0)} s, {len(got.get("reasoning") or "")} of thought, '
                          f'finish {finish}, usage {json.dumps(got.get("usage") or {})}')
            else:
                row.update(status='ok', host=host, route=f'{host}:{mid}', s=round(time.time() - t0), chars=len(text))
                self.save(m, row, prefix, text)
                self.remember(r, ok=True, chars=len(text), s=row['s'], finish=finish)
                return True
            row['tries'].append({'host': host, 'model_id': mid, 'kind': kind, 'detail': detail[:300], 's': round(time.time() - t0)})
            self.remember(r, ok=False, kind=kind, s=round(time.time() - t0), finish=finish)
            return False

    def save(self, m, row, prefix, text, partial=False):
        name = f"{prefix}{m['canonical']}" + ('.partial.md' if partial else '.md')
        if not partial:
            row['file'] = name
        (self.out / name).write_text(self.head(m, {**row, 's': row['s'] if row['s'] is not None else '-',
                                                   'host': row['host'] or row['live'].get('route', '?').split(':')[0],
                                                   'route': row['route'] or row['live'].get('route', '')}) + text + '\n', encoding='utf-8')

    # ---- the round
    def run(self, picked, need=None, retry_failed=False):
        """ask the picked models; with `need`, ask in order until that many answered, the next model taking a fallen one's place"""
        prev = self.previous()
        todo = []
        for i, (prefix, m) in enumerate(picked):
            p = prev.get(m['canonical'])
            done = p and p.get('status') == 'ok' and p.get('file') and (self.out / p['file']).is_file()
            if done:
                self.rows[m['canonical']] = {**p, 'n': i + 1}
            elif not retry_failed or p:
                todo.append((i + 1, prefix, m))
        if prev and len(todo) < len(picked):
            self.say(f"{len(picked) - len(todo)} answered before: asking only the {len(todo)} left")
        stop_live = threading.Event()

        def live():
            while not stop_live.wait(LIVE_EVERY):
                with self.lock:
                    for row in self.rows.values():
                        if row.get('live'):
                            row['live']['s'] = round(time.time() - row['live'].get('started', time.time()))
                self.write_state()
        ticker = threading.Thread(target=live, daemon=True)
        ticker.start()
        try:
            if need is None:
                with ThreadPoolExecutor(max_workers=self.workers) as pool:
                    list(pool.map(lambda x: self.ask_model(*x), todo))
            else:
                self.run_until(todo, need)
        finally:
            stop_live.set()
            save_mem(self.mem_file, self.mem)
            self.write_state()
        return self.report()

    def run_until(self, todo, need):
        queue, lock = list(todo), threading.Lock()
        good = lambda: sum(r.get('status') == 'ok' for r in self.rows.values())
        busy = [0]

        def worker():
            while True:
                with lock:
                    if not queue or good() + busy[0] >= need:
                        return
                    item = queue.pop(0)
                    busy[0] += 1
                try:
                    self.ask_model(*item)
                finally:
                    with lock:
                        busy[0] -= 1
        threads = [threading.Thread(target=worker) for _ in range(min(need, self.workers, max(1, len(queue))))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if good() < need:
            self.say(f'only {good()} of {need} answered: no other model with a free route was left')

    def report(self):
        rows = sorted(self.rows.values(), key=lambda x: x['n'])
        self.say(f"{'n':>2} {'model':<34} {'route':<34} {'s':>6} {'chars':>6} {'finish':<8} {'srch':>4}  why it fell")
        for r in rows:
            why = '' if r.get('status') == 'ok' else '; '.join(f"{t.get('host', '')} {t.get('kind', '')}: {t.get('detail', '')[:70]}" for t in r.get('tries', [])[-3:]) or str(r.get('status'))
            self.say(f"{r['n']:>2} {r['model'][:34]:<34} {(r.get('route') or 'NO ANSWER')[:34]:<34} {r.get('s') if r.get('s') is not None else '':>6} "
                     f"{r.get('chars', 0):>6} {str(r.get('finish') or '')[:8]:<8} {r.get('searches', 0):>4}  {why[:160]}")
        self.say(f"{sum(r.get('status') == 'ok' for r in rows)}/{len(rows)} answers in {self.out}")
        return rows


def consult(prompt, out, picked, has_key, complete, deadline=None, workers=WORKERS, say=print, need=None, retry_failed=False, **kw):
    """ask every picked model (or, with `need`, until that many answered); returns the rows, one line printed for each"""
    return Consult(prompt, out, has_key, complete, deadline=deadline, workers=workers, say=say, **kw).run(picked, need, retry_failed)


def council(question, out, candidates, has_key, complete, n=10, say=print, **kw):
    """the model council: the n smartest models with a free route are asked for improvements, a constructive fact-check and
    brilliant ideas on the user's situation; a model that does not answer gives its place to the next one, until n answered"""
    rows = consult(COUNCIL.format(n=n, question=question.strip()), out, candidates, has_key, complete, say=say, need=n, **kw)
    good = [r for r in rows if r['status'] == 'ok']
    index = [f'# Model council: {len(good)} of {n} advisers answered', '']
    index += [f"- [{r['model']}]({r['file']}) ({r['route']}, {r['s']} s, {r['chars']} characters)" for r in good]
    (Path(out) / 'COUNCIL.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    return rows


# ------------------------------------------------------------------ the Claude arm (claude -p beside the free models)
def claude_arm(prompt, out, model, runner=None, say=print):
    """the same question to Claude through `claude -p` with web search, started detached so it outlives this process (a rerun
    picks up its output); the full model id is passed and checked in modelUsage, since an alias can land on another model.
    Returns the row; waits for the end."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    src, res, err = out / 'claude-prompt.txt', out / f'claude-{model}.json', out / f'claude-{model}.err'
    row = {'model': f'claude:{model}', 'status': 'asking', 'route': 'claude -p', 'file': None, 'tries': []}
    if not (res.is_file() and res.stat().st_size):
        src.write_text(prompt, encoding='utf-8')
        cmd = [shutil.which('claude') or 'claude', '-p', '--model', model, '--output-format', 'json', '--allowedTools', 'WebSearch', 'WebFetch']
        if runner is None:
            import doctor
            problem = doctor.claude_login_problem(cmd[0])
            if problem:
                row.update(status='failed', tries=[{'kind': 'claude', 'detail': problem}])
                say(problem)
                return row
            flags = {'creationflags': 0x00000008 | 0x00000200} if sys.platform == 'win32' else {'start_new_session': True}   # DETACHED_PROCESS | NEW_PROCESS_GROUP
            with open(src, 'rb') as i, open(res, 'wb') as o, open(err, 'wb') as e:
                proc = subprocess.Popen(cmd, stdin=i, stdout=o, stderr=e, **flags)
            say(f'claude -p started (pid {proc.pid}): {res}')
            proc.wait()
        else:
            runner(cmd, src, res)
    try:
        data = json.loads(res.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        row.update(status='failed', tries=[{'kind': 'claude', 'detail': f'no JSON from claude -p: {exc}'}])
        return row
    used = list((data.get('modelUsage') or {}).keys())
    text = (data.get('result') or '').strip()
    if used and not any(u == model or u.startswith(model) for u in used):
        row.update(status='failed', tries=[{'kind': 'wrong_model', 'detail': f'asked {model}, claude -p used {", ".join(used)}'}])
    elif data.get('is_error') or len(text) < MIN_CHARS:
        row.update(status='failed', tries=[{'kind': 'claude', 'detail': f"error or short answer ({len(text)} characters): {str(data.get('subtype', ''))}"}])
    else:
        name = f'claude-p-{model}.md'           # not <model>.md: a free route of the same model may answer too
        (out / name).write_text(f"# claude:{model}\n\nclaude -p · {', '.join(used) or '?'} · {round((data.get('duration_ms') or 0) / 1000)} s\n\n{text}\n", encoding='utf-8')
        row.update(status='ok', file=name, chars=len(text))
    return row
