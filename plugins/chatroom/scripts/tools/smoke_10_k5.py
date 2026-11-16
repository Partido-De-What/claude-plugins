"""1.0, KERN: section K5 of smoke_10_kern.py alone (a queued run the machine cannot take waits and retries). Run: python -X utf8 smoke_10_k5.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K5'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
