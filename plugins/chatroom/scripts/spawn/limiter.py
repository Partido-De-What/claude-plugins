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
whether it is down."""
import hashlib
import random
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

    def _lane(self, provider, key, model):
        rpm, conc, scope = FREE_LIMITS.get(provider, DEFAULT)
        name = (provider, fingerprint(key), model if scope == 'model' else '*')
        return self.lanes.setdefault(name, _Lane(rpm, conc))

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
            try:
                out = fn()
            except Exception as exc:
                err = errors.from_exception(exc) if not isinstance(exc, errors.ProviderError) else exc
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
    done.set()
    print('limiter ok')


if __name__ == '__main__':
    _prova()
