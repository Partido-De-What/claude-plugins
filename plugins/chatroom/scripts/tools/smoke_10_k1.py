"""1.0, K1: `research reseal --reason` reopens the drafting after a baseline, with the history kept, so that a faulty
evaluator can be corrected through the usual gates (smoke, seal, a new baseline). Run: python -X utf8 smoke_10_k1.py"""
import json
import os
import runpy
import sys
from pathlib import Path

src = Path(__file__).with_name('smoke_10_kern.py')        # the helpers of the kernel smoke: its text up to the first section
k = {'__file__': str(src), '__name__': 'helpers'}
exec(compile(src.read_text(encoding='utf-8').split("if section('K3'):")[0], str(src), 'exec'), k)
ok, run, research_room = k['ok'], k['run'], k['research_room']


def state(room):
    return json.loads((room / 'research' / 'state.json').read_text(encoding='utf-8'))


room, repo, work = research_room('k1')
c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
ok('K1 baseline kept', c == 0 and 'KEEP' in o, o)
(work / 'program.py').write_text('X = 3\n')
c, o = run(room, 'research', 'evaluate', '--desc', 'X 3', '--as', 'W')
ok('K1 an attempt kept', c == 0 and 'KEEP' in o, o)
before = state(room)

c, o = run(room, 'research', 'amend', '--evaluate', f'"{sys.executable}" eval.py --v2', '--as', 'LEAD')
ok('K1 amend of the evaluator after a baseline is refused, and names reseal', c != 0 and 'reseal' in o, o)
c, o = run(room, 'research', 'reseal', '--as', 'LEAD')
ok('K1 reseal without a reason is refused', c != 0 and 'reason' in o, o)
c, o = run(room, 'research', 'reseal', '--reason', 'x', '--as', 'W')
ok('K1 reseal by a worker is refused', c != 0, o)
c, o = run(room, 'research', 'reseal', '--reason', 'the coherence check kills honest gains over 40%', '--as', 'LEAD')
st = state(room)
ok('K1 reseal goes back to drafting', c == 0 and st['phase'] == 1 and st['best'] is None and st['baseline'] is None, o)
ok('K1 history kept: same runs, stamped era 1', len(st['attempts']) == len(before['attempts']) and all(a.get('era') == 1 for a in st['attempts']),
   [(a['n'], a.get('era')) for a in st['attempts']])
ok('K1 reseal recorded with its reason and the old best', st.get('era') == 2 and st['reseals'][0]['best']['n'] == before['best']['n']
   and 'coherence' in st['reseals'][0]['reason'], st.get('reseals'))
ok('K1 the run count is not reset', st['evals'] == before['evals'], (st['evals'], before['evals']))

c, o = run(room, 'research', 'amend', '--evaluate', f'"{sys.executable}" eval.py', '--as', 'LEAD')
ok('K1 the evaluator can be amended now', c == 0, o)
c, o = run(room, 'research', 'status', '--as', 'LEAD')
ok('K1 status says the earlier runs belong to another era', c == 0 and 'era 2' in o, o)
c, o = run(room, 'research', 'evaluate', '--desc', 'evaluator corrected', '--as', 'W')
ok('K1 a run in the reopened drafting is a smoke, not an attempt', c == 0 and 'SMOKE' in o and state(room)['evals'] == before['evals'], o)
c, o = run(room, 'research', 'seal', '--as', 'LEAD')
ok('K1 the usual seal closes the drafting again', c == 0 and state(room)['phase'] == 2, o)
c, o = run(room, 'research', 'evaluate', '--desc', 'baseline', '--as', 'W')
st = state(room)
ok('K1 a new baseline is measured and kept', c == 0 and 'KEEP' in o and st['baseline'] and st['baseline']['n'] > before['best']['n'], o)
ok('K1 the new runs carry no old era', [a.get('era') for a in st['attempts'] if a['n'] == st['baseline']['n']] == [None], st['attempts'][-1])
fails = ok.__globals__['fails']                           # the helpers count in their own module
print(f'ok: {fails} failed')
sys.exit(1 if fails else 0)
