"""1.0, K2: the evaluator's info numbers (the absolute values behind a ratio) are recorded and shown with every run, and a
reference arm that moved since the compared run is said on the run's line. Run: python -X utf8 smoke_10_k2.py"""
import json
import sys
from pathlib import Path

src = Path(__file__).with_name('smoke_10_kern.py')        # the helpers of the kernel smoke: its text up to the first section
k = {'__file__': str(src), '__name__': 'helpers'}
exec(compile(src.read_text(encoding='utf-8').split("if section('K3'):")[0], str(src), 'exec'), k)
ok, run, research_room = k['ok'], k['run'], k['research_room']

# the metric is a ratio of two arms; the reference arm (base_ms) comes from the environment, so the test can move it between runs
EVAL = '\n'.join(['import os, program',
                  'base = float(os.environ.get("BASE_MS", "180"))',
                  'patch = 180.0 - 10 * (5 - program.X)',
                  'print("loss:", patch / base)',
                  'print("base_ms:", base)',
                  'print("patch_ms:", patch)', ''])


def state(room):
    return json.loads((room / 'research' / 'state.json').read_text(encoding='utf-8'))


room, repo, work = research_room('k2', eval_src=EVAL)
c, o = run(room, 'research', 'amend', '--info', 'base_ms,patch_ms', '--reference', 'nope', '--as', 'LEAD')
ok('K2 a reference that is not an info number is refused', c != 0 and 'info' in o, o)
c, o = run(room, 'research', 'amend', '--info', 'base_ms,patch_ms', '--reference', 'base_ms', '--as', 'LEAD')
ok('K2 amend --info --reference at any time', c == 0 and 'base_ms' in o, o)
c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
st = state(room)
ok('K2 the baseline records its info numbers', c == 0 and st['attempts'][-1].get('info') == {'base_ms': 180.0, 'patch_ms': 180.0}, st['attempts'][-1].get('info'))
ok('K2 the run line shows the absolute values', 'base_ms 180' in o and 'patch_ms 180' in o, o)
ok('K2 no drift said on the baseline', 'moved' not in o, o)
(work / 'program.py').write_text('X = 3' + chr(10))
c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
ok('K2 same reference: kept, no drift said', c == 0 and 'KEEP' in o and 'moved' not in o and 'patch_ms 160' in o, o)
(work / 'program.py').write_text('X = 2' + chr(10))
c, o = run(room, 'research', 'evaluate', '--desc', 'X 2, slow reference', '--as', 'W', env={'BASE_MS': '190'})
ok('K2 a reference that moved 5.6% since the compared run is said on the line', c == 0 and 'moved +5.6%' in o and 'base_ms 190' in o, o)
c, o = run(room, 'research', 'status', '--as', 'LEAD')
ok('K2 status shows the absolute values of the best and of the baseline', c == 0 and o.count('patch_ms') >= 2, o)
print(f"ok: {ok.__globals__['fails']} failed")
sys.exit(1 if ok.__globals__['fails'] else 0)
