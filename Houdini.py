# Standard:
import os
import itertools

# Host specific:
import hou

# Custom: 
import hafarm
import ha
from ha.hafarm import utils
from ha.hafarm import const
#from ha.hafarm import Batch
from ha.path import padding, find_sequence

reload(utils)
reload(hafarm)
reload(const)

class HbatchFarm(hafarm.HaFarm):
    def __init__(self, node, rop):
        super(HbatchFarm, self).__init__()
        # Keep reference to assigned rop
        self.rop = rop
        self.node = node

        # command will be either hscript csh script shipped with Houdini 
        # or any custom render script (harender atm.)
        self.parms['command']     = str(self.node.parm("command").eval())

        # This is because we do tiling ourselfs:
        if self.rop.type().name() == 'ifd':
            self.parms['command_arg'] += " --ignore_tiles "

            # This will change Rop setting to save ifd to disk:
            self.parms['command_arg'] += ' --generate_ifds '
            # also within non-default path:
            if not self.node.parm("ifd_path").isAtDefault():
                self.parms['command_arg'] += " --ifd_path %s " % self.node.parm("ifd_path").eval()

            # Default Mantra imager (doesn't make sense in hbatch cache though)
            # TODO: Shouln't it be an ifd file instead of the image?
            self.parms['output_picture'] = str(self.rop.parm("vm_picture").eval())

        # 
        self.parms['scene_file']  = str(hou.hipFile.name())
        self.parms['job_name']    = self.generate_unique_job_name(self.parms['scene_file'])
        # Job name should be driver dependant:
        if rop: 
            self.parms['job_name']    += "_"
            self.parms['job_name']    += rop.name()

        # Requests resurces and licenses (TODO shouldn't we aquire slot here?)
        self.parms['req_license']   = 'hbatchlic=1' 
        self.parms['req_resources'] = 'procslots=%s' % int(self.node.parm('slots').eval())

        # Use single host for everything (for simulation for example)
        if self.node.parm("use_one_slot").eval():
            self.parms['step_frame']  = int(self.rop.parm('f2').eval())
        else:
            self.parms['step_frame']  = int(self.node.parm('step_frame').eval())

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
            self.parms['command_arg'] += '-l %s ' %  self.parms['frame_list']


        # FIXME: this is meaningless, make it more general
        if self.node.parm("ignore_check").eval():
            self.parms['ignore_check'] = True

        # Notification settings:
        self.parms['email_list']  = [utils.get_email_address()]
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

        # Requested delay in evaluation time:
        delay = self.node.parm('delay').eval()
        if delay != 0:
            self.parms['req_start_time'] = utils.compute_delay_time(delay)

        # This will overwrite any from above command arguments for harender according to command_arg parm:
        self.parms['command_arg'] += str(self.node.parm("command_arg").eval())


    def pre_schedule(self):
        """ This method is called automatically before job submission by HaFarm.
            Up to now:
            1) All information should be aquired from host application.
            2) They should be placed in HaFarmParms class (self.parms).
            3) Scene should be ready to be copied to handoff location.
            
            Main purpose is to prepare anything specific that HaFarm might not know about, 
            like renderer command and arguments used to render on farm.
        """

        # Save current state of a scene: 
        # TODO: Make optional:
        # We assume hip file is already saved, otherwise have scenes takes ages to export 
        # with multipy Mantras.
        # hou.hipFile.save()

        #TODO: copy_scene_file should be host specific.:
        result  = self.copy_scene_file()

        # Command for host application:
        command = self.parms['command_arg']

        # Threads:
        command += '-j %s ' % self.parms['slots']

        # Add targets:
        if self.parms['target_list']:
            command += ' -d %s ' % " ".join(self.parms['target_list'])

        # Save to parms again:
        self.parms['command_arg'] = command

        # Any debugging info [object, outout]:
        return ['pre_schedule', 'render with arguments:' + command]





