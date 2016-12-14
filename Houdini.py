# Standard:
import os
import itertools
import time

# Host specific:
import hou

# Custom: 
import hafarm

import Batch
from hafarm import utils
from hafarm import const
from Batch import BatchFarm
from hafarm import NullAction
from hafarm import RootAction

# Jobs multi-tasking are always diabled for these nodes:
SINGLE_TASK_NODES = ('alembic', 'mdd', 'channel', 'dop', 'filmboxfbx')
MULTI_TASK_NODES  = ('ifd', 'geometry', 'comp', 'baketexture', 'fetch')

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
        if self.rop.type().name() in ('ifd', "baketexture"):
            self.parms['command_arg'] += ["--ignore_tiles"]

            # This will change Rop setting to save ifd to disk:
            self.parms['command_arg'] += ["--generate_ifds"]
            # also within non-default path:
            if not self.node.parm("ifd_path").isAtDefault():
                self.parms['command_arg'] += ["--ifd_path %s" % self.node.parm("ifd_path").eval()]

            # Default Mantra imager (doesn't make sense in hbatch cache though)
            # TODO: Shouln't it be an ifd file instead of the image?
            if self.rop.type().name() == 'ifd': # baketexure doesnt have vm_picture
                self.parms['output_picture'] = str(self.rop.parm("vm_picture").eval())

        # 
        self.parms['scene_file']  = str(hou.hipFile.name())
        self.parms['job_name']    = self.generate_unique_job_name(self.parms['scene_file'])

        # FIXME "if rop:"" This isn't clear now
        if rop: 
            self.parms['job_name']    += "_"
            self.parms['job_name']    += rop.name()

            # Use single host for everything (for simulation for example)
            if self.node.parm("use_one_slot").eval() or rop.type().name() in SINGLE_TASK_NODES:
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
                job_name = utils.convert_seconds_to_SGEDate(time.time()) + "_mantra"
        
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
            # baketexture doesn't have vm_picture:
            if rop.type().name() == "ifd":
                self.parms['output_picture'] = str(self.rop.parm("vm_picture").eval())        
            
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


def mantra_render_frame_list(action, frames):
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


def mantra_render_with_tiles(action):
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


def mantra_render_from_ifd(node, frames, job_name=None):
    """Separated path for renderig directly from provided ifd files."""
    import glob
    mantra_frames = []

    # Params from hafarm node:
    ifds  = node.parm("ifd_files").eval()
    start = node.parm("ifd_range1").eval() #TODO make automatic range detection
    end   = node.parm("ifd_range2").eval() #TODO as above

    # Rediscover ifds:
    # FIXME: should be simple unexpandedString()
    seq_details = utils.padding(ifds)

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
    image = utils.get_ray_image_from_ifd(real_ifds[0])
    for frame in mantra_frames:
        frame.parms['output_picture'] = image 

    return mantra_frames



def post_render_actions(node, actions, queue='3d'):
    # Proceed with post-render actions (debug, mp4, etc):
    # Debug images:
    post_renders = []
    if node.parm("debug_images").eval():
        for action in actions:
            # Valid only for Mantra renders;
            if not isinstance(action, MantraFarm):
               continue
            # Generate report per file:
            debug_render = BatchFarm(job_name = action.parms['job_name'] + "_debug", queue = queue)
            debug_render.debug_image(action.parms['output_picture'], 
                                     start = action.parms['start_frame'], 
                                     end   = action.parms['end_frame'])
            debug_render.node = action.node
            debug_render.insert_input(action)
            post_renders.append(debug_render)
            # Merge reports:
            merger   = BatchFarm(job_name = action.parms['job_name'] + "_mergeReports", queue = queue)
            ifd_path = os.path.join(os.getenv("JOB"), 'render/sungrid/ifd')
            merger.merge_reports(action.parms['output_picture'], ifd_path=ifd_path, resend_frames=node.parm('rerun_bad_frames').eval())
            merger.node = action.node
            merger.add_input(debug_render)
            post_renders.append(merger)

    # Make a movie from proxy frames:
    if node.parm("make_proxy").eval() and node.parm("make_movie").eval():
        for action in actions:
            # Valid only for Mantra renders:
            if not isinstance(action, MantraFarm):
                continue
            movie  = Batch.BatchFarm(job_name = action.parms['job_name'] + "_mp4", queue = queue)
            movie.make_movie(action.parms['output_picture'])
            movie.node = action.node
            movie.insert_input(action)
            post_renders.append(movie)

    return post_renders

