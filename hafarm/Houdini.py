# Standard:
import os
import itertools

# Host specific:
import hou

# Custom: 
import hafarm
import ha
from ha.hafarm import utils
#from ha.hafarm.icomp import ICompFarm
from ha.path import padding, find_sequence

reload(utils)
reload(hafarm)

class HbatchFarm(hafarm.HaFarm):
    def __init__(self, node, rop):
        super(HbatchFarm, self).__init__()
        # Keep reference to assigned rop
        self.rop = rop
        self.node = node

        # command will be either hscript csh script shipped with Houdini 
        # or any custom render script (harender atm.)
        self.parms['command']     = str(self.node.parm("command").eval())

        # This is because we do tiling by our own:
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
        self.parms['job_name']    = self.genarate_unique_job_name(self.parms['scene_file'])

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


        # Prepare rop for IFD generation if required:
        # FIXME: This shouldn't be here at all:
        # if self.rop.type().name() == 'ifd':
        #     old_soho_outputmode = self.rop.parm("soho_outputmode").eval()
        #     old_soho_diskfile   =  self.rop.parm('soho_diskfile').unexpandedString()
        #     self.rop.parm("soho_outputmode").set(1)
        #     path = os.path.join(self.node.parm("ifd_path").eval(), self.parms['job_name'] + ".$F.ifd")
        #     self.rop.parm('soho_diskfile').set(path)

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

        # Restore old ifd file and scene setting:
        # FIXME: This also shouln't be here at all. 
        # if self.rop.type().name() == 'ifd':
        #     self.rop.parm('soho_diskfile').set(old_soho_diskfile)
        #     self.rop.parm('soho_outputmode').set(old_soho_outputmode)

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
            self.parms['job_name']  += "_tile%s" % str(crop_parms[2])

        self.parms['req_license']    = '' 
        self.parms['req_resources']  = ''
        #self.parms['step_frame']      = int(self.node.parm('step_frame').eval())

        # FIXME: this is meaningless, make it more general
        if self.node.parm("ignore_check").eval():
            self.parms['ignore_check'] = True

        self.parms['email_list']   = [utils.get_email_address()]
        if self.node.parm("add_address").eval():
            self.parms['email_list'] += list(self.node.parm('additional_emails').eval().split())
        self.parms['email_opt']   = str(self.node.parm('email_opt').eval())
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
        self.parms['req_resources'] = 'procslots=%s' % int(self.node.parm('slots').eval())
        # Hold until parent job isn't completed
        if parent_job_name:
            self.parms['hold_jid'] = [parent_job_name]
        
        # Bellow needs any node to be connected, which isn't nececery for rendering directly
        # from ifd files:
        if rop:
            self.parms['scene_file']     = os.path.join(self.node.parm("ifd_path").eval(), job_name + '.${SGE_TASK_ID}' + '.ifd')
            self.parms['command']        = '$HFS/bin/' +  str(self.rop.parm('soho_pipecmd').eval()) 
            self.parms['start_frame']    = int(self.rop.parm('f1').eval())
            self.parms['end_frame']      = int(self.rop.parm('f2').eval())
            self.parms['output_picture'] = str(self.rop.parm("vm_picture").eval())

        # Crop support via python filtering:
        # crop_parms (a,b,c):
        # a: number of horizontal tiles
        # b: number of vertical tiles
        # c: current tile number
        if crop_parms != (1,1,0) and rop: 
            filter_path = '/STUDIO/houdini/houdini13.0/scripts/python/HaFilterIFD_v01.py'
            # TODO: Kind of hacky, as we don't have currently standard way of dealing with ifd python 
            # filtering. 
            if not 'mantra -P' in self.parms['command']:
                crop_arg = ' -P "%s --tiling %s"' % (filter_path, "%".join([str(x) for x in crop_parms]))
            else:
                # FIXME: This won't work atm:
                print "Double Python filtering not supported atm. Remove -P flag from ROP command field."

            self.parms['command'] += crop_arg
        

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



class ICompFarm(hafarm.HaFarm):
    '''This small utility class calls icomp exec, which is Python wrapper around nuke comand line mode.
        icomp has a built-in old school SGE support, which we should replace with new stuff soon.'''
    def __init__(self, command=''):
        super(ICompFarm, self).__init__()
        self._exec    = '/STUDIO/scripts/icomp/icomp'
        self.command = command


    def render(self):
        from os import popen
        result = popen(self._exec + self.command).readlines()
        return result


    def join_tiles(self, job_parent_name, filename, start, end, ntiles):
        '''Creates a command specificly for merging tiled rendering.'''
        from ha.path import padding

        # Retrive full frame name (without _tile%i)
        if "_tile" in filename:
            base, rest = filename.split("_tile")
            tmp, ext   = os.path.splitext(filename)
            filename   = base + ext
        else:
            base, ext  = os.path.splitext(filename)

        details = padding(filename, format='nuke')
        base    = os.path.splitext(details[0])[0]
        reads   = [base + '_tile%s' % str(tile) + ext for tile in range(ntiles)]

        # Reads:
        command = ' '
        for read in reads:
            command += '--Read file=%s:first=%s:last=%s ' % (read, start, end)

        # Mereges:
        command += '--Merge over,0,1 ' 
        for read in range(2, len(reads)):
            command += '--Merge over,%s ' % read

        # Final touch:
        command += '--Write file=%s ' % details[0]
        command += '--globals %s,%s,24 --hold %s -f' % (start, end, job_parent_name)
        self.command = command



