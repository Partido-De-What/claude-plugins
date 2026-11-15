"""The plugin's two layers: the core (the plugin folder, replaced by every update) and the user's (CLAUDE_CONFIG_DIR/chatroom/user,
which an update never touches). A file in the user's layer, at the same relative path as one of the core (templates/agent_prompt.md,
guides/it/lead-normal.md), is read instead of it; locales/<lang>.json in the user's layer overrides single keys. Reading is
what is here: the merge of an override with a newer core file (merge.py) and the recovery of hand edits (manifest.py) use base_save and
stale; the one thing a read writes is the base of an override that has none (_first_read). That base is the core as it is at the first
read: right when the override is read before the update that changes the core, wrong when the first read comes after it, so the
session start runs `merge --auto` (merge.py, which warns about an override with no base and a changed version) before anything reads.

chatroom_dir() is the one place that says where the user's own data lives (settings, lessons, rooms, spawn/, secrets/...): every
module asks it instead of building ~/.claude/chatroom itself, so CLAUDE_CONFIG_DIR is honoured everywhere or nowhere. (Not
skills_d6.user_dir(), which is the user's skills folder, CLAUDE_CONFIG_DIR/skills.)
BASE: user/.base/<rel> is a copy of the core file an override started from, the third side of a three-way merge."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

KINDS = ('templates', 'guides', 'locales')           # the folders a reader asks for; the core's hooks/agents/skills are Claude Code's
DRAFTS = ('.merged', '.tmp')                         # a merge in progress, a write in progress: not overrides


def claude_dir():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')


def chatroom_dir():
    return claude_dir() / 'chatroom'


def user_root():
    return chatroom_dir() / 'user'


def core_root():
    return Path(__file__).resolve().parent.parent


def find(kind, name, lang='en'):
    """(path, 'user'|'core') of templates|guides NAME for lang, or (None, None). Order: the user's file in lang, the core's in lang,
    then the same two in English (the files at the root of the folder). A name that leaves its folder is not found; a user's file
    that is not UTF-8 or is empty is skipped with a line on stderr (_unusable). The readers open the file with utf-8-sig"""
    for sub in ([lang] if lang not in ('', 'en') else []) + ['']:
        for layer, root in (('user', user_root()), ('core', core_root())):
            base = (root / kind).resolve()
            path = (base / sub / str(name)).resolve()
            if base in path.parents and path.is_file():
                if layer == 'user':
                    if _unusable(path):
                        continue
                    _first_read('/'.join(x for x in (kind, sub, str(name)) if x))
                return path, layer
    return None, None


def _unusable(path):
    """True (and a line on stderr that names the file) when the user's file cannot stand in for the core's: it is not UTF-8
    text (Notepad saves ANSI) or it is empty, and the page would break or vanish without a word. A BOM is not a fault: readers use utf-8-sig"""
    try:
        text = path.read_bytes().decode('utf-8-sig')
    except OSError:
        return False                                      # the reader says it
    except ValueError:
        text = None
    if text and text.strip():
        return False
    import i18n                                           # i18n reads the locales through this module
    print(i18n.say('layers.skipped.not_utf8', path=path) if text is None else i18n.say('layers.skipped.empty', path=path), file=sys.stderr)
    return True


def _say_core(lang, key, **fields):
    """a line of the plugin's own catalog in lang (English when it has none): the user's overlay is what is being read, so it cannot go
    through i18n.say"""
    import i18n
    for code in (lang, 'en'):
        try:
            text = json.loads((i18n.LOCALES / f'{code}.json').read_text(encoding='utf-8-sig')).get(key)
        except (OSError, ValueError):
            text = None
        if text:
            return i18n.fill(text, fields)
    return f'{fields.get("path")}: {key}'


def locale_overlay(lang):
    """{key: text} the user's locales/<lang>.json gives, {} when there is none or it cannot be read (the core text is then used); a value
    that is not a text (5, a list) is left out: it would break every command that says that key"""
    path = user_root() / 'locales' / f'{lang}.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except OSError:
        return {}                                         # no file: nothing to say
    except ValueError:                                    # not UTF-8, empty or not JSON
        data = None
    if not isinstance(data, dict):
        print(_say_core(lang, 'layers.skipped.locale', path=path), file=sys.stderr)      # not i18n.say: this is the catalog being read
        return {}
    _first_read(f'locales/{lang}.json')
    text = lambda v: isinstance(v, str) or (isinstance(v, dict) and bool(v) and all(isinstance(x, str) for x in v.values()))   # a text, or its plurals
    return {k: v for k, v in data.items() if isinstance(k, str) and text(v)} if isinstance(data, dict) else {}


def locale_stamp(lang):
    """changes when the user's locale file does (i18n looks again only then)"""
    try:
        return (user_root() / 'locales' / f'{lang}.json').stat().st_mtime_ns
    except OSError:
        return None


def sha(path):
    """sha256 of a file's text with LF endings (a CRLF working copy and its LF index are the same text), None if it is not there"""
    try:
        return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    except OSError:
        return None


def overrides():
    """the relative paths (posix) of the user's override files: what the reader can take from the user's layer (KINDS), not the
    .folders (.base, .pristine, .merged-backup) nor the drafts of a merge. merge.py lists the same"""
    root = user_root()
    return sorted(p.relative_to(root).as_posix() for kind in KINDS if (root / kind).is_dir() for p in (root / kind).rglob('*')
                  if p.is_file() and not any(x.startswith('.') for x in p.relative_to(root).parts) and p.suffix not in DRAFTS)


def base_path(rel):
    return user_root() / '.base' / rel


def base_save(rel):
    """the core's file now becomes the base of the override rel: call it when the override is created or has been merged with it"""
    src, dst = core_root() / rel, base_path(rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _first_read(rel):
    """an override made by hand has no base, and the merge of the next update needs the core it was written against: the core
    file as it is when the override is first read is the nearest there is (the update comes after it). A read never fails here"""
    try:
        if (core_root() / rel).is_file() and not base_path(rel).exists():
            dst = base_path(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + '.tmp')
            shutil.copyfile(core_root() / rel, tmp)
            os.replace(tmp, dst)
    except OSError:
        pass


def stale():
    """the overrides whose core file changed since their base was saved: [rel]. One with no base (made by hand) is not here"""
    return [rel for rel in overrides() if sha(base_path(rel)) not in (None, sha(core_root() / rel))]