def build_graph(hafarm_rop, verbose=False):
    '''Builds simple dependency graph from Rops.
    '''
    def is_supported(node):
        return  node.type().name() in SINGLE_TASK_NODES + MULTI_TASK_NODES

    def add_recursively(parent, actions, rops):
        for rop in parent.rop.inputs():
            # Houdini sometimes keeps None inputs...
            if not rop:
                continue
            # This rop was already hafarm'ed, so we just connect its hafarm class 
            # to our current node (parent)
            if rop.name() in rops.keys():
                parent.add_input(rops[rop.name()])
                continue
            if not is_supported(rop) or rop.isBypassed():
                if verbose:
                    print "Creating NullAction from %s" % rop.name()
                farm      = NullAction()
                farm.parms = {'job_name': rop.name()}
                farm.rop  = rop
                farm.node = parent.node
                farm.array_interdependencies  = False
                if rop.type().name() == "HaFarm":
                    farm.node  = rop
            else:
                # We may import node from different network:
                if rop.type().name() == 'fetch':
                    rop = hou.node(rop.parm("source").eval())

                farm = HbatchFarm(parent.node, rop)

            actions.append(farm)
            parent.add_input(farm)
            if verbose:
                print "Adding %s to %s inputs." % (farm.rop.name(), parent.rop.name())
            rops[rop.name()] = farm
            if rop.inputs():
                add_recursively(farm, actions, rops)
    
    # This is book-keeper while creating graph:
    actions = []
    rops    = {}
    # This is the only root we will have...
    root = RootAction()
    # NOTE: This is only for debugging:
    root.parms = {'job_name': hafarm_rop.name()}
    root.node   = hafarm_rop
    root.rop    = hafarm_rop
    root.array_interdependencies  = False
    # Go:
    add_recursively(root, actions, rops)

    return root,  actions
 

def render_recursively(root, dry_run=False, ignore_types=[]):
    """Executes render() command of actions in graph order (children first).
    """
    def render_children(action, submitted, ignore_types):
        for child in action.get_renderable_inputs():
            render_children(child, submitted, ignore_types)
            if True in [isinstance(child, t) for t in ignore_types]:
                continue
            if child not in submitted:
                if dry_run:
                    names = [x.parms['job_name'] for x in child.get_renderable_inputs()]
                    print "Dry submitting: %s, settings: %s, children: \n\t%s" % (child.parms['job_name'], child.node.name(), ", ".join(names))
                else:
                    child.render()
                submitted += [child]

    submitted = []
    render_children(root, submitted, ignore_types)
    return submitted



def build_debug_graph(parent, subnet):
    def build_recursive(parent, subnet, hnode):
        for child in parent.get_direct_inputs():
            if child.parms['job_name'] not in [node.name() for node in subnet.children()]:
                ch = subnet.createNode('merge')
                ch.setName(child.parms['job_name'])
            else:
                ch = subnet.node(child.parms['job_name'])
            print ch.name() + " connected to " + hnode.name()
            hnode.setNextInput(ch)
            build_recursive(child, subnet, ch)

    for child in subnet.children():
        child.destroy()

    null = subnet.createNode('merge')
    null.setName('root')
    build_recursive(parent, subnet, null)
    for node in subnet.children():
        node.moveToGoodPosition()


def render_pressed(node):
    '''Direct callback from Render button on Hafarm ROP.'''

    # FIXME: This shouldn't be here?
    hou.hipFile.save()
    queue    = str(node.parm('queue').eval())
    job_name = node.name()
    parent_job_name = []
    output_picture = ''
    mantra_farm = None
    hscripts = []
    mantras  = []
    posts    = []
    debug_dependency_graph = node.parm("debug_graph").eval()

    # a) Ignore all inputs and render from provided ifds:
    if node.parm("render_from_ifd").eval():
        root = RootAction()
        frames = []
        # support selective frames as well:
        if  node.parm("use_frame_list").eval():
            frames = node.parm("frame_list").eval()
            frames = utils.parse_frame_list(frames)

        # TODO Make validiation of submiting jobs...
        mantra_frames = mantra_render_from_ifd(node, frames)
        root.add_inputs(mantra_frames)
        posts = post_render_actions(node, mantra_frames)
        root.add_inputs(posts)
        # End of story:
        render_recursively(root, debug_dependency_graph)
        root.clear()
        return 
        
    # b) Iterate over inputs 
    print
    print "Building dependency graph:"
    root, hscripts = build_graph(node)


    for action in hscripts:
        # This is not mantra node, we are done here:
        if action.rop.type().name() not in ("ifd", "baketexture"):
            continue

        # Render randomly selected frames provided by the user in HaFarm parameter:
        if  action.node.parm("use_frame_list").eval():
            frames         = action.node.parm("frame_list").eval()
            frames         = utils.parse_frame_list(frames)
            mantra_frames  = mantra_render_frame_list(action, frames)
        else:
            # TODO: Move tiling inside MantraFarm class...
            # Custom tiling:
            if action.rop.parm('vm_tile_render').eval():
                mantra_frames, merger = mantra_render_with_tiles(action)
            else:
                # Proceed normally (no tiling required):
                mantra_frames = [MantraFarm(action.node, action.rop, job_name = action.parms['job_name'] + "_mantra")]
                # Build parent dependency:
                action.insert_outputs(mantra_frames)

        # Posts actions
        posts = post_render_actions(action.node, mantra_frames)
        root.add_inputs(posts)
    


    # Debug previous renders (ignore all rops but debugers) mode:
    if node.parm('debug_previous_render'):
        if node.parm('debug_previous_render').eval():
            render_recursively(root, debug_dependency_graph, ignore_types=[MantraFarm, HbatchFarm])
            return
 
    
    # Again end of story:
    print "Submitting nodes in top-to-buttom from dependency graph:"
    render_recursively(root, debug_dependency_graph)

    if debug_dependency_graph:
        subnet = node.parent().createNode("subnet")
        build_debug_graph(root, subnet)

    # Side effect of singelton root. It's not destroyed after run, so we need to clean it here.
    root.clear()

