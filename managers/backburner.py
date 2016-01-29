# No dramaa atm
# import drmaa
import os, sys
import subprocess
import hafarm
from hafarm import const
from hafarm.manager import RenderManager 

# Python 2.6 compatibility:
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

__plugin__version__ = 0.1

# TODO: Windows only atm.
# TODO: No config class atm.
CMDJOB_BIN  = "cmdjob.exe"
CMDJOB_PATH = "C:\\Program Files (x86)\\Autodesk\\Backburner"


class Backburner(RenderManager):
    def __init__(self):
        self.session = None
        # NOTE: This is place to pre-config qsub executable for example:
        self.cmdjob_command = []

    @property
    def register_manager(self):
        # TODO: How we could test here
        # if this is proper implementation of RenderManager?
        # calling test_connection()? or running attached unittest?
        # Do we need this at all?
        return True

    @property
    def version(self):
        return __plugin__version__ 


    def _create_submit_command(self):
        """Submit an array job based on already provided job's parameters in HAFarmParms.
        """

        # We repeat work here temporarly for extra clearnless(see above):
        path        = os.path.expandvars(self.parms['script_path'])
        # script_path = os.path.join(path, self.parms['job_name'] + '.job')
        args = OrderedDict()
        args['-jobName']  = self.parms['job_name']
        args['-group']    = self.parms['queue']              # Can't be group as subset of queue as backburner doesn't support that. 
        args['-priority'] = abs(int(self.parms['priority'])) / 10 # Apparently 0-100
        args['-logPath']  = os.path.expandvars(self.parms['log_path'])
        args['-workPath'] = os.path.expandvars(self.parms['log_path'])
        args['-showOutput'] = self.parms['output_picture']
        args['-numTasks']   = self.parms['end_frame']
        # Hold job:
        if self.parms['job_on_hold']: args['-suspended'] = ""
        # Executable and its variables
        # args[self['command']] = self.parms['command_arg']

        # Time parameters handling:
        time_parm = (int(self.parms['start_frame']), int(self.parms['end_frame']), int(self.parms['step_frame']))
        backburner_frame_variables = []
        for key in self.parms['frame_range_arg'][1:]: # All but first should be key of parms dict (first is a string to fill out)
            if key == "start_frame": backburner_frame_variables.append('%tn') 
            elif key == 'end_frame': backburner_frame_variables.append('1')
            else:
                if not key in self.parms: backburner_frame_variables.append(key)
                else: backburner_frame_variables.append(self.parms[key])

        self.parms['command_arg'] += [self.parms['frame_range_arg'][0] % tuple(backburner_frame_variables)]
        command_arg = " ".join(arg for arg in self.parms['command_arg'])

                
        # FIXME: Change hafarm specific variables for SGE once. Currently we do it manually. 
        scene_file = self.parms['scene_file'].replace(const.TASK_ID, '%tn')

        # TODO: Look for general way of doing things like this...
        # This should work in both cases where client class privided @SCENE_FILE/> in command_arg or
        # expects scene_file to be appended as last argument (old behaviour)
        if const.SCENE_FILE in command_arg:
            command_arg = command_arg.replace(const.SCENE_FILE, scene_file)
            scene_file  = ""

        command = '%s %s %s' % (os.path.expandvars(self.parms['command']), command_arg, scene_file)
        # This should be clean uped. Either all with flag names or none. 
        arguments = []
        for key in args.keys():
            arguments += [str(key), str(args[key])]

        arguments += [command]
        # FIXME: Temporary cleanup: 
        cc = []
        for word in arguments:
            if " " in word:
                for subword in word.split():
                    if subword != " ":
                        cc.append(subword)
            elif isinstance(word, type([])):
                for subitem in word:
                    if len(subitem) > 1:
                        cc.append(str(subitem))
            else:
                if word != "":
                    cc.append(str(word))

        cc = [os.path.join(CMDJOB_PATH, CMDJOB_BIN)] + cc 
        self.cmdjob_command = cc 
        print cc
        return cc

    def _submit_job(self, command=None):
        '''Last part of scheduling process by calling backstaged render manager.
        '''
        import subprocess

        if not command: 
            command = self.cmdjob_command
        # print command

        # TODO: What we should do with output?
        try:
            result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print result.stderr.read()
            print result.stdout.read()
            return result
        except subprocess.CalledProcessError, why:
            return why



    def render(self, parms):
        """ This will be called by any derived class, to submit the jobs to farm. 
        Any information are to be provided in HaFarmParms class kept in self.parms
        variable.
        """
        self.parms = dict(parms)
        result = {}
        # result['_create_job_script']      = self._create_job_script()
        result['_create_submit_command']  = self._create_submit_command()
        result['_submit_job']             = self._submit_job()
        return result

    def get_queue_list(self):
        """Get list of defined queues from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -sql
        return ('3d', 'nuke', 'turbo_nuke', 'dev')

    def get_group_list(self):
        """Get list of defined groups from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -shgrpl
        return ('allhosts', 'grafiki', 'renders')

    def get_host_list(self):
        """Get list of defined groups from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -shgrpl
        return 

    def get_job_stats(self, job_name):
        return 

    def test_connection(self):
        return

 
