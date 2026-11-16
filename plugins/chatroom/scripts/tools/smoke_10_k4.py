"""1.0, KERN: section K4 of smoke_10_kern.py alone (a run that dies with the machine is invalid). Run: python -X utf8 smoke_10_k4.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K4'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