class MantraFarm(hafarm.HaFarm):
    def __init__(self, node, rop=None, job_name=None, parent_job_name=None, crop_parms=(1,1,0)):
        super(MantraFarm, self).__init__()

        # Keep reference to assigned rop
        self.rop = rop
        self.node = node
        self.parms['command_arg']    = ''
        self.parms['command']        = '$HFS/bin/mantra'

        # Mantra jobs' names are either derived from parent job (hscript)
        # or provided by user (to allow of using ifd names for a job.)
        if not job_name: job_name    = parent_job_name
        self.parms['job_name']       = job_name + '_mantra'

        # Tiling support:
        if crop_parms != (1,1,0):
            self.parms['job_name']  += "%s%s" % (const.TILE_ID , str(crop_parms[2]))

        self.parms['req_license']    = '' 
        self.parms['req_resources']  = ''
        #self.parms['step_frame']      = int(self.node.parm('step_frame').eval())

        # FIXME: this is meaningless, make it more general
        if self.node.parm("ignore_check").eval():
            self.parms['ignore_check'] = True

        # Mailing support based on SGE, make it more robust. 
        self.parms['email_list']   = [utils.get_email_address()]
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
            self.parms['req_start_time'] = utils.compute_delay_time(delay)
            
        # Doesn't make sense for Mantra, but will be expected as usual later on:
        self.parms['frame_range_arg'] = ["%s%s%s", '', '', ''] 
        self.parms['req_resources']   = 'procslots=%s' % int(self.node.parm('slots').eval())
        self.parms['make_proxy']      = bool(self.node.parm("make_proxy").eval())

        # Hold until parent job isn't completed
        if parent_job_name:
            self.parms['hold_jid'] = [parent_job_name]
        
        # Bellow needs any node to be connected, which isn't nececery for rendering directly
        # from ifd files:
        if rop:
            self.parms['scene_file']     = os.path.join(self.node.parm("ifd_path").eval(), job_name + '.' + const.TASK_ID + '.ifd')
            self.parms['command']        = '$HFS/bin/' +  str(self.rop.parm('soho_pipecmd').eval()) 
            self.parms['start_frame']    = int(self.rop.parm('f1').eval())
            self.parms['end_frame']      = int(self.rop.parm('f2').eval())
            self.parms['output_picture'] = str(self.rop.parm("vm_picture").eval())

        # Adding Python filtering:
        # Crop support:
        python_command = []
        if crop_parms != (1,1,0):     
            python_command.append('--tiling %s' % ("%".join([str(x) for x in crop_parms])))
        # Make proxies (mutually exclusive with crops...)
        elif self.parms['make_proxy']:
            python_command.append("--proxy")

        self.parms['command'] += ' -P "%s ' % const.MANTRA_FILTER + " ".join(python_command) + '"'
        

    def pre_schedule(self):
        """ This method is called automatically before job submission by HaFarm.
            Up to now:
            1) All information should be aquired from host application.
            2) They should be placed in HaFarmParms class (self.parms).
            3) Scene should be ready to be copied to handoff location.
            
            Main purpose is to prepare anything specific that HaFarm might not know about, 
            like renderer command and arguments used to render on farm.
        """

        # Command for host application:
        command = self.parms['command_arg']

        # Threads:
        command += ' -j %s ' % self.parms['slots']

        # Save to parms again:
        self.parms['command_arg'] = command + " -f " # <- place for IFD fiile

        # Any debugging info [object, outout]:
        return ['pre_schedule', 'render with arguments:' + command]


def mantra_render_frame_list(node, rop, hscript_farm, frames):
    """Renders individual frames by sending separately to manager
    This basically means HaFarm doesn't support any batching of random set of frames
    so we manage them individually. Unlike hscript exporter (HBachFarm), which does recognize
    frame_list parameter and via harender script supporting random frames."""

    mantra_frames = []
    for frame in frames:
        mantra_farm = MantraFarm(node, rop, job_name=None, parent_job_name=hscript_farm.parms['job_name'])
        # Single task job:
        mantra_farm.parms['start_frame'] = frame
        mantra_farm.parms['end_frame']   = frame
        show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 
        mantra_frames.append(mantra_farm)

    return mantra_frames


def mantra_render_with_tiles(node, rop, hscript_farm):
    '''Creates a series of Mantra jobs using the same ifds stream with different crop setting 
    and overwritten filename. Secondly generates merge job with general BatchFarm class for 
    joining tiles.'''
    tile_job_ids = []
    mantra_tiles = []
    tiles_x = rop.parm('vm_tile_count_x').eval()
    tiles_y = rop.parm('vm_tile_count_y').eval()

    for tile in range(tiles_x*tiles_y):
        mantra_farm = MantraFarm(node, rop, job_name = None, parent_job_name = hscript_farm.parms['job_name'], \
                                                            crop_parms = (tiles_x,tiles_y,tile))
        show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 
        tile_job_ids.append(mantra_farm.parms['job_name'])
        mantra_tiles.append(mantra_farm)

    
    # Tile merging job:
    merging_job_name = hscript_farm.parms['job_name'] + '_merge'
    batch_farm = hafarm.BatchFarm(job_name = merging_job_name, 
                                  parent_job_name = tile_job_ids, 
                                  queue = str(node.parm('queue').eval()))

    # Need to copy it here, as proxies can be made after tiles merging of course...
    batch_farm.parms['make_proxy']  = bool(node.parm("make_proxy").eval())
    # Queue control
    batch_farm.parms['start_frame'] = mantra_farm.parms['start_frame']
    batch_farm.parms['end_frame']   = mantra_farm.parms['start_frame'] # This is single job script (oiiotool does looping well): 
    batch_farm.parms['output_picture'] = mantra_farm.parms['output_picture'] # This is for house keeping only

    # This prepares commandline to execute:
    batch_farm.join_tiles(mantra_farm.parms['output_picture'],
                          mantra_farm.parms['start_frame'],
                          mantra_farm.parms['end_frame'],
                          tiles_x*tiles_y)

    batch_farm.render()
    return mantra_tiles.append(batch_farm)


