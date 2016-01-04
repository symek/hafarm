# Standard:
import os

# Host specific:
import nukescripts, nuke

# Fix for commanline call to this module:
class FakePythonPanel(object):
    pass

if not 'PythonPanel' in nukescripts.__dict__:
    nukescripts.PythonPanel = FakePythonPanel

# Custom: 
import hafarm
from hafarm import utils

class NukeFarm(hafarm.HaFarm):
    def __init__(self, **kwargs):
        super(NukeFarm, self).__init__(**kwargs)
        version = str(nuke.NUKE_VERSION_MAJOR) + "." + str(nuke.NUKE_VERSION_MINOR)
        self.parms['command']     = 'Nuke%s' % version
        self.parms['command_arg'] = ['-x -V ']
        self.parms['scene_file']  = str(nuke.root().name())
        self.parms['job_name']    = self.generate_unique_job_name(self.parms['scene_file'])
        self.parms['req_license']    = 'nuke_lic=1' 
        self.parms['req_resources']  = ''
        self.parms['frame_range_arg'] = ["-F %s-%sx1", 'start_frame', 'end_frame']
        self.parms['step_frame']      = 5
        self.parms['ignore_check'] = True #FIXME: nuke queue doesn't have check_suspend specifid as availbe sensor,
                                          #Still it appears like it obeys it??? WTF, but doesn't render at all with False.
        self.parms['pre_render_script'] = 'nuke_tmp_dir=`mktemp -d --tmpdir=/tmp`; export NUKE_TEMP_DIR=$nuke_tmp_dir;\n echo Making Nuke own tmp place in $nuke_tmp_dir '
        self.parms['post_render_script'] = 'echo Deleting Nukes tmp: $nuke_tmp_dir; rm -rf $NUKE_TEMP_DIR;'

    def pre_schedule(self):
        """ This method is called automatically before job submission by HaFarm.
            Up to now:
            1) All information should be aquired from host application.
            2) They should be placed in HaFarmParms class (self.parms).
            3) Scene should be ready to be copied to handoff location.
            
            Main purpose is to prepare anything specific that HaFarm might not know about, 
            like renderer command and arguments used to render on farm's machines.
        """
        # TODO: copy_scene_file should be host specific.
        result  = self.copy_scene_file()
        # Command for host application:
        command = self.parms['command_arg']

        # Threads:
        command += ['-m %s ' % self.parms['slots']]

        # Add targets:
        if self.parms['target_list']:
            command += [' -X %s ' % " ".join(self.parms['target_list'])]

        # Save to parms again:
        self.parms['command_arg'] = command

        # Any debugging info [object, outout]:
        return []



