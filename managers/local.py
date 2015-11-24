# Concurent: 
import multiprocessing, logging
from multiprocessing import Process, Pipe, Manager
from multiprocessing.connection import Listener, Client
from xmlrpclib import ServerProxy
from SimpleXMLRPCServer import SimpleXMLRPCServer
from subprocess import Popen, PIPE
from Queue import PriorityQueue
# Std
import threading
import traceback
import sys, time, os
# Own
import hafarm
from hafarm import utils
from hafarm import const
from hafarm.manager import RenderManager 

__plugin__version__ = 0.1

HOST = 'localhost'
XMLRPC_SOCKET  = 15000
CONNECT_SOCKET = 25000
AUTHKEY        = b'HAFARM'


class LocalProcess(Process):
    def __init__(self, parms, status, feedback=False):
        super(LocalProcess, self).__init__()
        self.parms  = parms
        self.status = status
        self.deamon = True
        self.name   = parms['job_name']
        self.feedback = feedback

    def run(self):
        """ Run command saved in parms.
        """
        command = [self.parms['command']] + list(self.parms['command_arg'])
        sp = Popen(command, shell=False, stdout=PIPE, stderr=PIPE)
        # Child job is running...
        while sp.poll() is None:
            try: 
                self.status['pid']      = self.pid
                self.status['is_alive'] = self.is_alive()
            except: 
                pass
        # We finished job:
        try: 
            self.status['is_alive']      = False
            self.status['exitcode']      = sp.returncode
        except: 
            pass

class LocalServer(object):
    """ LocalSever is spawned first time HaFarm is executed,
        and keeps track of localed jobs. It brings basic functionality
        of cluster schedulers / renderfarm managers. 
        There are two ways of communicating with LocalSever process:
            - via xmlrpc server 
            - via pipe connection multiprocessing.connection
            The latter one allows trasfering pickable objects,
            the former one executes LocalServer's commands. () 
    """
    _queue   = PriorityQueue(100)
    _manager = Manager()
    _tasks   = []
    _status  = _manager.dict()
    _stdout  = _manager.dict()
    _stderr  = _manager.dict()
    # 
    _rpc_methods_ = ['job_submit', 'job_get_status', 'get_queue_size', \
    'job_terminate', 'job_exists',]

    def __init__(self, address=('', XMLRPC_SOCKET)):
        """ Register xmlrpc functions for xmlrpc server.
            Initalize XMLRPC server wihtin its onw thread.
            Start listening on conneciton pipe for a new jobs.
        """
        # multiprocessing.conneciton pipe:
        self._pipe    = Listener(('', CONNECT_SOCKET), authkey=AUTHKEY)
        # Server to execute remote commands (see _rpc_methods):
        self._serv = SimpleXMLRPCServer(address, allow_none=True)
        for name in self._rpc_methods_:
            self._serv.register_function(getattr(self, name))
        # Start xmlrpc server in own thread:
        rpc_thread = threading.Thread(target=self._serv.serve_forever)
        rpc_thread.start()
        # Start main loop:
        self.queue_loop()

    def queue_loop(self, interval=1):
        """ This is main loop of the scheduler.
            We do as follows:
                - we listen for new jobs via pipe.
                - we place them in private list checking if
                  job is sutable to run (dependencies)
                - job which pass the test, are placed in PriorityQueue we have.
                - we get job from a queue and start new execution process.
        """
        while True:
            # Submit job to remote processes:
            while not self._queue.empty():
                priority, job_scheduled = self._queue.get()
                print "Job prepared for running: " + job_scheduled['job_name']
                status = self._manager.dict()
                self._status[job_scheduled['job_name']] = status
                job_process   = LocalProcess(job_scheduled, status)
                job_process.start()
                print "Job started: " + job_scheduled['job_name']
                time.sleep(interval)
            time.sleep(interval)
            print self._status



    def job_submit(self, job_file):
        """ Remote method used for job submission.
        """
        if os.path.isfile(job_file):
            job_candidate = hafarm.HaFarm()
            job_candidate.load_parms_from_file(job_file)
            # TODO: Type checking on job_candidate 
            # NOTE: currently HAFARM priority spawns -1024 <--> 1024 (SGE style), 
            priority = 1 - ((job_candidate.parms['priority'] + 1024) / 2048.0)
            self._queue.put((priority, job_candidate.parms))
            return True
        return

    def get_queue_size(self):
        """ Remote method returning all
            jobs currently queued.
        """
        return self._queue.qsize()

    def get_jobs(self): pass
    def job_get_status(self, job_id): pass
    def job_terminate(self, job_id): pass
    def job_exists(self, job_id): pass


class LocalScheduler(RenderManager):
    _instance = None
    
    _logger   = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            print "Creating instance of %s" % str(cls)
            cls._instance = super(LocalScheduler, cls).__new__(
                                cls, *args, **kwargs)
            cls._proxy    = ServerProxy('http://%s:%s' \
                % (HOST, XMLRPC_SOCKET), allow_none=True)
            # cls._client   = Client((HOST, CONNECT_SOCKET),\
             # authkey=AUTHKEY)
        else:
            print "Reusing instance of %s" % str(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        super(LocalScheduler, self).__init__(*args, **kwargs)
        self.feedback = kwargs.get('feedback', False)
        # Logger:
        if kwargs.get("log", True) and not self._logger:
            self._logger = multiprocessing.log_to_stderr()
            self._logger.setLevel(logging.INFO)

    def job_submit(self, parms):
        """ Submits job via pipe to server.
        """
        # result = self._client.send(parms)

        print "LocalScheduler sending job" + str(result)
        return result

    def get_queue_size(self):
        """ Returns a number of currently queued jobs.
        """
        return self._proxy.get_queue_size()


    @property
    def register_manager(self):
        # TODO: How we could test here
        # if this is proper implementation of RenderManager?
        # calling test_connection()? or running attached unittest?
        # Do we need this at all?
        return True

    @property
    def version(self):
        return __plugin__version__ 

    def render(self, parms):
        """ This will be called by any derived class, to submit the jobs to farm. 
        Any information are to be provided in HaFarmParms class kept in self.parms
        variable.
        """
        self.parms = dict(parms)
        job_file  = os.path.join(self.parms['script_path'], self.parms['job_name'] + ".json")
        return self._proxy.job_submit(job_file)
         

    def get_queue_list(self):
        """Get list of defined queues from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -sql
        return ('localhost',)

    def get_group_list(self):
        """Get list of defined groups from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -shgrpl
        return ('localhost')

    def get_host_list(self):
        """Get list of defined groups from manager. 
        NOTE: API candidate.."""
        #TODO: get this from sge with qconf -shgrpl
        return ['localhost']

    def get_job_stats(self, job_name):
        return

    def test_connection(self):
        return





        
