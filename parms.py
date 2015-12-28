import os
from const import hafarm_defaults
import json
# import yaml
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
    def __init__(self, copyfrom=None, name='', value=0, type='str', description='', optional=False, *args, **kwargs):
        if not copyfrom:
            self.name = name
            super(Parm, self).__init__(*args, **kwargs)
            super(Parm, self).__setitem__('value', value)
            super(Parm, self).__setitem__('type', str(type))
            # super(Parm, self).__setitem__('class', )
            super(Parm, self).__setitem__('description', description)
            super(Parm, self).__setitem__('optional', optional)
            super(Parm, self).__setitem__('properties', {})
        else:
            self.merge_parms(copyfrom)
            # super(Parm, self).__init__(copyfrom)

    def merge_parms(self, parms_dict):
        """Copies a content of parms_dict into self.
        """
        import copy
        for key, value in parms_dict.iteritems():
            if isinstance(value, type(u'')):
                super(Parm, self).__setitem__(str(key), str(value))  
            elif isinstance(value, type([])):
                super(Parm, self).__setitem__(str(key), list(value))
            elif isinstance(value, type(())):
                super(Parm, self).__setitem__(str(key), tuple(value))
            elif isinstance(value, type("")):
                super(Parm, self).__setitem__(str(key), str(value))
            elif isinstance(value, type({})) and value.keys():
                parm = Parm()
                parm.merge_parms(value)
                super(Parm, self).__setitem__(str(key), parm)
            else:
                super(Parm, self).__setitem__(str(key),copy.deepcopy(value))

    def __setitem__(self, key, value):
        """Custom item setter. Main reason fo it is type checking.
        """
        # assert key in self, "Key %s has to have default in hafarm_defaults" % key
        if key in self.keys():
            # if isinstance(value, type(self[key])):
            super(Parm, self).__setitem__(key, value)
            # else:
                # raise TypeError("Wrong type of value %s: %s" % (key, value))
        else:
            if issubclass(type(value), Parm): 
                pass
            if not 'properties' in self.keys():
                super(Parm, self).__setitem__('properties', {})
            super(Parm, value).__setitem__('parent', self)
            self['properties'][key] = value

    def __getitem__(self, key):
        if key in self.keys():
            if key != 'value':
                return super(Parm, self).__getitem__(key)
            else:
                print "self.eval()"
                return self.eval()
        else:
            properties = super(Parm, self).__getitem__('properties')
        print 'return properties[key]'
        return properties[key].eval()

    def eval(self, context=None):
        def find_key(key): pass

        value = super(Parm, self).__getitem__('value')
        if isinstance(value, type('')):
            if value.startswith('$'):
                value = value.strip("$")
                if not context:
                    value = os.getenv(value, 'not set.')
                else:
                    if value in context.keys():
                        value = context[value]
            elif value.startswith('@') and value.endswith("/>"):
                value = None

        _type = getattr(__builtin__, self['type'])
        value = _type(value)
        return value

    def __repr__(self):
        return json.dumps(self, indent=4, check_circular=False)
        # return yaml.dump(self)

    def load(self, filename):
        with open(filename) as file:
            parms = json.load(file)
            self.merge_parms(parms)
            return True
        return

    def add_properties(self, properties):
        for p in properties:
            p.parent = self
            self['properties'][p.name] = p




if __name__ == "__main__":
    JSON_FILE = './test.json'
    YAML_FILE = './test.yaml'
    a = array.array('f', range(3))
    scene = Parm(name='hafarm_job', value='test_job', type='str', description='Parameters controling job.')
    user  = Parm(name='user', value='$USER', type='str', description='Owner of the job.' )
    start = Parm(name='start_frame', value=1, type='int', description='Start frame of jobs tasks' )
    end   = Parm(name='end_frame', value=48, type='int', description='End frame of jobs tasks' )
    com   = Parm(name='command', value='ls', type='str', description='Command to be executed' )
    arg   = Parm(name='command_arg', value=['-la', '/tmp'], type='list', description='Command arguments to be executed.' )
    pos   = Parm(name ='position', value=[1.2,2.2,3.3], type='list')
    ran   = Parm(name='frame_range', vale=['-f', ' ', '@START_FRAME/>', '-', '@END_FRAME/>'])
    # pos['value'] = a

    scene.add_properties((user, start, end, com, arg, pos))
    # print e
    # print scene['user']
    # test = Parm(copyfrom=scene)
    # test['value'] = 'DDDDD'
    # print scene['value']
    # print test['value']

    # print scene

    scene['user'] = 'ktos'
    print scene['user']

    with open(JSON_FILE, 'w') as file:
        # json.dump(scene, file)
        file.write(scene.__repr__())

    scene = Parm()
    scene.load(JSON_FILE)
    # print scene
    # print scene.keys()
    # print a
    # with open(JSON_FILE) as file:
    #     # print file.read()
    #     scene = yaml.load(file.read())
    #     print scene
# # print scene





# class HaFarmParms(dict):
#     """Render manager agnostic job's parameters container.
#     """
#     def __init__(self, initilize=False, defaults=hafarm_defaults):
#         super(HaFarmParms, self).__init__()
#         from uuid import uuid4
#         self.id = uuid4()

#         # Init with defaults:
#         self.merge_parms(defaults)

#         # Set parms unrelated to host, like jobname, user etc:
#         if initilize:
#             self.initialize_env_parms()

#     def __setitem__(self, key, value):
#         """Custom item setter. Main reason fo it is type checking.
#         """
#         assert key in hafarm_defaults, "Key %s has to have default in hafarm_defaults" % key
#         if isinstance(value, type(hafarm_defaults[key])):
#             super(HaFarmParms, self).__setitem__(key, value)
#         else:
#             raise TypeError("Wrong type of value %s: %s" % (key, value))

#     def initialize_env_parms(self):
#         """Parameters to be derived without touching host app and not having defaults.
#         """
#         self['job_asset_name'] = os.getenv("JOB_ASSET_NAME", 'Not_Set')
#         self['job_asset_type'] = os.getenv("JOB_ASSET_TYPE", 'Not_Set')
#         self['job_current']    = os.getenv("JOB_CURRENT", 'Not_Set')
#         self['user']           = os.getenv("USER", 'Not_Set')

#     def merge_parms(self, parms_dict):
#         """Copies a content of parms_dict into self.
#         """
#         import copy
#         for key, value in parms_dict.iteritems():
#             if isinstance(value, type(u'')):
#                 self[str(key)] = str(value)
#             elif isinstance(value, type([])):
#                 self[str(key)] = list(value)
#             elif isinstance(value, type(())):
#                 self[str(key)] = tuple(value)
#             elif isinstance(value, type("")):
#                 self[str(key)] = str(value)
#             else:
#                 self[str(key)] = copy.deepcopy(value)


#     def has_entry(self, entry):
#         if entry in self.keys():
#             return True
#         return


