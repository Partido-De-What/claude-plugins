"""1.0, KERN: section H2 of smoke_10_kern.py alone (a holder that fell releases the GPU hold). Run: python -X utf8 smoke_10_h2.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'H2'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
