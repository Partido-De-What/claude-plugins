"""1.0, KERN: sections H3 and H4 of smoke_10_kern.py alone (the "still running" warning, the resource name in the hold texts). Run: python -X utf8 smoke_10_h3.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'H3,H4'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
