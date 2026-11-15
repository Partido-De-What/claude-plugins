"""D7 of the skill workshop: where a skill comes from and whether its creator published a newer one.
Contract: stanza-skill/scratch/CORE/skills.d7.contract.md. skills.py decorates every skill (source, updatable: local files only, no network)
and routes update_check / update_apply here.

update_check only reads (git ls-remote, raw files and the compare API of GitHub); update_apply runs `claude plugin update` or
`git pull --ff-only` and only after the user's confirm. The three outside calls (http_get, git, run) are module functions: tests replace them.
Account, built-in and desktop skills, the user's own folders and the plugins of a local-directory marketplace never get an update."""
import json
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from i18n import say
from skills import claude_dir, fail, find, read_json_file

# like skills.REPO (owner, name) but also the ssh form that a clone's .git/config often has
REPO_URL = re.compile(r'(?:https?://github\.com/|git@github\.com:)([\w.-]+)/([\w.-]+?)(?:\.git)?/?\Z')
SAFE_URL = re.compile(r'(?:https://|ssh://|git@github\.com:)[\w.@:/~+-]+\Z')      # never "-option", ext:: or file: urls
TIMEOUT = 20
KINDS = ('you', 'project', 'marketplace', 'repo', 'local', 'desktop', 'claude', 'builtin', 'folder')
ACTIONS = ('update_check', 'update_apply')


# ---------------------------------------------------------------- the three outside calls

def http_get(url):
    rq = urllib.request.Request(url, headers={'User-Agent': 'chatroom-skills', 'Accept': 'application/json, text/plain'})
    with urllib.request.urlopen(rq, timeout=TIMEOUT) as r:
        return r.read(2_000_000).decode('utf-8', errors='replace')


def run(argv, cwd=None):
    """(exit code, output) of one command; -1 when it cannot run"""
    argv = [shutil.which(argv[0]) or argv[0], *argv[1:]]      # on Windows claude is claude.cmd: a bare name does not start
    try:
        p = subprocess.run(argv, cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=TIMEOUT * 6,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return p.returncode, (p.stdout or '') + (p.stderr or '')
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)


def git(args, cwd=None):
    return run(['git', '-c', 'core.fsmonitor=false', *args], cwd)      # a folder's own config must not run a program for a read


# ---------------------------------------------------------------- where a skill comes from (local files only)

def origin_url(folder):
    """the origin remote of a git folder (its .git/config), or None"""
    try:
        text = (Path(folder) / '.git' / 'config').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    m = re.search(r'\[remote "origin"\][^\[]*?\burl\s*=\s*(\S+)', text)
    return m[1] if m and SAFE_URL.match(m[1]) else None      # a .git/config can come from a zip: only a plain remote is ever given to git


def nice(url):
    m = REPO_URL.match(url or '')
    return f'{m[1]}/{m[2]}' if m else str(url or '')


def web(url):
    m = REPO_URL.match(url or '')
    return f'https://github.com/{m[1]}/{m[2]}' if m else (url if str(url or '').startswith('https://') else None)


def marketplaces(cdir):
    d = read_json_file(cdir / 'plugins' / 'known_marketplaces.json')
    return d if isinstance(d, dict) else {}


def where(s, mk):
    """(source, updatable, ctx) of a skill: source = what the panel shows, ctx = what the check needs"""
    o, put = s['origin'], (lambda kind, label='-', url=None, up=False, **ctx: ({'kind': kind, 'label': label, 'url': url, 'version': s.get('version')}, up, ctx))
    if o == 'builtin':
        return put('builtin')
    if o == 'account':
        return put('claude')
    if o == 'plugin':
        key = s.get('plugin') or ''
        market = key.split('@', 1)[1] if '@' in key else ''
        if market in ('desktop', 'account'):
            return put('desktop', key)
        src = (mk.get(market) or {}).get('source') if isinstance(mk.get(market), dict) else None
        src = src if isinstance(src, dict) else {}
        url = f"https://github.com/{src['repo']}" if src.get('source') == 'github' and src.get('repo') else src.get('url') if src.get('source') in ('git', 'url') else None
        if not url:
            return put('local', key)
        return put('marketplace', key, web(url), True, key=key, remote=url, project=s.get('project'))
    folder = Path(s['path']).parent if s.get('path') else None
    if folder:
        for p in ([folder, *list(folder.parents)[:3]] if o == 'added' else [folder]):     # an added folder may be inside a clone; the user's and the project's own only if it is a clone itself
            url = origin_url(p)
            if url:
                return put('repo', nice(url), web(url), True, root=str(p), remote=url)
    return put({'user': 'you', 'project': 'project'}.get(o, 'folder'))


