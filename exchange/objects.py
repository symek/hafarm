import abc
from collections import defaultdict
import plistlib
import os
import importlib

# Softimage Python 2.5.2 limitation
import sys
if sys.version_info < (2,6,0):
        import simplejson as json
else:
        import json



class Config(dict):
    '''Temporary wrapper for configuring environment.'''
    def __init__(self):
        self['path'] = '/STUDIO/scripts/'




class XForm(defaultdict):
    def __init__(self):
        self.samples = []

    def __len__(self):
        return len(self.samples)

# Test:
class CustomMetaclass(type):
    def __init__(cls, name, bases, dct):
        print "Creating class %s using CustomMetaclass" % name
        super(CustomMetaclass, cls).__init__(name, bases, dct)


class ExObjectBase(defaultdict):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.load_schema()

    def __repr__(self):
        v = ["%s: %s" % (key, self[key]) for key in self.keys()]
        return "<%s %s>" % (self.__class__.__name__, v)

    @abc.abstractproperty
    def kind(self):
        return None

    @abc.abstractmethod
    def parse_object(self, obj):
        '''Triggers convertion from host app object into Exchange version.'''
        return

    @abc.abstractmethod
    def apply_object(self):
        '''Triggers conversion from Exchange object into host specific one.'''
        return

    ##########################################################################

    
    def build_operators_list(self, module=None):
        operators = {}
        if not module:
            module = importlib.import_module(self.__module__)
            print module
        for clsname in dir(module):
            cls = getattr(module, clsname)
            if hasattr(cls, 'kind') and clsname != 'ExObjectBase':
                operators[cls().kind] = clsname
        self.operators = operators
        return operators

    def load_schema(self, file=None):
        '''Load Schema from plist file and applies as dictionary with default values.'''
        # By default schema file have the same name as class. 
        # FIXME: Don't hard code config here. We need location hierarchy defined by env. var.
        # with cascade of location overwriting each other, so different project could have 
        # different schemas.
        # TODO: Schemas should accumulate!
        if not file:
            file = os.path.join('/STUDIO/studio-packages/ha/exchange/config', self.__class__.__name__ +'.xml')
            if os.path.isfile(file):
                plist = plistlib.readPlist(file)
            else:
                plist = {}

        # Copies schema keys onto object. 
        for key in plist:
            self[key] = plist[key]

    def publish(self, state=None):
        '''Pushes an object into pipeline. This possibly implies a series of action from saving file on disk, 
        to logging an action into database, motifying supervisors or Tactic/Shotgun etc.'''
        return

    
    def dump_to_file(self, filename):
        try:
            file = open(filename, 'w')
            s = {'kind': self.kind, 'class': self}
            json.dump(s, file, indent=4)
            file.close()
            return True
        except:
            print "Can't save %s" % filename
            return False

    def load_from_file(self, filename):
        try:
            file = open(filename, 'r')
            _dict = json.load(file)
            file.close()
            for key in _dict.keys():
                self[key] = _dict[key]
            return True
        except:
            print "Can't open %s" % filename
            return False


def main():
    for cls in ExObjectBase.__subclasses__():
        print cls

if __name__ == '__main__': main()


