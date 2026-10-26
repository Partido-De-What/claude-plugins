# Adattato da free-claude-code (Alishahryar1), AGPL-3.0-only, commit 707b6dd: src/free_claude_code/providers/openai_chat/
# (transport.py, profiles.py, reasoning.py, reasoning_details.py, usage.py, tool_calls.py), providers/groq/tpm.py,
# providers/google_openai/thought_signatures.py, providers/nvidia_nim/client.py (retry_request_body)
"""One adapter for every provider of the spawn mode: they all speak OpenAI Chat Completions.

chat() sends the role's messages as they are (no Anthropic conversion: the roles already speak this format), streams the
answer and returns it as the assistant message to append to the history, with what the next request must carry back
intact: reasoning_content, OpenRouter's reasoning_details (merged by index and type, as free-claude-code does) and each
tool call's extra_content (Gemini's thought signatures). max_tokens is always set.

What differs between providers is data (PROFILES): the name of the max-tokens field, how reasoning is asked for and with
which words, names stripped from messages, extra headers. A request the provider refuses for one of these fields is
corrected once and sent again: without the reasoning fields, without the reasoning carried in the history, without the
usage option, or (Groq) with the output budget cut to its tokens-per-minute allowance.

list_models() returns the provider's models as plain dicts, with free when the provider says so."""
import copy
import json
import re

import httpx

from spawn import errors
from spawn.providers import catalog

ATTRIBUTION = {'HTTP-Referer': 'https://github.com/ArtyomITA', 'X-Title': 'Agents Chatroom'}
CONNECT, READ = 10.0, 180.0
EFFORTS = ('minimal', 'low', 'medium', 'high', 'xhigh', 'max')
VOCAB = {'all': {e: e for e in EFFORTS},
         'lmh': {'minimal': 'low', 'low': 'low', 'medium': 'medium', 'high': 'high', 'xhigh': 'high', 'max': 'high'},
         'lmhmax': {'minimal': 'low', 'low': 'low', 'medium': 'medium', 'high': 'high', 'xhigh': 'max', 'max': 'max'},
         'gemini': {'minimal': 'minimal', 'low': 'low', 'medium': 'medium', 'high': 'high', 'xhigh': 'high', 'max': 'high'}}
GOOGLE_SKIP_SIGNATURE = 'skip_thought_signature_validator'

# per provider: mt = the max-tokens field; reasoning = how effort travels: ('effort', vocab) reasoning_effort,
# ('object', vocab) a reasoning object, 'thinking' Z.ai's thinking object, ('template', field) chat_template_kwargs,
# ('flag', field) a top-level boolean; names = strip message names; ua = User-Agent
PROFILES = {
    'open_router': {'reasoning': ('object', 'all')},
    'nvidia_nim': {'reasoning': ('effort', 'all')},
    'groq': {'mt': 'max_completion_tokens', 'reasoning': ('effort', 'lmh'), 'names': True},
    'gemini': {'reasoning': ('effort', 'gemini')},
    'mistral': {}, 'mistral_codestral': {},
    'cerebras': {'mt': 'max_completion_tokens', 'reasoning': ('effort', 'lmh')},
    'sambanova': {'reasoning': ('effort', 'lmh')},
    'cohere': {'reasoning': ('effort', {e: 'high' for e in EFFORTS}), 'names': True},
    'cloudflare': {'mt': 'max_completion_tokens', 'reasoning': ('template', 'thinking')},
    'huggingface': {}, 'siliconflow': {}, 'tokenrouter': {}, 'llm7': {},
    'ollama_cloud': {'reasoning': ('effort', 'lmhmax')},
    'kilo': {'reasoning': ('object', 'all')},
    'opencode_zen': {'ua': 'opencode'},
    'vercel': {'reasoning': ('object', 'all')},
    'zenmux': {'mt': 'max_completion_tokens', 'reasoning': ('object', 'all')},
    'orcarouter': {'reasoning': ('effort', 'lmh')},
    'nararoute': {'reasoning': ('effort', 'lmh')},
    'xkiro': {'reasoning': ('effort', 'all')},
    'zai_api': {'reasoning': 'thinking'},
    'agnes': {'reasoning': ('template', 'enable_thinking')},
    'poolside': {'reasoning': ('template', 'enable_thinking')},
    'novita': {'reasoning': ('flag', 'enable_thinking')},
}
REASONING_FIELDS = ('reasoning_effort', 'reasoning', 'thinking', 'chat_template_kwargs', 'enable_thinking')
HISTORY_REASONING = ('reasoning_content', 'reasoning_details', 'reasoning')


