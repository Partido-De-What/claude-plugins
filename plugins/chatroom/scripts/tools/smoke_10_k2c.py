"""1.0, KERN: section K2C of smoke_10_kern.py alone (a challenger near the best while the reference arm moved: the best is measured again in the same run). Run: python -X utf8 smoke_10_k2c.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K2C'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