def mantra_render_from_ifd(ifds, start, end, node, job_name=None):
    """Separated path for renderig directly from provided ifd files."""
    import glob0
    seq_details = padding(ifds)
    #job name = ifd file name + current ROP name.
    if not job_name:
        job_name = os.path.split(seq_details[0])[1] + "from" + node.name()

    mantra_farm = MantraFarm(node, None, job_name)
    mantra_farm.parms['start_frame'] = node.parm("ifd_range1").eval() #TODO make automatic range detection
    mantra_farm.parms['end_frame']   = node.parm("ifd_range2").eval() #TODO as above
    mantra_farm.parms['step_frame']  = node.parm("ifd_range3").eval()
    mantra_farm.parms['scene_file']  = seq_details[0] + const.TASK_ID + '.ifd'

    # Find real file sequence on disk. Param could have $F4...
    real_ifds = glob.glob(seq_details[0] + "*" + seq_details[-1])

    # No ifds found:
    if not real_ifds: 
        print "Can't find ifds files: %s" % ifds
        return

    # Detect output image. Uses grep ray_image on ifd file:
    mantra_farm.parms['output_picture'] = utils.get_ray_image_from_ifd(real_ifds[0])
    print "Rendering with existing ifd files: %s" % ifds
    show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 


def show_details(title, parms, result, verbose=False):
    '''This is temporary debugging facility. '''
    
    if not verbose:
        if not os.getenv("HAFARM_DEBUG", False):
            return


    # TODO: replace with proper logging.
    print "\n\t %s execution... " % str(title)
    if parms and isinstance(parms, type({})):
        print " ==== Parameters: ==== "
        for key in parms.keys():
            print "\t " + key + ": " + str(parms[key])
        
    if result and isinstance(result, type([])):
        print " ==== Retured values: ==== "
        for x in range(0, len(result),2):
            print "\t" + result[x],
            print ": ",
            print str(result[x+1])


def render_pressed(node):
    '''Direct callback from Render button on Hafarm ROP.'''

    # FIXME: This shouldn't be here?
    hou.hipFile.save()

    # a) Ignore all inputs and render from provided ifds:
    if node.parm("render_from_ifd").eval():
        ifds  = node.parm("ifd_files").eval()
        start = node.parm("ifd_range1").eval() #TODO make automatic range detection
        end   = node.parm("ifd_range2").eval() #TODO as above
        mantra_render_from_ifd(ifds, start, end, node)
        return

    # b) Iterate over inputs 
    inputs = node.inputs()
    for rop in inputs:
        hscript_farm = HbatchFarm(node, rop)
        show_details('Hscript', hscript_farm.parms, hscript_farm.render())

        # Continue the loop in case this wasn't Mantra ROP.
        if rop.type().name() != 'ifd':
            continue

        # Use as usual frame ranges from connected rops to schedule Mantra renders:
        if not node.parm("use_frame_list").eval():
            # TODO: Move tiling inside MantraFarm class...
            # Custom tiling:
            if rop.parm('vm_tile_render').eval():
                mantra_tiles = mantra_render_with_tiles(node, rop, hscript_farm)
            else:
                # Proceed normally (no tiling required):
                mantra_farm = MantraFarm(node, rop, job_name = None, parent_job_name = hscript_farm.parms['job_name'],)
                show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 
                # Proceed with debuging:
                if node.parm("debug_images").eval():
                    debug_render  = hafarm.BatchFarm(job_name = hscript_farm.parms['job_name'] + "_debug", 
                                                     queue    = str(node.parm('queue').eval()),
                                                     parent_job_name = [mantra_farm.parms['job_name']])
                    debug_render.inspect_images(mantra_farm.parms['output_picture'])
                    debug_render.render()

        # Render randomly selected frames provided by the user in HaFarm parameter:
        # TODO: Doesn't suppport tiling atm.
        else:
            frames = node.parm("frame_list").eval()
            frames = utils.parse_frame_list(frames)
            mantra_frames = mantra_render_frame_list(node, rop, hscript_farm, frames)
            