# ------------------------------------------------------------------ the request
def build_body(provider, model, messages, tools=None, max_tokens=4096, effort=None, session_id=None):
    """the Chat Completions body for one provider; messages are deep-copied, never changed in place"""
    p = PROFILES[provider]
    msgs = prepare_history(messages, provider)
    if p.get('names'):
        for m in msgs:
            m.pop('name', None)
    if provider == 'gemini':
        _gemini_signatures(msgs)
    body = {'model': model, 'messages': msgs, 'stream': True, 'stream_options': {'include_usage': True},
            p.get('mt', 'max_tokens'): int(max_tokens)}
    if tools:
        body['tools'] = tools
    how = p.get('reasoning')
    if effort and how:
        if how == 'thinking':
            body['thinking'] = {'type': 'enabled', 'clear_thinking': False}
        else:
            kind, arg = how
            word = (VOCAB[arg] if isinstance(arg, str) and arg in VOCAB else arg).get(effort) if kind in ('effort', 'object') else None
            if kind == 'effort' and word:
                body['reasoning_effort'] = word
            elif kind == 'object' and word:
                body['reasoning'] = {'effort': word}
            elif kind == 'template':
                body['chat_template_kwargs'] = {arg: True}
            elif kind == 'flag':
                body[arg] = True
    if provider == 'open_router':                    # decision D4: providers that keep the prompts are never used
        body['provider'] = {'data_collection': 'deny', **({'require_parameters': True} if tools else {})}
        if session_id:
            body['session_id'] = str(session_id)[:128]
    elif session_id and provider in ('kilo', 'zenmux', 'vercel'):
        body['user'] = str(session_id)[:128]
    return body


def prepare_history(messages, provider):
    """a copy of the history for this provider (prepare_history of free-claude-code, simplified): an assistant message
    written on another host (its _origin) loses what only that host can read, its reasoning, reasoning_details and the
    tool calls' extra_content (signatures), and keeps its text and tool calls; _origin itself never travels"""
    out = copy.deepcopy(messages)
    for m in out:
        origin = m.pop('_origin', None)
        if m.get('role') == 'assistant' and origin is not None and origin != provider:
            for f in HISTORY_REASONING:
                m.pop(f, None)
            for c in m.get('tool_calls') or []:
                if isinstance(c, dict):
                    c.pop('extra_content', None)
    return out


def _gemini_signatures(msgs):
    """Gemini wants the thought signature back on the first tool call of each assistant step of the current turn:
    the ones it gave are carried in extra_content; a step without one gets Google's documented skip value"""
    last_user = max((i for i, m in enumerate(msgs) if m.get('role') == 'user'), default=-1)
    for m in msgs[last_user + 1:]:
        calls = m.get('tool_calls') if m.get('role') == 'assistant' else None
        if calls and isinstance(calls[0], dict):
            google = calls[0].setdefault('extra_content', {}).setdefault('google', {})
            google.setdefault('thought_signature', GOOGLE_SKIP_SIGNATURE)


def headers(provider, key):
    h = {'Content-Type': 'application/json', 'Accept': 'text/event-stream', **catalog.auth_headers(provider, key)}
    if provider == 'open_router':
        h.update(ATTRIBUTION)
    if PROFILES[provider].get('ua'):
        h['User-Agent'] = PROFILES[provider]['ua']
    return h


# ------------------------------------------------------------------ corrections after a refusal (once each)
_TPM = re.compile(r'tokens\s+per\s+minute\s*\(\s*tpm\s*\)\s*:\s*limit\s+(\d{1,19})\s*,\s*requested\s+(\d{1,19})', re.I)


def correct(body, status, text, used):
    """a corrected copy of body for a refusal we know how to fix, or None; used: the corrections already made"""
    low = text.lower()
    if status == 413 and 'tpm' not in used:
        m = _TPM.search(text)
        mt = 'max_completion_tokens' if 'max_completion_tokens' in body else 'max_tokens'
        if m and int(m[2]) > int(m[1]) and isinstance(body.get(mt), int):
            new = body[mt] - (int(m[2]) - int(m[1]))
            if 0 < new < body[mt]:
                used.add('tpm')
                return {**body, mt: new}
    if status != 400:
        return None
    if 'usage' not in used and ('stream_options' in low or 'include_usage' in low) and 'stream_options' in body:
        used.add('usage')
        return {k: v for k, v in body.items() if k != 'stream_options'}
    if 'history' not in used and any(f in low for f in ('reasoning_content', 'reasoning_details')):
        used.add('history')
        out = copy.deepcopy(body)
        for m in out['messages']:
            for f in HISTORY_REASONING:
                m.pop(f, None)
        return out
    if 'reasoning' not in used and any(f in body for f in REASONING_FIELDS) and re.search(
            r'reasoning|thinking|chat_template|enable_thinking', low):
        used.add('reasoning')
        return {k: v for k, v in body.items() if k not in REASONING_FIELDS}
    return None


