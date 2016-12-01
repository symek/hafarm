# Standards:
import os
# Custom: 
import hafarm


class MayaFarm(hafarm.HaFarm):

    def makeAbc(self, scene_path, output_path, abc_args):
        """ Export alembic file.
        """
        file_name = os.path.basename(scene_path)
        self.parms['job_name'] = self.generate_unique_job_name(file_name)
        self.parms['scene_file'] = scene_path
        self.parms['output_picture'] = output_path
        self.parms['command_arg'] = abc_args
        self.parms['command'] = '$MAYA_LOCATION/bin/mayapy'
        self.parms['start_frame'] = 1
        self.parms['end_frame'] = 48
        self.parms['step_frame'] = 48
