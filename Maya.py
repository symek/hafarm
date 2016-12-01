# Standards:
import os
import shutil
# Custom: 
import hafarm


class MayaFarm(hafarm.HaFarm):

    def makeAbc(self, scene_path, abc_args, output_path):
        """ Export alembic file.
        """
        # Create an unique job name, than copy scene file.
        job_name = self.createJobName(scene_path)
        scene_path = self.copyScene(scene_path, job_name)
        # Collect command arguments.
        args = list()
        args.append('/STUDIO/maya/maya2016/scripts/hafarm/maya_abc.py')
        args.append(scene_path)
        args += abc_args
        args.append('-file ' + output_path)
        # Set HaFarm parms.
        self.parms['job_name'] = job_name
        self.parms['scene_file'] = scene_path
        self.parms['output_picture'] = output_path
        self.parms['command_arg'] = args
        self.parms['command'] = '$MAYA_LOCATION/bin/mayapy'
        self.parms['start_frame'] = 1
        self.parms['end_frame'] = 48
        self.parms['step_frame'] = 48

    def createJobName(self, scene_path):
        file_name = os.path.basename(scene_path)
        prefix, extention = file_name.split('.')
        new_prefix = self.generate_unique_job_name(prefix)
        job_name = '.'.join([new_prefix, extention])
        return str(job_name)

    def copyScene(self, scene_path, job_name):
        script_path = os.path.expandvars(self.parms['script_path'])
        new_scene_path = os.path.join(script_path, job_name)
        shutil.copy2(scene_path, new_scene_path)
        return new_scene_path
