# Adattato da free-claude-code (Alishahryar1), AGPL-3.0-only, commit 707b6dd: src/free_claude_code/providers/admission.py,
# admission_capacity.py, admission_policy.py e core/rate_limit.py (StrictSlidingWindowLimiter)
"""The one limiter of the spawn mode: every request of every role of the room passes here, in the viewer's process.

Per lane (provider, key and, where the provider counts per model, the model): a strict sliding window (at most rpm
starts in any 60 s), a cap on requests in flight, and free-claude-code's recovery episode: after a retryable failure
(429, overload, 5xx, timeout, network) the lane waits max(backoff, Retry-After) and lets ONE probe through while the
others wait; the probe's success reopens the lane for all, its failure starts a longer wait. A request has at most 10
attempts, with backoff from 2 to 60 s plus jitter. Errors that a wait cannot fix (auth, payment, quota, context...) go
straight back to the caller, which moves to another host or stops the role.

The limits are the free tiers' (FREE_LIMITS), so the room never causes a 429 itself; Retry-After and the probe handle
the rest. snapshot() is what the Hangar's tanks and doors read: per provider the free quota left (when known) and
whether it is down.

Quota per route (provider and model): every answer's x-ratelimit-* headers (observe(), called by the adapter, 429s
included) say what is left in each of the provider's windows (requests and tokens, per minute or per day) and when it
resets; OpenRouter's /key adds the free daily requests (refresh_openrouter, called explicitly: no hidden network call),
counted down with the requests started today. route() gives, for one route, the share left in its tightest window, the
requests and tokens left, when that window resets and the 429s of the last 10 minutes: what the runner uses to pick a
host, and what the cards show. Nothing is known about a route before its first answer."""
import email.utils
import hashlib
import math
import random
import re
import threading
import time
from collections import deque

from spawn import errors

ATTEMPTS, BASE_DELAY, MAX_DELAY, JITTER = 10, 2.0, 60.0, 1.0
WINDOW = 60.0
# requests per minute, in flight at once, and whether the provider counts per model ('model') or per key ('key').
# shortcut: published free-tier figures as of 10/2026, a 429 with Retry-After still corrects them; when a provider
# publishes per-model limits in its model list, read them from there.
FREE_LIMITS = {'open_router': (20, 16, 'key'), 'nvidia_nim': (40, 4, 'key'), 'groq': (30, 4, 'model'), 'gemini': (10, 2, 'model'),
               'mistral': (60, 2, 'key'), 'cerebras': (30, 4, 'model'), 'sambanova': (20, 2, 'model'), 'cohere': (20, 2, 'key'),
               'cloudflare': (300, 4, 'key'), 'huggingface': (30, 2, 'key')}
DEFAULT = (20, 2, 'key')
RECENT = 600.0                                      # the 429s that count against a route: the last 10 minutes
_RL = re.compile(r'x-ratelimit-(limit|remaining|reset)(?:-(.+))?', re.I)
_DURATION = re.compile(r'(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?')


def reset_seconds(value, now=None):
    """seconds until a window resets, from what providers write: seconds ("7.66"), a duration ("1m26.4s", "120ms"),
    an epoch in seconds or milliseconds, or an HTTP date; None when it is none of these"""
    v, now = str(value or '').strip(), time.time() if now is None else now
    m = _DURATION.fullmatch(v)
    if v and m and any(m.groups()) and not v.replace('.', '').isdigit():
        h, mi, s, ms = (float(x) if x else 0.0 for x in m.groups())
        return h * 3600 + mi * 60 + s + ms / 1000
    try:
        n = float(v)
    except ValueError:
        try:
            n = email.utils.parsedate_to_datetime(v).timestamp() - now
        except (TypeError, ValueError, OverflowError):
            return None
        return max(0.0, n)
    if not math.isfinite(n):
        return None
    return max(0.0, n / 1000 - now if n > 1e12 else n - now if n > 1e9 else n)


def _window_name(suffix):
    return (suffix or 'requests').lower()


def fingerprint(key):
    """a short name for a key in memory and in the snapshot: never the key itself"""
    return hashlib.sha256(str(key).encode()).hexdigest()[:12]


class _Lane:
    def __init__(self, rpm, concurrency):
        self.rpm, self.concurrency = rpm, concurrency
        self.starts, self.inflight = deque(), 0
        self.ready_at, self.probe, self.failures, self.last_error = 0.0, False, 0, None   # the recovery episode


