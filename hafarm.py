import haSGE, ha
reload(haSGE)
from haSGE import HaSGE
import os, sys
import const
import utils


hafarm_defaults = {'start_frame': 1,
                   'end_frame'  : 48,
                   'step_frame' : 1,
                   'queue'      : '3d', # Queue to be used. FIXME: This should be list
                   'group'      : '' ,  # Group of a machines to be used (subset of queue or farm most of the case.) FIXME: This should be list.
                   'slots'      : 15,   # Consume slots. On SGE these are custom numbers, not necceserly cores. 
                   'priority'   : -500, # TODO: Shouldn't it be genereal 0-1 value translated into specific number by manager class?
                   'req_memory' : 4,    # Minimal free memory on rendernode.
                   'job_on_hold': False,#
                   'hold_jid'   : [],   # Job's names or ids which current job is depend on.
                   'target_list': [],   # Used in applications with multiply targets (cameras in Maya batch, Write node in Nuke)
                   'layer_list' : [],   # A subset of a scene to be rendered (used by Maya, in Houdini it would be takes for example.)
                   'command'    : "",   # Rendering command.
                   'command_arg': [],   # Rendering command arguments as list.
                   'email_list' : [],   # A list of emails for notification
                   'email_opt'  : '',   # Options for emails (job's states triggering notification)
                   'make_proxy' : False,# Optionally makes a proxy for output image. 
                   # Render farm settigs bellow:
                   'job_name'   : "",   # Render job name.
                   'log_path'   : "$JOB/render/sungrid/log", # Env. variables will be expanded by render manager. 
                   'script_path': "$JOB/render/sungrid/jobScript", # Rendermanager will execute that script.
                   'email_stdout': False, # Homebrew support for mailing.
                   'email_stderr': False, # Same as above.
                   'scene_file' : "",   # The scene file used for rendering. It always should be a copy of source scene file. 
                   'user'       : "",   # Login user.
                   'include_list':[],   # Explicite list of computers to be used for job's execution. 
                   'exclude_list':[],   # Explicite list of computers to be excluded from job's execution.
                   'ignore_check':False,# Ignore checkpoint used to find out, if machine is avaiable (user login in SGE).
                   'job_asset_name': "",
                   'job_asset_type': "",
                   'job_current'   : "",
                   'rerun_on_error': True,
                   'submission_time': 0.0,  # As a name implies. Not sure if this is essential to record it ourselfs, but still.
                   'req_start_time': 0.0,   # As a name implies. Time a job will unhold and scheduled according to free resources. 
                   'req_resources' : "",  # Request additional resources.
                   'req_license'   : "",  # Request the license in format: license=number (mayalic=1)
                   'output_picture': "",  # This file is referential for rendering output (for debugging etc)
                   'frame_range_arg':["%s%s%s", '', '', ''],  # It should be ["-flag %s -flag %s", parm_key, parm_key], to produce:
                                          # '-s %s -e' % (self.parms['start_frame'], self.parms['end_frame']) for example (Maya)
                   'frame_list'    :'',    # It is sometimes useful to render specific frames, not ranges of it. Supported format: 1,2,3,4-10,11-20x2
                   'max_running_tasks':1000 # Max number of tasks in a job run at the same time (1000 considered to be non limit.)
                                        }


class HaFarmParms(dict):
    """Render manager agnostic job's parameters container.
    """
    def __init__(self, initilize=False, defaults=hafarm_defaults):
        super(HaFarmParms, self).__init__()

        # Init with defaults:
        self.merge_parms(defaults)

        # Set parms unrelated to host, like jobname, user etc:
        if initilize:
            self.initialize_env_parms()

    def __setitem__(self, key, value):
        """Custom item setter. Main reason fo it is type checking.
        """
        assert key in hafarm_defaults, "Key %s has to have default in hafarm_defaults" % key
        if isinstance(value, type(hafarm_defaults[key])):
            super(HaFarmParms, self).__setitem__(key, value)
        else:
            raise TypeError("Wrong type of value %s: %s" % (key, value))

    def initialize_env_parms(self):
        """Parameters to be derived without touching host app and not having defaults.
        """
        self['job_asset_name'] = os.getenv("JOB_ASSET_NAME", 'Not_Set')
        self['job_asset_type'] = os.getenv("JOB_ASSET_TYPE", 'Not_Set')
        self['job_current']    = os.getenv("JOB_CURRENT", 'Not_Set')
        self['user']           = os.getenv("USER", 'Not_Set')

    def merge_parms(self, parms_dict):
        """Copies a content of parms_dict into self.
        """
        for key, value in parms_dict.iteritems():
            self[key] = value

    def has_entry(self, entry):
        if entry in self.keys():
            return True
        return

   
# TODO think about this approach.
class FrameRangeParm(HaFarmParms):
  def __init__(self):
    self['start_frame'] = 1
    self['end_frame']   = 48
    self['frame_step']  = 1
    self['command']     = ["-s %s -e %s -i %s", 'start_frame', 'end_frame', 'frame_step']



