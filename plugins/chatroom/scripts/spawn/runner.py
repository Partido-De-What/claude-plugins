"""The roles of the spawn mode: agents of the room that run on external models, one thread each inside the room's viewer
server (chat.py serve), all through the one limiter of PORTE (spawn.limiter).

A role is a name, a mission, its tools, and its current road: a model (canonical id of the catalog) on one host
(provider and model id). The model can change; the role, its history and its notes stay. ROOM/spawn/roles.json holds the
roles, ROOM/spawn/history-NAME.json the conversation of each, so a restart of serve picks them up where they were.

One step: spawn.providers.complete() with the room's own tools (the MCP tools of chat.py, run as the role with
mcp_call, so a role posts, waits, takes tasks and writes its notebook like any agent; shell only for the roles the user
gives it, in a folder of their own, through RTK). An answer without a tool call ends the turn: the role waits for the
room (chat_wait) and goes on with what arrives. The system prompt is the same bytes on every call and the session id is
fixed per road, so the provider's cache works.

In this order, when things go wrong:
1. the context passes 80% of the road's window (estimated with tiktoken) or the provider says it is full: the role
   writes its handover (task, decisions, open points), it goes to its notebook, and the history starts again from it;
2. quota over, model gone from the host, or a host that keeps failing after the limiter's 10 attempts: the same model on
   another host of its card (the cache is lost, the reasoning does not cross: the adapter keeps only text and tool calls);
3. no host left: the role is "without tokens" (state notokens), its name blinks in the viewer and the Hangar, and a
   message tags the user, who picks the replacement on the Sostituisci card (replace()). Never a different model by itself.
401/402/403 stop the role with a message (the key or the account needs the user)."""
import copy
import json
import os
import re
import threading
import time
from collections import deque
from pathlib import Path

from spawn import errors

CTX_SHARE, DEFAULT_CTX, MAX_TOKENS, WAIT = 0.8, 32768, 4096, 540
NAME = re.compile(r'[A-Z][A-Z0-9_]{1,19}\Z')
STATES = ('service', 'switch', 'notokens', 'stopped')
SHELL = {'type': 'function', 'function': {'name': 'shell', 'description': 'Run a shell command in your own folder (120 s at most). '
                                                                          'Long output comes back compressed: chat_expand gives it whole.',
                                         'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}},
                                                        'required': ['command']}}}
PROMPT = '''You are {name}, a role in the chat room "{title}", working with: {others}. Your mission: {mission}

You act only through your tools. chat_read reads the room (focus: what concerns you in full, the rest as a digest),
chat_wait waits for someone (up to 540 s), chat_post writes (a message; status=true with your percentage "60%";
idle=true once when you wait for someone; reply=N answers #N), board and task are the shared plan (take a task before
working on it, close it with a proof that names an artifact), notebook keeps notes that survive when your context is
renewed, chat_expand gives back a text marked ⟨compressed: ID⟩.{shell}

Rules: short messages, tag who must answer (@NAME), answer the user first, every fact with its source (#n, file:line,
command and exit code), a vote is the first line of its message ("VOTE v2: yes, checked <what>"). Do not stop: when you
have nothing to do, chat_wait.

STYLE: caveman ultra. Terse like a smart caveman: no articles, filler, pleasantries or hedging; fragments are fine; one
word when one word is enough; every fact said once. Keep all technical substance: exact numbers, names, errors.

Write in {language}.'''
START = 'Start: read the room with chat_read, then do your mission.'
HANDOVER = ('Your context is almost full and will be renewed. Write your handover for yourself, at most 300 words: your '
            'task and where it is, the decisions taken (with #n), the open points, the files and commands that matter. '
            'Text only, no tool.')
