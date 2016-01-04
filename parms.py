import os
from const import hafarm_defaults
import json
import yaml
import __builtin__
import gc
import array
import re
import fnmatch # Should we simply use re instead?
__SEPARATOR__ = '/'

# Python 2.6 compatibility:
try:
    from collections import OrderedDict, defaultdict
except ImportError:
    from ordereddict import OrderedDict

"""
TODO:
+ Serlize on disk both __builtin__ and Parm type.;
+ Evaluate values using key words from a graph parms (use nested items to evaluate @KEYWORD/>)
+ Use registed methods to evaluate values (with @/> syntax?)
- Access to default and current values?
- Use for both hafarm parms and exchange format?
"""



class Parm(dict):
    def __init__(self, copyfrom=None, name='', value=0, type='str', description='', 
        optional=False, post_action=None, context=None, initilize=False, *args, **kwargs):
        if not copyfrom:
            self.context = context
            super(Parm, self).__init__(*args, **kwargs)
            super(Parm, self).__setitem__('value', value)
            super(Parm, self).__setitem__('type', str(type))
            super(Parm, self).__setitem__('description', description)
            super(Parm, self).__setitem__('properties', OrderedDict())
            # TODO: This is bad thing. Used only in add_properties()?,
            # We should remove that or make something like '.private' 
            # dict items perhpas
            self.name = name
            # self.post_action = post_action
            # super(Parm, self).__setitem__('class', )
            # super(Parm, self).__setitem__('optional', optional)
            # TODO: configure it.
            if initilize:
                self.initialize()
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
                parm = Parm(init=False)
                parm.merge_parms(value)
                super(Parm, self).__setitem__(str(key), parm)
            else:
                super(Parm, self).__setitem__(str(key), value)

    def initialize(self, default=None): 
        '''Load default settings. Not implemented.'''
        path = os.getenv("HAFARM_HOME", "./")
        defaults  = 'defaults.json'
        defaults = os.path.join(path, defaults)
        if os.path.isfile(defaults):
            self.load(defaults)
            return True
        return
            
    def __setitem__(self, key, value):
        """Custom item setter. Main reason fo it is type checking.
        """
        if key in self.keys():
            super(Parm, self).__setitem__(key, value)
        else:
            if not 'properties' in self.keys():
                super(Parm, self).__setitem__('properties', {})
            if not issubclass(type(value), Parm):
                # FIXME: Extend this logic.  
                # print 'issubclass(type(value, Parm)'
                # parm = Parm()
            # self['properties'][key] = parm
                pass
            if not key in self['properties']:
                raise KeyError("Can't add non-default keys to Parm class.")
            self['properties'][key]['value'] = value

    def __getitem__(self, key):
        """ Dictionary-like getter. Except:
            (a) keys not present in self are passed down to 'properties' dict. 
            (b) items are evaluted with eval() method, not returned 'as-is'.
            (c) keys can be path-like key/nestedkey for access to nested parms.
        """
        if key in self.keys():
            if key != 'value':
                return super(Parm, self).__getitem__(key)
            else:
                return self.eval(context=self.context)
        else:
            properties = super(Parm, self).__getitem__('properties')
            if __SEPARATOR__ in key:
                parts = key.split(__SEPARATOR__)
                key, parts = parts[0], __SEPARATOR__.join(parts[1:])
                return properties[key][parts]
            else:
                assert key in properties.keys()
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
            (d) @value/> are evaluated as self's keys overwrite.
            (e) values area strongly typed (according to type='')
            (f) todo: allow non-builtin types ?
            (g) allow @*/> (wild cards / pattern matching.)
        """
        
        def find_key(key): 
            pass
        def eval_variable(value, context):
            '''Evalute variable on env or provided context.'''
            key = value.strip("$")
            # NOTE: atm we leave variable unexpanded on fail:
            if not context:
                value = os.getenv(key, value)
            else:
                if key in context.keys():
                    value = context[key]
            return value
            
        def eval_value(value, parent, context): 
            ''' Evaluate value possibly with $v or @v syntax. In general case
                we have here single item (world or digit), but by using globing
                @foo*/> this can evaluate to list of keys. This list will be then
                flattend back in eval().
            '''
            if isinstance(value, (type(''), type(u''))):
                value = str(value)
                path = False
                # Environmental variables pass:
                # NOTE: special treatment for paths with embedded $variables
                if '$' in value:
                    elements = value.split(os.path.sep)
                    path     = [eval_variable(v, context) for v in elements]
                    value    = os.path.sep.join(path)
                # Local overwrites pass:
                elif value.startswith('@') and value.endswith("/>"): #TODO: opt. with re
                    # NOTE: UPPER/lower stricly speaking we don't need this.
                    # but we could make it usful by making: @UPPER/> overwrites upper->down
                    # policy and @lower/> with lower->up policy?
                    key = value[1:-2].lower()
                    if key in parent['properties'].keys():
                        value = parent[key]
                    # Embedded overwrites pass (with pattern matching...):
                    else:
                        keys = fnmatch.filter(self['properties'].keys(), key)
                        return [eval_value(self['properties'][k].eval(self, context),\
                         parent, context) for k in keys]

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
            # NOTE: Flatening sublists isn't very general, but eval_value might return
            # lists itself if @foo*/> syntax was applied.
            value = [item for sublist in value for item in sublist]
            # NOTE: hard-coded logic?
            # NOTE: I don't know what to do with " " vs. "" scenario...
            if self['type'] == 'str':
                value = "".join([str(x) for x in value])
        else:
            value = eval_value(value, parent, context)
        return value

    def __repr__(self):
        return json.dumps(self, indent=4, check_circular=False)

    def __yaml__(self):
        return yaml.dump(self)

    # def __str__(self):
        # return zip(self['properties'].keys(), self['properties'].values())

    def load(self, filename, context=None):
        with open(filename) as file:
            parms = json.load(file, object_pairs_hook=OrderedDict)
            self.merge_parms(parms)
            self.context= context
            return True
        return

    def dump(self, filename):
        with open(filename, 'w') as file:
            file.write(self.__repr__())

    def add_properties(self, properties):
        # NOTE: tmp solution;
        for p in properties:
            self['properties'][p.name] = p

# FIXME: tmp
HaFarmParms = Parm

if __name__ == "__main__":
    path = os.getenv("HAFARM_HOME", "./")
    JSON_FILE = os.path.join(path, './defaults.json')

    # TODO: Group parms into logical sets. 
    scene = Parm(name='hafarm_job',  value='test_job', type='str',   description='Parameters controling job.')
    start = Parm(name='start_frame', value=1,          type='int',   description='Start frame of jobs tasks.' )
    end   = Parm(name='end_frame',   value=48,         type='int',   description='End frame of jobs tasks.' )
    step  = Parm(name='step_frame',  value=1,          type='int',   description='Step frame of jobs tasks.' )
    queue = Parm(name='queue',       value='3d',       type='str',   description='Queue to be used.' ) #  FIXME: This should be list?
    group = Parm(name='group',       value=[],         type='str',   description='Group of the machinges to be used (subset of queue).' )
    slots = Parm(name='slots',       value=-1,         type='int',   description='Machinges slots to be taken, usually cores.' )
    cpu_s = Parm(name='cpu_share',   value=1.0,        type='float', description='Controls multithreading based on percentage of avaiable resources (cpus).' )
    prior = Parm(name='priority',    value=-500,       type='int',   description="Job priority. User cannot have more then 0, with range -1024:0 to control own jobs' priorities" )
    req_m = Parm(name='req_memory',  value=4,          type='int',   description='Request minimal RAM amount for job to start on.' )
    hold  = Parm(name='job_on_hold', value=False,      type='bool',  description="Don't start execution of submitted job." )
    hjid  = Parm(name='hold_jid',    value=[],         type='list',  description='List of job dependencies.')
    hjida = Parm(name='hold_jid_ad', value=[],         type='list',  description='List of array jobs with inter-dependencies.' )
    # target_list and layer_list are something like command_arg_optinal. They either don't have to be here at all
    # (being a part of command_arg in fact), or they should be implemented as general procedure of extending
    # command_arg with modifiers. Atm they are added to command_arg by client class in pre_schedule() what doesn't
    # make much sense. If we really need them (do we?), they could use @/> syntax to indicate, they're meant to
    # be placed somewhere and provide them inside command_arg properties?  
    # So now use: $foo   for overwrites with env.var. 
    #             @foo/> for overwrites with own keys.
    #             ?foo? for overwrites with embedded keys? 
    #             ... or we should simply look recurcively for @foo/>?
    # in which order? Seems logical that the user would rather properties 
    # key to overwrite higher level key upper<lower.
    # 

    # targets, leyers are extensions to command 
    targets  = Parm(name='target_list', value=[],    type='str',  description='Comman line modifier: used in applications with multiply targets (cameras in Maya batch, Write node in Nuke).' )
    layers   = Parm(name='layer_list',  value=[],    type='str',  description='Command like modifier: a subset of scene to be rendered (used by Maya, in Houdini it would be takes or bundles for example.)' )
    command  = Parm(name='command',     value='',    type='str',  description='Command, usually binary or script to be executed.' )
    comm_arg = Parm(name='command_arg', value=[],    type='str',  description='Command arguments to be passed to binary.' )
    # 
    emails   = Parm(name='email_list',  value=[],    type='str',  description='Email addresses to motify.')
    proxy    = Parm(name='make_proxy',  value=False, type='bool', description='Hint for forthcomming pipeline to make proxy from output_picture.')
    # hafarm's settings:
    jname    = Parm(name='job_name',    value="",    type='str',  description='Unique job name usually provided with hafarm.generate_unique_job_name.')
    log_path = Parm(name='log_path',    value="$JOB/render/sungrid/log",       type='str', description='Path to logs to be saved.')
    scripts  = Parm(name='script_path', value="$JOB/render/sungrid/jobScript", type='str', description='Path for execution scripts.')
    scenefile= Parm(name='scene_file',  value="",      type='str', description='File to execute by binary specified by command.')
    user     = Parm(name='user',        value='$USER', type='str', description='Owner of the job.' )
    # TODO: These should be jobs' variables stored in own space (parm's subspace)
    asset_name  = Parm(name='job_asset_name', value="$JOB_ASSET_NAME", type='str', description='Studio specific variable.')
    asset_type  = Parm(name='job_asset_type', value="$JOB_ASSET_TYPE", type='str', description='Studio specific variable.')
    jobcurrent  = Parm(name='job_current',    value="$JOB_CURRENT",    type='str', description='Studio specific variable.')

    # TODO: scheduler controlers
    rerun     = Parm(name='rerun_on_error',  value=True,  type='bool',  description='Rerun if job fails.')
    ignore    = Parm(name='ignore_check',    value=False, type='bool',  description='Ignore check if machine is in use.')
    req_start = Parm(name='req_start_time',  value=0.0,  type='float', description='Absolute epoch (sec) when job should be set to unhold.')
    include   = Parm(name='include_list',value=[], type='str', description='Explicite list of machines to be used.')
    exclude   = Parm(name='exclude_list',value=[], type='str', description='Explicite list of machines to be excluded from use.')
    
    sub_time   = Parm(name='submission_time', value=0.0,  type='float', description='Set when job is submitted.')
    req_res    = Parm(name='req_resources',   value=[],   type='str',   description='Requested cluster resources.')
    req_lic    = Parm(name='req_license',     value=[],   type='str',   description='Requested licenses avaiable on the cluster.')

    # TODO: outputs should have special logic for file resources ()
    # It could be implameted via type, instead of 'list' we may support custom types, like Resource()
    outputs    = Parm(name='output_picture',  value=[],     type='list',   description='List of output files from the job.')
    inputs     = Parm(name='intputs_files',   value=[],     type='list',   description='List of input files for the job (requested disk resources.)')
    frange     = Parm(name='frame_range',     value=['-f', ' ', '@START_FRAME/>', '-', '@END_FRAME/>'], type='str', description='Appliction specific frame range command argument.')
    frames     = Parm(name='frame_list',      value=[],     type='int',   description='List of separate frames to be rendered.')
    max_tasks  = Parm(name='max_running_tasks', value=1000, type='int',   description=' Number of tasks running simulatinously.')
    pre_sript  = Parm(name='pre_render_script', value="",   type='str',   description='Bash commands prepended to job script.')
    post_script= Parm(name='post_render_script',value="",   type='str',   description='Bash commands appended to job script.')
    
    # TODO: Parms() allow nested structure, for now we mimic old behaviour
    # and keep flat dictionary. Once we make it working, we may move on to
    # nested directory (see above for hints)
    local = (start, end, step, queue, group, slots, cpu_s, prior, req_m, hold, hjid, hjida,
        targets, layers, command, comm_arg, emails, proxy, jname, log_path, scripts, scenefile,
        user, include, exclude, asset_name, asset_type, jobcurrent, rerun, ignore, sub_time, req_start,
        req_res, req_lic, outputs, frange, frames, max_tasks, pre_sript, post_script)

    # This won't keep order:
    # local = dir()
    # local.remove('scene')
    # parms = [locals()[x] for x in local if isinstance(locals()[x], Parm)]

    parms = local
    scene.add_properties(parms)
    scene.dump(JSON_FILE)



