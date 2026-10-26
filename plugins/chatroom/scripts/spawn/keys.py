# Le sonde di verifica sono adattate da free-claude-code (Alishahryar1), AGPL-3.0-only, commit 707b6dd:
# src/free_claude_code/providers/credential_validation.py
"""The keys of the spawn mode: stored encrypted, checked without generating anything, never shown.

- Where: ~/.claude/chatroom/secrets/<provider>.<n>.key (CHATROOM_SECRETS moves it, for tests), one file per key; a
  provider may have several (numbered, as in free-claude-code). On Windows each file is encrypted with DPAPI for the
  current user; elsewhere it is a file only the user can read.
- Never in the room, the chat, a log, a URL or an answer of the viewer: status() says which providers have keys and how
  they were checked, never the keys; scrub() removes any stored key (and any OpenRouter-shaped key) from a text.
- verify(): one GET on an endpoint that needs the key (OpenRouter /key, Groq /models, Google's model list, Hugging
  Face whoami...): verified, rejected, or unverified when the provider gives no evidence either way.
- OpenRouter: login from the browser with OAuth PKCE (pkce_start, pkce_finish); the callback lands on the viewer, which
  only serves 127.0.0.1, and carries a one-time state.
- The environment variable of a provider (OPENROUTER_API_KEY...) counts as one more key, after the stored ones."""
import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

import httpx

from spawn.providers import catalog

TIMEOUT = 5.0
PKCE_TTL = 600                                     # a login must come back within 10 minutes
OPENROUTER_KEY = re.compile(r'sk-or-v1-[A-Za-z0-9]{8,}')
_pkce, _lock = {}, threading.Lock()                # state -> (verifier, created)


def secrets_dir():
    return Path(os.environ.get('CHATROOM_SECRETS') or Path.home() / '.claude' / 'chatroom' / 'secrets')


# ------------------------------------------------------------------ encryption at rest
if os.name == 'nt':
    import ctypes
    import ctypes.wintypes as w

    class _Blob(ctypes.Structure):
        _fields_ = [('cbData', w.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    _P = ctypes.POINTER(_Blob)
    _c32, _k32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    for _f in (_c32.CryptProtectData, _c32.CryptUnprotectData):    # without argtypes, 64-bit pointers fail (error 998)
        _f.argtypes = [_P, ctypes.c_void_p, _P, ctypes.c_void_p, ctypes.c_void_p, w.DWORD, _P]
        _f.restype = w.BOOL
    _k32.LocalFree.argtypes = [ctypes.c_void_p]

    def _dpapi(fn, data):
        buf = ctypes.create_string_buffer(data, len(data))
        src, out = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _Blob()
        if not fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out)):   # 0x1: no UI
            raise OSError(f'DPAPI failed ({ctypes.get_last_error()})')
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _k32.LocalFree(out.pbData)

    def _seal(data):
        return _dpapi(_c32.CryptProtectData, data)

    def _open(data):
        return _dpapi(_c32.CryptUnprotectData, data)
else:
    # shortcut: no OS keyring outside Windows, the file is only readable by the user (0600); use the keyring if asked
    def _seal(data):
        return base64.b64encode(data)

    def _open(data):
        return base64.b64decode(data)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_bytes(data)
    if os.name != 'nt':
        tmp.chmod(0o600)
    os.replace(tmp, path)


# ------------------------------------------------------------------ the stored keys
def _check(provider):
    catalog.get(provider)                           # KeyError for an unknown provider: no file named by a stranger
    return provider


def _files(provider):
    return sorted(secrets_dir().glob(f'{_check(provider)}.*.key'), key=lambda p: int(p.name.split('.')[-2]))


