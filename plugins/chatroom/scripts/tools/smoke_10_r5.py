"""1.0 R5: no skill, guide, template or locale tells the lead to start the relay with `--batch 60`: a fixed batch overrides the pace
of the room (lead_pace), so half the wakes were empty. Run: python -X utf8 smoke_10_r5.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
hits = []
for d in ('skills', 'guides', 'templates', 'locales', 'hooks', 'agents'):
    for f in (ROOT / d).rglob('*'):
        if f.is_file() and f.suffix in ('.md', '.json', '.txt', '.py', '.sh'):
            for i, line in enumerate(f.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                if '--batch 60' in line:
                    hits.append(f'{f.relative_to(ROOT).as_posix()}:{i}')
hits += [f'README.md:{i}' for i, l in enumerate((ROOT / 'README.md').read_text(encoding='utf-8').splitlines(), 1) if '--batch 60' in l]
print(('PASS' if not hits else 'FAIL') + ' R5 no `--batch 60` in skills, guides, templates, locales, README', hits or '')
sys.exit(1 if hits else 0)
