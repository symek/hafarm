import os, sys, json, abc

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

class Graph(dict):
    pass

class HaResource(object):
    pass



#TODO: This isn't still  correct...
class HaAction(object):
    #__metaclass__ = abc.ABCMeta
    def __init__(self, graph=None):
        '''Initialize  a list of direct input actions referenced by its unique names.
        '''
        self.inputs = []

    def get_all_inputs(self):
        '''Returns a list of all input actions (including indirect inputs).
        '''
        def get_inputs_recurently(action, actions):
            for child in action.get_direct_inputs():
                actions += [child]
                actions += get_inputs_recurently(child, actions)
            return actions

        actions = []
        actions = get_inputs_recurently(self, actions)
        return actions

    def is_related(self, action, graph):
        '''Finds if provided action relates on current action.
        '''
        pass

    def get_my_recipe(self, graph):
        '''Returns a list of nececery steps to fulfill current action requirements.
        '''
        pass

    def get_direct_inputs(self):
        '''Returns a list of direct inputs to current action.
        '''
        return self.inputs

    def get_renderable_inputs(self):
        ''' Returns a list of direct inputs or a list
        of inputs of inputs, if current input is NullAction
        '''
        inputs = []
        for action in self.get_direct_inputs():
            if issubclass(action.__class__, HaFarm) \
            or isinstance(action, HaFarm):
                inputs += [action]
            else:
                inputs += action.get_renderable_inputs()
        return inputs

    def insert_input(self, child, actions):
        ''' Add self to edge between A and B.
        '''
        # First find child's parents:
        parents = child.get_direct_outputs(actions)

        for parent in parents:
            # Remove child from parents' inputs
            # and add self instead of it:
            parent.remove_input(child)
            parent.add_input(self)
            
        # Finally add child to self:
        self.add_input(child)
        return True

    def insert_inputs(self, children, actions):
        '''Multi-insert wrapper.
        '''
        for child in children:
            self.insert_input(child, actions)

    def get_all_parents(self, actions):
        ''' Returns a list of actions without outputs.
        '''
         # FIXME: brute force
        parents = []
        for action in actions:
            if not action.get_direct_outputs(actions):
                parents += [action]
        return parents


    def get_output_parent(self, actions):
        '''Returns a single action without outputs and with the longest children list.
        '''
        # FIXME: brute force
        parents = []
        winner  = 0
        output  = None
        for action in actions:
            if not action.get_direct_outputs(actions):
                parents += [action]

        for parent in parents:
            nchildren = len(parent.get_all_inputs())
            if nchildren > winner:
                output = parent
                winner = nchildren

        return output


    def add_input(self, action): 
        '''Adds input to a node checking if its a array job.
        '''
        # Shell we raise here?
        if action == self:
            raise TypeError("Can't make self an input.")
        if issubclass(action.__class__, HaFarm):
            if action.parms['start_frame'] != action.parms['end_frame']:
                action.array_interdependencies = True
            if action not in self.inputs:
                self.inputs.append(action)
                return True
        elif issubclass(action.__class__, NullAction):
            if action not in self.inputs:
                self.inputs.append(action)
                return True
        else:
            raise TypeError("Child is not %s" % type(self))
        return

    def add_inputs(self, actions):
        '''Multi action addition.
        '''
        for action in actions:
            self.add_input(action)

    def remove_input(self, action):
        '''Removes action from self inputs.
        '''
        if action in self.inputs:
            idx = self.inputs.index(action)
            return self.inputs.pop(idx)
        return


    def get_direct_outputs(self, actions):
        '''Get actions with self as inputs.
        '''
        # FIXME: brute force:
        result = []
        for action in actions:
            if self in action.get_direct_inputs():
                result += [action]
        return result



class NullAction(HaAction):
    def __init__(self):
        super(NullAction, self).__init__()

    def render(self):
        pass



class HaFarm(HaAction):
    """Parent class to be inherited by host specific classes (Houdini, Maya, Nuke etc).
    It's a child of renderfarm manager class (currently SGE, but maybe any thing else in
    a future: OpenLava/whatever. Neither this class nor its children should notice if
    underlying manager will change.
    """
    def __init__(self, job_name='', queue='', backend = 'Sungrid', backend_version = None):
        super(HaFarm, self).__init__()
        # Possibly useless, good for debuging:
        from uuid import uuid4
        self.id = uuid4()
        # Can we interlease per task with dependant job?:
        self.array_interdependencies  = False
        # Resolve dependecies based on provided graph or direct inputs before
        # sending to manager.
        self.resolve_dependencies = True
        # Render backends:
        self.render_backends = {}
        self.parms   = HaFarmParms(initilize=True)
        self.logger  = Logger(self.__class__.__name__)  
        self.manager = DummyManager() # This is dummy object usefil for debugging.
        # Find some less dummy render manager:
        if not self.install_render_backend(backend, backend_version):
            self.logger.info("Can't find any backend. Using Dummy()")

    def install_render_backend(self, backend, version):
        """Find RenderManager subclasses and attach it to self.manager as a rendering backend.
        """
        # FIXME That not only doesn't work well, it doesn't work at all!
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
        # TODO: Make it more suitable for disk paths. (no *, -)
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
            elif scene_file != new_scene_file:
                shutil.copy2(scene_file, new_scene_file)
            else:
                self.logger.debug("Scene file already copied. %s " % new_scene_file)
        except (IOError, os.error), why:
            self.logger.debug('%s: %s' % (new_scene_file, why))
            new_scene_file = None


        return {'copy_scene_file': new_scene_file}

    def render(self):
        """Make defaults steps, scene copy and call parent specific command.
        """
        from time import time
        self.parms['submission_time'] = time()

        # Dependences:
        # FIXME: This shouldn't be here I suppose... 
        if self.resolve_dependencies:
            if self.parms['start_frame'] != self.parms['end_frame'] \
            and self.parms['end_frame']  != self.parms['step_frame']:
                self.array_interdependencies = True

            for action in self.get_renderable_inputs():
                # Both needs to be true...
                if action.array_interdependencies and self.array_interdependencies:
                    self.parms['hold_jid_ad'] += [action.parms['job_name']]
                else:
                    self.parms['hold_jid'] += [action.parms['job_name']]

        # Save current state into file/db:
        save_result= self.save_parms()
        # self.logger.info(save_result[1])

        # Render:
        pre_result = self.pre_schedule()

        # Send our parms to scheduler...
        result     = self.manager.render(self.parms)
        post_result= self.post_schedule()

        # Info logger call:
        #FIXME THIS IS SO BAD
        # for item in result:
        #     if isinstance(result[item], type([])):
        #         output = " ".join(result[item])
        #     elif isinstance(result[item], type("")):
        #         output = result[item]
        #     else:
        #         output = result[item]

        #     self.logger.info("%s: %s" % (item, output))
        
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
        _db['inputs']       = [item.parms['job_name'] for item in self.get_renderable_inputs()]
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





