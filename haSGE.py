# No dramaa atm
# import drmaa
import os
import utils


class HaSGE(object):
    def __init__(self):
        self.session = None

    def create_job_script(self):
        """Creates a script sutable for SGE to run.
        """
        path        = os.path.expandvars(self.parms['script_path'])
        script_path = os.path.join(path, self.parms['job_name'] + '.job')
        time_parm   = (int(self.parms['start_frame']), int(self.parms['end_frame']), int(self.parms['step_frame']))
        file = open(script_path, 'w')

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
        file.write("echo Memory stats: `egrep 'Mem|Cache|Swap' /proc/meminfo`\n")
        file.write("echo Scene file  : %s\n" % self.parms['scene_file'])
        #file.write("echo CPU    stats: `mpstat`\n")

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

        # SGE specific tweak (we can rely on SGE env variable instead of specifying explicite frames)
        self.parms['command_arg'] += self.parms['frame_range_arg'][0] % tuple(sge_frames_variables)

        # Finally render command:
        file.write('%s %s %s\n' \
            % (self.parms['command'], self.parms['command_arg'], self.parms['scene_file']))

        file.write("echo Render ends: `date`\n")
        file.write("echo Render target: %s\n" % self.parms['output_picture'])
        file.write("echo Command was: %s %s %s\n" % (self.parms['command'], self.parms['command_arg'], self.parms['scene_file']))
        #file.write("echo Current mem: `egrep 'Mem|Cache|Swap' /proc/meminfo`\n")
        #file.write("echo CPU   stats: `mpstat`\n")
        file.close()

        # As a convention we return a list with function name and return value:
        self.parms['script_path'] = script_path
        return ['create_job_script', script_path]


    def submit_array_job(self):
        """Submit an array job based on already provided job's parameters in HAFarmParms.
        """
        # self.set_flags()

        # Job is send in 'hold' state:
        job_on_hold   = '-h' if  self.parms['job_on_hold'] else ""
        # Request license 
        # TODO: Add other resources
        req_resources = '-hard -l procslots=%s ' % self.parms['slots']
        req_resources += '-hard -l %s' % self.parms['req_license'] if self.parms['req_license'] else ""

        # Jobs' interdependency:
        hold_jid = '-hold_jid %s ' % ','.join(self.parms['hold_jid']) if self.parms['hold_jid'] else ""

        # Max running tasks:
        # FIXME: make consistent access to hafarm's defaults. 
        # Now this would require import of hafarm.py
        max_running_tasks = ""
        if self.parms['max_running_tasks'] != 1000:
            max_running_tasks = '-tc %s' % self.parms['max_running_tasks']

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
        check_suspend = '-ckpt check_suspend' if not self.parms['ignore_check'] else ""

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

        # Add target to job name:
        # job_name = "_".join([self.parms['job_name'],  

        # FIXME: This is drmaa free temporary replacement:
        command = 'qsub %s -N %s -V %s %s -o %s -e %s %s -ac OUTPUT_PICTURE=%s -p %s %s %s %s %s %s %s %s' % (job_on_hold, \
                                                                                   self.parms['job_name'],
                                                                                   max_running_tasks, \
                                                                                   rerun_on_error, \
                                                                                   os.path.expandvars(self.parms['log_path']), \
                                                                                   os.path.expandvars(self.parms['log_path']), \
                                                                                   queue, \
                                                                                   self.parms['output_picture'], \
                                                                                   self.parms['priority'], \
                                                                                   req_resources, \
                                                                                   check_suspend, \
                                                                                   email_list, \
                                                                                   email_opt, \
                                                                                   hold_jid, \
                                                                                   start_time, \
                                                                                   self.parms['script_path'])
        result = os.popen(command)
        return ['qsub command', command] + ['submit_array_job'] + result.readlines()


    def test_connection(self):
        """Create a session, show that each session has an id,
        use session id to disconnect, then reconnect. Then exit.
        """
        self.session = drmaa.Session()
        self.session.initialize()
        print 'A session was started successfully'
        response = self.session.contact
        print 'session contact returns: ' + response
        self.session.exit()
        print 'Exited from session'

        self.session.initialize(response)
        print 'Session was restarted successfullly'
        self.session.exit()
        self.session = None

    def end_connection(self):
        if not self.session:
            self.session = drmaa.Session()
            print self.session.contact
        self.session.exit()
        self.session = None

    def render(self):
        """ This will be called by any derived class, to submit the jobs to farm. 
        Any information are to be provided in HaFarmParms class kept in self.parms
        variable.
        """
        result  = self.create_job_script()
        result += self.submit_array_job()
        return result

    def get_queue_list(self):
        """Get list of defined queues from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -sql
        return ('3d', 'nuke', 'turbo_nuke')

    def get_group_list(self):
        """Get list of defined groups from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -shgrpl
        return ('allhosts', 'grafiki', 'renders')




    # Who needs a case statement when you have dictionaries?
# SGEstatus = {
#     drmaa.JobState.UNDETERMINED: 'process status cannot be determined',
#     drmaa.JobState.QUEUED_ACTIVE: 'job is queued and active',
#     drmaa.JobState.SYSTEM_ON_HOLD: 'job is queued and in system hold',
#     drmaa.JobState.USER_ON_HOLD: 'job is queued and in user hold',
#     drmaa.JobState.USER_SYSTEM_ON_HOLD: 'job is queued and in user and system hold',
#     drmaa.JobState.RUNNING: 'job is running',
#     drmaa.JobState.SYSTEM_SUSPENDED: 'job is system suspended',
#     drmaa.JobState.USER_SUSPENDED: 'job is user suspended',
#     drmaa.JobState.DONE: 'job finished normally',
#     drmaa.JobState.FAILED: 'job finished, but failed',
#     }



  # def set_flags(self):
  #       """Creates a dictionary of defualt flags for SGE. Flags are those job parms,
  #       which are suspected to be not comapatible with others render managers' settings."""
  #       self.flags = {}
  #       self.flags['b'] = 'y'  # handle command as binary 
  #       self.flags['V'] = True # export all environment variables
  #       self.flags['h'] = True # place user hold on job
  #       # TODO: logs' names and job scripts names should be configureable:
  #       self.OUTPUT_PICTURE = ""


        # FIXME: Bellow doesn't work, the job is submited but it's fails to execute
        # Basic usage of drmaa works as excepted. Also this script work when sent from
        # comman line ?

        # if not self.session:
        #     self.session = drmaa.Session()

        # self.session.initialize()
        # response = self.session.contact
        # print 'Session contact returns: ' + response
        # jobTemplate = self.session.createJobTemplate()
        # jobTemplate.remoteCommand =  self.parms['script_path']
        # jobTemplate.outputPath    = ":" + os.path.expandvars(self.parms['log_path'])
        # jobTemplate.errorPath     = ":" + os.path.expandvars(self.parms['log_path'])
        # jobTemplate.args          = []
        # jobTemplate.joinFiles     = False
        # jobTemplate.nativeSpecification = '-N %s -q %s -V' % (self.parms['job_name'], self.parms['queue'])
        # jobTemplate.nativeSpecification = '-V '
        # jobid = self.session.runBulkJobs(jobTemplate, int(self.parms['start_frame']), 
        #                                     int(self.parms['end_frame']) , int(self.parms['step_frame']))

        # self.session.deleteJobTemplate(jobTemplate)
        # self.session.exit()
        # self.session = None
