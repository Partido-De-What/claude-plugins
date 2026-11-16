"""1.0, KERN: section K11 of smoke_10_kern.py alone (soft budget, --round confirmed, replica announced, noise advice). Run: python -X utf8 smoke_10_k11.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K11'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
