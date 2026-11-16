"""1.0, KERN: section K9 of smoke_10_kern.py alone. Run: python -X utf8 smoke_10_k9.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K9'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
