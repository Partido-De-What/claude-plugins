"""The skill workshop of the room: which skills exist on this computer, which agent has which, and the actions of the panel
(advise a skill in the chat, search for skills, add a folder). One source for the chat panel and the 3D office:
GET /skills.json -> index(room, ...), POST /skills/do -> do(room, body, ...) (chat.py routes both).

Only the frontmatter of a SKILL.md is read (name, description), never the body: the point of 0.18 is to spend fewer
tokens. Read only: ~/.claude is never written. What the panel adds lives in ROOM/skills.json (roots, advices,
requests); nothing is installed or downloaded without `confirm`, and a download goes to D: only.

Skill id: "<origin>:<plugin|->:<name>", origin in user | project | plugin | added."""
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections import Counter
from pathlib import Path

import layers
from i18n import say

ORIGINS = ('user', 'project', 'plugin', 'account', 'builtin', 'added')
FRONT_MAX, BRIEF_MAX, DESC_MAX, CARDS_MAX = 4096, 140, 600, 8
SEARCH_NAME = 'SKILLFIND'                                  # the temporary searcher the lead spawns when the room has none
DOWNLOADS = 'D:/skills-download'                           # shortcut: fixed D: folder (CHATROOM_SKILLS_DIR overrides), a setting if more is needed
REPO = re.compile(r'https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?\Z')
_front_cache, _used, _paths = {}, {}, {}                   # path -> (mtime, size, fields); transcript path -> [offset, Counter, ids seen]; agent id -> transcript


def claude_dir():
    return layers.claude_dir()


def front(text):
    """the top-level keys of a ---frontmatter--- block as text: a plain or quoted value, a folded/literal block (> |) joined by
    spaces, a list left as its lines (read it with items())"""
    m = re.match(r'\ufeff?---[ \t]*\r?\n(.*?)\r?\n---', text, re.S)
    out, key, buf = {}, None, []
    for line in (m.group(1) if m else '').splitlines():
        top = re.match(r'([A-Za-z_][\w-]*):[ \t]*(.*)', line)
        if top and not line[:1].isspace():
            if key:
                out[key] = '\n'.join(buf).strip()
            key, val = top.group(1), top.group(2).strip()
            buf = [] if val in ('>', '|', '>-', '|-', '') else [val]
        elif key:
            buf.append(line.strip())
    if key:
        out[key] = '\n'.join(buf).strip()
    return {k: v for k, v in out.items()}


def clean(v):
    v = v.replace('\n', ' ').strip()
    return v[1:-1] if len(v) > 1 and v[0] == v[-1] and v[0] in '"\'' else v


def items(v):
    """a frontmatter list as names: `a, b`, `[a, b]` or a `- a` per line"""
    return [clean(x.lstrip('- ').strip()) for x in re.split(r'[\n,]', (v or '').strip('[] \n')) if x.lstrip('- ').strip()]


def read_front(path):
    """the frontmatter of a file, read again only when the file changed; {} when it has none or cannot be read"""
    try:
        st = path.stat()
    except OSError:
        return {}
    hit = _front_cache.get(str(path))
    if hit and hit[:2] == (st.st_mtime_ns, st.st_size):
        return hit[2]
    try:
        with open(path, 'rb') as f:
            fields = front(f.read(FRONT_MAX).decode('utf-8', 'replace'))
    except OSError:
        fields = {}
    _front_cache[str(path)] = (st.st_mtime_ns, st.st_size, fields)
    return fields


def brief_of(description):
    d = clean(description)
    first = re.split(r'(?<=[.!?])\s', d, 1)[0]
    return (first if len(first) <= BRIEF_MAX else first[:BRIEF_MAX - 1].rstrip() + '…')


def skill_dirs(root):
    """the skill folders of a root: the root itself, its children, or its skills/ children (one level each)"""
    root = Path(root)
    if (root / 'SKILL.md').is_file():
        return [root]
    base = root / 'skills' if (root / 'skills').is_dir() else root
    try:
        return sorted(d for d in base.iterdir() if (d / 'SKILL.md').is_file())
    except OSError:
        return []


