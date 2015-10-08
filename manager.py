import abc
__plugin__version__ = 0


class RenderManager(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        pass

    @abc.abstractproperty
    def register_manager(self):
        return True

    @abc.abstractproperty
    def version(self):
        return __plugin__version__

    @abc.abstractmethod
    def test_connection(self):
        '''Test renderfarm backend condidtion.'''
        return

    @abc.abstractmethod
    def render(self, params):
        '''Sends job to farm. '''
        return

    @abc.abstractmethod
    def get_queue_list(self):
        '''Get possible queues / pools from render manager.'''
        return

    @abc.abstractmethod
    def get_group_list(self):
        '''Get posible host froup (subsets of queues) from render manager.'''
        return

    @abc.abstractmethod
    def get_host_list(self):
        '''Get the list of all hosts in render farm. '''
        return

    @abc.abstractmethod
    def get_job_stats(self, job_id):
        '''Get detailed statistics of finshed jobs.'''
        return {}



class DummyManager(RenderManager):
    @property
    def register_manager(self):
        return True
    @property
    def version(self):
        return __plugin__version__

    def test_connection(self):
        return True

    def render(self, parms):
        return {'DummyManager': 'I do not render, I am a placeholder.'}

    def get_queue_list(self):
        return []

    def get_host_list(self):
        return []

    def get_group_list(self):
        return []
        
    def get_job_stats(self, job_id):
        return {}