def decorate(skills, cdir=None):
    mk = marketplaces(cdir or claude_dir())
    for s in skills:
        s['source'], s['updatable'], _ = where(s, mk)


# ---------------------------------------------------------------- the check (read only)

def sha7(x):
    return str(x or '')[:7] or None


def vkey(v):
    return [int(x) if x.isdigit() else 0 for x in re.split(r'[.\-+]', str(v))]


def remote_head(url):
    if not SAFE_URL.match(str(url)):
        return None
    code, out = git(['ls-remote', '--', url, 'HEAD'])
    return out.split()[0] if code == 0 and out.strip() else None


def get_json(url):
    try:
        v = json.loads(http_get(url))
    except (OSError, ValueError):
        return None
    return v if isinstance(v, dict) else None


def compare(repo, a, b, sub=''):
    """(status, files under sub, text) of what changed between two commits of a github repo; (None, 0, '') when it cannot be read"""
    j = get_json(f'https://api.github.com/repos/{repo}/compare/{a}...{b}')
    if not j:
        return None, 0, ''
    files = [f.get('filename', '') for f in j.get('files') or [] if isinstance(f, dict)]
    mine = [f for f in files if f.startswith(sub)] if sub else files
    subjects = '; '.join(str((c.get('commit') or {}).get('message', '')).split('\n')[0] for c in (j.get('commits') or [])[-5:] if isinstance(c, dict))[:300]
    return j.get('status'), len(mine), say('skills.d7.changes', n=j.get('ahead_by') or 0, files=len(mine), subjects=subjects)


def installed_entry(key, project, cdir):
    d = read_json_file(cdir / 'plugins' / 'installed_plugins.json')
    for e in ((d or {}).get('plugins') or {}).get(key) or []:
        if isinstance(e, dict) and (e.get('projectPath') if e.get('scope') == 'project' else None) == project:
            return e
    return {}


def remote_plugin(repo, name):
    """(github repo of the plugin, folder inside it, version, error) from the marketplace.json the creator publishes"""
    mj = get_json(f'https://raw.githubusercontent.com/{repo}/HEAD/.claude-plugin/marketplace.json') or {}
    pe = next((p for p in mj.get('plugins') or [] if isinstance(p, dict) and p.get('name') == name), None)
    prepo, sub = repo, ''
    if pe:
        ps = pe.get('source')
        if isinstance(ps, str):
            sub = '' if ps.strip('./') == '' else ps[2:] if ps.startswith('./') else ps
        elif isinstance(ps, dict):
            m = REPO_URL.match(str(ps.get('url') or '')) or (re.match(r'([\w.-]+)/([\w.-]+)\Z', str(ps.get('repo') or '')))
            prepo = f'{m[1]}/{m[2]}' if m else None
            sub = str(ps.get('path') or '').strip('/') if m else ''
    ver = (pe or {}).get('version')
    if not ver and prepo:
        ver = (get_json(f"https://raw.githubusercontent.com/{prepo}/HEAD/{sub + '/' if sub else ''}.claude-plugin/plugin.json") or {}).get('version')
    return prepo, sub.strip('/'), ver