def entry(d, origin, plugin=None, version=None):
    f = read_front(d / 'SKILL.md')
    name = clean(d.name)      # the folder is what Claude lists and invokes; the frontmatter name can differ (hz-meta-xr-operator-*)
    desc = clean(f.get('description', ''))
    short = plugin.split('@')[0] if plugin else '-'
    return {'id': f'{origin}:{short}:{name}', 'name': name, 'brief': brief_of(desc), 'description': desc[:DESC_MAX], 'origin': origin,
            'plugin': plugin, 'version': version, 'path': str(d / 'SKILL.md').replace('\\', '/'), 'enabled': True, 'advised': [], 'agents': []}


def version_key(p):
    return [int(x) if x.isdigit() else 0 for x in re.split(r'[.\-+]', p.name)] + [p.stat().st_mtime]


def latest_plugins(cdir):
    """(marketplace, plugin, version folder) of the newest version of every cached plugin"""
    out = []
    for mk in sorted((cdir / 'plugins' / 'cache').glob('*')) if (cdir / 'plugins' / 'cache').is_dir() else []:
        for pl in sorted(p for p in mk.iterdir() if p.is_dir()):
            vs = [v for v in pl.iterdir() if v.is_dir()]
            if vs:
                out.append((mk.name, pl.name, max(vs, key=version_key)))
    return out


def project_roots(room_dir, cwd=None):
    """the .claude/skills of the folder the server runs in and of the room's folder and the parents of both (3 levels)"""
    seen, out = set(), []
    for start in (cwd or Path.cwd(), room_dir):
        for p in [Path(start).resolve(), *list(Path(start).resolve().parents)[:3]]:
            d = p / '.claude' / 'skills'
            if d.is_dir() and d.resolve() != (claude_dir() / 'skills').resolve() and str(d) not in seen:
                seen.add(str(d))
                out.append(d)
    return out


BUILTIN = {      # skills a session has with no file on disk (they are inside the program); shortcut: a fixed list, update when Claude Code adds one
    'claude-api': 'Reference for the Claude API and the Anthropic SDK.', 'code-review': 'Review a diff or PR for correctness bugs.',
    'simplify': 'Review changed code for reuse, simplification and efficiency, then fix.', 'loop': 'Run a prompt or command on a recurring interval.',
    'schedule': 'Create and manage scheduled cloud agents (routines).', 'init': 'Initialize a CLAUDE.md for the project.',
    'security-review': 'Security review of the pending changes.', 'update-config': 'Configure the Claude Code harness through settings.json.',
    'keybindings-help': 'Customize keyboard shortcuts.', 'fewer-permission-prompts': 'Build an allowlist from read-only calls in your transcripts.',
    'run': 'Launch and drive the project app to see a change working.', 'plugin-authoring': 'Make a mod: a theme, panel, status line, slash command or hook.',
    'workflow-authoring': 'Reference for writing a Workflow tool script.', 'artifact-design': 'Design guidance and fundamentals for Artifacts.',
    'artifact-diagramming': 'Diagramming know-how for Artifacts.', 'artifact-capabilities': 'Runtime capabilities a published Artifact page can be granted.',
    'dataviz': 'Charts, graphs and dashboards that read as one system.'}


