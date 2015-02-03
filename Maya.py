# Standards:
import os
# Host's specific:
import maya
# Custom: 
import hafarm
reload(hafarm)
import ha



class MayaFarm(hafarm.HaFarm):
    def __init__(self):
        super(MayaFarm, self).__init__()
        self.parms['command']     = '$MAYA_LOCATION/bin/Render'
        self.parms['command_arg'] = ['-mr:v 4 ']
        self.parms['scene_file']  = str(maya.cmds.file(save=True))
        self.parms['job_name']    = self.generate_unique_job_name(self.parms['scene_file'])
        self.parms['output_picture'] = ""
        self.parms['req_license']    = 'mayalic=1' 
        self.parms['req_resources']  = ''
        self.parms['frame_range_arg'] = ["-s %s -e %s", 'start_frame', 'end_frame']

        # First renderable camera we encounter will be the one we choose by default,
        # So basically we don't support multicamera rendering deliberatly.
        for camera in maya.cmds.ls(type='camera'):
            if maya.cmds.getAttr(camera + ".renderable"):
                self.parms['target_list']    = [str(camera)]
                break

        # Frame range:
        self.parms['start_frame'] = int(maya.cmds.playbackOptions(query=True, ast=True))
        self.parms['end_frame']   = int(maya.cmds.playbackOptions(query=True, aet=True))

    def pre_schedule(self):
        """This method is called automatically before job submission by HaFarm.
            Up to now:
            1) All information should be aquired from host application.
            2) They should be placed in HaFarmParms class (self.parms).
            3) Scene should be ready to be copied to handoff location.
            
            Main purpose is to prepare anything specific that HaFarm might not know about, 
            like renderer command and arguments used to render on farm.
        """
        # TODO: copy_scene_file should be host specific.
        result  = self.copy_scene_file()

        command = self.parms['command_arg']
        # Threads (mentalray specific atm):
        command += ['-mr:rt %s ' % self.parms['slots']]
        
        # Add camera option to commanline:
        camera  = self.parms['target_list']
        command += [' -cam %s ' % camera[0]]

        # Add Render Layer to commanline:
        if self.parms['layer_list']: command += ["-l "]
        for layer in self.parms['layer_list']:
            command += ['%s ' % layer]

        self.parms['command_arg'] = command

        # Any debugging info [object, outout]:
        return []
        #return ['pre_schedule(): %s ' % command]


