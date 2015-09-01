# Standards:
import os

# Custom: 
import hafarm


class ClarisseFarm(hafarm.HaFarm):
    def __init__(self):
        super(ClarisseFarm, self).__init__()
        self.parms['command']     = '$CLARISSE_HOME/crender '
        self.parms['command_arg'] = []
        self.parms['output_picture'] = ""
        self.parms['req_license']    = 'clarisselic=1' 
        self.parms['req_resources']  = ''
        self.parms['job_on_hold'] = True
        self.parms['frame_range_arg'] = ["-start_frame %s -end_frame %s", 'start_frame', 'start_frame']

        # First renderable camera we encounter will be the one we choose by default,
        # So basically we don't support multicamera rendering deliberatly.
        # for camera in maya.cmds.ls(type='camera'):
        #     if maya.cmds.getAttr(camera + ".renderable"):
        #         self.parms['target_list']    = [str(camera)]
        #         break

        # Frame range:
        # self.parms['start_frame'] = int(maya.cmds.playbackOptions(query=True, ast=True))
        # self.parms['end_frame']   = int(maya.cmds.playbackOptions(query=True, aet=True))

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

        # Add Render Layer to commanline:
        # if self.parms['layer_list']: command += ["-l "]
        # for layer in self.parms['layer_list']:
        #     command += ['%s ' % layer]

        self.parms['command_arg'] = command

        # Any debugging info [object, outout]:
        return []
        #return ['pre_schedule(): %s ' % command]

    def post_schedule(self):
        """
        """
        # FIXME Ugly fix for wrong arguments' treatment inside sungrid.py
        # Need to remove last argumetn from commandline...
        script_path = os.path.join(self.parms['script_path'], self.parms['job_name'] + '.job')
        script_path = os.path.expandvars(script_path)
        with open(script_path) as file:
            lines = file.readlines()
            file.close()
        with open(script_path, 'w') as file:
            for line in lines:
                if line.startswith("$CLARISSE_HOME"):
                    line = line.split()[:-1]
                    line = " ".join(line)
                    line += '\n'
                file.write(line)
            file.close()
        return []