def desktop_dir():
    """where the Claude desktop app keeps its plugins and the account's skills (CLAUDE_DATA_DIR overrides, for tests)"""
    return Path(os.environ.get('CLAUDE_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'Claude-Data')


def enabled_plugins(cdir, projects=()):
    """enabledPlugins of the user's settings and of the given projects' settings (True wins; False only when nothing says True)"""
    out = {}
    for f in [cdir / 'settings.json', *(Path(p) / '.claude' / n for p in projects for n in ('settings.json', 'settings.local.json'))]:
        try:
            d = json.loads(f.read_text(encoding='utf-8-sig')).get('enabledPlugins') or {}
        except (OSError, ValueError, AttributeError):
            continue
        for k, v in d.items():
            out[k] = out.get(k) is True or v is True
    return out


def installed_plugins(cdir):
    """(plugin@marketplace, folder, version, project or None) of what ~/.claude/plugins/installed_plugins.json says is installed; when
    that file is not there, the newest version of every cached plugin"""
    try:
        d = json.loads((cdir / 'plugins' / 'installed_plugins.json').read_text(encoding='utf-8-sig')).get('plugins') or {}
    except (OSError, ValueError, AttributeError):
        return [(f'{pl}@{mk}', ver, ver.name, None) for mk, pl, ver in latest_plugins(cdir)]
    out = []
    for key, entries in d.items():
        for e in entries if isinstance(entries, list) else []:
            path = Path(str(e.get('installPath') or ''))
            if path.is_dir():
                out.append((key, path, str(e.get('version') or path.name), e.get('projectPath') if e.get('scope') == 'project' else None))
    return out


def scan(room_dir, roots=(), cwd=None):
    cdir, found = claude_dir(), []
    found += [entry(d, 'user') for d in skill_dirs(cdir / 'skills')]
    for r in project_roots(room_dir, cwd):
        found += [entry(d, 'project') for d in skill_dirs(r)]
    inst = installed_plugins(cdir)
    for key, path, ver, project in inst:
        on = enabled_plugins(cdir, [project] if project else [])         # a project install is on where that project's settings say so
        for d in skill_dirs(path):
            e = entry(d, 'plugin', key, ver)
            e['enabled'] = on.get(key, False) if (cdir / 'settings.json').is_file() else True
            e['project'] = project
            found.append(e)
    dd = desktop_dir()
    for pdir in sorted(dd.glob('claude_*/rpm/*/*/plugin_*')):                     # the plugins of the desktop app: all on
        name = (read_json_file(pdir / '.claude-plugin' / 'plugin.json') or {}).get('name') or pdir.name
        found += [entry(d, 'plugin', f'{name}@desktop', None) for d in skill_dirs(pdir)]
    for sdir in sorted(dd.glob('claude_*/local-agent-mode-sessions/skills-plugin/*/*')):   # the account's skills (docx, pdf...)
        found += [entry(d, 'account', 'anthropic-skills@account', None) for d in skill_dirs(sdir)]
    for name, brief in BUILTIN.items():
        found.append({'id': f'builtin:-:{name}', 'name': name, 'brief': brief, 'description': brief, 'origin': 'builtin', 'plugin': None, 'version': None,
                      'path': None, 'enabled': True, 'advised': [], 'agents': []})
    for r in roots:
        found += [entry(d, 'added') for d in skill_dirs(r)]
    uniq = {}
    for s in found:                       # the same id reached twice counts once; a copy that is enabled wins over one that is not
        old = uniq.get(s['id'])
        if old is None or (s['enabled'] and not old['enabled']):
            uniq[s['id']] = s
    return list(uniq.values())


def find(skills, ref):
    """a skill from an id, "plugin:name", or a bare name; user and project beat plugin for a bare name"""
    ref = str(ref or '').strip()
    for s in skills:
        if s['id'] == ref:
            return s
    parts = ref.split(':')
    if len(parts) == 2:
        hit = [s for s in skills if s['name'] == parts[1] and (s['plugin'] or '').split('@')[0] == parts[0]]
    else:
        hit = [s for s in skills if s['name'] == ref]
        hit.sort(key=lambda s: ORIGINS.index(s['origin']))
    return hit[0] if hit else None


# ---------------------------------------------------------------- the room's file

def state_of(room):
    import chat
    s = chat.read_json(room.dir / 'skills.json', {})
    s = s if isinstance(s, dict) else {}
    return {'roots': [r for r in s.get('roots', []) if isinstance(r, str)], 'advised': [a for a in s.get('advised', []) if isinstance(a, dict)],
            'requests': [r for r in s.get('requests', []) if isinstance(r, dict)], 'seq': int(s.get('seq', 0) or 0)}


def change(room, fn):
    import chat

    def run():
        s = state_of(room)
        out = fn(s)
        chat.write_atomic(room.dir / 'skills.json', json.dumps(s, indent=1, ensure_ascii=False))
        return out
    return room.locked(run)


# ---------------------------------------------------------------- what each agent has

def agent_file(name, cdir, room_dir):
    """the agents/<name>.md of an agent type "plugin:name" or "name": the user's, the project's, then the plugin's newest version"""
    short = name.split(':')[-1]
    cands = [cdir / 'agents' / f'{short}.md', *(r.parent / 'agents' / f'{short}.md' for r in project_roots(room_dir))]
    cands += [v / 'agents' / f'{short}.md' for _, pl, v in latest_plugins(cdir) if ':' not in name or pl == name.split(':')[0]]
    return next((c for c in cands if c.is_file()), None)


def mentions(text, skills):
    """skills a prompt names: `plugin:name` or the word skill followed by the name (a bare name like "close" is too common to count)"""
    out, low = set(), text.lower()
    for s in skills:
        if s['name'].lower() not in low:                     # the cheap test first: most names are nowhere in the text
            continue
        pl, n = (s['plugin'] or '').split('@')[0], re.escape(s['name'])
        if (pl and re.search(r'(?<![\w:-])' + re.escape(pl) + ':' + n + r'(?![\w-])', text)) or \
                re.search(r'\bskills?\s+[`"\']?' + n + r'(?![\w-])', text, re.I):
            out.add(s['id'])
    return out


def transcript_calls(path):
    """how many times a transcript invoked each skill (the Skill tool), read from where the last call stopped"""
    off, cnt, seen = _used.get(str(path), [0, Counter(), set()])
    try:
        with open(path, 'rb') as f:
            f.seek(off)
            data = f.read()
    except OSError:
        return cnt
    end = data.rfind(b'\n') + 1                         # a line being written waits for the next call
    for raw in data[:end].splitlines():
        if b'"Skill"' not in raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        for c in (d.get('message') or {}).get('content') or []:
            if isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('name') == 'Skill' and c.get('id') not in seen:
                seen.add(c.get('id'))                     # a streamed message is written more than once
                ref = (c.get('input') or {}).get('skill')
                if isinstance(ref, str) and ref:
                    cnt[ref.strip().lstrip('/')] += 1
    _used[str(path)] = [off + end, cnt, seen]
    return cnt


def agents_of(room, skills):
    import cost
    cdir, cfg = claude_dir(), room.config()
    roster = room.roster()
    names = list(dict.fromkeys([*(cfg.get('participants') or []), *roster]))
    shared = ''
    for k in ('goal', 'style', 'rules'):                 # what every participant is told in its brief
        v = (read_json_file(room.dir / 'brief.json') or {}).get(k)
        shared += str(v or '') + '\n'
    out = []
    for name in names:
        have, aid = {}, roster.get(name)
        p = room.dir / 'prompts' / f'{name}.md'
        try:
            text = shared + (p.read_text(encoding='utf-8') if p.is_file() else '')
        except OSError:
            text = shared
        for sid in mentions(text, skills):
            have.setdefault(sid, {'via': set(), 'count': 0})['via'].add('brief')
        if isinstance(aid, str) and aid.startswith('a') and not _paths.get(aid):
            _paths[aid] = cost.transcript_of(agent_id=aid)      # the glob over every project is the slow part: found once
        tp = _paths.get(aid)
        typ = None
        if tp:
            try:
                typ = json.loads(tp.with_suffix('.meta.json').read_text(encoding='utf-8')).get('agentType')
            except (OSError, ValueError):
                typ = None
            for ref, n in transcript_calls(tp).items():
                s = find(skills, ref)
                if s:
                    h = have.setdefault(s['id'], {'via': set(), 'count': 0})
                    h['via'].add('used')
                    h['count'] += n
        af = agent_file(typ, cdir, room.dir) if typ else None
        for ref in items(read_front(af).get('skills')) if af else []:
            s = find(skills, ref)
            if s:
                have.setdefault(s['id'], {'via': set(), 'count': 0})['via'].add('type')
        out.append({'name': name, 'type': (typ or '').split(':')[-1] or None,
                    'skills': [{'id': k, 'via': sorted(v['via'], key=('brief', 'type', 'used').index), 'count': v['count']} for k, v in sorted(have.items())]})
    return out


def read_json_file(p):
    import chat
    try:
        return chat.read_json(p, {})
    except ValueError:      # a corrupt file (bad JSON or bad utf-8) counts as absent: one bad job output or meta.json must not take the whole panel down
        return {}


# ---------------------------------------------------------------- requests and the searcher

def searcher_of(room):
    cfg = room.config()
    names = [n for n in dict.fromkeys([*(cfg.get('participants') or []), *room.roster()]) if re.match(r'(?i)search|skillfind', n)]
    return names[0] if names else None


def request_view(room, r):
    """a request as the panel shows it: done when the searcher's file is there, paused when it said so after the request"""
    f = room.dir / 'research' / f"skills-{r['req']}.json"
    data = read_json_file(f) if f.is_file() else {}
    data = data if isinstance(data, dict) else {}
    state = 'done' if f.is_file() and data.get('status', 'done') == 'done' else 'pending'
    if r.get('kind') == 'activation':      # D8: the test of a description (skills_act)
        import skills_act
        return skills_act.request_view(room, r)
    if r.get('kind') in ('derive', 'suggest', 'improve'):      # D6 jobs: done = a candidate of the request exists (skills_d6)
        import skills_d6
        chat = r.get('src') == 'chat'      # D7: the lead's own session does it: no log, and the lead's last word is the note
        return {'req': r['req'], 'kind': r['kind'], 'q': r.get('q', ''), 'for': [], 'by': r.get('by'), 'at': int(r.get('at', 0)),
                'state': skills_d6.request_state(room, r), 'log': None if chat else f"skills-temp/{r['req']}.log", 'file': None, 'cards': [],
                'via': 'lead' if chat else 'job', 'announced': bool(r.get('announced')) if chat else None,
                'note': skills_d6.answer_of(room, r) if chat else ''}
    if state == 'pending' and r.get('failed') is not None:      # the temporary searcher ended without its file
        state = 'failed'
    if state == 'pending':
        for m in room.messages():
            if m.get('ts', 0) >= r.get('at', 0) and m.get('kind') in ('status', 'idle') and re.search(r'(?i)paus', m.get('text', '')) \
                    and 'SKILLSEARCH' in m.get('text', '') and m.get('from') == r.get('searcher'):
                state = 'paused'
    roots = state_of(room)['roots']
    added = {e['name'] for root in roots for e in (entry(d, 'added') for d in skill_dirs(root))}
    cards = [{**{k: c.get(k) for k in ('name', 'what', 'source', 'url', 'skill_path', 'install_hint', 'trust', 'fit')}, 'added': c.get('name') in added}
             | ({'url': ''} if not re.match(r'https?://', str(c.get('url') or '')) else {})      # a javascript: link from the web never reaches a page
             for c in (data.get('results') or [])[:CARDS_MAX] if isinstance(c, dict)]
    return {'req': r['req'], 'kind': 'search', 'q': r.get('q', ''), 'for': r.get('for', []), 'by': r.get('by'), 'at': int(r.get('at', 0)), 'state': state,
            'file': f'research/skills-{r["req"]}.json' if f.is_file() else None, 'cards': cards}


# ---------------------------------------------------------------- GET /skills.json

def index(room, q='', origin='', cwd=None):
    st = state_of(room)
    skills = scan(room.dir, st['roots'], cwd)
    agents = agents_of(room, skills)
    by_id = {s['id']: s for s in skills}
    for a in agents:
        for s in a['skills']:
            if s['id'] in by_id:
                by_id[s['id']]['agents'].append(a['name'])
    for adv in st['advised']:
        s = by_id.get(adv.get('skill'))
        if s:
            s['advised'].append({'to': adv.get('to'), 'at': int(adv.get('at', 0))})
    import skills_d6
    rooms, candidates = skills_d6.listing(room, skills)      # D6: the candidates of the known rooms (no body)
    import skills_d7
    skills_d7.decorate(skills)      # D7: where each skill comes from, and whether it can be updated (local files only)
    import skills_d8
    skills_d8.decorate(skills)      # D8: check and verified of each skill (its sidecar file)
    import skills_use
    skills_use.decorate(room, skills)      # D8: how often and with what outcome each skill was called (the registry, no transcript read)
    words = [w for w in re.split(r'\s+', q.lower().strip()) if w]
    skills = [s for s in skills if (not origin or s['origin'] == origin) and
              all(w in (s['name'] + ' ' + s['description']).lower() for w in words)]
    reqs = [request_view(room, r) for r in st['requests'][-20:]]
    name = searcher_of(room)
    return {'v': 1, 'at': int(time.time()), 'origins': list(ORIGINS), 'skills': skills, 'agents': agents,
            'searcher': {'present': bool(name), 'name': name, 'busy': any(r['state'] in ('pending', 'paused') and r['kind'] == 'search' for r in reqs)},
            'requests': reqs, 'rooms': rooms, 'candidates': candidates}


# ---------------------------------------------------------------- POST /skills/do

def fail(text):
    return {'ok': False, 'error': text}


def listed(v):
    v = [v] if isinstance(v, str) else v if isinstance(v, list) else []
    return [str(x).strip() for x in v if str(x).strip()]


def is_all(v):
    """nothing, or "all"/"*"/"tutti" in the list: everybody"""
    v = listed(v)
    return not v or any(x.lower() in ('all', '*', 'tutti', 'everybody') for x in v)


def names_for(room, v):
    """the agents an advice or a search is for: the known names of a name or a list; [] = everybody (or none known)"""
    v = listed(v)
    if is_all(v):
        return []
    known = {n.lower(): n for n in [*(room.config().get('participants') or []), *room.roster()]}
    return [known[x.lower()] for x in v if x.lower() in known]


def tags(names):
    return ' '.join('@' + n for n in names) if names else '@all'


def post(room, text):
    return room.append(room.config().get('user_name', 'USER'), text[:4000])


def do(room, body, cwd=None):
    """one action of the panel; always {"ok": bool, "error": text?, ...}"""
    body = body if isinstance(body, dict) else {}
    action = body.get('action')
    confirm = body.get('confirm') is True
    st = state_of(room)
    skills = scan(room.dir, st['roots'], cwd)
    if action == 'advise':
        s = find(skills, body.get('skill') or body.get('id'))
        if not s:
            return fail(say('skills.core.err_no_skill', skill=str(body.get('skill') or body.get('id') or '')))
        raw = body.get('to') if body.get('to') is not None else body.get('for')
        to = names_for(room, raw)
        if not to and not is_all(raw):
            return fail(say('skills.core.err_no_agent', name=str(raw)))
        note = str(body.get('note') or '').strip()[:300]
        text = say('skills.core.advise', name=s['name'], brief=s['brief'], to=', '.join(to) or say('skills.core.everybody'), tags=tags(to))
        n = post(room, text + (f'\n{note}' if note else ''))
        change(room, lambda x: x['advised'].append({'skill': s['id'], 'to': ', '.join(to) or 'all', 'at': int(time.time())}))
        return {'ok': True, 'msg': n}
    if action == 'search':
        q = re.sub(r'\s+', ' ', str(body.get('q') or body.get('query') or '')).strip()[:300]
        if not q:
            return fail(say('skills.core.err_empty_query'))
        name = searcher_of(room)
        if not name:
            return {'ok': False, 'need': 'temp_searcher', 'error': say('skills.core.err_no_searcher')}
        req = new_request(room, q, names_for(room, body.get('for')), name)
        post(room, say('skills.core.search_line', req=req['req'], q=q, forwho=forwho(req['for']), tag=name))
        return {'ok': True, 'req': req['req'], 'searcher': name}
    if action == 'temp_searcher':
        q = re.sub(r'\s+', ' ', str(body.get('q') or body.get('query') or '')).strip()[:300]
        if not q:
            return fail(say('skills.core.err_empty_query'))
        for_ = names_for(room, body.get('for'))
        task = say('skills.core.temp_task', q=q, forwho=forwho(for_))
        if not confirm:
            return {'ok': True, 'preview': {'name': SEARCH_NAME, 'task': task}}
        req = new_request(room, q, for_, SEARCH_NAME)
        try:
            proc, out = launch_searcher(room, req)
        except OSError as exc:
            return fail(say('skills.core.err_launch', exc=str(exc)[:200]))
        post(room, say('skills.core.temp_line', name=SEARCH_NAME, req=req['req'], q=q, forwho=forwho(for_)))
        threading.Thread(target=watch, args=(room, req, proc, out), daemon=True).start()     # after the line: its done line comes last
        return {'ok': True, 'req': req['req'], 'name': SEARCH_NAME}
    if action == 'request':
        r = next((r for r in st['requests'] if r.get('req') == body.get('req')), None)
        return {'ok': True, 'request': request_view(room, r)} if r else fail(say('skills.core.err_no_request', req=str(body.get('req') or '')))
    if action == 'add':
        return add(room, body, st, confirm)
    import skills_d6
    import skills_d7
    if action in skills_d7.ACTIONS:
        return skills_d7.do(room, action, body, skills, confirm)
    import skills_d8
    if action in skills_d8.ACTIONS:
        return skills_d8.do(room, action, body, skills, confirm)
    import skills_use
    if action in skills_use.ACTIONS:
        return skills_use.do(room, action, body, skills, confirm)
    import skills_act
    if action in skills_act.ACTIONS:
        return skills_act.do(room, action, body, skills, confirm)
    if action in skills_d6.ACTIONS:
        return skills_d6.do(room, 'promote' if action == 'promote' else action, body, skills, confirm)
    return fail(say('skills.core.err_unknown_action', action=str(action)))


def launch_searcher(room, req):
    """the temporary searcher: a headless `claude -p` the viewer's server starts after the user's confirm. The prompt goes in on
    stdin (no quoting), the tools are only the web, a Read and the one file it may write (dontAsk refuses the rest), a budget and a
    timeout end it. watch() waits for it and says in the chat when it is done. launch() is the one place that starts a process"""
    out = f"research/skills-{req['req']}.json"
    (room.dir / 'research').mkdir(exist_ok=True)
    prompt = say('skills.core.temp_prompt', name=SEARCH_NAME, req=req['req'], q=req['q'], forwho=forwho(req.get('for') or []), file=out,
                 room=str(room.dir).replace('\\', '/'))
    cmd = [shutil.which('claude') or 'claude', '-p', '--model', 'sonnet', '--permission-mode', 'dontAsk', '--tools', 'WebSearch,WebFetch,Read,Write',
           '--allowedTools', f'WebSearch WebFetch Read Edit({out})', '--strict-mcp-config', '--max-budget-usd', '1', '--no-session-persistence']
    work = room.dir / 'skills-temp'
    work.mkdir(exist_ok=True)
    return launch(cmd, prompt, room.dir, work / f"{req['req']}.log"), out


def launch(cmd, prompt, cwd, log):
    """start the process with the prompt on stdin and its output in a log; no window, not tied to the viewer's console"""
    with open(log, 'wb') as f:
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.PIPE, stdout=f, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    proc.stdin.write(prompt.encode('utf-8'))
    proc.stdin.close()
    return proc


def watch(room, req, proc, out, timeout=900):
    """one line in the chat when the searcher is gone (or killed after the timeout), so nobody waits on a ghost"""
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    f = room.dir / out
    if not f.is_file():      # gone without its file: say so and where the log is, never "done (0)"
        change(room, lambda s: [r.update(failed=proc.returncode if proc.returncode is not None else -1) for r in s['requests'] if r.get('req') == req['req']])
        room.append(SEARCH_NAME, say('skills.core.temp_failed', req=req['req'], file=out, code=proc.returncode, log=f"skills-temp/{req['req']}.log"))
        return
    data = read_json_file(f)
    n = len(data.get('results') or []) if isinstance(data, dict) else 0
    room.append(SEARCH_NAME, say('skills.core.temp_done', req=req['req'], file=out, n=n))


def forwho(names):
    return f' [for: {", ".join(names)}]' if names else ''


def new_request(room, q, for_, searcher):
    def run(s):
        s['seq'] += 1
        r = {'req': f"r{s['seq']}", 'q': q, 'for': for_, 'by': room.config().get('user_name', 'USER'), 'at': int(time.time()), 'searcher': searcher}
        s['requests'].append(r)
        return r
    return change(room, run)


def downloads_dir():
    return Path(os.environ.get('CHATROOM_SKILLS_DIR') or DOWNLOADS)


def add(room, body, st, confirm):
    """add a skill folder to the panel: a local path, or a card of a search (a github repo cloned into D:). Without confirm only
    the preview: nothing is written, nothing is fetched"""
    src, path, clone = '', None, None
    if body.get('path'):
        path = Path(str(body['path'])).expanduser()
        src = str(path)
    else:
        card = next((c for r in st['requests'] if r.get('req') == body.get('req') for c in request_view(room, r)['cards']
                     if c['name'] == (body.get('card') or body.get('result_id'))), None)
        if not card:
            return fail(say('skills.core.err_no_card'))
        m = REPO.match(str(card.get('url') or ''))
        if not m:
            return fail(say('skills.core.err_no_repo', url=str(card.get('url') or '')))
        src, clone = card['url'], downloads_dir() / f'{m[1]}__{m[2]}'
        sub = card.get('skill_path') or ''
        path = clone / Path(sub).parent if sub.endswith('SKILL.md') else clone
        if not path.resolve().is_relative_to(clone.resolve()):      # the path comes from the web: never out of the clone
            path = clone
        if clone.is_dir() and not skill_dirs(path):
            path = clone
    if clone is None and not skill_dirs(path):
        return fail(say('skills.core.err_no_skill_folder', path=str(path)))
    found = skill_dirs(path) if path.exists() else []
    first = entry(found[0], 'added') if found else None
    if not confirm:
        return {'ok': True, 'preview': {'name': first['name'] if first else clone.name, 'brief': first['brief'] if first else '',
                                        'from': src, 'to': str(path).replace('\\', '/'), 'path': str(path).replace('\\', '/'),
                                        'downloads': clone is not None and not clone.is_dir()}}
    if clone is not None and not clone.is_dir():
        if not str(clone.resolve()).replace('\\', '/').upper().startswith(('D:/',)) and 'CHATROOM_SKILLS_DIR' not in os.environ:
            return fail(say('skills.core.err_not_d'))
        try:
            clone.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'clone', '--depth', '1', '--', src, str(clone)], check=True, capture_output=True, timeout=180)
        except (OSError, subprocess.SubprocessError) as exc:
            return fail(say('skills.core.err_clone', exc=str(getattr(exc, 'stderr', b'') or exc)[:200]))
        if not skill_dirs(path):
            path = clone
    if not skill_dirs(path):
        return fail(say('skills.core.err_no_skill_folder', path=str(path)))
    p = str(path).replace('\\', '/')
    change(room, lambda s: s['roots'].append(p) if p not in s['roots'] else None)
    return {'ok': True, 'id': entry(skill_dirs(path)[0], 'added')['id']}
