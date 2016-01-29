# Place for small plugin archtecture...
import sys

# FIXME: Local not working on Windows:
if sys.platform in ('linux', 'darwin', 'win32'):
	from local import LocalScheduler
	from backburner import Backburner

if sys.platform in ('linux',):
	from slurm import Slurm
	from sungrid import *