# The following defines a new class called ModalFramePanel.
class NukeFarmGUI(nukescripts.PythonPanel ):
    def __init__( self ):
        nukescripts.PythonPanel.__init__( self, "NukeFarmGUI", "com.human-ark.NukeFarmGUI" )
        self.setMinimumSize(100,400)
        self.farm = NukeFarm(backend='Slurm')
        self.initGUI()

    def run(self):
        result = nukescripts.PythonPanel.showModalDialog(self)
        if result:
            self.farm.parms['queue']       = str(self.queueKnob.value())
            self.farm.parms['group']       = str(self.group_list.value())
            self.farm.parms['start_frame'] = int(self.start_frame.getValue())
            self.farm.parms['end_frame']   = int(self.end_frame.getValue())
            self.farm.parms['frame_range_arg'] = ["-F %s-%sx%s", 'start_frame', 'end_frame', int(self.every_of_Knob.getValue())]
            self.farm.parms['target_list'] = self.write_name.value().split()
            # First Write node selected will be passed as output_picture varible to render manager
            # It is used mostly for debuging, previewing etc. 
            write_node = self.farm.parms['target_list'][0]
            self.farm.parms['output_picture']   = str(nuke.root().node(write_node).knob("file").getEvaluatedValue())
            self.farm.parms['job_on_hold'] = bool(self.hold_Knob.value())
            self.farm.parms['priority']    = int(self.priorityKnob.value())

            if self.email_Knob.value():
                self.farm.parms['email_list']  = [utils.get_email_address()]
                self.farm.parms['email_opt']   = "eas"

            # Request slots exclusively:
            if self.requestSlots_Knob.value():
                self.farm.parms['req_resources'] = 'procslots=%s' % int(self.slotsKnob.value())
            nuke.scriptSave()
            print self.farm.render()
            return True
        return
                     

    def initGUI(self):
        import os
        job = os.getenv("JOB_CURRENT", "none")

        # Queue list
        self.queue_list = self.farm.manager.get_queue_list()
        self.queueKnob = nuke.Enumeration_Knob("queue", "Queue:", self.queue_list)
        self.queueKnob.setTooltip("Queue to submit job to.")
        self.queueKnob.setValue('nuke')
        self.addKnob(self.queueKnob)

        # Group list:
        self.group_list = nuke.Enumeration_Knob("group", "Host Group:", self.farm.manager.get_group_list())
        self.group_list.setTooltip("Host group to submit job to.")
        self.group_list.setValue('allhosts')
        self.addKnob(self.group_list)

        # Max render tasks:
        self.maxTasks_Knob = nuke.WH_Knob("max_tasks", 'Maximum tasks:')
        self.maxTasks_Knob.setTooltip("Maximum number of tasks running on farm at once.")
        self.maxTasks_Knob.setValue(10)
        self.addKnob(self.maxTasks_Knob)

        # Separator:
        self.separator5 = nuke.Text_Knob("")
        self.addKnob(self.separator5)

        # Write nodes list:
        write_name = " ".join([node.name() for node in nuke.root().selectedNodes() if node.Class() in ('Write',)])
        self.write_name = nuke.String_Knob("write_name", "Write nodes:")
        self.write_name.setTooltip("Write nodes selected to rendering (empty for all Writes in a scene)")
        self.addKnob(self.write_name)
        self.write_name.setValue(write_name)   

        # Separator
        self.separator2 = nuke.Text_Knob("")  
        self.addKnob(self.separator2)

        # Request slost exclusively
        self.requestSlots_Knob = nuke.Boolean_Knob("request_slots", "Request Slots")
        self.requestSlots_Knob.setTooltip("Normally Nuke doesn't require free slots on the farm, which causes instant start of rendering\
            for a cost of potentially slower renders in over-loaded conditions. This is because, unlike 3d renderes, Nuke is often limited \
            by network access, not CPU power. The toggle forces Nuke to behave like 3d renderer and run only on a machine \
            where free slots (cores) are avaiable. It will eventually run faster, but will have to wait in a queue for free resources. \
            You may try to set the slots number lower (4 for example) while toggling that on.")
        self.addKnob(self.requestSlots_Knob)

        # Threads number:
        self.slotsKnob = nuke.WH_Knob("slots", 'Slots:')
        self.slotsKnob.setTooltip("Maximum number of threads to use by Nuke.")
        self.slotsKnob.setValue(15)
        self.addKnob(self.slotsKnob)

        # Priority:
        self.priorityKnob = nuke.WH_Knob("priority", 'Priority:')
        self.priorityKnob.setTooltip("Set render priority (set lower value if you want to down grade your own renders, to control\
            which from your submited jobs are prioritized (as you can't overwrite others prority, you are about only to prioritize your own.")
        self.priorityKnob.setRange(-1023,1024)
        self.priorityKnob.setValue(-500)
        self.addKnob(self.priorityKnob)

        # Step size:
        self.stepKnob = nuke.WH_Knob("steps", 'Render step:')
        self.stepKnob.setTooltip("Number of frames in a single batch. Lower value means more throughput on the farm, and fair share of resources, \
            for a little exapnse of time.")
        self.stepKnob.setValue(5)
        self.addKnob(self.stepKnob)

        # Separator:
        self.separator3 = nuke.Text_Knob("")  
        self.addKnob(self.separator3)

        # Frames range control:
        self.start_frame = nuke.Int_Knob( "start_frame", "Start Frame:" )
        self.addKnob( self.start_frame )
        self.start_frame.setValue(int(nuke.root().knob("first_frame").getValue()))

        self.end_frame = nuke.Int_Knob( "end_frame", "End Frame:" )
        self.addKnob( self.end_frame )
        self.end_frame.setValue(int(nuke.root().knob("last_frame").getValue()))

        self.every_of_Knob = nuke.WH_Knob("every_of", 'Render every:')
        self.every_of_Knob.setTooltip("Render only the n-th frame in a row.")
        self.every_of_Knob.setValue(1)
        self.addKnob(self.every_of_Knob)

        # Separator:
        self.separator4 = nuke.Text_Knob("")  
        self.addKnob(self.separator4) 

        # On hold
        self.hold_Knob = nuke.Boolean_Knob("hold", "Submit job on hold")
        self.hold_Knob.setTooltip("Job won't start unless manually unhold in qmon.")
        self.addKnob(self.hold_Knob)

         # Email config:
        self.email_Knob = nuke.Boolean_Knob("email", "Send me mail when finished")
        self.email_Knob.setTooltip("Sends an email for every finised/aborded task.")
        self.addKnob(self.email_Knob)