"""1.0, KERN: section(s) K8S of smoke_10_kern.py alone. Run: python -X utf8 smoke_10_k8s.py"""
import os
import runpy
from pathlib import Path

os.environ['ONLY'] = 'K8S'
runpy.run_path(str(Path(__file__).with_name('smoke_10_kern.py')), run_name='__main__')