class HaFarm(HaSGE):
    """Parent class to be inherited by host specific classes (Houdini, Maya, Nuke etc).
    It's a child of renderfarm manager class (currently SGE, but maybe any thing else in
    a future: OpenLava/whatever. Neither this class nor its children should notice if
    underlying manager will change.
    """
    def __init__(self):
        super(HaFarm, self).__init__()
        self.parms = HaFarmParms(initilize=True)


    def generate_unique_job_name(self, name):
        """Returns unique name for a job. 'Name' is usually a scene file. 
        """
        from base64 import urlsafe_b64encode
        name = os.path.basename(name)
        return "_".join([os.path.split(name)[1], urlsafe_b64encode(os.urandom(3))])
        

    def copy_scene_file(self, scene_file=None):
        """Makes a copy of a scene file.
        """
        # TODO: some error checking might be useful here...
        from shutil import copy
        if not scene_file:
            scene_file = self.parms['scene_file']
        filename, ext  = os.path.splitext(scene_file)
        path           = os.path.expandvars(self.parms['script_path'])
        new_scene_file = os.path.join(path, self.parms['job_name']) + ext
        self.parms['scene_file'] = new_scene_file
        copy(scene_file, new_scene_file)
        return ['copy_scene_file', new_scene_file]

    def render(self):
        """Make defaults steps, scene copy and call parent specific command.
        """
        from time import time
        self.parms['submission_time'] = time()
        result  = self.pre_schedule()
        # This should stay renderfarm agnostic call.
        result += super(HaFarm, self).render()
        result += self.post_schedule()
        return result

    def get_queue_list(self):
        """Returns queue list as provided by render manager.
        """
        return super(HaFarm, self).get_queue_list()

    def pre_schedule(self):
        """This should be provided by derived classes to perform any application specific actions before the submit.
        """
        return []

    def post_schedule(self):
        """This should be provided by derived classes to perform any application specific actions after the submit.
        """
        return []



# For some reason this can't be in its own module for now and we'd like to
# use it across the board, so I put it here. At some point, we should remove haSGE inheritance
# making it more like a plugin class. At that point, this problem should be reviewed.
class BatchFarm(HaFarm):
    '''Performs arbitrary script on farm. Also encapsulates utility functions for handling usual tasks.
    like tile merging, dubuging renders etc.'''
    def __init__(self, job_name=None, parent_job_name=[], queue=None, command='', command_arg=''):
        super(BatchFarm, self).__init__()
        self.parms['queue']          = queue
        self.parms['job_name']       = job_name
        self.parms['command']        = command
        self.parms['command_arg']    = [command_arg]
        self.parms['hold_jid']       = parent_job_name
        self.parms['ignore_check']   = True
        self.parms['slots']          = 1
        self.parms['req_resources'] = ''

    def join_tiles(self, filename, start, end, ntiles):
        '''Creates a command specificly for merging tiled rendering with oiiotool.'''
        from ha.path import padding

        # Retrive full frame name (without _tile%i)
        if const.TILE_ID in filename:
            base, rest = filename.split(const.TILE_ID)
            tmp, ext   = os.path.splitext(filename)
            filename   = base + ext
        else:
            base, ext  = os.path.splitext(filename)


        details = padding(filename, format='nuke')
        base    = os.path.splitext(details[0])[0]
        base, file = os.path.split(base)
        base    = os.path.join(base, const.TILES_POSTFIX, file)
        reads   = [base + const.TILE_ID + '%s' % str(tile) + ext for tile in range(ntiles)]


        # Reads:
        command = ' '
        command += '%s ' % reads[0]
        command += '%s ' % reads[1]
        command += '--over ' 

        for read in reads[2:]:
            command += "%s " % read
            command += '--over ' 

        # Final touch:
        command += '-o %s ' % details[0]
        command += '--frames %s-%s ' % (start, end)

        # Additional path for proxy images (to be created from joined tiles)
        if self.parms['make_proxy']:
            path, file = os.path.split(details[0])
            path = os.path.join(path, const.PROXY_POSTFIX)

            # FIXME: It shouldn't be here at all. 
            if not os.path.isdir(path): os.mkdir(path)

            proxy    = os.path.join(path, os.path.splitext(file)[0] + '.jpg')
            command += '--tocolorspace "sRGB" -ch "R,G,B" -o %s ' % proxy

        self.parms['command_arg'] = [command]
        self.parms['command']     = const.OIIOTOOL      
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1 
        return command

    def debug_images(self, filename):
        '''By using iinfo utility inspect filename (usually renders).'''
        from ha.path import padding
        details = padding(filename, 'shell')
        self.parms['command'] = const.IINFO
        self.parms['command_arg'] =  ['`ls %s | grep -v "%s" ` | grep File ' % (details[0], const.TILE_ID)]
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1
        self.parms['email_stdout'] = True

    def make_movie(self, filename):
        '''Make a movie from custom files. '''
        from ha.path import padding

        # Input filename with proxy correction:
        details = padding(filename, 'nuke')
        base, file = os.path.split(details[0])
        file, ext  = os.path.splitext(file)
        inputfile  = os.path.join(base, const.PROXY_POSTFIX, file + '.jpg')
        outputfile = os.path.join(base, padding(filename)[0] + 'mp4')
        command = "-y -r 25 -i %s -an -vcodec libx264 %s" % (inputfile, outputfile)
        self.parms['command'] = 'ffmpeg '
        self.parms['command_arg'] = [command]
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1

