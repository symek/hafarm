# Standards:
import os

# Custom: 
import hafarm


class ClarisseFarm(hafarm.HaFarm):
    def __init__(self):
        # Note: Force non-default version of backend support class.
        super(ClarisseFarm, self).__init__(backend='Sungrid2')
        self.parms['command']     = '$CLARISSE_HOME/crender '
        self.parms['command_arg'] = []
        self.parms['output_picture'] = ""
        self.parms['req_license']    = 'clarisselic=1' 
        self.parms['req_resources']  = ''
        self.parms['job_on_hold'] = False
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
        # Threads (mentalray specific atm):
        command += [self.parms['scene_file']]
        
        # Add camera option to commanline:
        camera  = self.parms['target_list']
        command += [' -image %s ' % camera[0]]

        self.parms['command_arg'] = command

        # Any debugging info [object, outout]:
        return []