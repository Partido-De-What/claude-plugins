# Adattato da free-claude-code (Alishahryar1), AGPL-3.0-only, commit 707b6dd: src/free_claude_code/core/anthropic/streaming/recovery.py
# (continuation_suffix, make_response_recovery_body, make_tool_repair_body, _repair_suffix_candidates, validate_tool_input,
# accept_tool_json_repair) e src/free_claude_code/providers/openai_chat/transport.py (_repair_tool_args)
"""What happens after the answer: a stream that broke half way is continued, a tool call with broken JSON is repaired.

complete(): one chat() through the limiter; on 'stream_cut' it asks the same model to continue where it stopped (the
partial text and thinking are given back to it) and keeps only the part that is new (continuation_suffix); then every
tool call whose arguments are not a JSON object valid for the tool's schema is repaired: the model is asked for the
missing suffix of that JSON only, which is accepted when prefix + suffix parses and validates. Each step is one
attempt more for the same request, never a resend of the whole conversation as new."""
import copy
import json

import jsonschema

from spawn import errors
from spawn.limiter import LIMITER
from spawn.providers import openai_compat

RESUMES, REPAIRS = 2, 2
_RESUME = ('The previous provider stream was interrupted. Continue the assistant response exactly where it stopped. '
           'Do not repeat text already written.')
_THINKING = 'The assistant had already emitted this hidden thinking before the interruption:\n'