TEXT = {  # shortcut: the room's own words for the notices, until the i18n pass of F8 moves them to locales (spawn.role.*)
    'en': {'switch': '🚪 {name}: change of door {old} → {new} (the provider cache is lost)',
           'notokens': '📟 {name} has no tokens left: every host of {model} is used up. @{user} pick the replacement (Sostituisci card).',
           'stopped': '⛔ {name} stopped: {kind} on {provider}. @{user} the key or the account needs you.',
           'replaced': '🔁 {name} now runs on {model} ({provider}).',
           'handover': '🧳 {name}: context renewed from its handover.'},
    'it': {'switch': '🚪 {name}: cambio porta {old} → {new} (la cache del provider si perde)',
           'notokens': '📟 {name} senza token: tutte le strade di {model} sono esaurite. @{user} scegli il sostituto (scheda Sostituisci).',
           'stopped': '⛔ {name} fermo: {kind} su {provider}. @{user} la chiave o l\'account chiedono te.',
           'replaced': '🔁 {name} ora gira su {model} ({provider}).',
           'handover': '🧳 {name}: contesto rinnovato dalle sue consegne.'}}
CAVEMAN_FACTOR = 1.5     # shortcut: caveman ultra cuts about 60% of an answer's tokens, so a role that wrote N saved ~1.5 N; an estimate, said so in /spawn.json
RUNNERS = {}                                             # (room folder, name) -> Runner
_RTK_SAVED = {}                                          # room folder -> (when, tokens): `rtk gain` asked at most every 30 s
RTK_RECENT = deque(maxlen=200)                           # when the roles' shell commands went through RTK (the Hangar's funnel)
_lock = threading.Lock()


# ------------------------------------------------------------------ the roles' file
def _dir(room):
    d = Path(room.dir) / 'spawn'
    d.mkdir(exist_ok=True)
    return d


