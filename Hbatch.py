# Host specific:
import hou

# Custom: 
import hafarm
from hafarm import const

class HbatchFarm(hafarm.HaFarm):
    def __init__(self, node, rop):
        super(HbatchFarm, self).__init__()
        # Keep reference to assigned rop
        self.rop = rop
        self.node = node
        # command will be either hscript csh script shipped with Houdini 
        # or any custom render script (harender atm.)
        self.parms['command']           = '$HFS/bin/hython'
        # Max tasks render managet will attempt to aquire at once: 
        self.parms['max_running_tasks'] = int(self.node.parm('max_running_tasks').eval())

        # This is because we do tiling ourselfs:
        if self.rop.type().name() in ('ifd', "baketexture", 'baketexture::3.0'):
            self.parms['command_arg'] += ["--ignore_tiles"]

            # This will change Rop setting to save ifd to disk:
            self.parms['command_arg'] += ["--generate_ifds"]
            # also within non-default path:
            if not self.node.parm("ifd_path").isAtDefault():
                self.parms['command_arg'] += ["--ifd_path %s" % self.node.parm("ifd_path").eval()]

            # Default Mantra imager (doesn't make sense in hbatch cache though)
            # TODO: Shouln't it be an ifd file instead of the image?
            # if self.rop.type().name() == 'ifd': # baketexure doesnt have vm_picture
            # ... but it does have vm_uvoutput*
            vm_picture = ""
            if self.rop.parm('vm_picture'):
                vm_picture = self.rop.parm('vm_picture').eval()
            else:
                vm_picture = safe_eval_parm(self.rop, 'vm_uvoutputpicture1')
            self.parms['output_picture'] = str(vm_picture)

        # 
        self.parms['scene_file']  = str(hou.hipFile.name())
        self.parms['job_name']    = self.generate_unique_job_name(self.parms['scene_file'])

        # FIXME "if rop:"" This isn't clear now
        if rop: 
            self.parms['job_name']    += "_"
            self.parms['job_name']    += rop.name()

            # Use single host for everything (for simulation for example)
            if self.node.parm("use_one_slot").eval() or rop.type().name() in const.HOUDINI_SINGLE_TASK_NODES:
                self.parms['step_frame']  = int(self.rop.parm('f2').eval())
            else:
                self.parms['step_frame']  = int(self.node.parm('step_frame').eval())

        # Requests resurces and licenses (TODO shouldn't we aquire slot here?)
        self.parms['req_license']   = 'hbatch_lic=1' 
        self.parms['req_resources'] = 'procslots=%s' % int(self.node.parm('hbatch_slots').eval())

        # Change only for slots != 0:
        if self.node.parm('hbatch_slots').eval():
            self.parms['slots'] = self.node.parm('hbatch_slots').eval()

        # Use provided frame list instead of frame range. Hscript needs bellow changes to
        # make generic path to work with list of frames: 
        #   a) change step frame to end_frame to discourage render mananger from spliting tasks among hosts
        #   b) add "-l 1,2,3[4-6,7-12x2]" argument to custom render script.
        # TODO: This isn't generic approach, it won't transfer to any render manager. 
        # NOTE:
        #   Mantra is sent as a series of single task jobs though, so frame list isn't supported per se by
        #   this class, but rather host specific code. 
        if self.node.parm("use_frame_list").eval():
            self.parms['frame_list']  = str(self.node.parm("frame_list").eval())
            self.parms['step_frame']  = int(self.rop.parm('f2').eval())
            self.parms['command_arg'] += ['-l %s' %  self.parms['frame_list']]


        # FIXME: this is meaningless, make it more general
        if self.node.parm("ignore_check").eval():
            self.parms['ignore_check'] = True

        # Notification settings:
        self.parms['email_list']  = [hafarm.utils.get_email_address()]
        if self.node.parm("add_address").eval():
            self.parms['email_list'] += list(self.node.parm('additional_emails').eval().split())
        self.parms['email_opt']   = str(self.node.parm('email_opt').eval())

        # Queue, groups, frame ranges
        self.parms['queue']       = str(self.node.parm('queue').eval())
        self.parms['group']       = str(self.node.parm('group').eval())
        self.parms['start_frame'] = int(self.rop.parm('f1').eval())
        self.parms['end_frame']   = int(self.rop.parm('f2').eval())
        self.parms['frame_range_arg'] = ["-f %s %s -i %s", 'start_frame', 'end_frame',  int(self.rop.parm('f3').eval())]
        self.parms['target_list'] = [str(self.rop.path()),]

        # job on hold, priority, 
        self.parms['job_on_hold'] = bool(self.node.parm('job_on_hold').eval())
        self.parms['priority']    = int(self.node.parm('priority').eval())

        # Request RAM per job:
        if self.node.parm("hbatch_ram").eval():
            self.parms['req_memory'] = self.node.parm("hbatch_ram").eval()

        # Requested delay in evaluation time:
        delay = self.node.parm('delay').eval()
        if delay != 0:
            self.parms['req_start_time'] = delay*3600

        # This will overwrite any from above command arguments for harender according to command_arg parm:
        self.parms['command_arg'].insert(0, str(self.node.parm("command_arg").eval()))


    def pre_schedule(self):
        """ This method is called automatically before job submission by HaFarm.
            Up to now:
            1) All information should be aquired from host application.
            2) They should be placed in HaFarmParms class (self.parms).
            3) Scene should be ready to be copied to handoff location.
            
            Main purpose is to prepare anything specific that HaFarm might not know about, 
            like renderer command and arguments used to render on farm.
        """


        #TODO: copy_scene_file should be host specific.:
        result  = self.copy_scene_file()

        # Command for host application:
        command = []

        # Threads:
        if self.parms['slots']:
            command += ['-j %s' % self.parms['slots']]

        # Render script:
        command += self.parms['command_arg']


        # Add targets:
        if self.parms['target_list']:
            command += ['-d %s' % " ".join(self.parms['target_list'])]

        # Save to parms again:
        self.parms['command_arg'] = command

        # Any debugging info [object, outout]:
        return []






