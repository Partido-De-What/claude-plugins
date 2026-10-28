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

HERE = Path(__file__).resolve().parent
PLUGIN = 'chatroom@artyomita-plugins'
OK, WARN, FAIL = 'ok', 'warn', 'fail'
MARK = {OK: '✔', WARN: '!', FAIL: '✘'}


def claude_dir():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')


def version_of(plugin_dir):
    try:
        return json.loads((Path(plugin_dir) / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8')).get('version')
    except (OSError, ValueError):
        return None


def installed():
    """(version, install path) of the plugin Claude Code has installed, or (None, None)"""
    try:
        e = json.loads((claude_dir() / 'plugins' / 'installed_plugins.json').read_text(encoding='utf-8'))['plugins'][PLUGIN][0]
        return e.get('version'), e.get('installPath')
    except (OSError, ValueError, KeyError, IndexError):
        return None, None


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


def mcp_command(path, env):
    """the command that points the MCP server at the installed copy (the environment variables are the ones it has now)"""
    p = str(path).replace('\\', '/')
    e = ''.join(f'-e {k}={v} ' for k, v in env.items())
    return f'claude mcp remove chatroom -s user && claude mcp add chatroom -s user {e}-- uv run --python 3.14 --project {p} python {p}/scripts/chat.py mcp'


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
    text = mcp_get(claude)
    if text is None:
        out.append(('mcp_unknown', WARN, {}, 'claude mcp get chatroom'))
    else:
        args = (re.search(r'^\s*Args:\s*(.*)$', text, re.M) or [None, ''])[1].replace('\\', '/')
        env = dict(re.findall(r'^\s{4}(\w+)=(.*)$', text, re.M))
        if not path or (str(path).replace('\\', '/') in args and 'Connected' in text):
            out.append(('mcp_ok', OK, {}, ''))
        else:
            out.append(('mcp_stale', FAIL, {'path': str(path)}, mcp_command(path, env)))
    py = sys.version_info
    out.append(('python_ok' if py >= (3, 14) else 'python_old', OK if py >= (3, 14) else WARN, {'version': f'{py[0]}.{py[1]}'},
                '' if py >= (3, 14) else 'uv run --python 3.14 python chat.py doctor'))
    out.append(('uv_ok', OK, {}, '') if shutil.which('uv') else ('uv_missing', FAIL, {}, 'winget install astral-sh.uv'))
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
    rtk = os.environ.get('CHATROOM_RTK') or shutil.which('rtk') or str(claude_dir() / 'chatroom' / 'bin' / ('rtk.exe' if os.name == 'nt' else 'rtk'))
    out.append(('rtk_ok', OK, {'path': rtk}, '') if Path(rtk).is_file() else ('rtk_missing', WARN, {}, 'see the README (RTK): install rtk, then restart the viewer'))
    try:
        keys = stored_keys()
        out.append(('keys', OK if any(keys.values()) else WARN, {'yes': ', '.join(p for p, v in keys.items() if v) or '-',
                                                              'no': ', '.join(p for p, v in keys.items() if not v) or '-'}, ''))
    except Exception as exc:                                   # a broken key store must not stop the doctor
        out.append(('keys_error', WARN, {'why': type(exc).__name__}, ''))
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