def roles(room):
    try:
        return json.loads((_dir(room) / 'roles.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _write(path, data):
    tmp = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def update(room, name, **changes):
    """change one role under the room's lock; returns it"""
    def run():
        rs = roles(room)
        rs[name].update(changes)
        _write(_dir(room) / 'roles.json', rs)
        return rs[name]
    return room.locked(run)


def _history_path(room, name):
    return _dir(room) / f'history-{name}.json'


def _say(room, key, **f):
    c = room.config()
    lang = 'it' if c.get('lang') == 'it' else 'en'
    return TEXT[lang][key].format(user=c.get('user_name', 'USER'), **f)


# ------------------------------------------------------------------ catalog and tokens
def routes_of(canonical, cat=None):
    """the hosts of a model in the catalog, free ones with tools first, the fastest ping first"""
    from spawn.catalog import catalog
    cat = cat or catalog.load()
    m = next((m for m in cat['models'] if m['canonical'] == canonical), None)
    rs = [r for r in (m or {}).get('routes', []) if r.get('free') and r.get('tools') is not False]
    return sorted(rs, key=lambda r: (not (r.get('ping') or {}).get('ok'), (r.get('ping') or {}).get('ms') or 10 ** 6))


_ENC = []


def tokens(messages):
    """an estimate of the tokens of a history: tiktoken's cl100k when it loads, else 4 characters a token"""
    text = json.dumps(messages, ensure_ascii=False)
    if not _ENC:
        try:
            import tiktoken
            _ENC.append(tiktoken.get_encoding('cl100k_base'))
        except Exception:
            _ENC.append(None)
    return len(_ENC[0].encode(text, disallowed_special=())) if _ENC[0] else len(text) // 4


# ------------------------------------------------------------------ the tools
def research_room(room):
    return room is not None and (Path(room.dir) / 'research' / 'contract.json').is_file()


def tool_defs(role, room=None):
    """the room's MCP tools as OpenAI tools (without room and as: the runner fills them), plus shell when given. In a
    research room (mode C) also the research kernel's tool, whose roles the kernel enforces"""
    import chat
    out = []
    for t in chat.MCP_TOOLS:
        if t['name'] == 'research' and not research_room(room):
            continue
        params = copy.deepcopy(t['inputSchema'])
        for k in ('room', 'as'):
            params['properties'].pop(k, None)
        out.append({'type': 'function', 'function': {'name': t['name'], 'description': t['description'], 'parameters': params}})
    return out + ([SHELL] if 'shell' in role.get('tools', []) else [])


def run_shell(room, role, command):
    """a command of a role that has the shell, in ROOM/spawn/work-NAME, through RTK when it is there"""
    import chat
    from activity import rtk_path
    work = _dir(room) / f"work-{role['name']}"
    work.mkdir(exist_ok=True)
    exe = rtk_path()
    if exe:
        code, out = chat.run_tree(f'"{exe}" rewrite {json.dumps(command)}', str(work), 10)
        out = out.strip().splitlines()[-1] if out.strip() else ''
        if code in (0, 3) and out and out != command:     # the rewrite calls rtk by name: every call gets the full path
            command = re.sub(r'(^|&&|\|\||;|\|)(\s*)rtk ', lambda m: f'{m[1]}{m[2]}"{exe}" ', out)
            RTK_RECENT.append(time.time())
    code, out = chat.run_tree(command, str(work), 120)
    out = f'exit {code if code is not None else "timeout (120 s)"}\n{out}'
    try:
        import compress
        return compress.shrink(room, out)
    except Exception:
        return out[-20000:]


def run_tool(room, role, call, stop):
    import chat
    name = call['function']['name']
    try:
        args = json.loads(call['function']['arguments'] or '{}')
    except ValueError:
        return 'error: the arguments are not JSON'
    if name == 'shell' and 'shell' in role.get('tools', []):
        return run_shell(room, role, str(args.get('command', '')))
    if not isinstance(args, dict) or name not in {t['name'] for t in chat.MCP_TOOLS} or (name == 'research' and not research_room(room)):
        return f'error: no tool {name}'
    if name == 'chat_wait':
        args['timeout'] = min(int(args.get('timeout') or 100), WAIT)
    text, _ = chat.mcp_call(room, role['name'], name, {k: v for k, v in args.items() if k not in ('room', 'as')}, stop)
    return text or ('stopped' if stop.is_set() else 'ok')


# ------------------------------------------------------------------ the loop
class Runner(threading.Thread):
    def __init__(self, room, name, complete=None):
        super().__init__(daemon=True, name=f'role-{name}')
        self.room, self.name, self.stop, self.wake = room, name, threading.Event(), threading.Event()
        self.complete = complete                          # tests give a fake one

    def _complete(self, *a, **kw):
        if self.complete:
            return self.complete(*a, **kw)
        from spawn.providers import complete
        return complete(*a, **kw)

    def system(self, role):
        c = self.room.config()
        others = ', '.join(n for n in c.get('participants', []) if n != self.name) or '-'
        return PROMPT.format(name=self.name, title=c.get('title') or c.get('topic', ''), others=others,
                             mission=role.get('mission', ''), language='Italian' if c.get('lang') == 'it' else 'English',
                             shell=('\nshell runs a command in your own folder.' if 'shell' in role.get('tools', []) else ''))

    def history(self, role):
        try:
            h = json.loads(_history_path(self.room, self.name).read_text(encoding='utf-8'))
            if isinstance(h, list) and h:
                h[0] = {'role': 'system', 'content': self.system(role)}
                return h
        except (OSError, ValueError):
            pass
        return [{'role': 'system', 'content': self.system(role)}, {'role': 'user', 'content': START}]

    def save(self, h):
        _write(_history_path(self.room, self.name), h)

    def call(self, role, h, tools=True, max_tokens=None):
        r = role['route']
        return self._complete(r['adapter'], r['model_id'], h, tools=tool_defs(role, self.room) if tools else None,
                              max_tokens=max_tokens or role.get('max_tokens') or MAX_TOKENS, effort=role.get('effort'),
                              session_id=f"{self.name}-{r['adapter']}", stop=self.stop)

    def run(self):
        while not self.stop.is_set():
            role = roles(self.room).get(self.name)
            if not role or role.get('state') in ('notokens', 'stopped'):
                self.wake.wait(5)
                self.wake.clear()
                continue
            try:
                self.step(role)
            except errors.ProviderError as e:
                self.fail(role, e)
            except Exception as e:                        # a bug must not kill the role silently: it stops, the user sees why
                update(self.room, self.name, state='stopped', error=f'{type(e).__name__}: {str(e)[:200]}')

    def step(self, role):
        h = self.history(role)
        if tokens(h) > CTX_SHARE * (role['route'].get('ctx') or DEFAULT_CTX):
            h = self.handover(role, h)
        r = self.call(role, h)
        used = role.get('usage') or {}
        u = r.get('usage') or {}
        update(self.room, self.name, state='service', usage={'in': used.get('in', 0) + int(u.get('prompt_tokens') or 0),
                                                             'out': used.get('out', 0) + int(u.get('completion_tokens') or 0),
                                                             'cost': used.get('cost', 0) + float(u.get('cost') or 0)})
        h.append(r['message'])
        if r['tool_calls']:
            for c in r['tool_calls']:
                h.append({'role': 'tool', 'tool_call_id': c['id'], 'content': run_tool(self.room, role, c, self.stop)})
        else:                                             # the turn is over: wait for the room, then go on with it
            import chat
            text, _ = chat.mcp_call(self.room, self.name, 'chat_wait', {'timeout': WAIT}, self.stop)
            h.append({'role': 'user', 'content': text or 'nothing new'})
        self.save(h)

    def handover(self, role, h, full=False):
        """the role writes its handover, which goes to its notebook and starts the new history; full: the provider said
        the context is full, so only the last messages are given to write it"""
        import chat
        short = [h[0]] + h[-12:] if full or tokens(h) > (role['route'].get('ctx') or DEFAULT_CTX) * 0.95 else h
        notes = self.call(role, short + [{'role': 'user', 'content': HANDOVER}], tools=False, max_tokens=1500)['text'].strip()
        chat.mcp_call(self.room, self.name, 'notebook', {'text': 'handover: ' + ' '.join(notes.split())[:1500]})
        update(self.room, self.name, handover=notes)
        self.room.append(self.name, _say(self.room, 'handover', name=self.name), 'board')
        h = [h[0], {'role': 'user', 'content': f'{START}\n\nYour handover from the context before:\n{notes}'}]
        self.save(h)
        return h

    def fail(self, role, e):
        route = role['route']
        if e.action == 'handover':
            self.handover(role, self.history(role), full=True)
            return
        if e.action in ('repair', 'resume'):              # a tool call or an answer that could not be mended: ask again
            h = self.history(role)
            h.append({'role': 'user', 'content': 'Your last answer was cut or its tool call arguments were broken: answer again.'})
            self.save(h)
            return
        if e.action == 'stop':
            update(self.room, self.name, state='stopped', error=e.kind)
            self.room.append(self.name, _say(self.room, 'stopped', name=self.name, kind=e.kind, provider=route['adapter']))
            return
        tried = role.get('tried', []) + [f"{route['adapter']}:{route['model_id']}"]   # next_host, or retries used up
        from spawn import keys
        nxt = next((r for r in routes_of(role['canonical']) if f"{r['adapter']}:{r['model_id']}" not in tried
                    and keys.load(r['adapter'])), None)
        if nxt:
            update(self.room, self.name, state='service', route=nxt, tried=tried)
            self.room.append(self.name, _say(self.room, 'switch', name=self.name, old=route['adapter'], new=nxt['adapter']), 'board')
        else:
            update(self.room, self.name, state='notokens', tried=tried)
            self.room.append(self.name, _say(self.room, 'notokens', name=self.name, model=role['canonical']))
            try:                                          # the Sostituisci card in the chat at once (VETRINA's cards_spawn.py)
                from spawn import cards_spawn
                cards_spawn.post_replace(self.room, self.name)
            except Exception:                              # no card is no reason to stop the role: the message above says it
                pass


# ------------------------------------------------------------------ what the cards and serve call
def start(room, name, complete=None):
    with _lock:
        key = (str(Path(room.dir).resolve()), name)
        r = RUNNERS.get(key)
        if r and r.is_alive():
            r.wake.set()
            return r
        r = RUNNERS[key] = Runner(room, name, complete)
        r.start()
        return r


def start_all(room):
    """serve's start: every role of the room runs again (the ones without tokens wait for their replacement)"""
    for name in roles(room):
        start(room, name)


def stop(room, name):
    r = RUNNERS.get((str(Path(room.dir).resolve()), name))
    if r:
        r.stop.set()
        r.wake.set()


def create(room, name, mission, canonical, route, tools=(), effort=None, profile=None, complete=None):
    """a new role in the room: a participant with its desk, and its thread. route: a host of the catalog
    ({adapter, model_id, ctx, ...}); tools: 'shell' only when the user gives it (D1)"""
    if not NAME.match(name or ''):
        raise ValueError('a role name is 2-20 capitals, digits or _, starting with a letter')
    if not route or not route.get('adapter') or not route.get('model_id'):
        raise ValueError('a role needs a host: adapter and model_id')
    import importlib.util
    if room.config().get('mode') == 'spawn' and importlib.util.find_spec('headroom') is None:
        raise ValueError('a spawn room needs Headroom: install it from the Prepara spawn card first')

    def add(c):
        if name in c.get('participants', []) or name in {c.get('user_name'), *c.get('self_names', [])}:
            raise ValueError(f'{name} is already in the room')
        c.setdefault('participants', []).append(name)
        c.setdefault('profiles', {}).setdefault(name, {}).update({'emoji': '🤖', 'color': '#16a085', **(profile or {}),
                                                                  'role': mission[:120], 'model': route['model_id'][-24:]})
    room.edit_config(add)

    def write():
        rs = roles(room)
        rs[name] = {'name': name, 'mission': mission[:2000], 'canonical': canonical, 'route': route,
                    'tools': [t for t in tools if t == 'shell'], 'effort': effort, 'state': 'service', 'tried': [], 'usage': {}}
        _write(_dir(room) / 'roles.json', rs)
    room.locked(write)
    return start(room, name, complete)


def replace(room, name, canonical, route):
    """the Sostituisci card: the role goes on with another model, chosen by the user; its history stays (what the new
    host cannot read is left out by the adapter), its tried hosts start again"""
    role = update(room, name, canonical=canonical, route=route, tried=[], state='service', error=None)
    room.update_config(profiles={name: {'model': route['model_id'][-24:]}})
    room.append(name, _say(room, 'replaced', name=name, model=canonical, provider=route['adapter']), 'board')
    start(room, name)
    return role


def rtk_saved(room):
    """the tokens RTK saved on the commands the roles ran in their folders (rtk gain -p counts a folder and those inside)"""
    from activity import rtk_path
    key, now = str(Path(room.dir).resolve()), time.time()
    hit = _RTK_SAVED.get(key)
    if hit and now - hit[0] < 30:
        return hit[1]
    saved, exe = 0, rtk_path()
    if exe:
        import subprocess
        try:
            r = subprocess.run([exe, 'gain', '-p', '-f', 'json'], cwd=_dir(room), capture_output=True, timeout=10, stdin=subprocess.DEVNULL)
            saved = int(json.loads(r.stdout.decode('utf-8', 'replace') or '{}').get('summary', {}).get('total_saved') or 0)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    _RTK_SAVED[key] = (now, saved)
    return saved


def snapshot(room):
    """what GET /spawn.json gives the Hangar (contract #104 #134 of the 0.13 room)"""
    from spawn.catalog import catalog
    from spawn.limiter import LIMITER
    from spawn.providers import catalog as providers
    cat, lim = catalog.load(), LIMITER.snapshot()
    cards = {m['canonical']: m for m in cat['models']}
    out = []
    for r in roles(room).values():
        m = cards.get(r.get('canonical')) or {}
        st = m.get('strengths') or []
        out.append({'name': r['name'], 'provider': r['route']['adapter'], 'model': r.get('canonical') or r['route']['model_id'],
                    'host': r['route']['adapter'], 'state': r.get('state', 'service'),
                    'trophy': next((s['bench'] for s in st if s.get('trophy')), None), 'aa': m.get('aa'),
                    'strong': [s['bench'] for s in st[:3]]})     # strengths come in order already: trophies, then strength (strengths.py)
    used = {r['provider'] for r in out} | set(lim)
    provs = [{'id': p, 'name': providers.ALL.get(p, {}).get('name', p), 'quota': (lim.get(p) or {}).get('quota'),
              'down': bool((lim.get(p) or {}).get('down'))} for p in sorted(used)]
    try:
        import compress
        cs = compress.stats(room)
    except Exception:
        cs = {'saved': 0, 'recent': 0}
    now = time.time()
    out_tokens = sum(int((r.get('usage') or {}).get('out', 0)) for r in roles(room).values())
    return {'providers': provs, 'roles': out, 'saved': {'headroom': cs['saved'], 'rtk': rtk_saved(room),
                                                         'caveman': int(out_tokens * CAVEMAN_FACTOR)}, 'caveman_estimated': True,
            'press': cs['recent'], 'funnel': sum(1 for t in RTK_RECENT if now - t < 10)}


def _prova():
    """a room in a temporary HOME and a fake provider: a role posts, waits, changes host, runs out of tokens, renews its
    context, is replaced, is stopped by a 402. python -m spawn.runner (from scripts/)"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['USERPROFILE'] = os.environ['HOME'] = tmp
        import chat
        from spawn import keys
        from spawn.catalog import catalog
        room = chat.Room(Path(tmp) / 'room')
        room.dir.mkdir()
        room.save_config({'topic': 't', 'title': 'Hangar', 'participants': ['A'], 'lang': 'it', 'user_name': 'Adrian',
                          'self_names': ['LEAD'], 'heartbeat': 120})
        r1 = {'adapter': 'open_router', 'model_id': 'x/m:free', 'ctx': 100000, 'free': True, 'tools': True, 'ping': {'ok': True, 'ms': 5}}
        r2 = {'adapter': 'kilo', 'model_id': 'x/m', 'ctx': 100000, 'free': True, 'tools': True, 'ping': {'ok': True, 'ms': 9}}
        catalog.save({'updated': 1, 'providers': {}, 'models': [{'canonical': 'm', 'name': 'M', 'routes': [r2, r1], 'aa': 40.0,
                      'strengths': [{'bench': 'swe-bench', 'rank': 1, 'trophy': True}, {'bench': 'gpqa', 'rank': 3}]}]})
        real_load, keys.load = keys.load, (lambda p: {'key': 'k', 'extra': None})
        script, seen, box = [], [], {}

        def fake(provider, model, msgs, tools=None, **kw):
            seen.append((provider, model, copy.deepcopy(msgs), tools, kw))
            step = script.pop(0)
            if isinstance(step, Exception):
                raise step
            if step == 'stop':
                (box.get('runner') or RUNNERS[(str(room.dir.resolve()), 'ARCH')]).stop.set()   # the thread may ask before create returns
                step = {'text': 'fatto'}
            calls = step.get('calls', [])
            return {'message': {'role': 'assistant', 'content': step.get('text'), **({'tool_calls': calls} if calls else {})},
                    'text': step.get('text', ''), 'reasoning': '', 'tool_calls': calls, 'finish': 'stop',
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 3}}
        try:
            for bad in ('ab', 'A B', ''):
                try:
                    create(room, bad, 'x', 'm', r1)
                    raise AssertionError(bad)
                except ValueError:
                    pass
            post = {'id': 'c1', 'type': 'function', 'function': {'name': 'chat_post', 'arguments': '{"text": "ciao @A"}'}}
            script[:] = [{'calls': [post]}, 'stop']
            box['runner'] = runner = create(room, 'ARCH', 'progetta', 'm', r1, profile={'emoji': '🛠'}, complete=fake)
            runner.join(15)
            assert not runner.is_alive(), 'the role did not stop'
            posted = [m for m in room.messages() if m['from'] == 'ARCH']
            assert posted and posted[0]['text'] == 'ciao @A', room.messages()
            assert 'ARCH' in room.config()['participants'] and room.config()['profiles']['ARCH']['model'] == 'x/m:free'
            p, m, msgs, tools, kw = seen[0]
            assert p == 'open_router' and msgs[0]['role'] == 'system' and 'caveman ultra' in msgs[0]['content'] and 'Italian' in msgs[0]['content']
            names = {t['function']['name'] for t in tools}
            assert kw['session_id'] == 'ARCH-open_router' and names >= {'chat_post', 'chat_wait', 'board', 'task'} and not names & {'shell', 'research'}
            assert seen[1][2][0] == msgs[0] and seen[1][2][-1]['role'] == 'tool'          # the same system bytes, the tool's answer carried
            assert roles(room)['ARCH']['usage'] == {'in': 20, 'out': 6, 'cost': 0.0}, roles(room)['ARCH']['usage']
            r = Runner(room, 'ARCH', fake)
            r.fail(roles(room)['ARCH'], errors.ProviderError('quota', 429))                # quota: the same model on another host
            role = roles(room)['ARCH']
            assert role['route']['adapter'] == 'kilo' and role['state'] == 'service' and 'cambio porta open_router → kilo' in room.messages()[-1]['text']
            r.fail(role, errors.ProviderError('rate_limit', 429))                           # the limiter gave up: no host left
            last = [m for m in room.messages() if m['from'] == 'ARCH' and not m.get('kind')][-1]
            assert any(m.get('kind') == 'card' for m in room.messages()) or not (Path(__file__).parent / 'cards_spawn.py').is_file()
            assert roles(room)['ARCH']['state'] == 'notokens' and '@Adrian' in last['text'] and 'senza token' in last['text'] and not last.get('kind')
            snap = snapshot(room)['roles'][0]
            assert snap == {'name': 'ARCH', 'provider': 'kilo', 'model': 'm', 'host': 'kilo', 'state': 'notokens',
                            'trophy': 'swe-bench', 'aa': 40.0, 'strong': ['swe-bench', 'gpqa']}, snap
            replace(room, 'ARCH', 'm', r1)
            assert roles(room)['ARCH']['state'] == 'service' and 'ora gira su m' in room.messages()[-1]['text']
            stop(room, 'ARCH')
            role = update(room, 'ARCH', route={**r1, 'ctx': 300})                           # a tiny window: the next step renews the context
            box['runner'] = r = Runner(room, 'ARCH', fake)
            script[:] = [{'text': 'task T3 a metà, deciso #4'}, 'stop']
            r.step(role)
            h = json.loads(_history_path(room, 'ARCH').read_text(encoding='utf-8'))
            assert len(h) == 4 and 'task T3 a metà' in h[1]['content'] and seen[-2][3] is None, h   # the handover is asked without tools
            assert 'handover: task T3' in (room.dir / 'notes' / 'ARCH.md').read_text(encoding='utf-8')
            r.fail(roles(room)['ARCH'], errors.ProviderError('payment', 402))
            assert roles(room)['ARCH']['state'] == 'stopped' and '⛔ ARCH fermo: payment' in room.messages()[-1]['text']
            shell_role = {**roles(room)['ARCH'], 'tools': ['shell']}
            assert 'shell' in {t['function']['name'] for t in tool_defs(shell_role)}
            assert 'research' not in {t['function']['name'] for t in tool_defs(shell_role, room)}
            (room.dir / 'research').mkdir()
            (room.dir / 'research' / 'contract.json').write_text('{}', encoding='utf-8')     # mode C: the kernel's tool, its roles enforced by it
            assert 'research' in {t['function']['name'] for t in tool_defs(shell_role, room)}
            out = run_tool(room, shell_role, {'function': {'name': 'shell', 'arguments': json.dumps({'command': 'echo hello'})}}, threading.Event())
            assert out.startswith('exit 0') and 'hello' in out and (room.dir / 'spawn' / 'work-ARCH').is_dir(), out
            no = run_tool(room, roles(room)['ARCH'], {'function': {'name': 'shell', 'arguments': '{"command": "echo x"}'}}, threading.Event())
            assert no.startswith('error'), no                                               # no shell unless the user gave it
            assert 'sk-' not in json.dumps(roles(room))
            s = snapshot(room)
            assert s['saved']['caveman'] == int(roles(room)['ARCH']['usage']['out'] * CAVEMAN_FACTOR) > 0 and s['caveman_estimated'], s
            assert isinstance(s['saved']['rtk'], int) and s['saved']['rtk'] >= 0, s
        finally:
            keys.load = real_load
    print('runner ok')


if __name__ == '__main__':
    _prova()
