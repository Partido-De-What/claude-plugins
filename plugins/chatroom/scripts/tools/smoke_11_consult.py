"""1.1: spawn consult with no budget of its own, the faults of the consult report of 21/11 (B0-B10, M1-M11) and the model council.
Every provider here is fake: nothing goes out. Run: python -X utf8 smoke_11_consult.py"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
BASE = Path(tempfile.mkdtemp(prefix='smoke11_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
from spawn import consult as sc, errors, web  # noqa: E402
from spawn.limiter import Limiter  # noqa: E402

fails = 0
LONG = 'answer ' * 120                               # 840 characters: above MIN_CHARS


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:600]}]'), flush=True)
    fails += not cond


def model(name, *routes, aa=50):
    return {'canonical': name, 'aa': aa, 'routes': [{'adapter': h, 'model_id': f'{h}/{name}', 'free': True, **extra} for h, extra in routes]}


def got(text, finish='stop', calls=None, reasoning=''):
    msg = {'role': 'assistant', 'content': text or None, **({'tool_calls': calls} if calls else {})}
    return {'message': msg, 'text': text, 'tool_calls': calls or [], 'finish': finish, 'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
            'reasoning': reasoning}


class Cat:
    def __init__(self):
        self.not_free = []

    def mark_not_free(self, canonical, adapter):
        self.not_free.append((canonical, adapter))


def run(picked, complete, out, **kw):
    lines = []
    kw.setdefault('mem', BASE / f'mem-{out}.json')
    rows = sc.consult('question', BASE / out, picked, lambda h: True, complete, say=lines.append, **kw)
    return rows, lines


# ---- B0: no budget of our own
seen = {}


def fake(host, mid, msgs, **kw):
    seen.update(kw)
    return got(LONG)


rows, _ = run([('', model('m-a', ('hostA', {'max_out': 32000})))], fake, 'b0')
ok('B0 the output asked is the most the host takes (its max_out)', seen.get('max_tokens') == 32000, seen)
ok('B0 a route waits an hour for a byte (read)', seen.get('read') == sc.READ_LONG, seen)
ok('B0 no deadline by default: nothing stops the route', 'stop' in seen and not seen['stop'].is_set())
run([('', model('m-b', ('hostA', {})))], fake, 'b0b')
ok('B0 a host that does not say asks 65536', seen.get('max_tokens') == sc.MAX_OUT, seen)
ok('B0 the answer file is named after the model alone (M3)', (BASE / 'b0' / 'm-a.md').is_file(), list((BASE / 'b0').iterdir()))
head = (BASE / 'b0' / 'm-a.md').read_text(encoding='utf-8')
ok('M8 the file starts with its outcome: host, seconds, finish, searches, usage', 'host hostA' in head and 'finish stop' in head and 'usage in 10' in head, head[:300])

# ---- B0e: a truncated answer is never a success
calls = []


def trunc(host, mid, msgs, **kw):
    calls.append(kw['max_tokens'])
    return got(LONG, finish='length')


rows, lines = run([('', model('m-t', ('hostA', {'max_out': 100000})))], trunc, 'trunc')
ok('B0e finish=length is asked again with twice the output', calls == [100000, 200000], calls)
ok('B0e and stays truncated, never ok', rows[0]['status'] == 'truncated' and not (BASE / 'trunc' / 'm-t.md').exists(), rows[0])
ok('B0e what came is kept as .partial.md', (BASE / 'trunc' / 'm-t.partial.md').is_file())
ok('B0e the cap that cut it is in the outcome', 'max_tokens 200000' in json.dumps(rows[0]['tries']), rows[0]['tries'])

# ---- no_output: the thought used the whole output
n_calls = []


def think(host, mid, msgs, **kw):
    n_calls.append(kw['max_tokens'])
    if len(n_calls) == 1:
        raise errors.ProviderError('no_output', None, None, 'the reasoning used the whole output budget')
    return got(LONG)


rows, _ = run([('', model('m-k', ('hostA', {'max_out': 16000})))], think, 'think')
ok('no_output: asked again with twice the output, then answered', n_calls == [16000, 32000] and rows[0]['status'] == 'ok', (n_calls, rows[0]))

# ---- B2: a tool call written as text
texts = iter(['<tool_call>{"name": "search_web", "arguments": {"query": "x"}}</tool_call>', LONG])
rows, _ = run([('', model('m-c', ('kilo', {})))], lambda h, m, msgs, **kw: got(next(texts)), 'textcall')
ok('B2 a call written as text is not an answer: asked again in prose', rows[0]['status'] == 'ok' and any('tool call as text' in x for x in rows[0]['notes']), rows[0])
ok('B2 an answer that only talks about tool calls is an answer', not sc.looks_like_call(LONG * 3 + ' the <tool_call> token is how models call tools'))
rows, _ = run([('', model('m-c2', ('kilo', {})))], lambda h, m, msgs, **kw: got('function=cerca_paper {"q": 1}'), 'textcall2')
ok('B2 twice a call as text: failed as tool_text', rows[0]['status'] == 'failed' and rows[0]['tries'][-1]['kind'] == 'tool_text', rows[0])

# ---- B3: the limiter says until when, shows and clears its blocks
lim = Limiter(sleep=lambda s: None, path=BASE / 'out.json')
lim._mark_out('gemini', 'k', 'gemini-4-neon', errors.ProviderError('quota', 429, None, 'you have used up your daily free allocation'))
try:
    lim.run('gemini', 'k', 'gemini-4-neon', lambda: got(LONG), attempts=1)
    said = ''
except errors.ProviderError as e:
    said = e.detail
ok('B3 a blocked host says until when', 'blocked until' in said and time.strftime('%Y-%m-%d') <= said.split('until ')[-1][:10], said)
ok('B3 blocks() lists it', any(b[0] == 'gemini' for b in lim.blocks()), lim.blocks())
lim._mark_out('gemini', 'k', 'gemini/gemini-4-neon', errors.ProviderError('quota', 429, None, 'you have used up your daily free allocation'))
rows, _ = run([('', model('gemini-4-neon', ('gemini', {})))], lambda *a, **k: got(LONG), 'blocked', limiter=lim)
ok('M10 a blocked route is not tried, the outcome says until when', rows[0]['status'] == 'failed' and 'blocked by the limiter until' in json.dumps(rows[0]['tries']), rows[0])
ok('B3 clear() takes the blocks off', lim.clear('gemini') >= 1 and not lim.blocks())

# ---- B4: a route that wants money is not a quota, and leaves the free ones
e = errors.classify(403, 'This pay-as-you-go premium model requires real deposited balance')
ok('B4 "deposited balance" is payment, not quota', e.kind == 'payment', e.kind)
ok('B4 "Purchase pre-paid credits" (402) is payment', errors.classify(402, 'Purchase pre-paid credits').kind == 'payment')
ok('B4 a daily free quota is still a quota', errors.classify(429, 'free-model token quota exceeded for today').kind == 'quota')
cat = Cat()


def paid(host, mid, msgs, **kw):
    if host == 'xkiro':
        raise errors.classify(403, 'This pay-as-you-go premium model requires real deposited balance')
    return got(LONG)


rows, _ = run([('', model('claude-x', ('xkiro', {}), ('open_router', {})))], paid, 'paid', catalog_mod=cat)
ok('B4 the paid route is marked not free in the catalog, the next route answers', cat.not_free == [('claude-x', 'xkiro')] and rows[0]['route'] == 'open_router:open_router/claude-x', (cat.not_free, rows[0]))
lim2 = Limiter(sleep=lambda s: None, path=BASE / 'out2.json')
for name in ('claude-x', 'gpt-x'):
    lim2._mark_out('xkiro', 'k', name, errors.classify(403, 'requires real deposited balance'))
ok('B4 two paid models on a mixed host do not block its free ones', not lim2.is_out('xkiro', 'qwen-free', 'k'), lim2.blocks())
mem = json.loads((BASE / 'mem-paid.json').read_text(encoding='utf-8'))
ok('M6 the memory keeps the paid route as not_free', mem['routes']['xkiro|xkiro/claude-x']['kind'] == 'not_free', mem['routes'])
rows, _ = run([('', model('claude-x', ('xkiro', {}), ('open_router', {})))], paid, 'paid2', catalog_mod=cat, mem=BASE / 'mem-paid.json')
ok('M6 next time the remembered paid route is skipped, and said', rows[0]['tries'][0]['detail'].startswith('skipped: remembered') and rows[0]['status'] == 'ok', rows[0])

# ---- B5: a route the probe found not to be a chat model
m5 = model('gemini-antigravity', ('gemini', {}), ('open_router', {}))
m5['probe'] = {'ok': False, 'tries': {'gemini': 'not_chat'}}
asked = []
rows, _ = run([('', m5)], lambda h, m, msgs, **kw: (asked.append(h), got(LONG))[1], 'notchat')
ok('B5 a not_chat route is skipped', asked == ['open_router'], asked)

# ---- B7: a question too big for the route is not sent
asked.clear()
rows, _ = sc.consult('x' * 40000, BASE / 'big', [('', model('m-small', ('groq', {'ctx': 8000}), ('nvidia_nim', {'ctx': 128000})))], lambda h: True,
                     lambda h, m, msgs, **kw: (asked.append(h), got(LONG))[1], say=lambda x: None, mem=BASE / 'mem-big.json'), None
ok('B7 the small route is skipped with the sizes, the big one answers', asked == ['nvidia_nim'] and 'context 8000' in json.dumps(rows[0]['tries']), (asked, rows[0]))


def tpm(host, mid, msgs, **kw):
    raise errors.classify(413, 'Request too large: tokens per minute (TPM): Limit 6000, Requested 14000')


rows, _ = run([('', model('m-tpm', ('groq', {})))], tpm, 'tpm')
ok('B7 a 413 says the question size against the limit', 'question of 14000 tokens, limit 6000' in json.dumps(rows[0]['tries']), rows[0]['tries'])

# ---- B8: our deadline, and the text that came is kept
def slow(host, mid, msgs, stop=None, **kw):
    stop.wait(5)
    raise errors.ProviderError('stopped', None, None, 'stopped during the stream', got('half of an answer ' * 10))


rows, _ = run([('', model('m-slow', ('hostA', {})))], slow, 'deadline', deadline=1)
ok('B8 the deadline is said as a deadline, not "the role was stopped"', rows[0]['tries'][-1]['kind'] == 'deadline' and 'deadline of 1 s' in rows[0]['tries'][-1]['detail'], rows[0])
ok('B8 the text that came is saved', (BASE / 'deadline' / 'm-slow.partial.md').is_file())

# ---- B9: an empty answer says if it thought
rows, _ = run([('', model('m-e', ('hostA', {})))], lambda *a, **k: got('ok.', reasoning='x' * 5000), 'empty')
ok('B9 a short answer says the thought and the usage', '5000 of thought' in rows[0]['tries'][-1]['detail'] and 'completion_tokens' in rows[0]['tries'][-1]['detail'], rows[0]['tries'])

# ---- B10: a gateway's duration limit is learnt and said
def gate(host, mid, msgs, **kw):
    raise errors.ProviderError('upstream', 504, None, "The response reached the gateway's 600-second duration limit")


rows, _ = run([('', model('m-g', ('hostG', {})))], gate, 'gate')
mem = json.loads((BASE / 'mem-gate.json').read_text(encoding='utf-8'))
ok('B10 the limit is learnt for the host', mem['gateway'].get('hostG') == 600 and rows[0]['tries'][-1]['kind'] == 'gateway', (mem.get('gateway'), rows[0]['tries']))
rows, _ = run([('', model('m-k2', ('kilo', {})))], lambda *a, **k: got(LONG), 'kilo')
ok('B10 a known gateway is said before, as a note', any('600 s' in x for x in rows[0]['notes']), rows[0]['notes'])

# ---- M1/B6/M2: the web, a guard against endless searching, the fallback without tools
searched = []
impl = {'search_web': lambda q: (searched.append(q), 'result for ' + q)[1], 'search_arxiv': lambda q: 'papers', 'read_page': lambda u: 'page'}
step = [0]


def searcher(host, mid, msgs, tools=None, **kw):
    step[0] += 1
    if tools and step[0] <= 3:
        q = 'same' if step[0] < 3 else 'other'
        return got('', finish='tool_calls', calls=[{'id': f'c{step[0]}', 'type': 'function', 'function': {'name': 'search_web', 'arguments': json.dumps({'query': q})}}])
    return got(LONG)


rows, _ = run([('', model('m-w', ('hostA', {})))], searcher, 'web', web=True, tools_impl=impl)
ok('M1 the searches run and the answer comes after them', rows[0]['status'] == 'ok' and searched == ['same', 'other'], (searched, rows[0]))
ok('B6 the same search twice is not run again', rows[0]['searches'] == 2, rows[0])
old, sc.TOOL_ROUNDS = sc.TOOL_ROUNDS, 2
step[0], searched[:] = -100, []
rows, _ = run([('', model('m-w2', ('hostA', {})))], lambda h, m, msgs, tools=None, **kw: searcher(h, m, msgs, tools=tools) if tools else got(LONG), 'web2', web=True, tools_impl=impl)
sc.TOOL_ROUNDS = old
ok('B6 past the rounds the last one is asked without tools, and said', rows[0]['status'] == 'ok' and any('rounds of searching' in x for x in rows[0]['notes']), rows[0])


def no_tools(host, mid, msgs, tools=None, **kw):
    if tools:
        raise errors.ProviderError('bad_request', 400, None, 'this model does not support tools / function calling')
    return got(LONG)


rows, _ = run([('', model('m-nt', ('hostA', {})))], no_tools, 'notools', web=True, tools_impl=impl)
ok('M2 a host that refuses the tools is asked without, and said', rows[0]['status'] == 'ok' and rows[0]['tools'] == 'refused by the host', rows[0])
ok('M1 web.run answers an unknown tool, never raises', 'unknown tool' in web.run({'name': 'nope', 'arguments': '{}'}, impl))
ok('M1 read_page refuses what is not http', web.read_page('file:///etc/passwd').startswith('refused'))
ok('M1 search_web parses the result page', 'Example' in web.search_web('x', get=lambda u: '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">Example</a><a class="result__snippet">snip</a>'))

# ---- M3: the same command again asks only the ones without an answer
asked.clear()
flip = {'m-r2': 0}


def flaky(host, mid, msgs, **kw):
    name = mid.split('/')[-1]
    asked.append(name)
    if name == 'm-r2' and flip['m-r2'] == 0:
        flip['m-r2'] = 1
        raise errors.ProviderError('overloaded', 503, None, 'high demand')
    return got(LONG)


picked = [('', model('m-r1', ('hostA', {}))), ('', model('m-r2', ('hostA', {})))]
run(picked, flaky, 'resume')
asked.clear()
rows, lines = run(picked, flaky, 'resume')
ok('M3 a rerun asks only the model without an answer', asked == ['m-r2'] and all(r['status'] == 'ok' for r in rows), (asked, rows))
asked.clear()
rows, _ = run(picked + [('', model('m-new', ('hostA', {})))], flaky, 'resume', retry_failed=True)
ok('M3 --retry-failed asks no new model', asked == [], asked)

# ---- M4: files read with the question
(BASE / 'DOSSIER.md').write_text('the dossier', encoding='utf-8')
p = sc.with_files('the question', [BASE / 'DOSSIER.md'])
ok('M4 the attached file is in the prompt under its name', 'the question' in p and '===== FILE: DOSSIER.md =====' in p and 'the dossier' in p, p)

# ---- M5: the smartest of every host, stealth, the new ones
cat_models = [model('a1', ('h1', {}), aa=90), model('a2', ('h1', {}), aa=80), model('a3', ('h1', {}), aa=70), model('b1', ('h2', {}), aa=60)]
import spawn.catalog.catalog as realcat  # noqa: E402
order = realcat.order
realcat.order = lambda m: -(m.get('aa') or 0)
got_ph = sc.pick(per_host=2, catalog_models=cat_models, has_key=lambda h: True)
ok('M5 --per-host 2 takes the 2 smartest of each host', [m['canonical'] for _, m in got_ph] == ['a1', 'a2', 'b1'], [m['canonical'] for _, m in got_ph])
live = [{'id': 'openrouter/sly-alpha:free', 'name': 'Sly Alpha (stealth)', 'description': ''}, {'id': 'x/plain:free', 'name': 'Plain'}]
got_st = sc.pick(1, catalog_models=cat_models, has_key=lambda h: True, stealth=True, live=live)
ok('M5 --stealth adds the stealth models of OpenRouter', [m['canonical'] for _, m in got_st] == ['a1', 'openrouter_sly-alpha_free'], [m['canonical'] for _, m in got_st])
got_new = sc.pick(1, catalog_models=cat_models, has_key=lambda h: True, new_since='2026-01-01', mem={'seen': {'a2': 0, 'a3': 0}})
ok('M5 --new-since adds the models never asked', [m['canonical'] for _, m in got_new] == ['a1', 'b1'], [m['canonical'] for _, m in got_new])

# ---- M7: the state is written while the models think
started = threading.Event()


def thinking(host, mid, msgs, on_delta=None, **kw):
    on_delta('reasoning', 'x' * 300)
    started.set()
    time.sleep(1.5)
    return got(LONG)


old_every, sc.LIVE_EVERY = sc.LIVE_EVERY, 0.3
th = threading.Thread(target=run, args=([('', model('m-live', ('hostA', {})))], thinking, 'live'))
th.start()
started.wait(5)
time.sleep(0.8)
mid_state = json.loads((BASE / 'live' / 'stato.json').read_text(encoding='utf-8'))
th.join()
sc.LIVE_EVERY = old_every
ok('M7 while it thinks, stato.json shows the route and the thought so far', mid_state and mid_state[0]['live'].get('think') == 300 and mid_state[0]['live'].get('route') == 'hostA:hostA/m-live', mid_state)

# ---- M9: the day's quota said before
note = sc.quota_note('xkiro', 500000, 15000, 10)
ok('M9 the note says how many models the quota fits', 'fits about 21' in note or 'fits about 21 of its 10' in note, note)
ok('M9 when it fits fewer than the models, it says the others will find it over', 'others will find the quota over' in sc.quota_note('xkiro', 50000, 15000, 10))
from spawn.providers import openai_compat as oc  # noqa: E402
ok('M9 quota_left reads xKiro\'s /usage', oc.quota_left({'windows': [{'limit_per_day': 500000, 'used': 120000}]}) == 380000)

# ---- M11: the Claude arm
def runner(cmd, src, res, used='claude-opus-5-5'):
    Path(res).write_text(json.dumps({'result': LONG, 'modelUsage': {used: {}}, 'duration_ms': 4000}), encoding='utf-8')


row = sc.claude_arm('q', BASE / 'claude', 'claude-opus-5-5', runner=runner, say=lambda x: None)
ok('M11 claude -p answer saved, with the full model id passed', row['status'] == 'ok' and (BASE / 'claude' / 'claude-p-claude-opus-5-5.md').is_file(), row)
row = sc.claude_arm('q', BASE / 'claude2', 'claude-opus-5-5', runner=lambda c, s, r: runner(c, s, r, used='claude-haiku-5-5'), say=lambda x: None)
ok('M11 an alias that landed on another model is refused', row['status'] == 'failed' and row['tries'][0]['kind'] == 'wrong_model', row)
ran = []
row = sc.claude_arm('q', BASE / 'claude', 'claude-opus-5-5', runner=lambda *a: ran.append(1), say=lambda x: None)
ok('M11 a rerun picks up the answer already written, without starting it again', not ran and row['status'] == 'ok', row)

# ---- the model council
def council_fake(host, mid, msgs, **kw):
    name = mid.split('/')[-1]
    if name in ('c2', 'c4'):
        raise errors.ProviderError('quota', 429, None, 'daily free quota over')
    return got('1. Improvements ' + LONG)


cands = [('', model(f'c{i}', ('hostA', {}), aa=100 - i)) for i in range(1, 9)]
lines = []
rows = sc.council('my plan: ship on friday', BASE / 'council', cands, lambda h: True, council_fake, n=4, say=lines.append, mem=BASE / 'mem-c.json')
good = [r['model'] for r in rows if r['status'] == 'ok']
ok('council: 4 answered, the fallen ones replaced by the next smartest', sorted(good) == ['c1', 'c3', 'c5', 'c6'], good)
ok('council: no model past the ones needed was asked', not any(r['model'] in ('c7', 'c8') for r in rows), [r['model'] for r in rows])
ok('council: COUNCIL.md lists the advisers', (BASE / 'council' / 'COUNCIL.md').read_text(encoding='utf-8').startswith('# Model council: 4 of 4'))
prompt_seen = []
sc.council('situation X', BASE / 'council2', cands[:1], lambda h: True, lambda h, m, msgs, **kw: (prompt_seen.append(msgs[0]['content']), got(LONG))[1],
           n=1, say=lambda x: None, mem=BASE / 'mem-c2.json')
ok('council: the prompt asks improvements, a constructive fact-check and brilliant ideas on the user\'s text',
   all(s in prompt_seen[0] for s in ('Improvements', 'Constructive fact-check', 'Brilliant ideas', 'situation X')), prompt_seen[0][:300])
rows = sc.council('q', BASE / 'council3', cands[:2], lambda h: True, council_fake, n=4, say=lines.append, mem=BASE / 'mem-c3.json')
ok('council: when the candidates end, it says how many answered', any('only 1 of 4 answered' in x for x in lines), lines[-3:])

realcat.order = order
print(f'fails {fails}')
sys.exit(1 if fails else 0)