def save(provider, key, extra=None, slot=None):
    """store one key (and the provider's extra fields, like Cloudflare's account ID); returns its slot number"""
    key = str(key or '').strip()
    if not key or len(key) > 4096 or any(c.isspace() for c in key):
        raise ValueError('a key is one line of text without spaces')
    need = catalog.get(provider).get('extra', ())
    extra = {k: str((extra or {}).get(k, '')).strip() for k in need}
    missing = [k for k, v in extra.items() if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', v)]
    if missing:
        raise ValueError(f'{provider} also needs: {", ".join(missing)}')
    if slot is None:
        used = [int(p.name.split('.')[-2]) for p in _files(provider)]
        slot = max(used, default=-1) + 1
    _write(secrets_dir() / f'{provider}.{int(slot)}.key', _seal(json.dumps({'key': key, 'extra': extra}).encode()))
    return int(slot)


def load_all(provider):
    """[{'key', 'extra', 'slot'}] of a provider, the stored ones first, then its environment variable"""
    out = []
    for p in _files(provider):
        try:
            d = json.loads(_open(p.read_bytes()))
            out.append({'key': d['key'], 'extra': d.get('extra') or {}, 'slot': int(p.name.split('.')[-2])})
        except (OSError, ValueError, KeyError):
            continue                                # another user's file, or a broken one: not a key
    env = os.environ.get(catalog.get(provider).get('env') or '')
    if env and all(k['key'] != env for k in out):
        out.append({'key': env, 'extra': {}, 'slot': None})
    return out


def load(provider):
    """the first key of a provider, or None"""
    keys = load_all(provider)
    return keys[0] if keys else None


def remove(provider, slot):
    (secrets_dir() / f'{_check(provider)}.{int(slot)}.key').unlink(missing_ok=True)
    _set_state(provider, int(slot), None)


def _state_path():
    return secrets_dir() / 'status.json'


def _states():
    try:
        return json.loads(_state_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _set_state(provider, slot, state):
    with _lock:
        d = _states()
        if state is None:
            d.pop(f'{provider}.{slot}', None)
        else:
            d[f'{provider}.{slot}'] = state
        _write(_state_path(), json.dumps(d).encode())


def status():
    """what the setup card shows, per provider: its links and offer, and for each key only its slot and its last check"""
    states = _states()
    out = {}
    for pid, p in catalog.ALL.items():
        keys = [{'slot': k['slot'], **states.get(f'{pid}.{k["slot"]}', {'state': 'unchecked'})} for k in load_all(pid)]
        out[pid] = {'name': p['name'], 'signup': p['signup'], 'offer': p['offer'], 'extra': list(p.get('extra', ())),
                    'pkce': bool(p.get('pkce')), 'can_verify': bool(p.get('verify')), 'keys': keys}
    return out


def scrub(text):
    """the text without any stored key and without anything shaped like an OpenRouter key"""
    text = OPENROUTER_KEY.sub('sk-or-v1-***', str(text))
    for pid in catalog.ALL:
        for k in load_all(pid):
            if len(k['key']) >= 8:
                text = text.replace(k['key'], '***')
    return text


# ------------------------------------------------------------------ checking a key without generating anything
def _field(payload, name):
    return payload.get(name) if isinstance(payload, dict) else None


def verify(provider, key, extra=None, client=None):
    """('verified' | 'rejected' | 'unverified', reason): one GET on an endpoint that needs the key, never a completion.
    A failure is 'unverified' unless the provider says plainly the key is wrong. client: an httpx.Client (tests)"""
    p = catalog.get(provider)
    if not p.get('verify'):
        return 'unverified', 'no_probe'
    out = _probe(provider, p['verify'], key, extra, client)
    if out[0] == 'rejected' and p.get('verify_fallback'):          # Cloudflare: an account token, else a user token
        second = _probe(provider, p['verify_fallback'], key, extra, client)
        out = second if second[0] != 'unverified' else out
    return out


def _probe(provider, probe, key, extra, client):
    path, field, rejected = probe
    try:
        path = path.format(**(extra or {}))
    except (KeyError, IndexError):
        return 'unverified', 'missing_extra'
    url = path if path.startswith('https://') else catalog.base_url(provider, extra).rstrip('/') + path
    headers = {'Accept': 'application/json', **catalog.auth_headers(provider, key)}
    try:
        if client is None:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as c:
                r = c.get(url, headers=headers)
        else:
            r = client.get(url, headers=headers)
        payload = r.json()
    except (httpx.HTTPError, ValueError, UnicodeError):
        return 'unverified', 'unreachable'
    if r.is_success and _field(payload, field) is not None:
        return 'verified', 'ok'
    api_error = isinstance(payload, dict) and bool(payload.get('error') or payload.get('message') or payload.get('detail')
                                                  or payload.get('errors'))
    google_bad = (provider == 'gemini' and r.status_code == 400 and any(
        _field(d, 'reason') == 'API_KEY_INVALID' for d in (_field(_field(payload, 'error'), 'details') or [])))
    if (api_error and r.status_code in rejected) or google_bad:
        return 'rejected', f'http_{r.status_code}'
    if r.status_code in (402, 403):
        return 'unverified', 'billing_or_permission'
    return 'unverified', f'http_{r.status_code}'


def check(provider, slot=None, client=None):
    """verify the stored key in slot (the first one when None) and remember the result, never the key"""
    keys = [k for k in load_all(provider) if slot is None or k['slot'] == slot]
    if not keys:
        raise ValueError(f'no key for {provider}')
    k = keys[0]
    state, why = verify(provider, k['key'], k['extra'], client)
    if k['slot'] is not None:
        _set_state(provider, k['slot'], {'state': state, 'why': why, 'ts': int(time.time())})
    return state, why


def openrouter_limits(key, client=None):
    """OpenRouter's GET /key: {'limit', 'limit_remaining', 'usage', 'is_free_tier'} (the card and the quota tank), or {}"""
    try:
        c = client or httpx.Client(timeout=TIMEOUT)
        try:
            r = c.get(catalog.FREE['open_router']['base'] + '/key', headers=catalog.auth_headers('open_router', key))
        finally:
            if client is None:
                c.close()
        data = r.json().get('data') if r.is_success else None
    except (httpx.HTTPError, ValueError, AttributeError):
        return {}
    return {k: data.get(k) for k in ('limit', 'limit_remaining', 'usage', 'is_free_tier')} if isinstance(data, dict) else {}


# ------------------------------------------------------------------ OpenRouter login (OAuth PKCE)
def pkce_start(callback):
    """the address to open in the browser; callback is the viewer's /spawn/oauth on 127.0.0.1 (the state goes in it)"""
    if not re.match(r'^http://(127\.0\.0\.1|localhost):\d{2,5}/', callback):
        raise ValueError('the callback must be the local viewer')
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(24)
    with _lock:
        now = time.time()
        for s in [s for s, (_, t) in _pkce.items() if now - t > PKCE_TTL]:
            del _pkce[s]
        _pkce[state] = (verifier, now)
    sep = '&' if '?' in callback else '?'
    from urllib.parse import quote
    return ('https://openrouter.ai/auth?callback_url=' + quote(f'{callback}{sep}state={state}', safe='')
            + f'&code_challenge={challenge}&code_challenge_method=S256'), state


def pkce_finish(state, code, client=None):
    """trade the code for a key (POST /api/v1/auth/keys with the verifier) and store it: (slot, check state).
    A state that is unknown, used or older than 10 minutes is refused"""
    with _lock:
        hit = _pkce.pop(str(state or ''), None)
    if not hit or time.time() - hit[1] > PKCE_TTL:
        raise ValueError('unknown or expired login: start it again')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{4,512}', str(code or '')):
        raise ValueError('bad code')
    body = {'code': code, 'code_verifier': hit[0], 'code_challenge_method': 'S256'}
    url = catalog.FREE['open_router']['base'] + '/auth/keys'
    try:
        if client is None:
            with httpx.Client(timeout=15) as c:
                r = c.post(url, json=body)
        else:
            r = client.post(url, json=body)
        key = r.json().get('key') if r.is_success else None
    except (httpx.HTTPError, ValueError, AttributeError):
        key = None
    if not key:
        raise ValueError(f'OpenRouter did not give a key (HTTP {getattr(locals().get("r"), "status_code", "?")})')
    slot = save('open_router', key)
    return slot, check('open_router', slot, client)[0]


# ------------------------------------------------------------------ the viewer's routes (chat.py serve hands them here)
def handle(method, path, query, body, port, client=None):
    """(status, content type, body) for /spawn/keys... and /spawn/oauth..., or None for any other path. The viewer
    calls it after its own check that the request comes from this computer (trusted()). No answer ever carries a key"""
    if not (path == '/spawn/keys' or path.startswith('/spawn/keys/') or path.startswith('/spawn/oauth')):
        return None
    ok = lambda obj: (200, 'application/json; charset=utf-8', json.dumps(obj))
    try:
        if method == 'GET' and path == '/spawn/keys':
            return ok(status())
        if method == 'POST' and path == '/spawn/keys':
            pid = str(body.get('provider', ''))
            slot = save(pid, body.get('key'), body.get('extra') if isinstance(body.get('extra'), dict) else None,
                        body.get('slot') if isinstance(body.get('slot'), int) else None)
            state, why = check(pid, slot, client)
            return ok({'provider': pid, 'slot': slot, 'state': state, 'why': why})
        if method == 'POST' and path == '/spawn/keys/check':
            state, why = check(str(body.get('provider', '')), body.get('slot') if isinstance(body.get('slot'), int) else None, client)
            return ok({'state': state, 'why': why})
        if method == 'POST' and path == '/spawn/keys/remove':
            remove(str(body.get('provider', '')), int(body.get('slot')))
            return ok({'removed': True})
        if method == 'GET' and path == '/spawn/oauth/start':
            url, _ = pkce_start(f'http://127.0.0.1:{int(port)}/spawn/oauth')
            return ok({'url': url})
        if method == 'GET' and path == '/spawn/oauth':
            from urllib.parse import parse_qs
            q = parse_qs(query or '')
            try:
                slot, state = pkce_finish(q.get('state', [''])[0], q.get('code', [''])[0], client)
                line = f'✓ OpenRouter ({state})'
            except ValueError as exc:
                line = f'✗ OpenRouter: {scrub(exc)}'
            page = ('<!doctype html><meta charset="utf-8"><title>OpenRouter</title><body style="font:16px system-ui;'
                    f'padding:2em">{line.replace("<", "&lt;")}<script>setTimeout(() => window.close(), 1500)</script>')
            return 200, 'text/html; charset=utf-8', page
    except (KeyError, ValueError, TypeError) as exc:
        return 400, 'application/json; charset=utf-8', json.dumps({'error': scrub(exc)})
    return 404, 'application/json; charset=utf-8', json.dumps({'error': 'not found'})


def _prova():
    """self-check, no network (httpx.MockTransport) and a temporary secrets folder: python -m spawn.keys"""
    import tempfile
    from urllib.parse import parse_qs, urlparse
    fake = 'sk-or-v1-' + 'a1b2c3d4' * 8                  # shaped like a key, it is not one
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['CHATROOM_SECRETS'] = tmp
        for p in catalog.ALL.values():
            os.environ.pop(p.get('env') or '_', None)
        assert load('groq') is None and save('groq', 'gsk_test1') == 0 and save('groq', 'gsk_test2') == 1
        assert [k['key'] for k in load_all('groq')] == ['gsk_test1', 'gsk_test2']
        raw = (Path(tmp) / 'groq.0.key').read_bytes()
        assert b'gsk_test1' not in raw or os.name != 'nt', 'stored in clear on Windows'
        for bad in ('', 'two words', 'x' * 5000):
            try:
                save('groq', bad)
                raise AssertionError(f'bad key accepted: {bad[:20]!r}')
            except ValueError:
                pass
        try:
            save('cloudflare', 'cf_token')
            raise AssertionError('cloudflare without account id accepted')
        except ValueError:
            pass
        save('cloudflare', 'cf_token', {'account_id': 'abc123'})
        assert load('cloudflare')['extra'] == {'account_id': 'abc123'}
        try:
            save('../x', 'k')
            raise AssertionError('unknown provider accepted')
        except KeyError:
            pass
        os.environ['GROQ_API_KEY'] = 'gsk_env'
        assert load_all('groq')[-1] == {'key': 'gsk_env', 'extra': {}, 'slot': None}
        del os.environ['GROQ_API_KEY']
        remove('groq', 0)
        assert [k['slot'] for k in load_all('groq')] == [1]

        cf_urls = []

        def answer(request):
            u = str(request.url)
            auth = request.headers.get('authorization', '') + request.headers.get('x-goog-api-key', '')
            if 'cloudflare' in u:
                cf_urls.append((u, auth))
                ok = ('acct-token' in auth and '/accounts/abc123/' in u) or ('user-token' in auth and '/user/' in u)
                return httpx.Response(200, json={'result': {'status': 'active'}, 'success': True}) if ok else \
                    httpx.Response(401, json={'success': False, 'errors': [{'code': 1000, 'message': 'Invalid API Token'}]})
            if u.endswith('/auth/keys'):
                b = json.loads(request.content)
                ok = b['code'] == 'good-code' and base64.urlsafe_b64encode(hashlib.sha256(b['code_verifier'].encode()).digest()).rstrip(b'=').decode() == seen['challenge']
                return httpx.Response(200 if ok else 403, json={'key': fake} if ok else {'error': 'no'})
            if 'googleapis' in u:
                return httpx.Response(400, json={'error': {'details': [{'reason': 'API_KEY_INVALID'}]}}) if 'bad' in auth else httpx.Response(200, json={'models': []})
            if 'good' in auth or fake in auth:
                return httpx.Response(200, json={'data': {'limit': 10, 'limit_remaining': 4, 'usage': 6, 'is_free_tier': True}} if u.endswith('/key') else {'data': []})
            if 'down' in auth:
                return httpx.Response(503, text='upstream down')
            return httpx.Response(401, json={'error': {'message': 'invalid key'}})
        seen = {}
        client = httpx.Client(transport=httpx.MockTransport(answer))
        assert verify('groq', 'good', client=client) == ('verified', 'ok')
        assert verify('groq', 'wrong', client=client) == ('rejected', 'http_401')
        assert verify('groq', 'down', client=client)[0] == 'unverified'
        assert verify('mistral', 'wrong', client=client)[0] == 'unverified'        # positive evidence only
        assert verify('gemini', 'bad', client=client)[0] == 'rejected' and verify('gemini', 'good', client=client)[0] == 'verified'
        assert verify('kilo', 'good', client=client) == ('unverified', 'no_probe')
        # Cloudflare: an account token answers only on its account's endpoint, a user token only on /user
        assert verify('cloudflare', 'acct-token', {'account_id': 'abc123'}, client) == ('verified', 'ok')
        assert verify('cloudflare', 'user-token', {'account_id': 'abc123'}, client) == ('verified', 'ok')
        assert verify('cloudflare', 'wrong', {'account_id': 'abc123'}, client)[0] == 'rejected'
        assert verify('cloudflare', 'acct-token', None, client) == ('unverified', 'missing_extra')
        assert [u for u in cf_urls if 'acct-token' in u[1]][0][0].endswith('/accounts/abc123/tokens/verify')
        assert check('groq', 1, client)[0] == 'rejected' and status()['groq']['keys'] == [{'slot': 1, 'state': 'rejected', 'why': 'http_401', 'ts': status()['groq']['keys'][0]['ts']}]
        assert 'gsk_test2' not in json.dumps(status()) and 'cf_token' not in json.dumps(status())
        url, state = pkce_start('http://127.0.0.1:8777/spawn/oauth')
        q = parse_qs(urlparse(url).query)
        seen['challenge'] = q['code_challenge'][0]
        assert q['code_challenge_method'] == ['S256'] and f'state={state}' in q['callback_url'][0]
        try:
            pkce_start('https://evil.example/cb')
            raise AssertionError('a remote callback was accepted')
        except ValueError:
            pass
        try:
            pkce_finish(state, 'wrong-code', client)
            raise AssertionError('a refused exchange stored a key')
        except ValueError:
            pass
        url, state = pkce_start('http://127.0.0.1:8777/spawn/oauth')
        seen['challenge'] = parse_qs(urlparse(url).query)['code_challenge'][0]
        slot, st = pkce_finish(state, 'good-code', client)
        assert load('open_router')['key'] == fake and st == 'verified'
        try:
            pkce_finish(state, 'good-code', client)
            raise AssertionError('a state was used twice')
        except ValueError:
            pass
        assert openrouter_limits(fake, client) == {'limit': 10, 'limit_remaining': 4, 'usage': 6, 'is_free_tier': True}
        text = scrub(f'error with {fake} and cf_token and sk-or-v1-zzzzzzzzzzzz')
        assert fake not in text and 'cf_token' not in text and 'sk-or-v1-zzzz' not in text, text
        code, ctype, out = handle('POST', '/spawn/keys', '', {'provider': 'groq', 'key': 'good-key-1'}, 8777, client)
        assert code == 200 and json.loads(out)['state'] == 'verified' and 'good-key-1' not in out
        code, _, out = handle('GET', '/spawn/keys', '', {}, 8777, client)
        assert code == 200 and 'good-key-1' not in out and fake not in out and json.loads(out)['open_router']['pkce'] is True
        code, _, out = handle('POST', '/spawn/keys', '', {'provider': 'nope', 'key': 'k'}, 8777, client)
        assert code == 400 and handle('GET', '/other', '', {}, 8777) is None
        code, _, out = handle('GET', '/spawn/oauth/start', '', {}, 8777, client)
        state2 = parse_qs(urlparse(parse_qs(urlparse(json.loads(out)['url']).query)['callback_url'][0]).query)['state'][0]
        seen['challenge'] = parse_qs(urlparse(json.loads(out)['url']).query)['code_challenge'][0]
        code, ctype, page = handle('GET', '/spawn/oauth', f'state={state2}&code=good-code', {}, 8777, client)
        assert code == 200 and 'text/html' in ctype and '✓' in page and fake not in page
        code, ctype, page = handle('GET', '/spawn/oauth', f'state={state2}&code=good-code', {}, 8777, client)
        assert '✗' in page
        for f in Path(tmp).iterdir():
            assert b'sk-or-v1-' not in f.read_bytes() or os.name != 'nt', f'a key in clear in {f.name}'
        del os.environ['CHATROOM_SECRETS']
    print('keys ok')


if __name__ == '__main__':
    _prova()
