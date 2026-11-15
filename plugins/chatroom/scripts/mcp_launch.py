"""The command the chatroom MCP server is registered with, so an update does not leave it behind.

`claude mcp add` used to name the versioned plugin folder, which moves at every update: the server kept running the old version
until someone registered it again by hand. Registered through this launcher (a copy of it sits in <claude dir>/chatroom/bin,
which an update never touches), the server starts whatever version is installed when Claude Code starts it:
    python mcp_launch.py --install     once: copy this launcher to <claude dir>/chatroom/bin/mcp_launch.py
    claude mcp add chatroom -s user -- uv run --no-project --python 3.14 python <claude dir>/chatroom/bin/mcp_launch.py
`chat.py doctor` prints the whole line. Standard library only: it runs before the plugin's environment exists."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = 'chatroom@artyomita-plugins'          # as doctor.PLUGIN: this file runs alone from bin/, it cannot import it


def claude_dir():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')


def installed_path():
    """the folder of the installed plugin (installed_plugins.json), or None"""
    try:
        entry = json.loads((claude_dir() / 'plugins' / 'installed_plugins.json').read_text(encoding='utf-8'))['plugins'][PLUGIN][0]
        return Path(entry['installPath'])
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None


def command(plugin):
    uv = os.environ.get('CHATROOM_UV') or shutil.which('uv') or 'uv'
    return [uv, 'run', '--python', '3.14', '--project', str(plugin), 'python', str(plugin / 'scripts' / 'chat.py'), 'mcp']


def install():
    dest = claude_dir() / 'chatroom' / 'bin' / 'mcp_launch.py'
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, dest)
    print(dest)
    return 0


def main():
    if '--install' in sys.argv:
        return install()
    plugin = installed_path()
    if plugin is None or not (plugin / 'scripts' / 'chat.py').is_file():
        print(f'chatroom MCP: {PLUGIN} is not installed (see {claude_dir() / "plugins" / "installed_plugins.json"}): '
              f'claude plugin install {PLUGIN}', file=sys.stderr)
        return 1
    # the environment goes where chat.py puts it (ENV_DIR), not into a .venv inside the plugin folder, which an update leaves behind
    env = {**os.environ, 'UV_PROJECT_ENVIRONMENT': os.environ.get('UV_PROJECT_ENVIRONMENT') or str(claude_dir() / 'chatroom' / 'env')}
    return subprocess.call(command(plugin), env=env)    # stdin and stdout pass straight through: this is the MCP stdio


if __name__ == '__main__':
    sys.exit(main())
