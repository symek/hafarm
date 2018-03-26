import os
# Host specific:
import hou

# Custom: 
import hafarm
from hafarm import const

class RSBatchFarm(hafarm.HaFarm):
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
        if self.rop.type().name() in ('ifd', "baketexture", 'baketexture::3.0', 'Redshift_ROP'):
            self.parms['command_arg'] += ["--ignore_tiles"]

            # This will change Rop setting to save ifd to disk:
            self.parms['command_arg'] += ["--generate_ifds"]
            # also within non-default path:
            if not self.node.parm("ifd_path").isAtDefault():
                self.parms['command_arg'] += ["--ifd_path %s" % self.node.parm("ifd_path").eval()]

            #
            vm_picture = ""
            if self.rop.parm('RS_outputFileNamePrefix'):
                vm_picture = self.rop.parm('RS_outputFileNamePrefix').eval()
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

        # Requests resources and licenses (TODO shouldn't we aquire slot here?)
        self.parms['req_license']   = 'redshift_lic=1' 
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




class RSRenderFarm(hafarm.HaFarm):
    def __init__(self, node, rop=None, job_name='', crop_parms=(1,1,0)):
        super(RSRenderFarm, self).__init__()

        # Keep reference to assigned rop
        self.rop = rop
        self.node = node
        self.parms['command_arg']    = []
        self.parms['command']        = '$REDSHIFT_COREDATAPATH/bin/redshiftCmdLine'

        # Max tasks render managet will attempt to aquire at once: 
        self.parms['max_running_tasks'] = int(self.node.parm('max_running_tasks').eval())

        if not job_name:
                # Fallback generates name from current time:
                job_name = hafarm.utils.convert_seconds_to_SGEDate(time.time()) + "_redshift"
        
        self.parms['job_name'] = job_name 

        # Tiling support:
        #if crop_parms != (1,1,0):
        #    self.parms['job_name']  += "%s%s" % (const.TILE_ID , str(crop_parms[2]))

        self.parms['req_license']    = 'redshift_lic=1' 
        self.parms['req_resources']  = ''
        #self.parms['step_frame']      = int(self.node.parm('step_frame').eval())

        # FIXME: this is meaningless, make it more general
        if self.node.parm("ignore_check").eval():
            self.parms['ignore_check'] = True

        # Mailing support based on SGE, make it more robust. 
        self.parms['email_list']   = [hafarm.utils.get_email_address()]
        if self.node.parm("add_address").eval():
            self.parms['email_list'] += list(self.node.parm('additional_emails').eval().split())
        self.parms['email_opt']   = str(self.node.parm('email_opt').eval())

        # Queue and group details:
        self.parms['queue']       = str(self.node.parm('queue').eval())
        self.parms['group']       = str(self.node.parm('group').eval())
        self.parms['job_on_hold'] = bool(self.node.parm('job_on_hold').eval())
        self.parms['priority']    = int(self.node.parm('priority').eval())

        # Requested delay in evaluation time:
        delay = self.node.parm('delay').eval()
        if delay != 0:
            self.parms['req_start_time'] = delay*3600
            
        # Doesn't make sense for Mantra, but will be expected as usual later on:
        self.parms['frame_range_arg'] = ["%s%s%s", '', '', ''] 
        self.parms['req_resources']   = 'procslots=%s' % int(self.node.parm('mantra_slots').eval())
        self.parms['make_proxy']      = bool(self.node.parm("make_proxy").eval())

        
        # Bellow needs any node to be connected, which isn't nececery for rendering directly
        # from ifd files:
        if rop:
            # FIXME: job_name is wrong spot to derive ifd name from...
            # This couldn't be worse, really... :( 
            # So many wrong decisions/bugs in one place...
            ifd_name = job_name
            if job_name.endswith("_redshift"):
                ifd_name = job_name.replace("_redshift", "")
            self.parms['scene_file']     = os.path.join(self.node.parm("ifd_path").eval(), ifd_name + '.' + const.TASK_ID + '.rs')
            # self.parms['command']        = '$HFS/bin/' +  str(self.rop.parm('soho_pipecmd').eval()) 
            self.parms['start_frame']    = int(self.rop.parm('f1').eval())
            self.parms['end_frame']      = int(self.rop.parm('f2').eval())

            vm_picture = ""
            if self.rop.parm('RS_outputFileNamePrefix'):
                vm_picture = self.rop.parm('RS_outputFileNamePrefix').eval()
            self.parms['output_picture'] = str(vm_picture)     

        # Request RAM per job:
        if self.node.parm("mantra_ram").eval():
            self.parms['req_memory'] = self.node.parm("mantra_ram").eval()

        # Adding Python filtering:
        # Crop support:
        python_command = []
        # if crop_parms != (1,1,0):     
        #     python_command.append('--tiling %s' % ("%".join([str(x) for x in crop_parms])))
        # # Make proxies (mutually exclusive with crops...)
        # elif self.parms['make_proxy']:
        #     python_command.append("--proxy")

        # TODO: Config issues. Should we rely on ROP setting or hafarm defaults?
        # mantra_filter = self.node.parm("ifd_filter").eval()
        # self.parms['command'] += ' -P "%s ' % mantra_filter + " ".join(python_command) + '"'
        

    def pre_schedule(self):
        """ This method is called automatically before job submission by HaFarm.
            Up to now:
            1) All information should be aquired from host application.
            2) They should be placed in HaFarmParms class (self.parms).
            3) Scene should be ready to be copied to handoff location.
            
            Main purpose is to prepare anything specific that HaFarm might not know about, 
            like renderer command and arguments used to render on farm.
        """

        # In this case, scene_file is IFD for mantra: 
        # TODO: Cleanup command creation process: we should create full command here
        # perhaps?
        self.parms['command_arg'] += [" @SCENE_FILE/>"] #% self.parm['scene_file']

        # Any debugging info [object, outout]:
        return []


