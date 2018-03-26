import os
# Host specific:
import hou

# Custom: 
import hafarm
from hafarm import const

class MantraFarm(hafarm.HaFarm):
    def __init__(self, node, rop=None, job_name='', crop_parms=(1,1,0)):
        super(MantraFarm, self).__init__()

        # Keep reference to assigned rop
        self.rop = rop
        self.node = node
        self.parms['command_arg']    = []
        self.parms['command']        = '$HFS/bin/mantra'

        # Max tasks render managet will attempt to aquire at once: 
        self.parms['max_running_tasks'] = int(self.node.parm('max_running_tasks').eval())

        # Mantra jobs' names are either derived from parent job (hscript)
        # or provided by user (to allow of using ifd names for a job.) 
        if not job_name:
                # Fallback generates name from current time:
                job_name = hafarm.utils.convert_seconds_to_SGEDate(time.time()) + "_mantra"
        
        self.parms['job_name'] = job_name 

        # Tiling support:
        if crop_parms != (1,1,0):
            self.parms['job_name']  += "%s%s" % (const.TILE_ID , str(crop_parms[2]))

        self.parms['req_license']    = 'mantra_lic=1' 
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
            if job_name.endswith("_mantra"):
                ifd_name = job_name.replace("_mantra", "")
            self.parms['scene_file']     = os.path.join(self.node.parm("ifd_path").eval(), ifd_name + '.' + const.TASK_ID + '.ifd')
            self.parms['command']        = '$HFS/bin/' +  str(self.rop.parm('soho_pipecmd').eval()) 
            self.parms['start_frame']    = int(self.rop.parm('f1').eval())
            self.parms['end_frame']      = int(self.rop.parm('f2').eval())

            vm_picture = ""
            if self.rop.parm('vm_picture'):
                vm_picture = self.rop.parm('vm_picture').eval()
            else:
                vm_picture = safe_eval_parm(self.rop, 'vm_uvoutputpicture1')
            self.parms['output_picture'] = str(vm_picture)     
            
        # Setting != 0 idicates we want to do something about it:
        if self.node.parm("mantra_slots").eval() != 0 or self.node.parm("cpu_share").eval() != 1.0:
            threads   = self.node.parm("mantra_slots").eval()
            cpu_share = self.node.parm('cpu_share').eval()
            # Note: "-j threads" appears in a command only if mantra doesn't take all of them. 
            # TODO: Bollow is a try to make autoscaling based on percentange of avaiable cpus.
            # Needs rethinking...
            self.parms['slots'] = threads
            self.parms['cpu_share'] = cpu_share
            if cpu_share != 1.0:
                self.parms['command_arg'] += ['-j', const.MAX_CORES]
            else:
                self.parms['command_arg'] += ['-j', str(threads)]

        # Request RAM per job:
        if self.node.parm("mantra_ram").eval():
            self.parms['req_memory'] = self.node.parm("mantra_ram").eval()

        # Adding Python filtering:
        # Crop support:
        python_command = []
        if crop_parms != (1,1,0):     
            python_command.append('--tiling %s' % ("%".join([str(x) for x in crop_parms])))
        # Make proxies (mutually exclusive with crops...)
        elif self.parms['make_proxy']:
            python_command.append("--proxy")

        # TODO: Config issues. Should we rely on ROP setting or hafarm defaults?
        mantra_filter = self.node.parm("ifd_filter").eval()
        self.parms['command'] += ' -P "%s ' % mantra_filter + " ".join(python_command) + '"'
        

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
        self.parms['command_arg'] += ["-V1", "-f", "@SCENE_FILE/>"] #% self.parm['scene_file']

        # Any debugging info [object, outout]:
        return []


def render_frame_list(action, frames):
    """Renders individual frames by sending separately to manager
    This basically means HaFarm doesn't support any batching of random set of frames
    so we manage them individually. Unlike hscript exporter (HBachFarm), which does recognize
    frame_list parameter and via harender script supporting random frames."""

    mantra_frames = []
    for frame in frames:
        job_name = action.parms['job_name'] + "_%s" % str(frame)
        mantra_farm = MantraFarm(action.node, action.rop, job_name=job_name + "_mantra")
        # Single task job:
        mantra_farm.parms['start_frame'] = frame
        mantra_farm.parms['end_frame']   = frame
        mantra_frames.append(mantra_farm)
    # frames are dependent on mantra:
    action.insert_outputs(mantra_frames)
    return mantra_frames


def render_with_tiles(action):
    '''Creates a series of Mantra jobs using the same ifds stream with different crop setting 
    and overwritten filename. Secondly generates merge job with general BatchFarm class for 
    joining tiles.'''
    tile_job_ids = []
    mantra_tiles = []
    tiles_x = action.rop.parm('vm_tile_count_x').eval()
    tiles_y = action.rop.parm('vm_tile_count_y').eval()

    parent_job_name = action.parms['job_name']
    for tile in range(tiles_x*tiles_y):
        mantra_farm = MantraFarm(action.node, action.rop, job_name = parent_job_name, \
            crop_parms = (tiles_x,tiles_y,tile))
        mantra_tiles.append(mantra_farm)

    # Tile merging job:
    merging_job_name = action.parms['job_name'] + '_merge'
    merger           = Batch.BatchFarm(job_name = merging_job_name, queue = str(action.node.parm('queue').eval()))
    merger.node      = action.node # NOTE: Only for debugging purposes, we don't rely on this overwise

    # Need to copy it here, as proxies can be made after tiles merging of course...
    merger.parms['make_proxy']  = bool(action.node.parm("make_proxy").eval())

    # Queue control
    merger.parms['output_picture'] = mantra_farm.parms['output_picture'] # This is for house keeping only

    # This prepares commandline to execute:
    merger.join_tiles(mantra_farm.parms['output_picture'],
                          mantra_farm.parms['start_frame'],
                          mantra_farm.parms['end_frame'],
                          tiles_x*tiles_y)

    action.insert_outputs(mantra_tiles)
    [tile.insert_output(merger) for tile in mantra_tiles] 
    # Returns tiles job and merging job. 
    return mantra_tiles, merger


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
        print "Can't find ifds files: %s" % ifds
        return []

    if not frames:
        mantra_farm = MantraFarm(node, '', job_name)
        mantra_farm.parms['start_frame'] = node.parm("ifd_range1").eval() #TODO make automatic range detection
        mantra_farm.parms['end_frame']   = node.parm("ifd_range2").eval() #TODO as above
        mantra_farm.parms['step_frame']  = node.parm("ifd_range3").eval()
        mantra_farm.parms['scene_file']  = seq_details[0] + const.TASK_ID + '.ifd'
        mantra_frames.append(mantra_farm)

    # Proceed with farme list:
    else:
        for frame in frames:
            mantra_farm = MantraFarm(node, '', job_name+str(frame))
            mantra_farm.parms['start_frame']  = frame
            mantra_farm.parms['end_frame']    = frame
            mantra_farm.parms['scene_file']  = seq_details[0] + const.TASK_ID + '.ifd'
            mantra_frames.append(mantra_farm)


    # Detect output image. Uses grep ray_image on ifd file:
    image = hafarm.utils.get_ray_image_from_ifd(real_ifds[0])
    for frame in mantra_frames:
        frame.parms['output_picture'] = image 

    return mantra_frames