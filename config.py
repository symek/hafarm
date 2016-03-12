import sys, os
from ConfigParser import SafeConfigParser, RawConfigParser

HAFARM_PATH = os.getenv("HAFARM_PATH", os.getenv("HAFARM_HOME",""))

class Config(SafeConfigParser):
    def __init__(self, *args, **kwargs):
        ''' Read in configuration stored in multiply files
            and locations.
        '''
        SafeConfigParser.__init__(self, *args, **kwargs)

    def setup(self):
        from glob import glob
        paths = HAFARM_PATH.split(":")
        for path in paths:
            configs = glob(os.path.join(path, "*.cfg"))
            self.read(configs)


