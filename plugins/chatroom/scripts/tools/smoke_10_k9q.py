"""1.0, KERN: section K9Q of smoke_10_kern.py alone (a probe through the queue runner). Run: python -X utf8 smoke_10_k9q.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K9Q'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
