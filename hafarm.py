import os, sys, json

# TODO: We either do proper Python's  eggs (see: http://docs.pylonsproject.org/projects/pylons-webframework/\
# en/latest/advanced_pylons/entry_points_and_plugins.html) or make something like: managers/__init__.py 
# will search through  HAFARM_PLUGINS path (specified via env var.) for all classes derived 
# from RenderManager and add them to its subspace managers.*, so below import will bring them here. 
# What if some plugin requeres custom module (like qube.py)? This should be catched
# inside managers module (maybe managers should even call  manager.test_connection() to verify
# that the backend under considertion works at all?)
import managers

from manager import RenderManager, DummyManager
from logger import Logger
from parms import HaFarmParms

import const
import utils

class Action(object):
    actions = []
    def __init__(self):
        '''Initialize  a list of direct input actions reference by its unique names.
        '''
        pass

    def get_all_actions(self):
        '''Returns a list of all input actions (including indirect inputs).
        '''
        pass

    def is_related(self, action):
        '''Finds if provided action relates on current action.
        '''
        pass

    def get_my_recipe(self, action):
        '''Returns a list of nececery steps to fulfill current action requirements.
        '''
        pass

    def get_direct_inputs(self):
        '''Returns a list of direct inputs to current action.
        '''
        return self.actions



class HaFarm(Action):
    """Parent class to be inherited by host specific classes (Houdini, Maya, Nuke etc).
    It's a child of renderfarm manager class (currently SGE, but maybe any thing else in
    a future: OpenLava/whatever. Neither this class nor its children should notice if
    underlying manager will change.
    """
    def __init__(self, job_name='', parent_job_name=[], queue='', backend = 'Sungrid', backend_version = None):
        # super(HaFarm, self).__init__()
        self.render_backends = {}
        self.parms   = HaFarmParms(initilize=True)
        self.logger  = Logger(self.__class__.__name__)  
        self.manager = DummyManager() # This is dummy object usefil for debugging.

        # Find some less dummy render manager:
        if not self.install_render_backend(backend, backend_version):
            self.logger.info("Can't find any backend. Using Dummy()")

        # Attach parms right to manger
        # TODO: Should be change this behavior? 
        self.manager.parms = self.parms

    def install_render_backend(self, backend, version):
        """Find RenderManager subclasses and attach it to self.manager as a rendering backend.
        """
        for plugin in RenderManager.__subclasses__(): 
            self.render_backends[plugin.__name__] = plugin
        self.logger.debug('Registered backends: %s ' % self.render_backends)

        # If reqested backend was found in correct version make it the manager:
        if not backend in self.render_backends.keys():
            return False
        else:
            if version:
                if self.render_backends[backend].version == version:
                    self.manager = self.render_backends[backend]()
                else:
                    # No backend with requested version found.
                    return False
            else:
                self.manager = self.render_backends[backend]()
        return True

    def generate_unique_job_name(self, name='no_name_job'):
        """Returns unique name for a job. 'Name' is usually a scene file. 
        """
        from base64 import urlsafe_b64encode
        name = os.path.basename(name)
        return "_".join([os.path.split(name)[1], urlsafe_b64encode(os.urandom(3))])
        

    def copy_scene_file(self, scene_file=None):
        """Makes a copy of a scene file.
        """
        import shutil

        if not scene_file:
            scene_file = self.parms['scene_file']

        # TODO: Currenty scene file is copied into job script directory
        # We might want to customize it, along with the whole idea of
        # coping scene. 
        filename, ext  = os.path.splitext(scene_file)
        path           = os.path.expandvars(self.parms['script_path'])
        new_scene_file = os.path.join(path, self.parms['job_name']) + ext
        self.parms['scene_file'] = new_scene_file

        # We do either file copy or link copy. The latter one is less expensive
        # but less safe also, as we do use render cache as backup history from
        # time to time... :/
        try:
            if os.path.islink(scene_file):
                linkto = os.readlink(scene_file)
                os.symlink(linkto, new_scene_file)
            else:
                shutil.copy2(scene_file, new_scene_file)
        except (IOError, os.error), why:
            self.logger.debug('%s: %s' % (new_scene_file, why))
            new_scene_file = None


        return {'copy_scene_file': new_scene_file}

    def render(self):
        """Make defaults steps, scene copy and call parent specific command.
        """
        from time import time
        self.parms['submission_time'] = time()


        # This should stay renderfarm agnostic call.

        # Save current state into file/db:
        save_result= self.save_parms()
        self.logger.info(save_result[1])
        # Render:
        pre_result = self.pre_schedule()
        result     = self.manager.render()
        post_result= self.post_schedule()

        # Info logger call:
        for item in result:
            if isinstance(result[item], type([])):
                output = " ".join(result[item])
            elif isinstance(result[item], type("")):
                output = result[item]
            else:
                output = result[item]

            self.logger.info("%s: %s" % (item, output))
        
        # Debugging. Should const.DEBUG overwrite HAFARM_DEBUG?
        # Should we select levels? 
        try: 
            debug = int(os.getenv("HAFARM_DEBUG"))
            if debug >= 1 and const.DEBUG != 0:
                self.logger.debug(self.parms)
        except:
                self.logger.debug("No HAFARM_DEBUG env. var.: %s (should be an integer)" % os.getenv("HAFARM_DEBUG"))

        return result


    def save_parms(self, save_to_db=False, parms_file=None):
        """ Save current state of a job into a file and/or database (TO BE DONE).
            This should be enough information to reacreate a job on farm with old 
            or any other backend.
        """
        _db = {}
        _db['actions']      = self.get_direct_inputs()
        _db['class_name']   = self.__class__.__name__
        _db['backend_name'] = self.manager.__class__.__name__
        _db['parms']        = self.parms

        if not parms_file:
            parms_file = os.path.expandvars(self.parms['script_path'])
            parms_file = os.path.join(parms_file, self.parms['job_name']) + ".json"

        with open(parms_file, 'w') as file:
            result = json.dump(_db, file, indent=2)
        return result, parms_file

    def load_parms_from_file(self, parms_file):
        """
        """
        with open(parms_file) as file:
            result = json.load(file)
            self.parms.merge_parms(result['parms'])
            self.parms['job_name'] = self.generate_unique_job_name(self.parms['job_name'])


    def get_queue_list(self):
        """Returns queue list as provided by render manager.
        """
        return self.manager.get_queue_list()

    def get_job_stats(self, job_name):
        """Returns job's statistics from render manger.
        """
        return self.manager.get_job_stats(job_name)

    def pre_schedule(self):
        """This should be provided by derived classes to perform any application specific actions before the submit.
        """
        return []

    def post_schedule(self):
        """This should be provided by derived classes to perform any application specific actions after the submit.
        """
        return []





