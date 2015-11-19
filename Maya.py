# Standards:
import os
# Host's specific:
import maya.cmds as cmds
# Custom: 
import hafarm


class MayaFarm(hafarm.HaFarm):
    def __init__(self):
        super(MayaFarm, self).__init__()
        self.parms['command']     = '$MAYA_LOCATION/bin/Render'
        self.parms['command_arg'] = ['-mr:v 4 ']
        self.parms['scene_file']  = str(cmds.file(save=True))
        self.parms['job_name']    = self.generate_unique_job_name(self.parms['scene_file'])
        self.parms['output_picture'] = ""
        self.parms['req_license']    = 'mayalic=1' 
        self.parms['req_resources']  = ''
        self.parms['frame_range_arg'] = ["-s %s -e %s", 'start_frame', 'end_frame']

        # First renderable camera we encounter will be the one we choose by default,
        # So basically we don't support multicamera rendering deliberatly.
        for camera in cmds.ls(type='camera'):
            if cmds.getAttr(camera + ".renderable"):
                self.parms['target_list']    = [str(camera)]
                break


        # Frame range
        self.startFrame = int(cmds.playbackOptions(query=True, min=True))
        self.parms['start_frame'] = self.startFrame
        cmds.setAttr('defaultRenderGlobals.startFrame', self.startFrame)
        
        self.endFrame = int(cmds.playbackOptions(query=True, max=True))
        self.parms['end_frame'] = self.endFrame
        cmds.setAttr('defaultRenderGlobals.endFrame', self.endFrame)


    def pre_schedule(self):
        '''This method is called automatically before job submission by HaFarm.
            Up to now:
            1) All information should be aquired from host application.
            2) They should be placed in HaFarmParms class (self.parms).
            3) Scene should be ready to be copied to handoff location.
            
            Main purpose is to prepare anything specific that HaFarm might not know about, 
            like renderer command and arguments used to render on farm.
        '''
        # TODO: copy_scene_file should be host specific.
        result  = self.copy_scene_file()

        command = self.parms['command_arg']
        # Threads (mentalray specific atm)
        command += ['-mr:rt %s ' % self.parms['slots']]
        
        # Add camera option to commanline
        camera  = self.parms['target_list']
        command += [' -cam %s ' % camera[0]]

        # Add Render Layer to commandline
        if self.parms['layer_list']: command += ["-l "]
        for layer in self.parms['layer_list']:
            command += ['%s ' % layer]

        self.parms['command_arg'] = command

        # Any debugging info [object, outout]
        return []
        #return ['pre_schedule(): %s ' % command]