# ------------------------------------------------------------------ the answer
def merge_detail(details, slots, d):
    """one streamed reasoning_details item into the list: same (index or id, type) means the same item, whose text
    fields are appended to (as reasoning_details.py does)"""
    d = copy.deepcopy(dict(d))
    ident = d.get('index', d.get('id'))
    key = (ident, d.get('type'))
    if isinstance(ident, (str, int)) and key in slots:
        cur = details[slots[key]]
        for name, part in d.items():
            if name in ('text', 'summary', 'content', 'reasoning', 'data', 'signature') and isinstance(part, str) \
                    and isinstance(cur.get(name), str):
                cur[name] += part
            else:
                cur[name] = part
    else:
        if isinstance(ident, (str, int)):
            slots[key] = len(details)
        details.append(d)


class Answer:
    """what a stream has said so far; partial() is what a cut-off stream leaves for the resume"""

    def __init__(self, on_delta=None, origin=None):
        self.origin = origin
        self.text, self.reasoning, self.details, self.slots = [], [], [], {}
        self.calls, self.finish, self.usage, self.on_delta, self.reasoning_field = {}, None, {}, on_delta, None

    def feed(self, chunk):
        if isinstance(chunk.get('error'), (dict, str)):
            err = chunk['error'] if isinstance(chunk['error'], dict) else {'message': chunk['error']}
            raise errors.classify(int(err.get('code')) if str(err.get('code', '')).isdigit() else 500, json.dumps(err))
        if isinstance(chunk.get('usage'), dict):
            self.usage = chunk['usage']
        for choice in chunk.get('choices') or []:
            delta = choice.get('delta') or choice.get('message') or {}
            content = delta.get('content')
            if isinstance(content, list):          # Mistral: [{"type": "thinking", ...}, {"type": "text", ...}]
                for part in content:
                    if part.get('type') == 'thinking':
                        think = part.get('thinking')
                        self._reason(''.join(t.get('text', '') for t in think) if isinstance(think, list) else str(think or ''), 'reasoning_content')
                    elif isinstance(part.get('text'), str):
                        self._text(part['text'])
            elif isinstance(content, str):
                self._text(content)
            for f in ('reasoning_content', 'reasoning'):
                if isinstance(delta.get(f), str) and delta[f]:
                    self._reason(delta[f], f)
                    break
            for d in delta.get('reasoning_details') or []:
                if isinstance(d, dict):
                    merge_detail(self.details, self.slots, d)
            for tc in delta.get('tool_calls') or []:
                self._call(tc)
            if choice.get('finish_reason'):
                self.finish = choice['finish_reason']

    def _text(self, t):
        if t:
            self.text.append(t)
            if self.on_delta:
                self.on_delta('text', t)

    def _reason(self, t, field):
        if t:
            self.reasoning.append(t)
            self.reasoning_field = self.reasoning_field or field
            if self.on_delta:
                self.on_delta('reasoning', t)

    def _call(self, tc):
        i = tc.get('index')
        i = i if isinstance(i, int) else next((k for k, c in self.calls.items() if tc.get('id') and c['id'] == tc.get('id')), len(self.calls))
        c = self.calls.setdefault(i, {'id': None, 'name': '', 'args': [], 'extra': None})
        if tc.get('id'):
            c['id'] = tc['id']
        fn = tc.get('function') or {}
        if isinstance(fn.get('name'), str) and fn['name']:
            c['name'] = fn['name'] if not c['name'] or fn['name'].startswith(c['name']) else c['name'] + fn['name']
        if isinstance(fn.get('arguments'), str):
            c['args'].append(fn['arguments'])
        if isinstance(tc.get('extra_content'), dict):
            c['extra'] = tc['extra_content']

    def message(self):
        """the assistant message for the history, with what must travel back intact"""
        m = {'role': 'assistant', 'content': ''.join(self.text) or None, **({'_origin': self.origin} if self.origin else {})}
        if self.reasoning:
            m[self.reasoning_field or 'reasoning_content'] = ''.join(self.reasoning)
        if self.details:
            m['reasoning_details'] = self.details
        if self.calls:
            m['tool_calls'] = []
            for i in sorted(self.calls):
                c = self.calls[i]
                call = {'id': c['id'] or f'call_{i}', 'type': 'function', 'function': {'name': c['name'], 'arguments': ''.join(c['args'])}}
                if c['extra']:
                    call['extra_content'] = c['extra']
                m['tool_calls'].append(call)
        return m

    def result(self):
        msg = self.message()
        return {'message': msg, 'text': msg['content'] or '', 'reasoning': ''.join(self.reasoning),
                'tool_calls': msg.get('tool_calls', []), 'finish': self.finish, 'usage': self.usage}