class MayaFarmGUI(object):
    """Pure GUI class for MayaFarm. It holds MayaFarm instance in self.farm variable. 
    """
    def __init__(self, *args):
        self.farm = MayaFarm()

    def show(self):
        self.createMyLayout()
        
    def createMyLayout(self):
        """Basic window for render parameters. It's minimalistic, as most scene settings we derive stright
           from Maya.
        """
        self.window = maya.cmds.window(widthHeight = (1000, 1000), title = "HA Render",   resizeToFitChildren = 1)
        maya.cmds.rowLayout("queue_list", numberOfColumns = 1)
        maya.cmds.columnLayout(adjustableColumn = True, columnAlign = "left", rowSpacing = 10)
        
        # Queue list:
        self.queue_list = maya.cmds.optionMenu(label = "Render Queues", cc = self.change_queue)        
        for q in self.farm.get_queue_list(): 
            maya.cmds.menuItem(label = q)
            maya.cmds.setParent(menu = True)

        # Group list:
        self.group_list = maya.cmds.optionMenu(label = "Host group", cc = self.change_group)        
        for q in self.farm.get_group_list(): 
            maya.cmds.menuItem(label = q)
            maya.cmds.setParent(menu = True)

        # Layer selection:
        layers = self.get_layer_list()
        self.layer_list = maya.cmds.textScrollList(numberOfRows = 5, ams = True, append = layers, sc = self.change_layers)

        # Camera selection:
        self.camera_list = maya.cmds.optionMenu(l = 'Render camera', cc = self.change_camera)
        current_camera_index = 1
        for c in self.get_camera_list():
            maya.cmds.menuItem(l = c)
            maya.cmds.setParent(menu=True)
            if c == self.farm.parms['target_list'][0]:
                current_camera_index = self.get_camera_list().index(c)

        # Change renderable camera:
        maya.cmds.optionMenu(self.camera_list, edit=True, select=current_camera_index+1)


        maya.cmds.separator()

        # Priority, slots, memory:
        self.priorityLabel  = maya.cmds.iconTextStaticLabel( st = 'textOnly', l = 'Render Priority: -500' )
        self.prioritySlider = maya.cmds.intSlider(ann = "Priority", min = -1023, max = 1024, value = self.farm.parms['priority'], \
                                                 step = 100, cc = self.change_priority)
        self.slotsLabel     = maya.cmds.iconTextStaticLabel(st = 'textOnly', l = 'Request Slots: 15' )
        self.slotsSlider    = maya.cmds.intSlider( min = 1, max = 24, value = self.farm.parms['slots'], \
                                                  step = 1, cc = self.change_slots)
        reqm =  self.farm.parms['req_memory']
        self.memoryLabel    = maya.cmds.iconTextStaticLabel(st = 'textOnly', l = 'Request memory: %s GB' % reqm)
        self.memorySlider   = maya.cmds.intSlider(min = 1, max = 16, value = reqm, step = 1, cc = self.change_memory)

        # Hold toggle:
        self.holdcheckBox     = maya.cmds.checkBox(label='Submit job on hold', cc= self.change_hold)

        maya.cmds.separator()
        # Render 
        self.renderButton = maya.cmds.button(label = 'Render', command = self.renderButton_pressed)

        # Show window
        maya.cmds.showWindow(self.window)

    def renderButton_pressed(self, v):
        """Send render and print some info."""
        result = self.farm.render()
        print 'Pre Render Log:'
        for x in range(len(result)/2):
            print str(result[x*2]) + str(":"), 
            print result[(x*2)+1]

        maya.cmds.deleteUI(self.window)

    def get_layer_list(self):
        """List of render layers."""
        return maya.cmds.ls(type="renderLayer")

    def get_camera_list(self):
        """List of cameras."""
        return maya.cmds.ls(type = 'camera')

    # CALLBACKS:
    def change_queue(self, v):
        """Change selected queue."""
        self.farm.parms['queue'] = str(v)

    def change_layers(self):
        """Set of layes were changed.
        """
        # NOTE: we can't specify in command line defaultRenderLayer, as Maya refuses to load a scene.
        the_list = [str(layer) for layer in \
        maya.cmds.textScrollList(self.layer_list, query=True, selectItem=True) if layer != "defaultRenderLayer"]
        self.farm.parms['layer_list'] = the_list     

    def change_camera(self, v):
        """Change render camera in command_arg parms.
        """
        # TODO: This probably should be replaced with some more generic engine, lile:
        # parms['camera'] and pre_schedule() action.
        self.farm.parms['target_list'] = [str(v)]      

    def change_slots(self, v):
        """Changed requested slots."""
        self.farm.parms['slots'] = int(v)
        maya.cmds.iconTextStaticLabel(self.slotsLabel, edit = 1, st = 'textOnly', l = 'Request Slots: %s' % v)

    def change_priority(self, v):
        """Change requested priority."""
        self.farm.parms['priority'] = int(v)
        maya.cmds.iconTextStaticLabel(self.priorityLabel, edit = 1, st = 'textOnly', l = 'Render Priority %s' % v)

    def change_memory(self, v):
        """Callback to change memory text label.
        """
        self.farm.parms['req_memory'] = int(v)
        maya.cmds.iconTextStaticLabel(self.memoryLabel, edit = 1, st = 'textOnly', l = 'Request memory: %sGB' % v)

    def change_hold(self, v):
        """Callback for on hold toggle.
        """
        self.farm.parms['job_on_hold'] = bool(v)

    def change_group(self, v):
        """Callback for host group change.
        """
        self.farm.parms['group'] = str(v)
