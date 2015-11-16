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

# This is hand crafted minimal and unoptimized graph engine
# for building DAGs from actions (pipline tasks in case of hafarm).
# It's a subject of change or replaced by something more robust 
# and optimized.
import inspect 

class Graph(dict):
    pass

class HaResource(object):
    pass

class HaAction(object):
    #__metaclass__ = abc.ABCMeta
    def __init__(self, name=None):
        """ Initialize  a list of direct input actions referenced by its unique names.
        """
        from uuid import uuid4
        self.inputs = []
        self.uuid   = uuid4()
        self.name   = name

        # RootAction will return new instance only 
        # for first node in module
        self.root   = RootAction()
        self.root.add_node(self)
       
    def is_root(self):
        return False

    def __repr__(self):
        if self.name:
            name = self.name
        else:
            name = self.uuid
        return "'%s'" % name

    def add_input(self, action): 
        """Adds input to self.
        """
        # Shell we raise here?
        if action == self:
            raise TypeError("Can't make self an input.")

        # TODO: Clean it up!
        if issubclass(action.__class__, HaAction):
            if action not in self.inputs:
                self.inputs.append(action)
                return True
        else:
            raise TypeError("Child %s is sublcass of %s" % (action, type(HaAction)))
        return

    def add_inputs(self, actions):
        """Multi action addition.
        """
        for action in actions:
            self.add_input(action)
        return True

    def remove_input(self, action):
        """Removes action from self inputs.
        """
        if action in self.inputs:
            idx = self.inputs.index(action)
            return self.inputs.pop(idx)
        return

    def get_direct_inputs(self, ignore_types=None):
        """ Returns a list of direct inputs to current action.
            ignore_types should be lists/tuples.
        """
        inputs = []
        # Stright from self.inputs:
        if not ignore_types:
            return self.inputs
        else:
            # Type check for ignore_types list/tuple:
            if not hasattr(ignore_types, '__iter__'):
                if inspect.isclass(ignore_types):
                    ignore_types = (ignore_types,)
                else:
                    raise TypeError("ignore_types must be either class of list of classes.")
            # Return either filtered inputs or go recurently further to
            # find child which passes filter test.
            for action in self.inputs:
                if True in [isinstance(action, type) for type in ignore_types]:
                    inputs += action.get_direct_inputs(ignore_types=ignore_types)
                else:
                    inputs += [action]

        return inputs

    def get_renderable_inputs(self):
        """ Returns a list of direct inputs or a list
            of inputs of inputs, if current input is NullAction.
            TODO: This depreciated in faviour of 
            get_direct_inputs(ignore=(NullAction,)) (not implemented.)
        """
        inputs = []
        for action in self.get_direct_inputs():
            if issubclass(action.__class__, HaFarm) \
            or isinstance(action, HaFarm):
                inputs += [action]
            else:
                inputs += action.get_renderable_inputs()
        return inputs

    def get_all_inputs(self):
        """ Returns a list of all input actions (including indirect inputs).
        """
        def get_inputs_recurently(action, actions):
            for child in action.get_direct_inputs():
                if child not in actions:
                    actions += [child]
                if child.get_direct_inputs():
                    get_inputs_recurently(child, actions)

        actions = []
        get_inputs_recurently(self, actions)
        return actions

    def get_direct_outputs(self):
        """Returns all actions with self as direct input.
        """
        # TODO: brute force:
        result = []
        actions = self.root.get_all_nodes()
        for action in actions:
            if self in action.get_direct_inputs():
                result += [action]
        return result
        
    def get_root_output(self):
        """ Returns a single action without outputs and with the longest children list.
            Note: this is probably obsolute function, as we have direct access to root
            anyway now, and this is what that function was meant for.
        """
        # TODO: brute force
        parents = []
        winner  = 0
        output  = None
        actions = self.root.get_all_nodes()
        for action in actions:
            if not action.get_direct_outputs():
                parents += [action]

        for parent in parents:
            nchildren = len(parent.get_all_inputs())
            if nchildren > winner:
                output = parent
                winner = nchildren

        return output

    def get_all_parents(self):
        """ Returns a list of actions without outputs.
        """
         # TODO: brute force
        parents = []
        actions = self.root.get_all_nodes()
        for action in actions:
            if not action.get_direct_outputs():
                parents += [action]
        return parents

    def insert_input(self, action):
        """ Insert action beteen self and all its children.
        """
        children = self.get_direct_inputs()
        # FIXME: Not sure why calling remove_input()
        # works only for first child, but we should not deal
        # with self.inputs directly (subject of change).
        self.inputs = []
        for child in children:
            action.add_input(child)
        # and node to our inputs (making it our child)
        self.add_input(action)
        return True

    def insert_inputs(self, children):
        ''' Multi-insert != N x insert_input().
        '''
        current_children = self.get_direct_inputs()
        # FIXME: Again: remove_input() doesnt work
        # but I should not play with self.inputs directly
        self.inputs      = []
        for child in current_children:
            for new_child in children:
                new_child.add_input(child)
        for child in children:
            self.add_input(child)
        return True

    def insert_output(self, action):
        """ Insert action between self and all its outputs.
        """
        parents = self.get_direct_outputs()
        action.add_input(self)
        for parent in parents:
            parent.remove_input(self)
            parent.add_input(action)
        return True

    def insert_outputs(self, children):
        """ Multi-insert != N x insert_output().
        """
        parents = self.get_direct_outputs()
        for parent in parents:
            print parent.remove_input(self)
        for child in children:
            for parent in parents:
                    parent.add_input(child)
            child.add_input(self)
        return True


class NullAction(HaAction):
    """ Actions which does nothing. Place holder to build graph
        with unsuppored nodes.
    """
    def __init__(self, name=None):
        super(NullAction, self).__init__(name)
        self.job_name = name
    def render(self):
        pass



class RootAction(HaAction):
    """ Singelton class keeping all memebers of graph
        and playing as root of tree. 
    """
    _instance = None
    name = 'root'
    nodes = list()
    inputs = list()
    # NOTE: This is singelton class
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RootAction, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        # NOTE: We can't call super() here...
        from uuid import uuid4
        self.uuid = uuid4()
        self.root = self
        if self not in self.nodes:
            self.nodes += [self]

    def get_all_nodes(self):
        """ Returns a list of all actions in graph.
        """
        # NOTE: return copy, so no one will screw
        # our list?
        return self.nodes

    def add_node(self, node):
        """ Add node to a graph. This shouldn't be call
            in general, as nodes add themself to root.nodes
            on creation.
        """
        if node not in self.nodes:
            self.nodes.append(node)

    def add_nodes(self, nodes):
        """ Multi-addition. See above.
        """
        self.nodes += list(nodes)

    def clear(self):
        """ Removes all nodes from root.
        """
        self.nodes = list()
        self.inputs = list()
        self.nodes += [self]

    def is_root(self): 
        """ Are we a root?
        """
        return True

    def render(self):
        """ We do not render.
        """
        pass




class HaFarm(HaAction):
    """Parent class to be inherited by host specific classes (Houdini, Maya, Nuke etc).
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





