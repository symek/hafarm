# No dramaa atm
# import drmaa
import os, sys
import subprocess
import hafarm
from hafarm import const
from hafarm.manager import RenderManager 

__plugin__version__ = 0.1


SQUEUE_BIN = 'squeue'

class Slurm(RenderManager):
    def __init__(self):
        self.session = None
        # NOTE: This is place to pre-config qsub executable for example:
        self.sbatch_command = []

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

    def _create_job_script(self):
        """Creates a script sutable for Slurm to run.
        """
        path        = os.path.expandvars(self.parms['script_path'])
        script_path = os.path.join(path, self.parms['job_name'] + '.job')
        time_parm   = (int(self.parms['start_frame']), int(self.parms['end_frame']), int(self.parms['step_frame']))

        # Normally a host application (Hou, Maya, Nuke) declares parms['frame_range_arg'] like:
        # ['-arbirary_flag %s -another -%s ...', key, key, ...], so render manager (which ever it is)
        # can construct its specific script/command here without knowing host syntax (see bellow)
        # Here SGE doesn't even need that (though it could if we were to create one script file per job).
        slurm_frames_variables = []
        for key in self.parms['frame_range_arg'][1:]: # All but first should be key of parms dict (first is a string to fill out)
            if key == "start_frame": slurm_frames_variables.append('${SLURM_ARRAY_TASK_ID}') 
            elif key == 'end_frame': slurm_frames_variables.append('${RANGE_FRAME}')
            else:
                # TODO This is rather questionable logic: key in frame_range_arg is either
                # a string or a key in self.parms, that should be expanded, but why?
                # If this is a key in self.parms, why host app didn't exapand it before
                # leaving it for us? 
                if not key in self.parms: slurm_frames_variables.append(key)
                else: slurm_frames_variables.append(self.parms[key])

        # Support for autoscaling multithreading  (must be optionl atm): 
        if const.MAX_CORES in self.parms['command_arg']:
            idx = self.parms['command_arg'].index(const.MAX_CORES)
            self.parms['command_arg'].pop(idx)
            if self.parms['cpu_share'] != 0.0:
                self.parms['command_arg'].insert(idx, '$(python -c "from math import ceil; print int(ceil($NPROC*%s))")' \
                    % self.parms['cpu_share'])
            else:
                # Set autoscaling for MAX:
                self.parms['command_arg'].insert(idx, '$NPROC')

        # SGE specific tweak (we can rely on SGE env variable instead of specifying explicite frames)
        self.parms['command_arg'] += [self.parms['frame_range_arg'][0] % tuple(slurm_frames_variables)]
        command_arg = " ".join(arg for arg in self.parms['command_arg'])
                
        # FIXME: Change hafarm specific variables for SGE once. Currently we do it manually. 
        scene_file = self.parms['scene_file'].replace(const.TASK_ID, '$SLURM_ARRAY_TASK_ID')

        # There are cases where TASK_ID should be padded. 
        # TODO: I don't know how to specify padding length thought atm
        scene_file  = scene_file.replace(const.TASK_ID_PADDED,  '$(python -c "print \'$SLURM_ARRAY_TASK_ID\'.zfill(%s)")' \
            % self.parms['frame_padding_length'])

        # TODO: Look for general way of doing things like this...
        # This should work in both cases where client class privided @SCENE_FILE/> in command_arg or
        # expects scene_file to be appended as last argument (old behaviour)
        if const.SCENE_FILE in command_arg:
            command_arg = command_arg.replace(const.SCENE_FILE, scene_file)
            scene_file  = ""

        with open(script_path, 'w') as file:

            # This is standard:
            file.write('#!/bin/bash  \n')
            file.write('#SBATCH --array=%s-%s:%s\n' %  time_parm) 

            # Hold:
            if  self.parms['job_on_hold']: 
                file.write('#SBATCH -H \n') 

            #Nice:
            # Slurm's nice is oposite to priority and ranges -10.000<-->10.000:
            file.write("#SBATCH --nice=%i\n" % min(max((self.parms['priority'] * -1), -10000), 10000))

            # Multithreading:
            file.write('#SBATCH -N 1 \n')
            # Slots == 0: all cores, reserve full node:
            if self.parms['slots'] == 0:
                file.write('#SBATCH --exclusive\n')
            else:
                file.write('#SBATCH -n %s\n' % self.parms['slots'])
            # file.write('#SBATCH -c %s \n' % self.parms['slots'])

            # RAM (MB in Slurm, GB in hafarm)
            if self.parms['req_memory']:
                ram = int(self.parms['req_memory']*1024)
                file.write("#SBATCH --mem=%i\n" % ram)

            if self.parms['req_license']: 
                req_license = self.parms['req_license'].split('=')
                req_license = ":".join(req_license)
                file.write('#SBATCH -L %s \n' % req_license)

            # ATM Slurm does't support array dependency nor does allow
            # creating dependecy based on job's names (only jobids)
            # We need to ask Slurn for jobids providing it with our names.
            # NOTE: We treat array dependencies as simply dependencies for now.
            if self.parms['hold_jid'] or self.parms['hold_jid_ad']:
                deps = self.parms['hold_jid'] + self.parms['hold_jid_ad']
                # get_jobids_by_name returns a list: [jobid, ...]
                deps = [self.get_jobid_by_name(name) for name in deps]
                # Flattern array of arrays:
                deps = [str(item) for sublist in deps for item in sublist]
                file.write('#SBATCH -d aftercorr:%s \n' % ','.join(deps)) 

            if self.parms['req_start_time'] != 0.0 : file.write('#SBATCH --begin=now+%i  \n' % self.parms['req_start_time'])
            if self.parms['rerun_on_error']: file.write('#SBATCH --requeue \n')
            if self.parms['email_list']: file.write('#SBATCH --mail-user=%s\n' % ",".join(self.parms['email_list']))
            if self.parms['email_opt']: file.write('#SBATCH --mail-type=%s\n' % self.parms['email_opt'])
            if self.parms['queue']: file.write('#SBATCH -p %s\n' % self.parms['queue'])
            if self.parms['group'] and self.parms['group'] != 'allhosts': file.write("#SBATCH  -C %s\n" % self.parms['group'])

            # We try to use single script for all chuncks, so we need some expressions:
            # TODO: this should work for multi-frame rendering like Nuke, Hscript, Maya.
            # Not sure about Mantra though. 
            file.write('LAST_FRAME=%s\n' % self.parms['end_frame'])
            file.write('RANGE_FRAME=$[${SLURM_ARRAY_TASK_ID}+%d]\n' % int(self.parms['step_frame']))
            file.write("if ((${RANGE_FRAME}>${LAST_FRAME})); then RANGE_FRAME=${LAST_FRAME}; fi\n")
            file.write("OUTPUT_PICTURE=%s\n" % self.parms['output_picture'])
            # Some standard info about current render:
            # TODO extend it with more system debuging info (current disc space, free RAM, CPU load etc.)
            file.write("echo Render start: `date`\n")
            file.write("echo Machine name: ${HOSTNAME}\n")
            file.write("echo User    name: ${USER}\n")
            file.write("echo Slots:        $NSLOTS\n")
            #file.write("echo Processors  : `nproc`\n")
            #file.write("NPROC=`nproc`\n")
            # Determine # of cores and set max for rendering if required (that is slots = 0)
            file.write("echo Memory stats: `egrep 'Mem|Cache|Swap' /proc/meminfo`\n")
            file.write("echo Scene file  : %s\n" % self.parms['scene_file'])
            #file.write("echo CPU    stats: `mpstat`\n")

             # Pre render script if any:
            file.write("%s\n" % self.parms['pre_render_script'])

            # Finally render command:
            # FIXME: this isn't generic. The only moment we know how the command should look like 
            # is host application class. 
            command = '%s %s %s \n' % (os.path.expandvars(self.parms['command']), command_arg, scene_file)
            file.write(command)

            # Exit code handling 
            file.write("exit_code=$?\n")

            # Post render script if any:
            file.write("%s\n" % self.parms['post_render_script'])

            file.write("echo Render ends: `date`\n")
            file.write("echo Render target: %s\n" % self.parms['output_picture'])
            file.write("echo Command was: '%s'\n" % command)

            #We track exit code from main command:
            file.write("exit $exit_code\n")


        # As a convention we return a dict with function's proper value or None
        return script_path


    def _create_submit_command(self):
        """Submit an array job based on already provided job's parameters in HAFarmParms.
        """

        # We repeat work here temporarly for extra clearnless(see above):
        path        = os.path.expandvars(self.parms['script_path'])
        script_path = os.path.join(path, self.parms['job_name'] + '.job')
        stdout      = "-o %s/%s" % (os.path.expandvars(self.parms['log_path']), self.parms['job_name']) + ".o%A.%a"
        stderr      = "-e %s/%s" % (os.path.expandvars(self.parms['log_path']), self.parms['job_name']) + ".e%A.%a"
        workdir     = '-D %s'    % os.path.expandvars(self.parms['log_path'])
       

               # This should be clean uped. Either all with flag names or none. 
        arguments = ['sbatch']
        arguments += ["-J %s" % self.parms['job_name'], '--export=ALL', workdir, stdout, stderr, script_path]

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
                 
        self.sbatch_command = cc 
        return cc

    def _submit_job(self, command=None):
        '''Last part of scheduling process by calling backstaged render manager.
        '''
        import subprocess

        if not command: 
            command = self.sbatch_command
        # print command

        # TODO: What we should do with output?
        try:
            result = subprocess.call(command, stdout=subprocess.PIPE)
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
        result['_create_job_script']      = self._create_job_script()
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
        return ('allhosts', 'grafika', 'render', "old_intel", "new_intel")

    def get_host_list(self):
        """Get list of defined groups from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -shgrpl
        return []

    def get_job_stats(self, job_name):
        import subprocess
        sp = subprocess.Popen(['sstat', '-j', job_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = sp.communicate()
        db = {}

    def test_connection(self):
        return

    def get_jobid_by_name(self, job_name, split_tasks=True):
        ''' Returns slurm's job id from the provided
            jobname. It may return more than single job.
        '''
        
        job_name = str(job_name)
        command = [SQUEUE_BIN, '--name=%s' % job_name, '-h' ,'-a' ,'-o', '%i' ]
        out, err =subprocess.Popen(command, universal_newlines=True ,shell=False, \
            stderr=subprocess.PIPE,stdout=subprocess.PIPE).communicate()
        if out:
            out = out.split()
            out = [line.strip() for line in out]
            if split_tasks:
                assert "_" in out[0]
                out = [x.split("_")[0] for x in out]
                out = [int(x) for x in out]
            return out
        return []
 
    def get_jobname_by_id(self, _id):
        ''' Returns slurm's job_id by its job_name. 
        '''
        assert isinstance(_id, int)
        command = [SQUEUE_BIN, '-j %d' %_id, '-h' ,'-a' ,'-o', '%j' ]
        out, err =subprocess.Popen(command, universal_newlines=True ,shell=False, \
            stderr=subprocess.PIPE,stdout=subprocess.PIPE).communicate()
        return out.strip(), err.strip()
       
