"""1.0, KERN: section K15 of smoke_10_kern.py alone (the recon: draft ideas and a recon worker in phase 1, the lead's gate). Run: python -X utf8 smoke_10_k15.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K15'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
