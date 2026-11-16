"""1.0, KERN: sections K10 and K18 of smoke_10_kern.py alone (class and level, shelved ideas, dry-eval). Run: python -X utf8 smoke_10_k10.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K10,K18'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