def continuation_suffix(existing, candidate):
    """the part of candidate that is new after existing; None when they cannot be joined"""
    existing, candidate = existing or '', candidate or ''
    if not candidate:
        return ''
    if not existing:
        return candidate
    if candidate.startswith(existing):
        return candidate[len(existing):]
    for size in range(min(len(existing), len(candidate)), 0, -1):
        if existing.endswith(candidate[:size]):
            return candidate[size:]
    return candidate if len(candidate) < max(200, len(existing) // 2) else None


def resume_messages(messages, partial_text, partial_thinking=''):
    out = copy.deepcopy(messages)
    if partial_text:
        out.append({'role': 'assistant', 'content': partial_text})
    out.append({'role': 'user', 'content': (f'{_THINKING}{partial_thinking}\n\n' if partial_thinking else '') + _RESUME})
    return out


def repair_messages(messages, tool_name, prefix, schema):
    return copy.deepcopy(messages) + [{'role': 'user', 'content': (
        'A streamed tool call was interrupted while writing JSON arguments.\n'
        f'Tool name: {tool_name}\nJSON schema: {json.dumps(schema or {"type": "object"}, separators=(",", ":"))}\n'
        f'Already emitted JSON prefix: {prefix}\n\n'
        'Return only the exact missing JSON suffix needed to complete the same object. '
        'Do not repeat the prefix. Do not include markdown or explanation.')}]


def valid_args(text, schema):
    """the arguments as a dict when they are a JSON object valid for the schema (a broken schema is not held against them)"""
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    if schema:
        try:
            cls = jsonschema.validators.validator_for(schema)
            cls.check_schema(schema)
            cls(schema).validate(parsed)
        except jsonschema.exceptions.SchemaError:
            return parsed
        except jsonschema.exceptions.ValidationError:
            return None
    return parsed


def accept_repair(prefix, candidate, schema):
    """the suffix that completes prefix into valid arguments, from the model's answer (fences and a repeated prefix
    are tolerated), or None"""
    raw = (candidate or '').strip()
    if raw.startswith('```'):
        lines = raw.splitlines()[1:]
        raw = '\n'.join(lines[:-1] if lines and lines[-1].strip() == '```' else lines).strip()
    for suffix in dict.fromkeys([raw] + ([raw[len(prefix):]] if prefix and raw.startswith(prefix) else [])):
        if suffix and valid_args(prefix + suffix, schema) is not None:
            return suffix
    return None


def complete(provider, model, messages, *, tools=None, key=None, stop=None, limiter=None, tokens=None, attempts=None, **kw):
    """the whole answer of one step of a role: limiter, resume of a broken stream, repair of broken tool JSON.
    tokens: what the first request counts against tokens per minute (input + max_tokens), when the caller counts it better
    than the estimate here. attempts: the limiter's tries for a wait-fixable failure (10 by default; fewer when the
    caller has another host for this model). Returns chat()'s result; raises errors.ProviderError for what neither a wait nor a repair can fix"""
    lim = limiter or LIMITER
    if key is None:
        from spawn import keys
        k = keys.load(provider)
        if not k:
            raise errors.ProviderError('auth', None, None, f'no key for {provider}')
        key, kw['extra'] = k['key'], kw.get('extra') or k['extra']
    budget = int(kw.get('max_tokens') or 4096)        # what a request counts against tokens per minute: its input and its max_tokens
    call = lambda msgs, t: lim.run(provider, key, model, lambda: openai_compat.chat(provider, model, msgs, tools=t, key=key, **kw), stop,
                                   tokens=tokens if tokens and msgs is messages else openai_compat.estimate_tokens(msgs, t) + budget,
                                   attempts=attempts)
    text, thinking, result = '', '', None
    for attempt in range(RESUMES + 1):
        try:
            got = call(messages if attempt == 0 else resume_messages(messages, text, thinking), tools)
        except errors.ProviderError as e:
            if e.kind != 'stream_cut' or not e.partial or attempt == RESUMES:
                raise
            got, cut = e.partial, True
        else:
            cut = False
        if result is None:
            result = got
        else:                                      # a continuation: keep only the new part
            extra = continuation_suffix(text, got['text'])
            if extra is None:
                raise errors.ProviderError('stream_cut', None, None, 'the continuation does not join the text', result)
            result['text'] = text + extra
            result['message']['content'] = result['text'] or None
            for f in ('tool_calls', 'finish', 'usage'):
                result[f] = got[f] or result[f]
            if got['tool_calls']:
                result['message']['tool_calls'] = got['tool_calls']
        text, thinking = result['text'], result['reasoning']
        if not cut:
            break
    if result['finish'] == 'length' and not (result['text'] or '').strip() and not result['tool_calls']:
        # the reasoning ate the whole output budget and nothing visible came out: once more without the effort and with
        # twice the budget; still nothing, and the role moves to another host
        kw2 = {**kw, 'effort': None, 'max_tokens': 2 * int(kw.get('max_tokens') or 4096)}
        again = lim.run(provider, key, model, lambda: openai_compat.chat(provider, model, messages, tools=tools, key=key, **kw2), stop,
                        tokens=openai_compat.estimate_tokens(messages, tools) + kw2['max_tokens'], attempts=attempts)
        if again['finish'] == 'length' and not (again['text'] or '').strip() and not again['tool_calls']:
            raise errors.ProviderError('no_output', None, None, 'the reasoning used the whole output budget', again)
        result = again
    schemas = {t['function']['name']: t['function'].get('parameters') for t in tools or [] if t.get('function')}
    for c in result['message'].get('tool_calls', []):
        args, name = c['function']['arguments'], c['function']['name']
        if name in schemas and valid_args(args or '{}', schemas[name]) is None:
            msgs = repair_messages(messages, name, args, schemas[name])
            for _ in range(REPAIRS):
                fix = accept_repair(args, call(msgs, None)['text'], schemas[name])
                if fix is not None:
                    c['function']['arguments'] = args + fix
                    break
            else:
                raise errors.ProviderError('tool_json', None, None, f'arguments of {name} could not be repaired', result)
    return result


def _prova():
    """python -m spawn.providers.recovery"""
    assert continuation_suffix('Hello wor', 'Hello world!') == 'ld!' and continuation_suffix('abc', 'bcdef') == 'def'
    assert continuation_suffix('', 'x') == 'x' and continuation_suffix('a' * 500, 'z' * 400) is None
    schema = {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']}
    assert accept_repair('{"te', 'xt": "hi"}', schema) == 'xt": "hi"}'
    assert accept_repair('{"te', '```json\n{"text": "hi"}\n```', schema) == 'xt": "hi"}'      # fenced, with the prefix repeated
    assert accept_repair('{"te', '{"other": 1}', schema) is None and accept_repair('{"text": 5', '}', schema) is None
    assert valid_args('{"text": "a"}', schema) == {'text': 'a'} and valid_args('[1]', None) is None
    import threading
    from spawn.limiter import Limiter
    script, sent, kws = [], [], []

    def fake_chat(provider, model, msgs, tools=None, key=None, **kw):
        sent.append((msgs, tools))
        kws.append(kw)
        step = script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step
    real = openai_compat.chat
    openai_compat.chat = fake_chat
    try:
        res = lambda text, calls=(), finish='stop': {'message': {'role': 'assistant', 'content': text or None, **({'tool_calls': list(calls)} if calls else {})},
                                                     'text': text, 'reasoning': '', 'tool_calls': list(calls), 'finish': finish, 'usage': {}}
        part = res('The answer is forty', finish=None)
        script[:] = [errors.ProviderError('stream_cut', None, None, 'cut', part), res('forty-two.')]
        r = complete('groq', 'm', [{'role': 'user', 'content': 'q'}], key='k', limiter=Limiter())
        assert r['text'] == 'The answer is forty-two.' and r['message']['content'] == r['text'], r
        assert sent[1][0][-1]['content'].startswith('The previous provider stream') and sent[1][0][-2] == {'role': 'assistant', 'content': 'The answer is forty'}
        tools = [{'type': 'function', 'function': {'name': 'chat_post', 'parameters': schema}}]
        call = {'id': 'c1', 'type': 'function', 'function': {'name': 'chat_post', 'arguments': '{"te'}}
        script[:] = [res('', [call], 'tool_calls'), res('nonsense'), res('xt": "ok"}')]
        sent.clear()
        r = complete('groq', 'm', [{'role': 'user', 'content': 'q'}], tools=tools, key='k', limiter=Limiter())
        assert r['tool_calls'][0]['function']['arguments'] == '{"text": "ok"}' and sent[1][1] is None and 'JSON schema' in sent[1][0][-1]['content']
        call = {'id': 'c2', 'type': 'function', 'function': {'name': 'chat_post', 'arguments': '{"te'}}
        script[:] = [res('', [call], 'tool_calls'), res('x'), res('y')]
        try:
            complete('groq', 'm', [{'role': 'user', 'content': 'q'}], tools=tools, key='k', limiter=Limiter())
            raise AssertionError('broken JSON accepted')
        except errors.ProviderError as e:
            assert e.kind == 'tool_json' and e.action == 'repair'
        script[:] = [res('', finish='length'), res('visible now')]
        sent.clear()
        r = complete('groq', 'm', [{'role': 'user', 'content': 'q'}], key='k', limiter=Limiter(), effort='high', max_tokens=100)
        assert r['text'] == 'visible now' and len(sent) == 2 and kws[-1]['effort'] is None and kws[-1]['max_tokens'] == 200, kws[-1]
        script[:] = [res('', finish='length'), res('', finish='length')]
        try:
            complete('groq', 'm', [{'role': 'user', 'content': 'q'}], key='k', limiter=Limiter())
            raise AssertionError('an empty answer passed')
        except errors.ProviderError as e:
            assert e.kind == 'no_output' and e.action == 'next_host'
        script[:] = [errors.ProviderError('payment', 402)]
        try:
            complete('groq', 'm', [{'role': 'user', 'content': 'q'}], key='k', limiter=Limiter())
            raise AssertionError('402 swallowed')
        except errors.ProviderError as e:
            assert e.kind == 'payment' and not script
    finally:
        openai_compat.chat = real
    print('recovery ok')


if __name__ == '__main__':
    _prova()
