"""1.0, KERN: section K16 of smoke_10_kern.py alone (final dry run on demand, per-run artifacts). Run: python -X utf8 smoke_10_k16.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K16'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
