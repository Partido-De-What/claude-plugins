"""1.0.1: a host that says the model does not exist (404) is taken off the model like one that says 410; a 404 of a wrong
address is not. Run: python -X utf8 smoke_101_gone.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spawn import errors  # noqa: E402

fails = 0


def ok(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else f'  [{info}]'), flush=True)
    fails += not cond


def gone(status, body):
    return errors.classify(status, body).model_gone


ok('410 Gone', gone(410, 'Gone'))
ok('404 "model does not exist" (xKiro)', gone(404, '{"error":{"message":"The model `qwen/qwen3.7-max:free` does not exist"}}'))
ok('404 "model not found"', gone(404, '{"error": "model qwen3-vl-plus not found"}'))
ok('404 "unknown model"', gone(404, 'unknown model: foo'))
ok('404 of a wrong address is not a gone model', not gone(404, '<html>404 page not found</html>'))
ok('404 with no text is not a gone model', not gone(404, ''))
ok('a 429 is not a gone model', not gone(429, 'the model does not exist in your quota'))
ok('a 500 is not a gone model', not gone(500, 'model not found in cache'))
print(f'fails {fails}')
sys.exit(1 if fails else 0)
