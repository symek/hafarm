import abc


class RenderManager(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        pass

    @abc.abstractproperty
    def register_manager(self):
        return True

    @abc.abstractmethod
    def test_connection(self):
        '''Test renderfarm backend condidtion.'''
        return

    @abc.abstractmethod
    def render(self):
        '''Triggers convertion from host app object into Exchange version.'''
        return

    @abc.abstractmethod
    def get_queue_list(self):
        '''Triggers conversion from Exchange object into host specific one.'''
        return

    @abc.abstractmethod
    def get_group_list(self):
        '''Triggers conversion from Exchange object into host specific one.'''
        return

    @abc.abstractmethod
    def get_host_list(self):
        '''Triggers conversion from Exchange object into host specific one.'''
        return


