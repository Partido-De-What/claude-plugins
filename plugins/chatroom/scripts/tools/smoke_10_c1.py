"""1.0 C1+C2: the models of a quota provider (xKiro, Z.ai) are free when its /usage shows a quota open, and the line before a big
round names the providers skipped for no key and those that failed. Run: python -X utf8 smoke_10_c1.py"""
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = os.environ.get('CHATROOM_SCRIPTS') or str(Path(__file__).resolve().parent.parent)
BASE = Path(tempfile.mkdtemp(prefix='smoke10c1_'))
os.environ['CLAUDE_CONFIG_DIR'] = str(BASE / 'claude')
os.environ['CHATROOM_RELAUNCHED'] = '1'
(BASE / 'claude' / 'chatroom').mkdir(parents=True)
sys.path.insert(0, SCRIPTS)
import httpx  # noqa: E402
import chat  # noqa: E402
from spawn.providers import openai_compat as oc  # noqa: E402
from spawn.catalog import catalog  # noqa: E402

fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{str(info)[:700]}]'), flush=True)
    fails += not cond


class Client:
    def __init__(self, models, usage):
        self.models, self.usage, self.urls = models, usage, []

    def get(self, url, headers=None):
        self.urls.append(url)
        body = self.usage if url.endswith('/usage') else {'data': self.models}
        return httpx.Response(200, json=body)


xk = [{'id': 'claude-x'}, {'id': 'gpt-y'}]            # no prices: the list says nothing of what is free
open_q = {'windows': [{'name': 'day', 'limit_per_day': 500000, 'used': 1200}]}
got = oc.list_models('xkiro', key='k', client=Client(xk, open_q))
ok('xKiro: every model is free while /usage shows a quota open', [m['free'] for m in got] == [True, True], got)
got = oc.list_models('xkiro', key='k', client=Client(xk, {'windows': [{'limit_per_day': 500000, 'used': 500000}]}))
ok('and none when the quota is used up', [m['free'] for m in got] == [False, False], got)
got = oc.list_models('xkiro', key='k', client=Client(xk, {'error': 'x'}))
ok('and none when /usage says nothing', [m['free'] for m in got] == [False, False], got)
c = Client(xk, open_q)
oc.list_models('xkiro', key='k', client=c)
ok('/usage is asked once for the whole list', sum(u.endswith('/usage') for u in c.urls) == 1, c.urls)
got = oc.list_models('zai_api', key='k', client=Client([{'id': 'glm-4.7-flash'}, {'id': 'glm-5.3'}, {'id': 'glm-4.5-FLASH'}], {}))
ok('Z.ai: the flash models are free, the others not', [m['free'] for m in got] == [True, False, True], got)
got = oc.list_models('groq', key='k', client=Client([{'id': 'a'}], {}))
ok('a provider without either rule is as before', got[0]['free'] is True)    # groq: all_free
ok('quota_open reads a nested answer', oc.quota_open({'data': {'windows': [{'limit_per_day': 5, 'remaining': 2}]}}) and not oc.quota_open({'limit_per_day': 5, 'remaining': 0}) and not oc.quota_open([]))
# the catalog keeps the models of a quota provider
cat = catalog.refresh({'providers': {}, 'models': []}, ['xkiro'], lambda pid: oc.list_models(pid, key='k', client=Client(xk, open_q)), now=1000.0)
ok('refresh keeps them (they were all dropped)', len(cat['models']) == 2, cat['models'])

# C2
cat['providers']['groq'] = {'at': 1, 'ok': False, 'error': 'RateLimit: quota of the day is over'}
line = chat.coverage_line(cat, lambda p: p in ('xkiro', 'groq'))
ok('the line says models, routes and providers read', '2 models on 2 routes, 1 providers read' in line, line)
ok('it names the providers skipped for no key, with their count', 'No key, skipped (' in line and 'open_router' in line and 'xkiro' not in line.split('No key')[1].split('Failed')[0], line)
ok('and the one that failed with the reason', 'groq (RateLimit: quota of the day is over)' in line, line)
gone = catalog.refresh({'providers': {}, 'models': []}, ['xkiro'], lambda pid: oc.list_models(pid, key='k', client=Client(xk, {'windows': [{'limit_per_day': 5, 'used': 5}]})), now=1000.0)
line = chat.coverage_line(gone, lambda p: p == 'xkiro')
ok('a quota that is over is named: listed models, no free route', 'no free route' in line and 'xkiro' in line.split('no free route')[1].split('.')[0], line)
print('FAILS', fails)
sys.exit(1 if fails else 0)
