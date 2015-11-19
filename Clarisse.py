# Standards:
import os, sys

# Custom: 
import hafarm

# Host specific:
import ix


class ClarisseFarm(hafarm.HaFarm):
    def __init__(self):
        # Note: Force non-default version of backend support class.
        super(ClarisseFarm, self).__init__(backend='Sungrid')
        self.parms['command']     = '$CLARISSE_HOME/crender '
        self.parms['command_arg'] = []
        self.parms['output_picture'] = ""
        self.parms['req_license']    = 'clarisselic=1' 
        self.parms['req_resources']  = ''
        self.parms['job_on_hold'] = False
        #NOTE We render single frame per task, so double 'start_frame' isn't a bug.
        self.parms['frame_range_arg'] = ["-start_frame %s -end_frame %s", 'start_frame', 'start_frame']


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

        # Scene file.
        command += ['@SCENE_FILE/>']
        
        # Add camera option to commanline:
        camera  = self.parms['target_list']
        command += [' -image %s ' % camera[0]]

        self.parms['command_arg'] = command

        # Any debugging info [object, outout]:
        return []



"""
==================  THIS IS TEMPORARY HAFARM GUI for NON-PyQt environment. ==========================
"""


CLARISSE_FORMATS = ('.exr', '.exr', ".jpg", ".bmp", ".tga", ".png", ".png", ".tiff", ".tiff", ".tiff")

class RenderButton(ix.api.GuiPushButton):
    def __init__(self, parent, x, y, w, h, label):
        ix.api.GuiPushButton.__init__(self, parent, x, y, w, h, label)
        self.connect(self, 'EVT_ID_PUSH_BUTTON_CLICK', self.on_click)
        self.parent = parent

    def on_click(self, sender, evtid):
        '''Runs per selected iamge in Clarisse GUI.
        '''
        render_archive  = self.parent.parms['render_archive']
        selected_images = self.parent.parms['selected_images']
        path, job_name  = os.path.split(render_archive)

        for image in selected_images:
            farm = ClarisseFarm()
            farm.parms['priority']    = 0
            farm.parms['job_on_hold'] = False
            farm.parms['scene_file']  = str(render_archive) 
            farm.parms['target_list'] = [image.get_full_name()]

            # target image to render:
            picture_path = image.m_object.get_attribute("save_as").get_string()
            format_idx   = int(image.m_object.get_attribute("format").get_double())
            farm.parms['output_picture'] = picture_path + "00001" +  CLARISSE_FORMATS[format_idx]

            # name, frame range per Clarisse image:
            farm.parms['job_name']    = farm.generate_unique_job_name(job_name) + "_" + image.get_name()
            farm.parms['start_frame'] = int(image.m_object.get_attribute("first_frame").get_string())
            farm.parms['end_frame']   = int(image.m_object.get_attribute("last_frame").get_string())

            # Get rid of frames = 0
            if farm.parms['start_frame'] < 1: 
                farm.parms['start_frame'] = 1

            farm.render()

        self.set_label('Render sent!')



def hafarm_run():
    """To be called by shelf button in Clarisse.
    """
    # If archive is not there, quit:
    render_archive =  ix.api.GuiWidget_open_file(ix.application)
    if not render_archive or not os.path.isfile(render_archive):
        sys.exit()

    # Windows and its labeling.
    window = ix.api.GuiWindow(ix.application, 5, 0, 320, 280)
    label  = ix.api.GuiLabel(window, 5, 5, 320, 40, "Clarisse Hafarm manager.")
    label.set_justification(ix.api.GuiWidget.JUSTIFY_CENTER)
    # TODO: This isn't used atm
    label2  = ix.api.GuiLabel(window, 5, 10, 320, 70, "Host groups:")
    groups = ix.api.GuiListView(window, 5, 60, 100, 60)
    for group in ('allhosts', 'renders', 'workstations'):
        groups.add_item(str(group))

    # The list of selected images
    selected_images = []
    for item in ix.selection:
        if item.is_kindof("Image"):
            selected_images.append(item)

    # The list of Clarisse imagaes to be rendered one by one on a farm (these will be separeted jobs)
    label3  = ix.api.GuiLabel(window, 5, 110, 320, 60, "Clarisse images:")
    images  = ix.api.GuiLineEdit(window, 5,150, 320, 20, " ". join([x.get_name() for x in selected_images]))

    # Get frame range
    frame_range = ix.application.get_current_frame_range()
    start_frame = int(frame_range[0])
    end_frame   = int(frame_range[1])

    # Get rid of 0 frame...
    if start_frame < 1: start_frame = 1

    # Set frameranges
    startFrameLabel  = ix.api.GuiLabel(window,  200, 60, 80, 20, "Start Frame:")
    startFrameLineEdit = ix.api.GuiLineEdit(window, 280, 60, 40, 20)
    startFrameLineEdit.set_text(str(start_frame))
    endFrameLabel  = ix.api.GuiLabel(window,  200, 80, 80, 20, "End Frame:")
    endFrameLineEdit = ix.api.GuiLineEdit(window, 280, 80, 40, 20)
    endFrameLineEdit.set_text(str(end_frame))

    # Render me button
    renderButton = RenderButton(window, 5, 250, 128, 22, "Render")

    # FIXME: In proper class this wouldn't be here...
    window.parms = {}
    window.parms['selected_images'] = selected_images
    window.parms['render_archive']  = render_archive
    window.parms['start_frame'] = start_frame
    window.parms['end_frame']   = end_frame
    # show time...
    window.show()
    while window.is_shown(): ix.application.check_for_events()