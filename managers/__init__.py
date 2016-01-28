# Place for small plugin archtecture...
import sys
from sungrid import *

# FIXME: Local not working on Windows:
if sys.platform in ('linux', 'darwin', 'win32'):
	from local import LocalScheduler
from slurm import Slurm