def render_frame_list(action, frames):
    """Renders individual frames by sending separately to manager
    This basically means HaFarm doesn't support any batching of random set of frames
    so we manage them individually. Unlike hscript exporter (HBachFarm), which does recognize
    frame_list parameter and via harender script supporting random frames."""

    rs_frames = []
    for frame in frames:
        job_name = action.parms['job_name'] + "_%s" % str(frame)
        rs_farm  = RSRenderFarm(action.node, action.rop, job_name=job_name + "_rs")
        # Single task job:
        rs_farm.parms['start_frame'] = frame
        rs_farm.parms['end_frame']   = frame
        rs_frames.append(rs_farm)
    # frames are dependent on mantra:
    action.insert_outputs(rs_frames)
    return rs_frames

def render_with_tiles(action):
    """Standin """ 
    _tiles, marger = None, None
    # Returns tiles job and merging job. 
    return _tiles, merger


def render_from_ifd(node, frames, job_name=None):
    """Separated path for renderig directly from provided ifd files."""
    import glob
    mantra_frames = []

    # Params from hafarm node:
    ifds  = node.parm("ifd_files").eval()
    start = node.parm("ifd_range1").eval() #TODO make automatic range detection
    end   = node.parm("ifd_range2").eval() #TODO as above

    # Rediscover ifds:
    # FIXME: should be simple unexpandedString()
    seq_details = hafarm.utils.padding(ifds)

    #job name = ifd file name + current ROP name.
    if not job_name:
        job_name = os.path.split(seq_details[0])[1] + "from" + node.name()

    # Find real file sequence on disk. Param could have $F4...
    real_ifds = glob.glob(seq_details[0] + "*" + seq_details[-1])

    # No ifds found:
    if not real_ifds: 
        print "Can't find rs files: %s" % ifds
        return []

    if not frames:
        rs_farm = RSRenderFarm(node, '', job_name)
        rs_farm.parms['start_frame'] = node.parm("ifd_range1").eval() #TODO make automatic range detection
        rs_farm.parms['end_frame']   = node.parm("ifd_range2").eval() #TODO as above
        rs_farm.parms['step_frame']  = node.parm("ifd_range3").eval()
        rs_farm.parms['scene_file']  = seq_details[0] + const.TASK_ID + '.rs'
        rs_frames.append(rs_farm)

    # Proceed with farme list:
    else:
        for frame in frames:
            rs_farm = RSRenderFarm(node, '', job_name+str(frame))
            rs_farm.parms['start_frame']  = frame
            rs_farm.parms['end_frame']    = frame
            rs_farm.parms['scene_file']  = seq_details[0] + const.TASK_ID + '.rs'
            rs_frames.append(rs_farm)


    # Detect output image. Uses grep ray_image on ifd file:
    #image = hafarm.utils.get_ray_image_from_ifd(real_ifds[0])
    #for frame in rs_frames:
    #    frame.parms['output_picture'] = image 

    return rs_frames
