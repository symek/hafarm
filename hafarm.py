import os, sys
import ha

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


class HaFarm(object):
    """Parent class to be inherited by host specific classes (Houdini, Maya, Nuke etc).
    It's a child of renderfarm manager class (currently SGE, but maybe any thing else in
    a future: OpenLava/whatever. Neither this class nor its children should notice if
    underlying manager will change.
    """
    def __init__(self, job_name=None, parent_job_name=[], queue=None, backend = 'Sungrid', backend_version = None):
        super(HaFarm, self).__init__()
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

    def generate_unique_job_name(self, name):
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

    def get_queue_list(self):
        """Returns queue list as provided by render manager.
        """
        return self.manager.get_queue_list()

    def pre_schedule(self):
        """This should be provided by derived classes to perform any application specific actions before the submit.
        """
        return []

    def post_schedule(self):
        """This should be provided by derived classes to perform any application specific actions after the submit.
        """
        return []



# For some reason this can't be in its own module for now and we'd like to
# use it across the board, so I put it here. At some point, we should remove haSGE inheritance
# making it more like a plugin class. At that point, this problem should be reviewed.
class BatchFarm(HaFarm):
    '''Performs arbitrary script on farm. Also encapsulates utility functions for handling usual tasks.
    like tile merging, dubuging renders etc.'''
    def __init__(self, job_name=None, parent_job_name=[], queue=None, command='', command_arg=''):
        super(BatchFarm, self).__init__()
        self.parms['queue']          = queue
        self.parms['job_name']       = job_name
        self.parms['command']        = command
        self.parms['command_arg']    = [command_arg]
        self.parms['hold_jid']       = parent_job_name
        self.parms['ignore_check']   = True
        self.parms['slots']          = 1
        self.parms['req_resources'] = ''

    def join_tiles(self, filename, start, end, ntiles):
        '''Creates a command specificly for merging tiled rendering with oiiotool.'''
        from ha.path import padding

        # Retrive full frame name (without _tile%i)
        if const.TILE_ID in filename:
            base, rest = filename.split(const.TILE_ID)
            tmp, ext   = os.path.splitext(filename)
            filename   = base + ext
        else:
            base, ext  = os.path.splitext(filename)


        details = padding(filename, format='nuke')
        base    = os.path.splitext(details[0])[0]
        base, file = os.path.split(base)
        base    = os.path.join(base, const.TILES_POSTFIX, file)
        reads   = [base + const.TILE_ID + '%s' % str(tile) + ext for tile in range(ntiles)]


        # Reads:
        command = ' '
        command += '%s ' % reads[0]
        command += '%s ' % reads[1]
        command += '--over ' 

        for read in reads[2:]:
            command += "%s " % read
            command += '--over ' 

        # Final touch:
        command += '-o %s ' % details[0]
        command += '--frames %s-%s ' % (start, end)

        # Additional path for proxy images (to be created from joined tiles)
        if self.parms['make_proxy']:
            path, file = os.path.split(details[0])
            path = os.path.join(path, const.PROXY_POSTFIX)

            # FIXME: It shouldn't be here at all. 
            if not os.path.isdir(path): os.mkdir(path)

            proxy    = os.path.join(path, os.path.splitext(file)[0] + '.jpg')
            command += '--tocolorspace "sRGB" -ch "R,G,B" -o %s ' % proxy

        self.parms['command_arg'] = [command]
        self.parms['command']     = const.OIIOTOOL      
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1 
        return command

    def debug_images(self, filename):
        '''By using iinfo utility inspect filename (usually renders).'''
        from ha.path import padding
        details = padding(filename, 'shell')
        self.parms['command'] = const.IINFO
        self.parms['command_arg'] =  ['`ls %s | grep -v "%s" ` | grep File ' % (details[0], const.TILE_ID)]
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1
        self.parms['email_stdout'] = True

    def make_movie(self, filename):
        '''Make a movie from custom files. '''
        from ha.path import padding

        # Input filename with proxy correction:
        details = padding(filename, 'nuke')
        base, file = os.path.split(details[0])
        file, ext  = os.path.splitext(file)
        inputfile  = os.path.join(base, const.PROXY_POSTFIX, file + '.jpg')
        outputfile = os.path.join(base, padding(filename)[0] + 'mp4')
        command = "-y -r 25 -i %s -an -vcodec libx264 %s" % (inputfile, outputfile)
        self.parms['command'] = 'ffmpeg '
        self.parms['command_arg'] = [command]
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1

