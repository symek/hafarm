# No dramaa atm
# import drmaa
import os, sys
import hafarm
from hafarm import utils
from hafarm import const
from hafarm.manager import RenderManager 

# This is new version accomodated for Clarisse.
# Version v0.1 should follow these changes and merge to new v0.3
__plugin__version__ = 0.2

class Sungrid2(RenderManager):
    def __init__(self):
        self.session = None
        # NOTE: This is place to pre-config qsub executable for example:
        self.qsub_command = []

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
        """Creates a script sutable for SGE to run.
        """
        # TODO: For now script file is created according to hardcoded logic:
        # user script_path + job_name + .'job' extension
        # This could  be extented: 
        #   - for customization/pipeline friendines we could have specialized  parm for a filename.
        #     (not used if left empty)
        #   - for safty reason / to avoid filename clashes we could check the location (or use private one) 
        # (although it's never good to make class 'too smart'... 
        # isn't it an user responsibility to make job_name unigue and safe)...

        # TODO: HaFarmParm should have (optinal) variables' expansion built it. 
        # Basically plugin class should blindly read in data, like a calf sucking milk (no thinking).
        path        = os.path.expandvars(self.parms['script_path'])
        script_path = os.path.join(path, self.parms['job_name'] + '.job')
        time_parm   = (int(self.parms['start_frame']), int(self.parms['end_frame']), int(self.parms['step_frame']))

        # Normally a host application (Hou, Maya, Nuke) declares parms['frame_range_arg'] like:
        # ['-arbirary_flag %s -another -%s ...', key, key, ...], so render manager (which ever it is)
        # can construct its specific script/command here without knowing host syntax (see bellow)
        # Here SGE doesn't even need that (though it could if we were to create one script file per job).
        sge_frames_variables = []
        for key in self.parms['frame_range_arg'][1:]: # All but first should be key of parms dict (first is a string to fill out)
            if key == "start_frame": sge_frames_variables.append('${SGE_TASK_ID}') 
            elif key == 'end_frame': sge_frames_variables.append('${RANGE_FRAME}')
            else:
                # TODO This is rather questionable logic: key in frame_range_arg is either
                # a string or a key in self.parms, that should be expanded, but why?
                # If this is a key in self.parms, why host app didn't exapand it before
                # leaving it for us? 
                if not key in self.parms: sge_frames_variables.append(key)
                else: sge_frames_variables.append(self.parms[key])

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
        self.parms['command_arg'] += [self.parms['frame_range_arg'][0] % tuple(sge_frames_variables)]
        command_arg = " ".join(arg for arg in self.parms['command_arg'])



        # Mailing support:
        # FIXME: This doesn't work atm....
        # if self.parms['email_stdout']:
        #     if not self.parms['email_list']:
        #         self.parms['email_list'] = [utils.get_email_address()]
        #     stdout = 'STDOUT=$(cd `dirname "${BASH_SOURCE[0]}"` && pwd)/`basename "${BASH_SOURCE[0]}"`;\n'
        #     topic = 'DEBUGING FOR: ' + self.parms['job_name']
        #     send_mail = 'echo `cat $STDOUT` | mail -s "%s" "%s" \n' % (topic, self.parms['email_list'][0])
                
        # FIXME: Change hafarm specific variables for SGE once. Currently we do it manually. 
        scene_file = self.parms['scene_file'].replace(const.TASK_ID, '$SGE_TASK_ID')

        with open(script_path, 'w') as file:

            # This is standard:
            file.write('#!/bin/bash\n')
            file.write('#$ -t %s-%s:%s\n' %  time_parm) 

            # We try to use single script for all chuncks, so we need some expressions:
            # TODO: this should work for multi-frame rendering like Nuke, Hscript, Maya.
            # Not sure about Mantra though. 
            file.write('LAST_FRAME=%s\n' % self.parms['end_frame'])
            file.write('RANGE_FRAME=$[${SGE_TASK_ID}+%d]\n' % int(self.parms['step_frame']))
            file.write("if ((${RANGE_FRAME}>${LAST_FRAME})); then RANGE_FRAME=${LAST_FRAME}; fi\n")

            # Some standard info about current render:
            # TODO extend it with more system debuging info (current disc space, free RAM, CPU load etc.)
            file.write("echo Render start: `date`\n")
            file.write("echo Machine name: ${HOSTNAME}\n")
            file.write("echo User    name: ${USER}\n")
            file.write("echo Slots:        $NSLOTS\n")
            file.write("echo Processors  : `nproc`\n")
            file.write("NPROC=`nproc`\n")
            # Determine # of cores and set max for rendering if required (that is slots = 0)
            file.write("echo Memory stats: `egrep 'Mem|Cache|Swap' /proc/meminfo`\n")
            file.write("echo Scene file  : %s\n" % self.parms['scene_file'])
            #file.write("echo CPU    stats: `mpstat`\n")

            # Pre render script if any:
            file.write("%s\n" % self.parms['pre_render_script'])

            # Finally render command:
            # FIXME: this isn't generic. The only moment we know how the command should look like 
            # is host application class. 
            file.write('%s %s \n' % (self.parms['command'], command_arg))

            # Post render script if any:
            file.write("%s\n" % self.parms['post_render_script'])

            file.write("echo Render ends: `date`\n")
            file.write("echo Render target: %s\n" % self.parms['output_picture'])
            file.write("echo Command was: %s %s \n" % (self.parms['command'], self.parms['command_arg']))
            #file.write("echo Current mem: `egrep 'Mem|Cache|Swap' /proc/meminfo`\n")
            #file.write("echo CPU   stats: `mpstat`\n")
            # file.write(stdout) FIXME: Mailig disabaled atm.
            # file.write(send_mail)

        # self.parms['script_path'] = script_path # FIXME: (look for other places hafarmparms are changed silently.)
        # This was philosophically wrong. Some deep small obscure function shouldn't change our only
        # data repository silently (I'm writing it down here to remeber next time.) 
        # We should have eihter simple logic to construct job script or dedicated function() for it. 


        # As a convention we return a dict with function's proper value or None
        return script_path


    def _create_submit_command(self):
        """Submit an array job based on already provided job's parameters in HAFarmParms.
        """

        # We repeat work here temporarly for extra clearnless(see above):
        path        = os.path.expandvars(self.parms['script_path'])
        script_path = os.path.join(path, self.parms['job_name'] + '.job')
       
        # Job is send in 'hold' state:
        job_on_hold   = '-h' if  self.parms['job_on_hold'] else ""
        # Request license 
        # TODO: Add other resources
        req_resources = ['-hard', '-l', 'procslots=%s' % self.parms['slots']]
        req_resources +=['-hard', '-l', '%s' % self.parms['req_license']] if self.parms['req_license'] else []

        # Jobs' interdependency:
        hold_jid = ['-hold_jid', '%s' % ','.join(self.parms['hold_jid'])] if self.parms['hold_jid'] else []

        # Job's array interdependency:
        hold_jid_ad = ['-hold_jid_ad', '%s' % ','.join(self.parms['hold_jid_ad'])] if self.parms['hold_jid_ad'] else []

        # Max running tasks:
        # FIXME: make consistent access to hafarm's defaults. 
        # Now this would require import of hafarm.py
        max_running_tasks = ""
        if self.parms['max_running_tasks'] != 1000:
            max_running_tasks = ['-tc', self.parms['max_running_tasks']]

        # This will put Nuke for example in queue waiting for free slots,
        # but we want it to be selectable based on chosen queue: nuke queue: don't wait
        # 3d queue: wait with others.
        # FIXME: Shouldn't we come back to -pe cores flag?
        # or even -pe $NSLOTS for that matter...
        # TODO: SGE have soft and hard requests... support it.
        #if self.parms['req_resources']:
        #    req_resources += ' -hard -l %s' % self.parms['req_resources']

        # Request start time:
        if self.parms['req_start_time'] != 0.0:
            start_time = '-a %s ' % utils.convert_seconds_to_SGEDate(self.parms['req_start_time'])
        else:
            start_time = ''

        # Allow job to rerun on error:
        rerun_on_error = ""
        if self.parms['rerun_on_error']: rerun_on_error = '-r yes'
 
        # If we want to avoid temporarly suspended machines
        check_suspend = ['-ckpt', 'check_suspend'] if not self.parms['ignore_check'] else []

        # Email list and triggers options:
        email_list = " "
        email_opt  = ''
        if self.parms['email_list']: email_list = '-M %s ' % ",".join(self.parms['email_list'])
        if self.parms['email_opt']: email_opt = '-m %s' % self.parms['email_opt']

        # Queue request with host groups support
        # TODO: add specific host support regular expressions (?)
        queue = ""
        if self.parms['queue']: queue = '-q %s' % self.parms['queue']
        if self.parms['group'] and self.parms['group'] != 'allhosts': 
            queue += "@@%s" % self.parms['group']

        # This should be clean uped. Either all with flag names or none. 
        arguments = ['qsub']
        arguments += [job_on_hold, "-N %s" % self.parms['job_name'],
                     '-V', rerun_on_error,
                     '-o %s' % os.path.expandvars(self.parms['log_path']),
                     '-e %s' % os.path.expandvars(self.parms['log_path']),
                     queue,
                    '-ac OUTPUT_PICTURE=%s' % self.parms['output_picture'],
                    '-p %s' % self.parms['priority'], req_resources, check_suspend,
                    email_list, email_opt, hold_jid, hold_jid_ad, start_time, script_path]

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
                 
        self.qsub_command = cc 
        return cc

    def _submit_job(self, command=[]):
        '''Last part of scheduling process by calling backstaged render manager.
        '''
        import subprocess

        if not command: 
            command = self.qsub_command

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
        return ('allhosts', 'grafiki', 'renders')

    def get_host_list(self):
        """Get list of defined groups from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -shgrpl
        return []
        
    def get_job_stats(self, job_name):
        import subprocess
        sp = subprocess.Popen(['qacct', '-j', job_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = sp.communicate()
        db = {}
        if not 'error' in err:
            return utils.parse_qacct(out, db)
        return

    def test_connection(self):
        return
        
