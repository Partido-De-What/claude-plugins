"""What each agent of a room and its lead cost, read from Claude Code's own transcripts: requests, input, cache reads and
writes, output, in input-equivalent tokens (input 1, cache write 1.25 at 5 minutes or 2 at one hour, cache read 0.1,
output 5), the cache rewrites (a write over half of the context after a pause longer than the cache: the waste that was
37% of a night room), and the share of the room's protocol (wait, read, post, statuses, pings) against the work. Each
request is charged to the tool result it digests. Files are read incrementally (offset and totals kept per file), so the
relay can ask every minute. No transcript (Codex, another machine): "n/a"."""
import json
import os
import re
import time
from pathlib import Path

W_IN, W_W5, W_W1, W_READ, W_OUT = 1, 1.25, 2, 0.1, 5
PROTOCOL = re.compile(r'chat\.py["\']?\s+(?:wait|read|post|board|task|notebook|status|check|expand|recap)\b|mcp__chatroom__|^SendMessage$')
_STATE = {}                    # (path, since) -> [offset, totals, seen message ids, last ts, last tool, last context]: a new since starts over


def transcript_of(agent_id=None, session_id=None):
    base = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'projects'
    pattern = f'*/*/subagents/agent-{agent_id}.jsonl' if agent_id else f'*/{session_id}.jsonl'
    return next(iter(base.glob(pattern)), None) if (agent_id or session_id) else None


def _blank():
    return {'requests': 0, 'input': 0, 'read': 0, 'write': 0, 'out': 0, 'eq': 0.0, 'rewrites': 0, 'protocol_eq': 0.0, 'context': 0,
            'compactions': 0}


def scan(path, since=0.0):
    """the totals of one transcript, read from where the last call stopped; lines before `since` (epoch) are skipped"""
    path = Path(path)
    off, tot, seen, last_ts, last_tool, last_ctx = _STATE.get((str(path), since), [0, _blank(), set(), 0.0, '', 0])
    try:
        with open(path, 'rb') as f:
            f.seek(off)
            data = f.read()
    except OSError:
        return None
    end = data.rfind(b'\n') + 1                           # a line being written waits for the next call
    for raw in data[:end].splitlines():
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if since and _ts(d.get('timestamp')) < since:
            continue                                      # before the room's reset (ROOM/cost_since.txt)
        m = d.get('message') or {}
        if d.get('subtype') == 'compact_boundary':
            tot['compactions'] += 1                       # after a few, a summary keeps a tenth of the rules: rotate instead
            continue
        if d.get('type') == 'assistant':
            u, mid = m.get('usage'), m.get('id')
            calls = [c.get('name', '') + ' ' + str((c.get('input') or {}).get('command') or '')[:200]
                     for c in m.get('content') or [] if isinstance(c, dict) and c.get('type') == 'tool_use']
            if not isinstance(u, dict) or mid in seen:
                last_tool = calls[-1] if calls else last_tool
                continue
            seen.add(mid)
            cc = u.get('cache_creation') or {}
            w1 = int(cc.get('ephemeral_1h_input_tokens') or 0)
            w = int(u.get('cache_creation_input_tokens') or 0)
            r, i, o = int(u.get('cache_read_input_tokens') or 0), int(u.get('input_tokens') or 0), int(u.get('output_tokens') or 0)
            eq = i * W_IN + (w - w1) * W_W5 + w1 * W_W1 + r * W_READ + o * W_OUT
            ts = _ts(d.get('timestamp'))
            ctx = i + r + w
            if last_ts and ts - last_ts > (3600 if w1 else 300) and w > ctx / 2:
                tot['rewrites'] += 1                     # it woke after its cache died and wrote the whole context again
            if PROTOCOL.search(last_tool.split(' ', 1)[-1]) or PROTOCOL.search(last_tool.split(' ', 1)[0]):
                tot['protocol_eq'] += eq
            tot['requests'] += 1
            tot['input'] += i
            tot['read'] += r
            tot['write'] += w
            tot['out'] += o
            tot['eq'] += eq
            tot['context'] = ctx
            last_ts = ts or last_ts
            last_tool = calls[-1] if calls else last_tool       # the next request digests this call's result
    _STATE[(str(path), since)] = [off + end, tot, seen, last_ts, last_tool, last_ctx]
    return dict(tot)


def _ts(s):
    try:
        return time.mktime(time.strptime(str(s)[:19], '%Y-%m-%dT%H:%M:%S')) if s else 0.0
    except ValueError:
        return 0.0


