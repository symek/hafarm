import os
from const import hafarm_defaults
import json
import yaml
import __builtin__
import gc
import array

# Python 2.6 compatibility:
try:
    from collections import OrderedDict, defaultdict
except ImportError:
    from ordereddict import OrderedDict

"""
TODO:
- Serlize on disk both __builtin__ and custom types;
- Evaluate values using key words from a graph parms (use nested items to evaluate @KEYWORD/>)
- Use registed methods to evaluate values (with @/> syntax?)
- Access to default and current values?
- Use for both hafarm parms and exchange format?
"""



class Parm(dict):
    def __init__(self, copyfrom=None, name='', value=0, type='str', description='', 
        optional=False, post_action=None, context=None, *args, **kwargs):
        if not copyfrom:
            self.name = name
            self.context = context
            self.post_action = post_action
            super(Parm, self).__init__(*args, **kwargs)
            super(Parm, self).__setitem__('value', value)
            super(Parm, self).__setitem__('type', str(type))
            # super(Parm, self).__setitem__('class', )
            super(Parm, self).__setitem__('description', description)
            super(Parm, self).__setitem__('optional', optional)
            super(Parm, self).__setitem__('properties', {})
        else:
            self.merge_parms(copyfrom)

    def merge_parms(self, parms_dict):
        """Copies a content of parms_dict into self.
        """
        import copy
        for key, value in parms_dict.iteritems():
            if isinstance(value, type(u'')):
                super(Parm, self).__setitem__(str(key), str(value))  
            elif isinstance(value, type("")):
                super(Parm, self).__setitem__(str(key), str(value))
            elif isinstance(value, type([])):
                super(Parm, self).__setitem__(str(key), list(value))
            elif isinstance(value, type(())):
                super(Parm, self).__setitem__(str(key), tuple(value))
            elif isinstance(value, type({})) and value.keys():
                parm = Parm()
                parm.merge_parms(value)
                super(Parm, self).__setitem__(str(key), parm)
            else:
                super(Parm, self).__setitem__(str(key), value)
            
    def __setitem__(self, key, value):
        """Custom item setter. Main reason fo it is type checking.
        """
        if key in self.keys():
            super(Parm, self).__setitem__(key, value)
        else:
            if not 'properties' in self.keys():
                super(Parm, self).__setitem__('properties', {})
            if not issubclass(type(value), Parm): 
                parm = Parm()
            self['properties'][key] = parm
            self['properties'][key]['value'] = value

    def __getitem__(self, key):
        """ Dictionary-like getter. Except:
            (a) keys not present in self are passed down to 'properties' dict. 
            (b) items are evaluted with eval() method, not returned 'as-is'.
        """
        if key in self.keys():
            if key != 'value':
                return super(Parm, self).__getitem__(key)
            else:
                return self.eval(context=self.context)
        else:
            properties = super(Parm, self).__getitem__('properties')
        return properties[key].eval(parent=self, context=self.context)

    def get(self, key):
        """ Get raw value by key, not evaluated as in __getitem__.
        """
        if key in self.keys():
            return super(Parm, self).__getitem__(key)
        else:
            properties = super(Parm, self).__getitem__('properties')
        return properties[key]

    def eval(self, parent=None, context=None):
        """ Evaluate key:
            (a) lists/tuples and singles are treated differntly
            (b) $value are evaluated as env. variables.
            (c) envirmental variables can be overwritten with context dict.
            (d) @value/> are evaluted as self's keys overwrite.
            (e) values area strongly typed (according to type='')
            (f) todo: allow non-builtin types ?
        """
        
        def find_key(key): 
            pass
        def eval_value(value, parent, context): 
            if isinstance(value, (type(''), type(u''))):
                value = str(value)
                if value.startswith('$'):
                    value = value.strip("$")
                    if not context:
                        value = os.getenv(value, 'not set.')
                    else:
                        if value in context.keys():
                            value = context[value]
                elif value.startswith('@') and value.endswith("/>"):
                    key = value[1:-2].lower()
                    if key in parent['properties'].keys():
                        value = parent[key]
            _type = getattr(__builtin__, self['type'])
            value = _type(value)
            return value
        
        # Start:
        value = super(Parm, self).__getitem__('value')
        # TODO: Make it plug-able: the logic of how to deal
        # with different types of values. Here: lists and single
        # items are eval_value'd(). Lists of strings are concatanted
        # Is this usual scenario? What to do in case of list(floats)?
        if isinstance(value, (type([]),type(()))):
            value = [eval_value(v, parent, context) for v in value]
            # NOTE: hard-coded logic?
            if self['type'] == 'str':
                value = "".join([str(x) for x in value])
        else:
            value = eval_value(value, parent, context)
        return value

    def __repr__(self):
        return json.dumps(self, indent=4, check_circular=False)
        # return yaml.dump(self)

    def load(self, filename, context=None):
        with open(filename) as file:
            parms = json.load(file)
            self.merge_parms(parms)
            self.context= context
            return True
        return

    def add_properties(self, properties):
        # NOTE: tmp solution;
        for p in properties:
            self['properties'][p.name] = p




if __name__ == "__main__":
    JSON_FILE = './test.json'

    scene = Parm(name='hafarm_job', value='test_job', type='str', description='Parameters controling job.')
    user  = Parm(name='user', value='$USER', type='str', description='Owner of the job.' )
    start = Parm(name='start_frame', value=1, type='int', description='Start frame of jobs tasks' )
    end   = Parm(name='end_frame', value=48, type='int', description='End frame of jobs tasks' )
    com   = Parm(name='command', value='ls', type='str', description='Command to be executed' )
    arg   = Parm(name='command_arg', value=['-la', " ",'@DIR/>'], type='str', description='Command arguments to be executed.' )
    pos   = Parm(name ='position', value=[1.2], type='float', description='World origin.')
    pos   = Parm(name ='dir', value='/tmp', type='str', description='tmp dir')
    ran   = Parm(name='frame_range', value=['-f', ' ', '@START_FRAME/>', '-', '@END_FRAME/>'], type='str')
   

    scene.add_properties((user, start, end, com, arg, pos, ran))
   
    context = {'USER': 'KTOSTAM', 'start_frame':30}
    print scene['user']
    print scene['frame_range']
    print scene['command_arg']
    # print scene['position']
    # print type(scene.get('position'))
    # print scene['user']

    with open(JSON_FILE, 'w') as file:
        # json.dump(scene, file)
        file.write(scene.__repr__())

    scene = Parm()
    scene.load(JSON_FILE, context)
    print scene['user']
    print scene['frame_range']
    # print scene['position']
    # print scene.get('position')
    # print type(scene.get('position'))
    # print scene.get('frame_range')
    # print scene
  


