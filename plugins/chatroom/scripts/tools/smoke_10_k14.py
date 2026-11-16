"""1.0, KERN: section K14 of smoke_10_kern.py alone (-text on sealed files, research promote). Run: python -X utf8 smoke_10_k14.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K14'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