def _stream(client, url, hdrs, body, answer):
    with client.stream('POST', url, headers=hdrs, json=body) as r:
        if r.status_code >= 400:
            raise errors.classify(r.status_code, r.read().decode('utf-8', 'replace'), r.headers)
        if 'json' in r.headers.get('content-type', '') and 'event-stream' not in r.headers.get('content-type', ''):
            answer.feed(json.loads(r.read()))      # a provider that ignored stream=true
            return
        for line in r.iter_lines():
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                return
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            answer.feed(chunk)


def chat(provider, model, messages, *, tools=None, max_tokens=4096, effort=None, key=None, extra=None, session_id=None,
         on_delta=None, client=None):
    """one completion, streamed; returns {'message', 'text', 'reasoning', 'tool_calls', 'finish', 'usage'} or raises
    errors.ProviderError. A stream that breaks after some output raises 'stream_cut' with .partial = the result so far"""
    if key is None:
        from spawn import keys
        k = keys.load(provider)
        if not k:
            raise errors.ProviderError('auth', None, None, f'no key for {provider}')
        key, extra = k['key'], extra or k['extra']
    url = catalog.base_url(provider, extra).rstrip('/') + '/chat/completions'
    body, used = build_body(provider, model, messages, tools, max_tokens, effort, session_id), set()
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(READ, connect=CONNECT))
    try:
        while True:
            answer = Answer(on_delta, provider)
            try:
                _stream(client, url, headers(provider, key), body, answer)
            except errors.ProviderError as e:
                fixed = correct(body, e.status, e.detail, used) if e.status in (400, 413) else None
                if fixed is None:
                    raise
                body = fixed                         # shortcut: a corrected resend is not counted by the limiter (at most 4 per call, on a 400/413)
                continue
            except httpx.HTTPError as exc:
                e = errors.from_exception(exc)
                if answer.text or answer.reasoning or answer.calls:
                    e.kind, e.partial = 'stream_cut', answer.result()
                raise e
            if answer.finish is None and (answer.text or answer.calls):
                raise errors.ProviderError('stream_cut', None, None, 'stream ended without a finish reason', answer.result())
            return answer.result()
    finally:
        if own:
            client.close()


# ------------------------------------------------------------------ the models
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def list_models(provider, key=None, client=None):
    """[{'id', 'name', 'ctx', 'max_out', 'tools', 'reasoning', 'free', 'price_in', 'price_out', 'modalities'}]: None
    where the provider does not say. Prices in dollars per million tokens"""
    extra = None
    if key is None:
        from spawn import keys
        k = keys.load(provider)
        key, extra = (k['key'], k['extra']) if k else (None, None)
    url = catalog.base_url(provider, extra).rstrip('/') + '/models'
    h = {'Accept': 'application/json', **(catalog.auth_headers(provider, key) if key else {})}

    def get():
        try:
            if client is None:
                with httpx.Client(timeout=20) as c:
                    r = c.get(url, headers=h)
            else:
                r = client.get(url, headers=h)
        except httpx.HTTPError as exc:
            raise errors.from_exception(exc)
        if r.status_code >= 400:
            raise errors.classify(r.status_code, r.text, r.headers)
        return r.json()
    from spawn.limiter import LIMITER                 # the model list counts against the same free limits
    payload = LIMITER.run(provider, key or '', '', get)
    rows = payload.get('data') if isinstance(payload, dict) else payload
    out = []
    for m in rows if isinstance(rows, list) else []:
        if not isinstance(m, dict) or not m.get('id'):
            continue
        price = m.get('pricing') if isinstance(m.get('pricing'), dict) else {}
        pin, pout = _num(price.get('prompt')), _num(price.get('completion'))
        params = m.get('supported_parameters') if isinstance(m.get('supported_parameters'), list) else None
        arch = m.get('architecture') if isinstance(m.get('architecture'), dict) else {}
        top = m.get('top_provider') if isinstance(m.get('top_provider'), dict) else {}
        free = (str(m['id']).endswith(':free') or (pin == 0 and pout == 0)
                or provider == 'nvidia_nim' or bool(m.get('free') or m.get('is_free')))
        out.append({'id': str(m['id']), 'name': str(m.get('name') or m['id']),
                    'ctx': m.get('context_length') or m.get('context_window') or m.get('max_context_length'),
                    'max_out': top.get('max_completion_tokens') or m.get('max_completion_tokens') or m.get('max_output_tokens'),
                    'tools': ('tools' in params) if params is not None else (m.get('capabilities') or {}).get('function_calling') if isinstance(m.get('capabilities'), dict) else None,
                    'reasoning': ('reasoning' in params) if params is not None else None,
                    'free': free, 'price_in': None if pin is None else pin * 1e6, 'price_out': None if pout is None else pout * 1e6,
                    'modalities': arch.get('input_modalities') or ['text']})
    return out


