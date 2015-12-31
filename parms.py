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
    def __init__(self, copyfrom=None, name='', value=0, type='str', description='', 
        optional=False, post_action=None, context=None, parent=None, *args, **kwargs):
        if not copyfrom:
            self.name = name
            self.parent = parent
            self.context = context
            self.post_action = post_action
            super(Parm, self).__init__(*args, **kwargs)
            super(Parm, self).__setitem__('value', value)
            super(Parm, self).__setitem__('type', str(type))
            # super(Parm, self).__setitem__('class', )
            # super(Parm, self).__setitem__('description', description)
            # super(Parm, self).__setitem__('optional', optional)
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
        if key in self.keys():
            super(Parm, self).__setitem__(key, value)
        else:
            if issubclass(type(value), Parm): 
                pass
            if not 'properties' in self.keys():
                super(Parm, self).__setitem__('properties', {})
            # super(Parm, self).__setitem__('parent', self)
            self['properties'][key]['value'] = value

    def __getitem__(self, key):
        if key in self.keys():
            if key != 'value':
                return super(Parm, self).__getitem__(key)
            else:
                return self.eval()
        else:
            properties = super(Parm, self).__getitem__('properties')
        return properties[key].eval()

    def get(self, key):
        if key in self.keys():
            return super(Parm, self).__getitem__(key)
        else:
            properties = super(Parm, self).__getitem__('properties')
        return properties[key]

    def eval(self, context=None):
        if not context:
            if not self.context:
                if self.parent:
                    if self.parent.context:
                        context = self.parent.context
            else:
                context = self.context
        def find_key(key): pass
        def eval_value(value, context): 
            if isinstance(value, type('')):
                if value.startswith('$'):
                    value = value.strip("$")
                    if not context:
                        value = os.getenv(value, 'not set.')
                    else:
                        if value in context.keys():
                            value = context[value]
                elif value.startswith('@') and value.endswith("/>"):
                    key = value[1:-2].lower()
                    if key in self.parent['properties'].keys():
                        value = self.parent[key]
            _type = getattr(__builtin__, self['type'])
            value = _type(value)
            return value
        print context
        value = super(Parm, self).__getitem__('value')
        if isinstance(value, type([])):
            value = [eval_value(v, context) for v in value]
            if self['type'] == 'str':
                value = "".join([str(x) for x in value])
        else:
            value = eval_value(value, context)
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
    pos   = Parm(name ='position', value=[1.2,2.2,3.3], type='float', description='World origin.')
    ran   = Parm(name='frame_range', value=['-f', ' ', '@START_FRAME/>', '-', '@END_FRAME/>'], type='str')
    # pos['value'] = a

    scene.add_properties((user, start, end, com, arg, pos, ran))
    # print e
    # print scene['user']
    # test = Parm(copyfrom=scene)
    # test['value'] = 'DDDDD'
    # print scene['value']
    # print test['value']

    # print scene

    # scene['user'] = '$USER'
    # print scene['user']
    # x = scene.get('user')
    # print type(x.parent)
    context = {'USER': 'KTOSTAM'}
    # scene.context = context
    print scene['frame_range']
    print scene['position']
    print scene.get('position')
    # print scene['user']

    with open(JSON_FILE, 'w') as file:
        # json.dump(scene, file)
        file.write(scene.__repr__())

    scene = Parm()
    scene.load(JSON_FILE, context)
    print scene
    print scene['user']
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