class MayaFarmGUI(object):
    '''Pure GUI class for MayaFarm. It holds MayaFarm instance in self.farm variable. 
    '''
    def __init__(self, *args):
        self.farm = MayaFarm()

    def show(self):
        self.createMyLayout()
        
    def createMyLayout(self):
        '''
        Basic window for render parameters. It's minimalistic, as most scene settings we derive stright
        from Maya.
        '''
        # Check if an instance of Ha Render Settings window already exists
        if cmds.window('haRenderWnd', ex = True):
            cmds.deleteUI('haRenderWnd')
               
        # Create window
        self.window = cmds.window('haRenderWnd', title = 'HA Render Settings', width = 500, height = 300, sizeable = True)
        fieldWidth = 60
        checkboxHeight = 20      
       
        # COMMON
                
        # Create menu
        cmds.columnLayout(adjustableColumn=True)
        cmds.frameLayout(label = 'Settings', borderStyle = 'etchedIn', lv = 0, mh = 5, mw = 5)
        cmds.frameLayout(label = 'Common', collapsable = True, borderStyle = 'out')
        cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 150), (2, 200)], columnAttach = (1, 'right', 5))
        
        # Create render queue list
        cmds.text(label = 'Render queues:')
        self.queue_list = cmds.optionMenu(cc = self.change_queue)        
        for q in self.farm.manager.get_queue_list(): 
            cmds.menuItem(label = q)
            cmds.setParent(menu = True)
        
        # Create host groups list
        cmds.text(label = 'Host group:')  
        self.group_list = cmds.optionMenu(cc = self.change_group)
        for q in self.farm.manager.get_group_list(): 
            cmds.menuItem(label = q)
            cmds.setParent(menu = True)
        
        # Create renderers list
        cmds.text(label = 'Renderer:')
        self.group_list = cmds.optionMenu(cc = self.change_renderer)
        for q in self.get_renderers_list():
            cmds.menuItem(label = q)
            cmds.setParent(menu = True)
            
        # Create cameras list
        cmds.text(label = 'Renderable camera:')
        cmds.optionMenu(cc = self.change_camera)
        for q in self.get_camera_list():
            cmds.menuItem(label = q)
            cmds.setParent(menu = True)

        # Create renderable layers list
        cmds.text(label = 'Renderable layer:')
        layers = self.get_layer_list()
        self.layer_list = cmds.textScrollList(numberOfRows = 5, ams = True, append = layers, sc = self.change_layers)
        
        # Hold toggle      
        cmds.text(label = '')
        self.holdcheckBox = cmds.checkBox(label='Submit job on hold', height = checkboxHeight, cc = self.change_hold)
        
        cmds.setParent('..')
        cmds.setParent('..')

        # MEMORY
              
        cmds.frameLayout(label = 'Memory', collapsable = True, borderStyle = 'out')
        cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 150), (2, 200)], columnAttach = (1, 'right', 5))     
        
        # Priority, slots, memory:            
        cmds.text(label = 'Render priority:')
        cmds.intSliderGrp(value = self.farm.parms['priority'], field = True, min = -1023, max = 0, step = 100, columnWidth = (1, fieldWidth), cc = self.change_priority)
        
        cmds.text(label = 'Number of slots:')
        self.slotsSld = cmds.intSliderGrp(value = self.farm.parms['slots'], field = True, enable = True, min = 1, max = 24, step = 1, columnWidth = (1, fieldWidth), cc = self.change_slots)
        
        cmds.text(label = '')
        cmds.checkBox(label='Set CPU share', height = checkboxHeight, cc = self.set_cpu)
                
        cmds.text(label = 'CPU share:')
        self.cpuSld = cmds.floatSliderGrp(value = self.farm.parms['cpu_share'], field = True, enable = False, min = 0.01, max = 1.0, step = 0.01, columnWidth = (1, fieldWidth), cc = self.change_cpu)

        cmds.text(label = 'Required memory (in GB):')
        cmds.intSliderGrp(value = self.farm.parms['req_memory'], field = True, min = 1, max = 16, step = 1, columnWidth = (1, fieldWidth), cc = self.change_memory)

        cmds.setParent('..')
        cmds.setParent('..')
        
        # FRAME RANGE
                
        cmds.frameLayout(label = 'Frame Range', collapsable = True, borderStyle = 'out')
        cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 150), (2, 60)], columnAttach = (1, 'right', 5))
                
        cmds.text(label = 'Start frame:')
        cmds.intField(value = int(cmds.playbackOptions(query=True, min=True)), cc = self.change_startFrame)
        
        cmds.text(label = 'End frame:')
        cmds.intField(value = int(cmds.playbackOptions(query=True, max=True)), cc = self.change_endFrame)     
        
        # MISCELLANEOUS
                
        cmds.setParent('..')
        cmds.setParent('..')
        cmds.frameLayout(label = 'Miscellaneous', borderStyle = 'out', collapsable = True, collapse = False)
        cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 150), (2, 200)], columnAttach = (1, 'right', 5))
                       
        cmds.text(label = 'Delay:')
        cmds.textField(cc = self.set_delay)
        
        cmds.text(label = '')
        cmds.checkBox(label='Make proxy', height = checkboxHeight, cc = self.make_proxy)
             
        cmds.setParent('..')
        cmds.setParent('..')
        cmds.setParent('..')
        cmds.setParent('..')      

        # RENDER
                
        form = cmds.formLayout()
        self.renderButton = cmds.button(label = 'Render', command = self.renderButton_pressed, height = 27)
        
        cmds.formLayout(
            form,
            edit = True,
            attachForm = [(self.renderButton, 'bottom', 5), (self.renderButton, 'left', 5), (self.renderButton, 'right', 5)])

        # Show window
        cmds.showWindow(self.window)


    def renderButton_pressed(self, v):
        '''Send render and print some info.'''
        result = self.farm.render()
        self.farm.parms['scene_file']  = str(cmds.file(save=True))
 

    # LISTS    
          
    def get_renderers_list(self):
        return cmds.renderer(query = True, namesOfAvailableRenderers = True)

    def get_layer_list(self):
        return cmds.ls(type="renderLayer")

    def get_camera_list(self):
        return cmds.listCameras()
        

    # CALLBACKS
    
    def change_queue(self, v):
        '''Callback for selected queue change.'''
        self.farm.parms['queue'] = str(v)

    def change_group(self, v):
        '''Callback for host group change.'''
        self.farm.parms['group'] = str(v)

    def change_renderer(self, v):
        '''Callback for renderer change.'''
        cmds.setAttr('defaultRenderGlobals.ren', str(v), type='string')
        
    def change_camera(self, v):
        '''Callback for change of render camera in command_arg parms.'''
        # TODO: This probably should be replaced with some more generic engine, lile:
        # parms['camera'] and pre_schedule() action.
        self.farm.parms['target_list'] = [str(v)]
        
        for q in self.get_camera_list():
            if q == v:
                cmds.setAttr(str(q) + "Shape.renderable", True)
            else:
                cmds.setAttr(str(q) + "Shape.renderable", False)
                
                
    def change_layers(self):
        '''Set of layes were changed.'''
        # NOTE: we can't specify in command line defaultRenderLayer, as Maya refuses to load a scene.
        the_list = [str(layer) for layer in \
        cmds.textScrollList(self.layer_list, query=True, selectItem=True) if layer != "defaultRenderLayer"]
        self.farm.parms['layer_list'] = the_list
        
    def change_hold(self, v):
        '''Callback to enable the hold toggle.'''
        self.farm.parms['job_on_hold'] = bool(v)
        
    def change_priority(self, v):
        '''Callback to change the requested priority.'''
        self.farm.parms['priority'] = int(v)
        
    def change_slots(self, v):
        '''Callback to change the number of requested slots.'''
        self.farm.parms['slots'] = int(v)
        
    def set_cpu(self, v):
        '''Callback to change the number of slots in use.'''
        if v == True:
            cmds.intSliderGrp(self.slotsSld, edit = True, enable = False)
            cmds.floatSliderGrp(self.cpuSld, edit = True, enable = True)
        else:
            cmds.intSliderGrp(self.slotsSld, edit = True, enable = True)
            cmds.floatSliderGrp(self.cpuSld, edit = True, enable = False)
            
    def change_cpu(self, v):
        '''Callback to change the requested cpu share.'''
        self.farm.parms['cpu_share'] = float(v)
        
    def change_memory(self, v):
        '''Callback to change the memory text label.'''
        self.farm.parms['req_memory'] = int(v)
        
    def change_startFrame(self, v):
	'''Callback to set the start frame.'''
        self.farm.parms['start_frame'] = int(v)
        cmds.setAttr('defaultRenderGlobals.startFrame', v)
        
    def change_endFrame(self, v):
        '''Callback to set the end frame.'''
        self.farm.parms['end_frame'] = int(v)
        cmds.setAttr('defaultRenderGlobals.endFrame', v)
        
    def make_proxy(self, v):
        '''Callback to enable making proxy.'''
        self.farm.parms['make_proxy'] = bool(v)
        
    def set_delay(self, v):
	'''Callback to enable setting delay.'''
        self.farm.parms['delay'] = int(v)

gui = MayaFarmGUI()
gui.show()