class Limiter:
    def __init__(self, sleep=time.sleep, clock=time.monotonic):
        self.cond = threading.Condition()
        self.lanes, self.quota, self.sleep, self.clock = {}, {}, sleep, clock
        self.windows, self.hits, self.seen = {}, {}, set()       # lane name -> {window: {limit, remaining, reset_at}}; route -> 429 times
        self.daily, self.today = {}, {}                          # (provider, key) -> free requests a day; -> [UTC day, requests started]

    def _name(self, provider, key, model):
        scope = FREE_LIMITS.get(provider, DEFAULT)[2]
        return (provider, fingerprint(key), model if scope == 'model' else '*')

    def _lane(self, provider, key, model):
        rpm, conc, _ = FREE_LIMITS.get(provider, DEFAULT)
        return self.lanes.setdefault(self._name(provider, key, model), _Lane(rpm, conc))

    def _admit(self, lane, stop):
        """wait for a start in the window, a free slot and (during an episode) the probe's turn; True when this one is
        the probe"""
        with self.cond:
            while True:
                if stop is not None and stop.is_set():
                    raise errors.ProviderError('network', None, None, 'stopped')
                now = self.clock()
                while lane.starts and lane.starts[0] <= now - WINDOW:
                    lane.starts.popleft()
                wait = 0.0
                if lane.failures and (lane.probe or now < lane.ready_at):
                    wait = max(0.05, lane.ready_at - now) if not lane.probe else 0.5
                elif len(lane.starts) >= lane.rpm:
                    wait = lane.starts[0] + WINDOW - now
                elif lane.inflight >= lane.concurrency:
                    wait = 0.5
                else:
                    lane.starts.append(now)
                    lane.inflight += 1
                    probe = bool(lane.failures)
                    lane.probe = lane.probe or probe
                    return probe
                self.cond.wait(min(max(wait, 0.01), 1.0))

    def _done(self, lane, probe, error, neutral=False):
        """neutral: an answer that says nothing of the lane (402, 400...): it only frees the slot. A success closes the
        episode only when it is the probe's (a request admitted before the failure proves nothing about now)"""
        with self.cond:
            lane.inflight -= 1
            if probe:
                lane.probe = False
            if neutral:
                pass
            elif error is None:
                if probe or not lane.failures:
                    lane.failures, lane.last_error = 0, None
            elif probe or not lane.failures:            # the first failure opens the episode, the probe's failure prolongs it
                lane.failures += 1
                lane.last_error = error.kind
                backoff = min(BASE_DELAY * 2 ** (lane.failures - 1), MAX_DELAY) + random.uniform(0, JITTER)
                lane.ready_at = self.clock() + max(backoff, error.retry_after or 0.0)
            self.cond.notify_all()

    def run(self, provider, key, model, fn, stop=None):
        """fn() under the limiter, attempted up to 10 times while the failure is one a wait can fix. fn raises
        errors.ProviderError (or an httpx error); anything else goes straight up. stop: a threading.Event that ends the
        waiting (the role was stopped)"""
        lane = self._lane(provider, key, model)
        last = None
        for _ in range(ATTEMPTS):
            probe = self._admit(lane, stop)
            self._count(provider, key, model)
            try:
                out = fn()
            except Exception as exc:
                err = errors.from_exception(exc) if not isinstance(exc, errors.ProviderError) else exc
                if err.kind in ('rate_limit', 'quota'):
                    with self.cond:
                        self.hits.setdefault((provider, model), deque(maxlen=200)).append(self.clock())
                if err.kind != 'stream_cut' and err.kind not in errors.RETRYABLE:
                    self._done(lane, probe, None, neutral=not probe)    # not the lane's fault; a probe that got an answer reopens it
                    raise err
                self._done(lane, probe, err)
                if err.kind == 'stream_cut':
                    raise err                        # the caller resumes from the partial answer, it is not resent whole
                last = err
                continue
            self._done(lane, probe, None)
            return out
        raise last

    def _count(self, provider, key, model):
        """one request started today on this key (OpenRouter counts the free requests per UTC day)"""
        day = time.strftime('%Y-%m-%d', time.gmtime())
        with self.cond:
            self.seen.add((provider, model))
            c = self.today.setdefault((provider, fingerprint(key)), [day, 0])
            if c[0] != day:
                c[:] = [day, 0]
            c[1] += 1

    def observe(self, provider, key, model, headers):
        """what an answer's x-ratelimit-* headers say of the provider's windows (any answer, a 429 too)"""
        got = {}
        for name, value in (headers.items() if hasattr(headers, 'items') else []):
            m = _RL.fullmatch(str(name).strip())
            if not m:
                continue
            w = got.setdefault(_window_name(m[2]), {})
            if m[1].lower() == 'reset':
                s = reset_seconds(value)
                if s is not None:
                    w['reset_at'] = self.clock() + s
            else:
                try:
                    w[m[1].lower()] = float(str(value).strip())
                except ValueError:
                    pass
        if got:
            with self.cond:
                self.seen.add((provider, model))
                self.windows.setdefault(self._name(provider, key, model), {}).update(got)

    def note_daily(self, provider, key, limit):
        """a daily limit of free requests (OpenRouter /key free_model_daily_requests)"""
        if isinstance(limit, (int, float)) and limit > 0:
            with self.cond:
                self.daily[(provider, fingerprint(key))] = float(limit)

    def refresh_openrouter(self, key, client=None):
        """OpenRouter's /key into the quota (credits) and the daily free requests: one GET, only when called"""
        from spawn import keys
        info = keys.openrouter_limits(key, client)
        self.note_quota('open_router', key, info.get('limit_remaining'), info.get('limit'))
        self.note_daily('open_router', key, info.get('free_model_daily_requests'))
        return info

    def route(self, provider, model, key=None):
        """what is left on one route: {quota 0..1|None, remaining_requests, limit_requests, remaining_tokens, limit_tokens,
        reset_s (of the tightest window), recent_429 (10 min), cooldown_s, down, inflight}. key None: the best key seen"""
        now, wall = self.clock(), time.time()
        with self.cond:
            scope = FREE_LIMITS.get(provider, DEFAULT)[2]
            names = [n for n in set(self.windows) | set(self.lanes) | {(p, f, '*') for p, f in self.daily}
                     if n[0] == provider and n[2] == (model if scope == 'model' else '*')
                     and (key is None or n[1] == fingerprint(key))]
            best = None
            for name in names:
                wins = {k: dict(v) for k, v in self.windows.get(name, {}).items()}
                limit = self.daily.get(name[:2])
                if limit:
                    day = time.strftime('%Y-%m-%d', time.gmtime())
                    used = self.today.get(name[:2], [day, 0])
                    midnight = (int(wall // 86400) + 1) * 86400
                    wins['requests-day-free'] = {'limit': limit, 'remaining': max(0.0, limit - (used[1] if used[0] == day else 0)),
                                                 'reset_at': now + midnight - wall}
                for w in wins.values():                     # a window past its reset is full again
                    if w.get('reset_at') is not None and w['reset_at'] <= now and w.get('limit'):
                        w['remaining'] = w['limit']
                rated = [(w['remaining'] / w['limit'], k, w) for k, w in wins.items()
                         if w.get('limit') and w.get('remaining') is not None]
                tight = min(rated, key=lambda x: x[0]) if rated else None
                req = min(((s, w) for s, k, w in rated if 'token' not in k), key=lambda x: x[0], default=(None, {}))[1]
                tok = min(((s, w) for s, k, w in rated if 'token' in k), key=lambda x: x[0], default=(None, {}))[1]
                lane = self.lanes.get(name)
                d = {'quota': round(max(0.0, min(1.0, tight[0])), 3) if tight else None,
                     'remaining_requests': req.get('remaining'), 'limit_requests': req.get('limit'),
                     'remaining_tokens': tok.get('remaining'), 'limit_tokens': tok.get('limit'),
                     'reset_s': round(max(0.0, tight[2]['reset_at'] - now), 1) if tight and tight[2].get('reset_at') is not None else None,
                     'cooldown_s': round(max(0.0, lane.ready_at - now)) if lane and lane.failures else 0,
                     'down': bool(lane and lane.failures >= 3), 'inflight': lane.inflight if lane else 0}
                if best is None or (d['quota'] if d['quota'] is not None else -1) > (best['quota'] if best['quota'] is not None else -1):
                    best = d
            best = best or {'quota': None, 'remaining_requests': None, 'limit_requests': None, 'remaining_tokens': None,
                            'limit_tokens': None, 'reset_s': None, 'cooldown_s': 0, 'down': False, 'inflight': 0}
            best['recent_429'] = sum(1 for x in self.hits.get((provider, model), ()) if now - x <= RECENT)
            return best

    def routes(self):
        """{"provider:model": route()} of every route that has been used or has answered"""
        with self.cond:
            seen = sorted(self.seen)
        return {f'{p}:{m}': self.route(p, m) for p, m in seen if m}

    def note_quota(self, provider, key, left=None, limit=None):
        """what the provider says of its free quota (OpenRouter /key: limit_remaining, limit)"""
        with self.cond:
            self.quota[(provider, fingerprint(key))] = (left, limit, time.time())

    def snapshot(self):
        """{provider: {'quota': 0..1 or None, 'down': bool, 'cooldown_s': seconds}} for the Hangar and the role cards"""
        out, now = {}, self.clock()
        with self.cond:
            for (provider, _, _), lane in self.lanes.items():
                d = out.setdefault(provider, {'quota': None, 'down': False, 'cooldown_s': 0})
                if lane.failures:
                    d['cooldown_s'] = max(d['cooldown_s'], round(max(0.0, lane.ready_at - now)))
                    d['down'] = d['down'] or lane.failures >= 3
            for (provider, _), (left, limit, _) in self.quota.items():
                if isinstance(left, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                    d = out.setdefault(provider, {'quota': None, 'down': False, 'cooldown_s': 0})
                    d['quota'] = round(max(0.0, min(1.0, left / limit)), 3)
            credits = {p for p, _ in self.quota}
        for name, r in self.routes().items():               # no credits figure: the best route of the provider
            p = name.split(':', 1)[0]
            d = out.setdefault(p, {'quota': None, 'down': False, 'cooldown_s': 0})
            if r['quota'] is not None and p not in credits:
                d['quota'] = max(d['quota'] or 0.0, r['quota'])
        return out


LIMITER = Limiter()                                  # one per process: the viewer's server of the room


def _prova():
    """a fake clock and fake calls: the window, the in-flight cap, the single probe, Retry-After, 10 attempts.
    python -m spawn.limiter"""
    t = [1000.0]
    lim = Limiter(sleep=lambda s: None, clock=lambda: t[0])
    lane = lim._lane('open_router', 'k', 'm')
    assert lim._lane('open_router', 'k', 'other') is lane and lim._lane('groq', 'k', 'a') is not lim._lane('groq', 'k', 'b')
    for _ in range(20):
        lim._admit(lane, None)
        lane.inflight -= 1
    threading.Timer(0.2, lambda: t.__setitem__(0, t[0] + 61)).start()
    lim._admit(lane, None)                               # the 21st waits for the window (the timer moves the clock)
    assert t[0] >= 1061
    lane.inflight -= 1
    calls = []

    def flaky():
        calls.append(t[0])
        if len(calls) < 3:
            raise errors.ProviderError('rate_limit', 429, 0.0 if len(calls) == 1 else 5.0, 'x')
        return 'ok'

    def tick():
        while not done.is_set():
            t[0] += 1
            time.sleep(0.005)
    done = threading.Event()
    threading.Thread(target=tick, daemon=True).start()
    assert lim.run('groq', 'k', 'm1', flaky) == 'ok' and len(calls) == 3
    assert calls[2] - calls[1] >= 5, calls             # Retry-After 5 s respected
    try:
        lim.run('groq', 'k', 'm2', lambda: (_ for _ in ()).throw(errors.ProviderError('payment', 402)))
        raise AssertionError('402 retried')
    except errors.ProviderError as e:
        assert e.kind == 'payment' and lim._lane('groq', 'k', 'm2').failures == 0
    n = []

    def always():
        n.append(1)
        raise errors.ProviderError('overloaded', 503)
    try:
        lim.run('groq', 'k', 'm3', always)
        raise AssertionError('no error after 10 attempts')
    except errors.ProviderError as e:
        assert e.kind == 'overloaded' and len(n) == ATTEMPTS
    lane6 = lim._lane('mistral', 'k6', 'a')               # another request's 402 or late success does not close an open episode
    lane6.failures, lane6.ready_at, lane6.inflight = 1, t[0] + 100, 2
    lim._done(lane6, False, None, neutral=True)
    lim._done(lane6, False, None)
    assert lane6.failures == 1 and lane6.inflight == 0
    snap = lim.snapshot()
    assert snap['groq']['down'] is True and 'k' not in str(snap).replace('groq', '')
    # three roles on one key: during an episode only one probe goes, the others wait for its answer
    lane4 = lim._lane('nvidia_nim', 'shared', 'x')
    lane4.failures, lane4.ready_at = 1, t[0]
    seen, gate = [], threading.Event()

    def role(i):
        def call():
            seen.append(i)
            gate.wait(2)
            return i
        return lim.run('nvidia_nim', 'shared', 'x', call)
    ths = [threading.Thread(target=role, args=(i,)) for i in range(3)]
    [x.start() for x in ths]
    time.sleep(0.3)
    assert len(seen) == 1, seen                         # one probe in flight, two waiting
    gate.set()
    [x.join(5) for x in ths]
    assert sorted(seen) == [0, 1, 2] and lane4.failures == 0
    stop = threading.Event()
    lane5 = lim._lane('cohere', 'k', 'x')
    lane5.failures, lane5.ready_at = 1, t[0] + 10 ** 6
    threading.Timer(0.2, stop.set).start()
    try:
        lim.run('cohere', 'k', 'x', lambda: 1, stop)
        raise AssertionError('stop ignored')
    except errors.ProviderError:
        pass
    lim.note_quota('open_router', 'k', 30, 50)
    assert lim.snapshot()['open_router']['quota'] == 0.6
    # quota per route, from the headers of three providers
    import json
    now = time.time()
    assert abs(reset_seconds('1m26.4s') - 86.4) < 1e-9 and reset_seconds('120ms') == 0.12 and reset_seconds('7.66') == 7.66
    assert abs(reset_seconds(str(int((now + 30) * 1000)), now) - 30) < 0.01 and abs(reset_seconds(str(now + 45), now) - 45) < 0.01
    assert 29 <= reset_seconds(email.utils.formatdate(now + 30, usegmt=True)) <= 31 and reset_seconds('soon') is None
    q = Limiter(clock=lambda: t[0])
    q.observe('groq', 'g', 'llama', {'x-ratelimit-limit-requests': '1000', 'x-ratelimit-remaining-requests': '999',
                                     'x-ratelimit-reset-requests': '1m26.4s', 'x-ratelimit-limit-tokens': '6000',
                                     'x-ratelimit-remaining-tokens': '1500', 'x-ratelimit-reset-tokens': '7.66s', 'content-type': 'x'})
    r = q.route('groq', 'llama')
    assert r['quota'] == 0.25 and r['remaining_requests'] == 999 and r['limit_tokens'] == 6000 and abs(r['reset_s'] - 7.7) < 0.11, r
    assert q.route('groq', 'other')['quota'] is None                          # Groq counts per model
    q.observe('cerebras', 'c', 'qwen', {'X-RateLimit-Limit-Requests-Day': '14400', 'X-RateLimit-Remaining-Requests-Day': '7200',
                                        'X-RateLimit-Reset-Requests-Day': '33011.38', 'x-ratelimit-limit-tokens-minute': '60000',
                                        'x-ratelimit-remaining-tokens-minute': '59000'})
    r = q.route('cerebras', 'qwen')
    assert r['quota'] == 0.5 and r['remaining_requests'] == 7200 and r['remaining_tokens'] == 59000, r
    q.observe('open_router', 'o', 'a:free', {'X-RateLimit-Limit': '20', 'X-RateLimit-Remaining': '5',
                                             'X-RateLimit-Reset': str(int((time.time() + 30) * 1000))})
    r = q.route('open_router', 'b:free')                                        # OpenRouter counts per key: every model of it
    assert r['quota'] == 0.25 and 29 <= r['reset_s'] <= 31, r
    t[0] += 40
    assert q.route('open_router', 'a:free')['quota'] == 1.0                     # past its reset the window is full again
    q.note_daily('open_router', 'o', 50)
    for _ in range(10):
        q.run('open_router', 'o', 'a:free', lambda: 'ok')
    r = q.route('open_router', 'a:free')
    assert r['remaining_requests'] == 40 and r['quota'] == 0.8, r
    try:
        q.run('groq', 'g', 'llama', lambda: (_ for _ in ()).throw(errors.ProviderError('quota', 429)))
    except errors.ProviderError:
        pass
    assert q.route('groq', 'llama')['recent_429'] == 1 and set(q.routes()) >= {'groq:llama', 'cerebras:qwen', 'open_router:a:free'}
    t[0] += RECENT + 1
    assert q.route('groq', 'llama')['recent_429'] == 0
    assert q.snapshot()['cerebras']['quota'] == 0.5 and fingerprint('o') not in json.dumps([q.routes(), q.snapshot()])
    done.set()
    print('limiter ok')


if __name__ == '__main__':
    _prova()
