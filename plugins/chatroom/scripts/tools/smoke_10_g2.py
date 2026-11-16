"""1.0 G2: the release notes draft and the README section are public text: first person, no long dashes, no drive path or name of a person of the
machine they were written on, and the README points to the notes. Run: python -X utf8 smoke_10_g2.py"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get('CHATROOM_SCRIPTS') or Path(__file__).resolve().parent.parent).parent
fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:300]}]'), flush=True)
    fails += not cond


notes = ROOT / 'history' / 'RELEASE-NOTES-1.0.md'
ok('the notes exist', notes.is_file())
n = notes.read_text(encoding='utf-8') if notes.is_file() else ''
readme = (ROOT / 'README.md').read_text(encoding='utf-8')
sec = readme.split('## What is new in 1.0', 1)[1].split('\n## ', 1)[0] if '## What is new in 1.0' in readme else ''
ok('the README has the section and points to the notes', 'history/RELEASE-NOTES-1.0.md' in sec, sec[:80])
for name, text in (('notes', n), ('README section', sec)):
    ok(f'{name}: no long dash', not re.search('[\u2014\u2013]', text) and ' - ' not in text, re.findall('.{15}(?:[\u2014\u2013]| - ).{15}', text))
    ok(f'{name}: no drive path, no user folder', not re.search(r'\b[A-Za-z]:[\/]|/Users/|/home/', text), re.findall(r'.{10}(?:[A-Za-z]:[\/]|/Users/|/home/).{10}', text))
    ok(f'{name}: no co-author or AI trace', not re.search(r'Co-Authored|Claude Code generated|as an AI', text))
ok('the notes are in the first person', re.search(r'\bI\b', n) is not None and 'Adrian' not in n)
print('FAILS', fails)
sys.exit(1 if fails else 0)