def check(s, cdir=None):
    """{'ok': True, 'update': {...}} for one skill: the installed and the available version, newer true|false|null, what changed"""
    cdir = cdir or claude_dir()
    src, up, ctx = where(s, marketplaces(cdir))
    if not up:
        why = {'you': lambda: say('skills.d7.why_you'), 'project': lambda: say('skills.d7.why_project'), 'local': lambda: say('skills.d7.why_local'),
               'desktop': lambda: say('skills.d7.why_desktop'), 'claude': lambda: say('skills.d7.why_claude'), 'builtin': lambda: say('skills.d7.why_builtin'),
               'folder': lambda: say('skills.d7.why_folder')}[src['kind']]()
        return fail(say('skills.d7.err_not_updatable', skill=s['name'], why=why))
    out = {'skill': s['id'], 'kind': src['kind'], 'checked_at': int(time.time()), 'installed': None, 'available': None, 'newer': None, 'changes': ''}
    if src['kind'] == 'marketplace':
        key = ctx['key']
        inst = installed_entry(key, ctx['project'], cdir)
        m = REPO_URL.match(ctx['remote'] or '')
        prepo, sub, ver = remote_plugin(f'{m[1]}/{m[2]}', key.split('@')[0]) if m else (None, '', None)
        head = remote_head(f'https://github.com/{prepo}.git') if prepo else remote_head(ctx['remote'])
        have, got = inst.get('gitCommitSha'), head
        out.update(source=f'plugin {key}', installed=inst.get('version') or sha7(have), available=ver or sha7(got), sub=sub)
        status, files, text = compare(prepo, have, got, sub) if prepo and have and got and have != got else (None, 0, '')
        out['changes'] = text
        if ver and inst.get('version'):
            out['newer'] = vkey(ver) > vkey(inst['version']) if ver != inst['version'] else False
        elif have and got:
            out['newer'] = False if have == got else (files > 0 if status else None)
    else:
        root, url = ctx['root'], ctx['remote']
        code, local = git(['rev-parse', 'HEAD'], root)
        local = local.strip() if code == 0 else None
        head = remote_head(url)
        out.update(source=f'repo {nice(url)}', installed=sha7(local), available=sha7(head))
        m = REPO_URL.match(url)
        status, files, text = compare(f'{m[1]}/{m[2]}', local, head) if m and local and head and local != head else (None, 0, '')
        out['changes'] = text
        if local and head:
            out['newer'] = False if local == head else (status == 'ahead' if status else None)
    if out['installed'] is None and out['available'] is None:
        return fail(say('skills.d7.err_offline'))
    out.pop('sub', None)
    return {'ok': True, 'update': out}


# ---------------------------------------------------------------- the apply (confirm first)

def apply(room, s, confirm, cdir=None):
    cdir = cdir or claude_dir()
    r = check(s, cdir)
    if not r['ok']:
        return r
    u = r['update']
    src, _, ctx = where(s, marketplaces(cdir))
    if u['newer'] is False:
        return fail(say('skills.d7.err_up_to_date', skill=s['name']))
    if src['kind'] == 'marketplace':
        inst = installed_entry(ctx['key'], ctx['project'], cdir)
        argv, cwd, writes, restart = ['claude', 'plugin', 'update', ctx['key'], '-s', inst.get('scope') or 'user'], ctx['project'], str(cdir / 'plugins').replace('\\', '/'), True
    else:
        argv, cwd, writes, restart = ['git', '-C', ctx['root'], 'pull', '--ff-only'], None, ctx['root'].replace('\\', '/'), False
    if not confirm:
        return {'ok': True, 'preview': {'name': s['name'], 'from': u['source'], 'to': writes, 'installed': u['installed'], 'available': u['available'],
                                        'changes': u['changes'], 'how': ' '.join(argv), 'writes': writes, 'restart': restart}}
    if src['kind'] == 'repo':
        code, st = git(['status', '--porcelain'], ctx['root'])
        if code != 0 or st.strip():
            return fail(say('skills.d7.err_dirty', folder=ctx['root']))
    if src['kind'] == 'marketplace':      # `plugin update` reads only the marketplace copy on disk: refresh it first or it reports "already at the latest"
        code, text = run(['claude', 'plugin', 'marketplace', 'update', ctx['key'].split('@', 1)[-1]], cwd)
        if code != 0:
            return fail(say('skills.d7.err_apply', code=code, out=text.strip()[-200:]))
    code, text = run(argv, cwd)
    if code != 0:
        return fail(say('skills.d7.err_apply', code=code, out=text.strip()[-200:]))
    if re.search(r'already at the latest', text, re.I):      # the tool changed nothing: never tell the user it was updated
        return fail(say('skills.d7.err_not_applied', skill=s['name'], out=text.strip()[-200:]))
    return {'ok': True, 'applied': True, 'installed': u['available'] or (installed_entry(ctx['key'], ctx['project'], cdir).get('version') if src['kind'] == 'marketplace' else None), 'restart': restart, 'out': text.strip()[:300]}


def do(room, action, body, skill_list, confirm):
    s = find(skill_list, body.get('skill') or body.get('id'))
    if not s:
        return fail(say('skills.core.err_no_skill', skill=str(body.get('skill') or body.get('id') or '')))
    return check(s) if action == 'update_check' else apply(room, s, confirm)
