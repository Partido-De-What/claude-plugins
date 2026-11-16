"""1.0, KERN: section K2B of smoke_10_kern.py alone (--info/--reference at init, the info column of results.tsv). Run: python -X utf8 smoke_10_k2b.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K2B'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
