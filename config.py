import sys, os
from ConfigParser import SafeConfigParser, RawConfigParser
from collections import OrderedDict

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
            configs = glob(os.path.join(path, "*.conf"))
            self.read(configs)

    def __getitem__(self, section):
        """ Returns a dictionary of options from a section.
        """
        if self.has_section(section):
            conf = OrderedDict()
            for option in self.options(section):
                conf[option] = self.get(section, option)
            return conf