def _prova():
    """no network: a fake provider (httpx.MockTransport) streams answers and refusals. python -m spawn.providers.openai_compat"""
    sse = lambda *chunks: ''.join(f'data: {json.dumps(c)}\n\n' for c in chunks) + 'data: [DONE]\n\n'
    seen = []

    def answer(request):
        body = json.loads(request.content) if request.content else {}
        seen.append(body)
        model = body.get('model', '')
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data': [
                {'id': 'a/free-one:free', 'name': 'Free One', 'context_length': 131072, 'pricing': {'prompt': '0', 'completion': '0'},
                 'supported_parameters': ['tools', 'reasoning'], 'top_provider': {'max_completion_tokens': 8192}},
                {'id': 'b/paid', 'pricing': {'prompt': '0.000002', 'completion': '0.000008'}, 'supported_parameters': ['max_tokens']}]})
        if model == 'refuses-reasoning' and 'reasoning_effort' in body:
            return httpx.Response(400, json={'error': {'message': 'reasoning_effort is not supported for this model'}})
        if model == 'refuses-history' and any('reasoning_content' in m or 'reasoning' in m for m in body['messages']):
            return httpx.Response(400, json={'error': {'message': 'unknown field reasoning_content in messages'}})
        if model == 'tpm' and body.get('max_completion_tokens', 0) > 5000:
            return httpx.Response(413, json={'error': {'message': 'Request too large: tokens per minute (TPM): Limit 6000, Requested 9000, please reduce',
                                                       'type': 'tokens', 'code': 'rate_limit_exceeded'}})
        if model == 'busy':
            return httpx.Response(429, headers={'retry-after': '3'}, json={'error': {'message': 'rate limit'}})
        if model == 'cut':
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                                  content='data: ' + json.dumps({'choices': [{'delta': {'content': 'half an ans'}}]}) + '\n\n')
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=sse(
            {'choices': [{'delta': {'reasoning': 'let me ', 'reasoning_details': [{'type': 'reasoning.text', 'index': 0, 'text': 'let me '}]}}]},
            {'choices': [{'delta': {'reasoning': 'think', 'reasoning_details': [{'type': 'reasoning.text', 'index': 0, 'text': 'think', 'signature': 'sig'}]}}]},
            {'choices': [{'delta': {'content': 'Hello'}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'call_1', 'function': {'name': 'chat_post', 'arguments': '{"te'},
                                                    'extra_content': {'google': {'thought_signature': 'S1'}}}]}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': 'xt": "hi"}'}}]}, 'finish_reason': 'tool_calls'}]},
            {'choices': [], 'usage': {'prompt_tokens': 12, 'completion_tokens': 7, 'cost': 0}}))
    client = httpx.Client(transport=httpx.MockTransport(answer))
    msgs = [{'role': 'system', 'content': 'x', 'name': 'sys'}, {'role': 'user', 'content': 'hi'}]
    deltas = []
    r = chat('open_router', 'm', msgs, tools=[{'type': 'function', 'function': {'name': 'chat_post', 'parameters': {}}}], max_tokens=100,
             effort='high', key='k', session_id='room-ROLE', on_delta=lambda kind, t: deltas.append(kind), client=client)
    b = seen[-1]
    assert b['max_tokens'] == 100 and b['reasoning'] == {'effort': 'high'} and b['provider'] == {'data_collection': 'deny', 'require_parameters': True}
    assert b['session_id'] == 'room-ROLE' and b['stream_options'] == {'include_usage': True} and msgs[0]['name'] == 'sys'
    m = r['message']
    assert m['content'] == 'Hello' and m['reasoning'] == 'let me think' and r['finish'] == 'tool_calls' and r['usage']['prompt_tokens'] == 12
    assert m['reasoning_details'] == [{'type': 'reasoning.text', 'index': 0, 'text': 'let me think', 'signature': 'sig'}], m['reasoning_details']
    assert m['tool_calls'] == [{'id': 'call_1', 'type': 'function', 'function': {'name': 'chat_post', 'arguments': '{"text": "hi"}'},
                                'extra_content': {'google': {'thought_signature': 'S1'}}}], m['tool_calls']
    assert deltas.count('text') == 1 and deltas.count('reasoning') == 2
    chat('groq', 'm', msgs, max_tokens=50, effort='xhigh', key='k', client=client)
    b = seen[-1]
    assert b['max_completion_tokens'] == 50 and b['reasoning_effort'] == 'high' and 'name' not in b['messages'][0] and 'provider' not in b
    r = chat('groq', 'refuses-reasoning', msgs, effort='low', key='k', client=client)
    assert 'reasoning_effort' not in seen[-1] and r['text'] == 'Hello'
    hist = msgs + [m, {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'ok'}]
    chat('open_router', 'refuses-history', hist, key='k', client=client)
    assert 'reasoning' in seen[-2]['messages'][2] and '_origin' not in seen[-2]['messages'][2]     # same host: carried back, then refused
    assert not any(f in x for x in seen[-1]['messages'] for f in HISTORY_REASONING) and 'reasoning' in hist[2]
    chat('groq', 'tpm', msgs, max_tokens=8000, key='k', client=client)
    assert seen[-1]['max_completion_tokens'] == 5000, seen[-1]
    try:
        chat('groq', 'busy', msgs, key='k', client=client)
        raise AssertionError('429 not raised')
    except errors.ProviderError as e:
        assert e.kind == 'rate_limit' and e.retry_after == 3.0 and e.action == 'retry'
    try:
        chat('groq', 'cut', msgs, key='k', client=client)
        raise AssertionError('cut stream not raised')
    except errors.ProviderError as e:
        assert e.kind == 'stream_cut' and e.partial['text'] == 'half an ans'
    g = build_body('gemini', 'g', [{'role': 'user', 'content': 'q'}, {'role': 'assistant', 'tool_calls': [{'id': 'a', 'function': {'name': 'x', 'arguments': '{}'}}]}],
                   effort='medium')
    assert g['messages'][1]['tool_calls'][0]['extra_content']['google']['thought_signature'] == GOOGLE_SKIP_SIGNATURE and g['reasoning_effort'] == 'medium'
    assert build_body('zai_api', 'z', msgs, effort='high')['thinking']['type'] == 'enabled'
    assert build_body('poolside', 'p', msgs, effort='high')['chat_template_kwargs'] == {'enable_thinking': True}
    assert build_body('novita', 'n', msgs, effort='high')['enable_thinking'] is True and 'enable_thinking' not in build_body('novita', 'n', msgs)
    assert set(PROFILES) == set(catalog.FREE), set(PROFILES) ^ set(catalog.FREE)
    ms = list_models('open_router', key='k', client=client)
    assert ms[0] == {'id': 'a/free-one:free', 'name': 'Free One', 'ctx': 131072, 'max_out': 8192, 'tools': True, 'reasoning': True,
                     'free': True, 'price_in': 0.0, 'price_out': 0.0, 'modalities': ['text']}, ms[0]
    assert ms[1]['free'] is False and ms[1]['tools'] is False and abs(ms[1]['price_out'] - 8.0) < 1e-9
    assert m['_origin'] == 'open_router'
    moved = prepare_history(hist, 'groq')
    assert not any(f in moved[2] for f in HISTORY_REASONING) and 'extra_content' not in moved[2]['tool_calls'][0] and '_origin' not in moved[2]
    same = prepare_history(hist, 'open_router')
    assert same[2]['reasoning_details'] and same[2]['tool_calls'][0]['extra_content'] and '_origin' not in same[2]
    print('openai_compat ok')


if __name__ == '__main__':
    _prova()
