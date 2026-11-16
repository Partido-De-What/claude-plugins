"""1.0, KERN: section K17 of smoke_10_kern.py alone (research wait --runs N, the list finished, the auditor told). Run: python -X utf8 smoke_10_k17.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K17'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
