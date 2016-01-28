# Place for small plugin archtecture...
import sys
from sungrid import *
# FIXME: Local not working on Windows:
if sys.platform in ('linux', 'darwin'):
	from local import LocalScheduler
from slurm import Slurm