def room_costs(room):
    """{name: totals or None} for the roster's agents and the lead's session, counted from ROOM/cost_since.txt if it exists"""
    try:                                              # an ISO time in UTC, as the transcripts write it: the counters start there
        since = _ts((room.dir / 'cost_since.txt').read_text(encoding='utf-8').strip())
    except OSError:
        since = 0.0
    out = {}
    for name, aid in room.roster().items():
        p = transcript_of(agent_id=aid) if re.fullmatch(r'[0-9a-z]{8,40}', str(aid)) else None
        out[name] = scan(p, since) if p else None
    try:
        sessions = json.loads((room.dir / 'sessions.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        sessions = {}
    for sid, name in sessions.items():
        if name in room.config().get('self_names', []):
            p = transcript_of(session_id=sid)
            out[name] = scan(p, since) if p else None
    return out


def table(costs):
    """the lines of chat.py cost"""
    rows = [f"{'who':12} {'requests':>8} {'eq tokens':>11} {'out':>8} {'rewrites':>8} {'protocol':>8} {'context':>8}"]
    total = 0.0
    for name, t in sorted(costs.items(), key=lambda kv: -(kv[1] or {}).get('eq', 0)):
        if not t:
            rows.append(f'{name:12} n/a')
            continue
        total += t['eq']
        rows.append(f"{name:12} {t['requests']:>8} {t['eq'] / 1e6:>10.2f}M {t['out'] / 1e3:>7.0f}k {t['rewrites']:>8} "
                    f"{100 * t['protocol_eq'] / t['eq'] if t['eq'] else 0:>7.0f}% {t['context'] / 1e3:>7.0f}k")
    rows.append(f"{'total':12} {'':>8} {total / 1e6:>10.2f}M")
    return rows


def checks(costs):
    """[(key, name, kind, value)] for the lead: cache rewrites, and the protocol over half of an agent's cost"""
    out = []
    for name, t in costs.items():
        if not t or t['requests'] < 20:
            continue
        if t['rewrites'] >= 3:
            out.append((f'rewrites:{name}:{t["rewrites"] // 3}', name, 'rewrites', t['rewrites']))
        if t.get('compactions', 0) >= 2:
            out.append((f'compactions:{name}:{t["compactions"]}', name, 'compactions', t['compactions']))
        share = t['protocol_eq'] / t['eq'] if t['eq'] else 0
        if share > 0.5:
            out.append((f'protocol:{name}:{int(share * 10)}', name, 'protocol', round(100 * share)))
    return out


def _prova():
    import tempfile
    d = Path(tempfile.mkdtemp(prefix='cost_')) / 't.jsonl'
    lines = []
    def msg(mid, ts, i, r, w, w1, o, tool=None):
        content = [{'type': 'tool_use', 'name': 'Bash', 'input': {'command': tool}}] if tool else []
        return json.dumps({'type': 'assistant', 'timestamp': ts, 'message': {'id': mid, 'content': content, 'usage': {
            'input_tokens': i, 'cache_read_input_tokens': r, 'cache_creation_input_tokens': w,
            'cache_creation': {'ephemeral_1h_input_tokens': w1}, 'output_tokens': o}}})
    lines.append(msg('m1', '2026-10-30T10:00:00', 2, 0, 50000, 0, 100, 'python chat.py wait --focus --as A'))
    lines.append(msg('m1', '2026-10-30T10:00:00', 2, 0, 50000, 0, 100))           # the same message again: counted once
    lines.append(msg('m2', '2026-10-30T10:00:30', 2, 50000, 1000, 0, 100, 'pytest -q'))
    lines.append(msg('m3', '2026-10-30T10:10:00', 2, 0, 52000, 0, 100))           # after 9.5 minutes: the cache died
    d.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    t = scan(d)
    assert t['requests'] == 3 and t['rewrites'] == 1, t
    assert abs(t['eq'] - (2 + 50000 * 1.25 + 500 + 2 + 5000 + 1250 + 500 + 2 + 52000 * 1.25 + 500)) < 1, t['eq']
    assert t['protocol_eq'] > 0 and t['protocol_eq'] < t['eq']                     # m2 digests the wait: protocol
    with open(d, 'a', encoding='utf-8') as f:
        f.write(msg('m4', '2026-10-30T10:10:10', 2, 52000, 10, 0, 10) + '\n')
    assert scan(d)['requests'] == 4                                               # incremental
    _STATE.clear()
    t = scan(d, _ts('2026-10-30T10:05:00'))                                       # reset at 10:05: only m3 and m4
    assert t['requests'] == 2 and t['rewrites'] == 0, t
    print('cost prova ok')


if __name__ == '__main__':
    _prova()