def render_from_ifd(ifds, start, end, node, job_name=None):
    """Separated path for renderig directly from provided ifd files."""
    seq_details = padding(ifds)
    #job name = ifd file name + current ROP name.
    if not job_name:
        job_name = os.path.split(seq_details[0])[1] + "from" + node.name()

    mantra_farm = MantraFarm(node, None, job_name)
    mantra_farm.parms['start_frame'] = node.parm("ifd_range1").eval() #TODO make automatic range detection
    mantra_farm.parms['end_frame']   = node.parm("ifd_range2").eval() #TODO as above
    mantra_farm.parms['scene_file']  = seq_details[0] + '${SGE_TASK_ID}' + '.ifd'
    # Detect output image. Uses grep ray_image on first ifd file:
    # TODO: This is potential source of errors without proper checking that file exists
    path, filename = os.path.split(ifds)
    single_ifd = find_sequence(path, filename)[0]
    mantra_farm.parms['output_picture'] = utils.get_ray_image_from_ifd(single_ifd)
    print "Rendering with existing ifd files: %s" % ifds
    show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 


def show_details(title, parms, result):
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
    # Flag storing original setting from a ROP, which will be disabled down the stream.
    tile_render = False

    # FIXME: This shouldn't be here?
    hou.hipFile.save()

    # a) Ignore all inputs and render from provided ifds:
    if node.parm("render_from_ifd").eval():
        ifds  = node.parm("ifd_files").eval()
        start = node.parm("ifd_range1").eval() #TODO make automatic range detection
        end   = node.parm("ifd_range2").eval() #TODO as above
        render_from_ifd(ifds, start, end, node)
        return

    # b) Iterate over inputs 
    inputs = node.inputs()
    for rop in inputs:
        hscript_farm = HbatchFarm(node, rop)

        # Ignore builtin tile rendering here (see bellow)
        # If vm_tile_render exists...
        if rop.parm('vm_tile_render'):
            # and is set True:
            if rop.parm('vm_tile_render').eval():
                tile_render = True
                #rop.parm('vm_tile_render').set(False)

        # Print details:
        show_details('Hscript', hscript_farm.parms, hscript_farm.render())

        # Continue the loop in case this wasn't Mantra ROP.
        if rop.type().name() != 'ifd':
            continue

        # ... or follow with Mantra job:
        # Use as usual frame ranges from connected rops to schedule Mantra renders:
        if not node.parm("use_frame_list").eval():
            # TODO: Move tiling inside MantraFarm class...
            # This a little harder approach than simple changine tile index and re-call MantraFarm
            # several times, but I don't want to use tiling parm on a node, because it will re-export ifds
            # which is waste of resources. I do prefer using python filtering for tiling atm.
            # Tiling:
            if tile_render:
                job_ids = []
                tiles_x = rop.parm('vm_tile_count_x').eval()
                tiles_y = rop.parm('vm_tile_count_y').eval()

                for tile in range(tiles_x*tiles_y):
                    mantra_farm = MantraFarm(node, rop, job_name = None, parent_job_name = hscript_farm.parms['job_name'], \
                                                                        crop_parms = (tiles_x,tiles_y,tile))
                    show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 
                    job_ids.append(mantra_farm.parms['job_name'])

                # Tile merging job:
                icomp_farm = ICompFarm(parent_job_name=",".join(job_ids))
                icomp_farm.join_tiles(mantra_farm.parms['job_name'], \
                                      mantra_farm.parms['output_picture'], \
                                      mantra_farm.parms['start_frame'],\
                                      mantra_farm.parms['end_frame'],\
                                      tiles_x*tiles_y)
                print icomp_farm.render()

                # Restore original setting of tiling:
                # rop.parm("vm_tile_render").set(True)
            else:
                # Proceed normally (no tiling required):
                mantra_farm = MantraFarm(node, rop, job_name = None, parent_job_name = hscript_farm.parms['job_name'],)
                show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 



        # Render randomly selected frames provided by the user in HaFarm parameter:
        # TODO: Doesn't suppport tiling atm.
        else:
            frames = node.parm("frame_list").eval()
            # Make a list of individual frames out of it, and send separately to manager
            # This basically means HaFarm doesn't support any batching of random set of frames
            # so we manage them individually. Unlike hscript exporter (HBachFarm), which does recognize
            # frame_list parameter and via harender script, supports random frames.
            frames = utils.parse_frame_list(frames)
            for frame in frames:
                mantra_farm = MantraFarm(node, rop, job_name=None, parent_job_name=hscript_farm.parms['job_name'])
                # Single task job:
                mantra_farm.parms['start_frame'] = frame
                mantra_farm.parms['end_frame']   = frame
                show_details("Mantra", mantra_farm.parms, mantra_farm.render()) 
