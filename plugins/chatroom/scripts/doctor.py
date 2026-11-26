"""chat.py doctor: one command that checks the chatroom and prints the command that fixes each thing that is wrong.

Checked: the installed plugin against the source, the MCP server `chatroom` (its path names the version, so it must be
pointed again at every update), Python 3.14 and uv, the viewers listening, the hooks of the plugin, Headroom, RTK, and
which spawn providers have a key stored (yes or no: a key is never read into the output). Reads only; changes nothing.
Adapted in spirit from the doctor of concord-mcp (MIT, get-concord-ai/concord-mcp, commit 37d48f7). Standard library only."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import layers

HERE = Path(__file__).resolve().parent
PLUGIN = 'chatroom@artyomita-plugins'
OK, WARN, FAIL = 'ok', 'warn', 'fail'
MARK = {OK: '✔', WARN: '!', FAIL: '✘'}


def claude_dir():
    return layers.claude_dir()


def version_of(plugin_dir):
    try:
        return json.loads((Path(plugin_dir) / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8')).get('version')
    except (OSError, ValueError):
        return None


def marketplace_version(plugin_dir):
    """the version the marketplace file of the repo gives the plugin (the file two folders above the plugin), or None where there is none"""
    try:
        d = json.loads((Path(plugin_dir).resolve().parent.parent / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
        return next((p.get('version') for p in d.get('plugins', []) if p.get('name') == PLUGIN.split('@')[0]), None)
    except (OSError, ValueError, AttributeError):
        return None


def installed():
    """(version, install path) of the plugin Claude Code has installed, or (None, None)"""
    try:
        e = json.loads((claude_dir() / 'plugins' / 'installed_plugins.json').read_text(encoding='utf-8'))['plugins'][PLUGIN][0]
        return e.get('version'), e.get('installPath')
    except (OSError, ValueError, KeyError, IndexError):
        return None, None


def stale_copy(here=None):
    """(this copy's version, the installed version, its path) when this script is an installed copy older than the one Claude
    Code has installed now: a session that updated the plugin while open keeps its old skills (with this copy's path written
    in), agent types and hooks until it restarts. None otherwise, and always for a source tree (a developer's copy)"""
    here = Path(here or HERE)
    try:
        mine = json.loads((here.parent / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8')).get('version')
    except (OSError, ValueError, AttributeError):
        return None
    ver, path = installed()
    cache = (claude_dir() / 'plugins' / 'cache').resolve()
    if not mine or not ver or ver == mine or cache not in here.resolve().parents:
        return None
    return mine, ver, str(path)


def mcp_get(claude):
    """the text of `claude mcp get chatroom`, or None when the command is missing or fails"""
    exe = claude or os.environ.get('CHATROOM_CLAUDE') or shutil.which('claude')
    if not exe:
        return None
    try:
        r = subprocess.run([exe, 'mcp', 'get', 'chatroom'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                           stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def claude_login_problem(exe=None):
    """None when the claude CLI is there and logged in; otherwise why not, in the user's words. A headless `claude -p` started
    while nobody is logged in from the terminal only exits 1 into a log nobody reads: every launch asks this first"""
    from i18n import say
    exe = exe or os.environ.get('CHATROOM_CLAUDE') or shutil.which('claude')
    if not exe:
        return say('doctor.claude_missing')
    try:
        r = subprocess.run([exe, 'auth', 'status', '--json'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                           stdin=subprocess.DEVNULL, timeout=30)
        logged = json.loads(r.stdout or '{}').get('loggedIn')
    except (OSError, subprocess.TimeoutExpired, ValueError, AttributeError):
        return None          # shortcut: a claude without `auth status` is let through, its own log says what went wrong
    return None if logged is True else say('doctor.claude_not_logged_in')


def mcp_command(path, env):
    """the command that points the MCP server at the installed copy (the environment variables are the ones it has now)"""
    p = str(path).replace('\\', '/')
    e = ''.join(f'-e {k}={v} ' for k, v in env.items())
    return f'claude mcp remove chatroom -s user && claude mcp add chatroom -s user {e}-- uv run --python 3.14 --project {p} python {p}/scripts/chat.py mcp'


def launcher_command(env):
    """one line, once: put the launcher where an update does not move it, then register the MCP server through it (mcp_launch.py):
    after that an update needs no new registration, the launcher starts whatever version is installed"""
    me = str(HERE / 'mcp_launch.py').replace('\\', '/')
    dest = str(claude_dir() / 'chatroom' / 'bin' / 'mcp_launch.py').replace('\\', '/')
    e = ''.join(f'-e {k}={v} ' for k, v in env.items())
    return (f'python "{me}" --install && claude mcp remove chatroom -s user && '
            f'claude mcp add chatroom -s user {e}-- uv run --no-project --python 3.14 python "{dest}"')


def viewers():
    """{room: url} of the rooms served right now, from the registry the viewers stamp every 5 s"""
    import time
    try:
        rooms = json.loads((claude_dir() / 'chatroom' / 'rooms.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {k: v['url'] for k, v in rooms.items() if time.time() - float(v.get('ts', 0)) < 60}


def listening(url):
    try:
        with urllib.request.urlopen(url + '/config.json', timeout=2):
            return True
    except (OSError, ValueError):
        return False


def stored_keys():
    """{provider: True/False}: a key is stored for it (a file) or in its environment variable. Names only, never a value"""
    sys.path.insert(0, str(HERE))
    from spawn import keys
    from spawn.providers import catalog
    return {p: bool(keys._files(p)) or bool(os.environ.get(e.get('env') or '')) for p, e in catalog.ALL.items()}


def checks(room=None, claude=None, source=None):
    """[(check, status, fields, fix)]: `check` and `fields` make the sentence (doctor.<check>), `fix` is a command or ''"""
    out = []
    ver, path = installed()
    src = version_of(source or HERE.parent)
    if not ver:
        out.append(('version_none', FAIL, {}, f'claude plugin install {PLUGIN}'))
    elif src and src != ver:
        out.append(('version_differs', FAIL, {'installed': ver, 'source': src},
                    f'claude plugin marketplace update artyomita-plugins && claude plugin update {PLUGIN}'))
    else:
        out.append(('version_ok', OK, {'version': ver}, ''))
    mk = marketplace_version(source or HERE.parent)
    if src and mk and mk != src:                             # a release read from the marketplace would announce the old number
        out.append(('marketplace_differs', FAIL, {'marketplace': mk, 'source': src}, ''))
    text = mcp_get(claude)
    if text is None:
        out.append(('mcp_unknown', WARN, {}, 'claude mcp get chatroom'))
    else:
        args = (re.search(r'^\s*Args:\s*(.*)$', text, re.M) or [None, ''])[1].replace('\\', '/')
        env = dict(re.findall(r'^\s{4}(\w+)=(.*)$', text, re.M))
        launcher = 'mcp_launch.py' in args                   # registered through the launcher: an update cannot leave it behind
        if launcher:
            out.append(('mcp_ok', OK, {}, '') if 'Connected' in text else ('mcp_down', FAIL, {}, 'claude mcp get chatroom'))
        elif not path or (str(path).replace('\\', '/') in args and 'Connected' in text):
            out.append(('mcp_ok', OK, {}, ''))
        else:
            out.append(('mcp_stale', FAIL, {'path': str(path)}, mcp_command(path, env)))
        if path and not launcher:
            out.append(('mcp_launcher', WARN, {}, launcher_command(env)))
        if path and launcher:                                    # the copy in bin/ is the one registered: an update of the launcher itself does not reach it
            new, old = Path(path) / 'scripts' / 'mcp_launch.py', claude_dir() / 'chatroom' / 'bin' / 'mcp_launch.py'
            if new.is_file() and old.is_file() and new.read_bytes().replace(b'\r\n', b'\n') != old.read_bytes().replace(b'\r\n', b'\n'):
                out.append(('mcp_launcher_old', WARN, {}, f'python "{new}" --install'))
    py = sys.version_info
    out.append(('python_ok' if py >= (3, 14) else 'python_old', OK if py >= (3, 14) else WARN, {'version': f'{py[0]}.{py[1]}'},
                '' if py >= (3, 14) else 'uv run --python 3.14 python chat.py doctor'))
    out.append(('uv_ok', OK, {}, '') if shutil.which('uv') else ('uv_missing', FAIL, {}, 'winget install astral-sh.uv'))
    login = claude_login_problem(claude)                       # the searchers and the other `claude -p` jobs need it
    out.append(('claude_login_ok', OK, {}, '') if login is None else ('claude_login', WARN, {'why': login}, 'claude auth login'))
    live = viewers()
    if room and str(Path(room).resolve()) not in live:
        out.append(('viewer_off', WARN, {'room': str(room)}, f'python chat.py serve --room "{room}"'))
    elif not live:
        out.append(('viewer_none', WARN, {}, 'python chat.py serve --room ROOM'))
    for k, url in live.items():
        if not room or Path(k) == Path(room).resolve():
            out.append(('viewer_up' if listening(url) else 'viewer_dead', OK if listening(url) else FAIL, {'room': k, 'url': url}, ''))
    root = Path(path) if path else HERE.parent
    try:
        hooks = json.loads((root / 'hooks' / 'hooks.json').read_text(encoding='utf-8')).get('hooks', {})
    except (OSError, ValueError):
        hooks = None
    if hooks is None:
        out.append(('hooks_unreadable', FAIL, {'path': str(root / 'hooks' / 'hooks.json')}, ''))
    else:
        found = sorted(hooks)
        missing = [h for h in ('SessionStart', 'PreToolUse') if h not in hooks]
        out.append(('hooks_ok', OK, {'found': ', '.join(found)}, '') if not missing else ('hooks_missing', WARN, {'missing': ', '.join(missing)}, ''))
    if not (shutil.which('python') or shutil.which('python3')):
        out.append(('hooks_no_python', FAIL, {}, 'winget install Python.Python.3.14'))
    try:
        enabled = json.loads((claude_dir() / 'settings.json').read_text(encoding='utf-8')).get('enabledPlugins', {}).get(PLUGIN)
    except (OSError, ValueError):
        enabled = None
    if enabled is False:
        out.append(('plugin_disabled', FAIL, {}, f'claude plugin enable {PLUGIN}'))
    env_dir = Path(os.environ.get('UV_PROJECT_ENVIRONMENT') or claude_dir() / 'chatroom' / 'env')
    hr = importlib.util.find_spec('headroom') is not None or any((env_dir / s).exists() for s in ('Lib/site-packages/headroom', 'lib/site-packages/headroom'))
    out.append(('headroom_ok', OK, {}, '') if hr else ('headroom_missing', WARN, {}, f'uv sync --frozen --inexact --project "{HERE.parent}"'))
    pil = importlib.util.find_spec('PIL') is not None or any((env_dir / s).exists() for s in ('Lib/site-packages/PIL', 'lib/site-packages/PIL'))
    out.append(('pillow_ok', OK, {}, '') if pil else ('pillow_missing', WARN, {}, f'uv sync --frozen --inexact --project "{HERE.parent}"'))
    try:
        import chat
        stale = chat.stale_install()
        out.append(('agents_code', OK, {'path': str(chat.chat_for_agents())}, '') if not stale else
                   ('agents_code_stale', WARN, {'path': str(chat.chat_for_agents()), 'files': ', '.join(stale[:6])},
                    'claude plugin marketplace update artyomita-plugins && claude plugin update chatroom@artyomita-plugins'))
    except Exception:
        pass
    try:                                                       # hand edits of an older copy (manifest.py): still to merge, and edited in the installed one
        import manifest
        todo = manifest.pending()
        if todo:
            out.append(('recover_pending', WARN, {'n': len(todo), 'files': ', '.join(f"{t['ver']}:{t['rel']}" for t in todo[:6])},
                        f'python "{HERE / "chat.py"}" recover' + ('' if any(t.get('why') == 'no_reference' for t in todo) else ' --list')))   # a whole old copy not compared yet (no manifest, 0.18): the full one, with git
        diff = (manifest.verify(path) if path else None) or {}
        changed = [f for k in ('modified', 'added', 'removed') for f in diff.get(k, [])]
        if changed:
            out.append(('install_modified', WARN, {'n': len(changed), 'files': ', '.join(changed[:6])}, ''))
    except ImportError:                                        # no manifest.py in this copy
        pass
    except Exception as exc:                                   # nor may a broken one
        out.append(('recover_error', WARN, {'why': type(exc).__name__}, ''))
    try:                                                       # the user's own copies against the version in use (reads only: merge.py writes)
        import merge
        from i18n import say
        res = merge.run(apply=False)
        out += [('merge_need', WARN, {'text': merge.sentence(x)}, '') for x in res if x['state'] in merge.NEED]
        ready = [x['rel'] for x in res if x['state'] in (merge.MERGED, merge.ADOPTED)]
        if ready:
            out.append(('merge_ready', WARN, {'files': ', '.join(ready)}, f'python "{HERE / "chat.py"}" merge'))
        elif res and not any(x['state'] in merge.NEED for x in res):
            out.append(('merge_ok', OK, {'n': len(res)}, ''))
    except Exception as exc:                                   # a broken user layer must not stop the doctor
        out.append(('merge_error', WARN, {'why': type(exc).__name__}, ''))
    rtk = os.environ.get('CHATROOM_RTK') or shutil.which('rtk') or str(claude_dir() / 'chatroom' / 'bin' / ('rtk.exe' if os.name == 'nt' else 'rtk'))
    out.append(('rtk_ok', OK, {'path': rtk}, '') if Path(rtk).is_file() else ('rtk_missing', WARN, {}, 'see the README (RTK): install rtk, then restart the viewer'))
    try:
        keys = stored_keys()
        out.append(('keys', OK if any(keys.values()) else WARN, {'yes': ', '.join(p for p, v in keys.items() if v) or '-',
                                                              'no': ', '.join(p for p, v in keys.items() if not v) or '-'}, ''))
    except Exception as exc:                                   # a broken key store must not stop the doctor
        out.append(('keys_error', WARN, {'why': f"{type(exc).__name__}: {getattr(exc, 'name', None) or exc}"}, ''))   # which module, not only its kind
    return out


def render(results, fmt):
    lines = []
    for check, status, fields, fix in results:
        lines.append(f'{MARK[status]} ' + fmt(f'doctor.{check}', **fields))
        if fix:
            lines.append('    ' + fmt('doctor.fix') + ' ' + fix)
    return '\n'.join(lines)


def main(room=None, claude=None, source=None):
    from i18n import say, use
    use(None)
    results = checks(room, claude, source)
    print(render(results, say))
    return 1 if any(s == FAIL for _, s, _, _ in results) else 0


def _prova():
    """self-check: a fake Claude home with a stale MCP path, then with a good one; no key value is ever printed"""
    import tempfile
    global claude_dir
    root = Path(tempfile.mkdtemp(prefix='doctor_'))
    (root / 'plugins').mkdir()
    old = claude_dir
    claude_dir = lambda: root
    try:
        (root / 'plugins' / 'installed_plugins.json').write_text(json.dumps({'plugins': {PLUGIN: [{'version': '9.9.9', 'installPath': str(root / 'c' / '9.9.9')}]}}), encoding='utf-8')
        assert installed() == ('9.9.9', str(root / 'c' / '9.9.9'))
        r = {c: (s, f) for c, s, _, f in checks(None, 'no-such-claude', HERE.parent)}
        assert r['version_differs'][0] == FAIL and 'claude plugin update' in r['version_differs'][1], r
        assert 'chat.py mcp' in mcp_command('C:/x/1.0', {'UV_CACHE_DIR': 'D:/c'}) and '-e UV_CACHE_DIR=D:/c' in mcp_command('C:/x/1.0', {'UV_CACHE_DIR': 'D:/c'})
        os.environ['GROQ_API_KEY'] = 'sk-SECRET-VALUE'
        text = render(checks(None, 'no-such-claude', HERE.parent), lambda k, **f: k + ' ' + json.dumps(f))
        assert 'SECRET' not in text and 'groq' in text
    finally:
        claude_dir = old
    print('doctor: self-check ok')


if __name__ == '__main__':
    if '--prova' in sys.argv:
        _prova()
    else:
        sys.exit(main(None))
