# Adattato da free-claude-code (Alishahryar1), AGPL-3.0-only, commit 707b6dd: src/free_claude_code/providers/failure_policy.py
# e src/free_claude_code/providers/admission.py (_retry_after_seconds)
"""What went wrong with a provider, as a kind the rest of the spawn mode acts on.

A ProviderError carries a kind, the HTTP status, the seconds the provider asked to wait (Retry-After) and a short detail
with every key scrubbed. The kind decides the action (ACTION): retry the same host after a wait, move to another host of
the same model, hand over the context, or stop the role and show a card. The texts the user reads are the card's (locales
spawn.err.<kind>), not these."""
import email.utils
import math
import re
import time

KINDS = ('rate_limit', 'quota', 'overloaded', 'upstream', 'timeout', 'network', 'stream_cut', 'auth', 'payment', 'forbidden',
         'context', 'too_large', 'bad_request', 'not_found', 'tool_json')
ACTION = {'rate_limit': 'retry', 'overloaded': 'retry', 'upstream': 'retry', 'timeout': 'retry', 'network': 'retry',
          'stream_cut': 'resume', 'tool_json': 'repair',
          'quota': 'next_host', 'not_found': 'next_host',
          'context': 'handover',
          'auth': 'stop', 'payment': 'stop', 'forbidden': 'stop', 'too_large': 'stop', 'bad_request': 'stop'}
RETRYABLE = frozenset(k for k, a in ACTION.items() if a == 'retry')

_CONTEXT = re.compile(r'context[_ ]length[_ ]exceeded|context[_ ]window|maximum context length|too many tokens|'
                      r'prompt is too long|input is too long|reduce the length', re.I)
_QUOTA = re.compile(r'quota|credits?|daily limit|free[- ]tier limit|per[- ]day|requests per day|insufficient[_ ]balance', re.I)
_OVERLOAD = re.compile(r'overloaded|capacity|resource[_ ]?exhausted|temporarily unavailable|degraded function', re.I)
_RATE = re.compile(r'rate[_ ]limit|too many requests', re.I)


class ProviderError(Exception):
    def __init__(self, kind, status=None, retry_after=None, detail='', partial=None):
        assert kind in KINDS, kind
        self.kind, self.status, self.retry_after, self.partial = kind, status, retry_after, partial
        self.detail = _scrub(str(detail))[:500]
        super().__init__(f'{kind} ({status}): {self.detail}')

    @property
    def action(self):
        return ACTION[self.kind]


def _scrub(text):
    try:
        from spawn import keys
        return keys.scrub(text)
    except Exception:                               # never fail while reporting a failure
        return re.sub(r'sk-or-v1-[A-Za-z0-9]{8,}', 'sk-or-v1-***', text)


def retry_after(headers):
    """seconds from a Retry-After header (seconds or an HTTP date), or None"""
    value = (headers or {}).get('retry-after') if hasattr(headers, 'get') else None
    if not value or not str(value).strip():
        return None
    value = str(value).strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        seconds = when.timestamp() - time.time()
    return max(0.0, seconds) if math.isfinite(seconds) else None


def classify(status, body='', headers=None):
    """ProviderError for an HTTP answer that is not a success; body is its text (JSON or not)"""
    text = body if isinstance(body, str) else str(body)
    wait = retry_after(headers)
    if _CONTEXT.search(text):
        kind = 'context'
    elif status == 401:
        kind = 'auth'
    elif status == 402:
        kind = 'payment'
    elif status == 403:
        kind = 'quota' if _QUOTA.search(text) else 'forbidden'
    elif status == 404:
        kind = 'not_found'
    elif status == 413:
        kind = 'too_large'
    elif status == 429:
        kind = 'quota' if _QUOTA.search(text) and not wait else 'rate_limit'
    elif status in (408, 504):
        kind = 'timeout'
    elif status == 529 or (status and status >= 500 and _OVERLOAD.search(text)):
        kind = 'overloaded'
    elif status and status >= 500:
        kind = 'upstream'
    elif _RATE.search(text):
        kind = 'rate_limit'
    elif _OVERLOAD.search(text):
        kind = 'overloaded'
    else:
        kind = 'bad_request'
    return ProviderError(kind, status, wait, text)


def from_exception(exc):
    """ProviderError for a transport failure (httpx), or the error itself"""
    if isinstance(exc, ProviderError):
        return exc
    import httpx
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError('timeout', None, None, type(exc).__name__)
    if isinstance(exc, (httpx.RemoteProtocolError, httpx.ReadError)):
        return ProviderError('stream_cut', None, None, type(exc).__name__)
    if isinstance(exc, httpx.TransportError):
        return ProviderError('network', None, None, type(exc).__name__)
    return ProviderError('upstream', None, None, f'{type(exc).__name__}: {exc}')


def _prova():
    """python -m spawn.errors"""
    c = lambda s, b='', h=None: classify(s, b, h).kind
    assert c(401) == 'auth' and c(402) == 'payment' and c(403) == 'forbidden' and c(404) == 'not_found'
    assert c(429, '{"error": "Rate limit exceeded"}', {'retry-after': '7'}) == 'rate_limit'
    assert classify(429, '', {'retry-after': '7'}).retry_after == 7.0
    assert c(429, '{"error": {"message": "free-models-per-day limit reached"}}') == 'quota'
    assert c(400, '{"error": {"code": "context_length_exceeded"}}') == 'context' and c(400, 'bad field x') == 'bad_request'
    assert c(503, 'model overloaded') == 'overloaded' and c(500, 'boom') == 'upstream' and c(504) == 'timeout'
    assert c(413, 'tokens per minute') == 'too_large'
    assert 0 < retry_after({'retry-after': email.utils.formatdate(time.time() + 30, usegmt=True)}) <= 31
    assert retry_after({'retry-after': 'nan'}) is None and retry_after({}) is None
    e = classify(500, 'key sk-or-v1-' + 'b' * 40 + ' leaked')
    assert 'bbbbbbbb' not in str(e) and e.action == 'retry'
    assert ProviderError('context').action == 'handover' and ProviderError('payment').action == 'stop'
    import httpx
    assert from_exception(httpx.ReadTimeout('x')).kind == 'timeout' and from_exception(httpx.RemoteProtocolError('x')).kind == 'stream_cut'
    assert from_exception(httpx.ConnectError('x')).kind == 'network'
    print('errors ok')


if __name__ == '__main__':
    _prova()
