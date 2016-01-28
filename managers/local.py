# Concurent: 
import multiprocessing, logging
from multiprocessing import Process, Pipe, Manager
from multiprocessing.connection import Listener, Client
from xmlrpclib import ServerProxy
from SimpleXMLRPCServer import SimpleXMLRPCServer
from subprocess import Popen, PIPE
from Queue import PriorityQueue
import threading
from threading import Lock

# Std
import traceback
import sys, time, os

# Python 2.6 compatibility:
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

# Own
import hafarm
from hafarm import utils
from hafarm import const
from hafarm.parms import HaFarmParms
from hafarm.manager import RenderManager 

__plugin__version__ = 0.1

HOST = 'localhost'
XMLRPC_SOCKET  = 15000
CONNECT_SOCKET = 25000
AUTHKEY        = b'HAFARM'
QUEUE_MAXITEMS = 100

class Cmp(object):
    """ Custom comparator wrapper, so we can refer to built-in
        compare methods via getattr.
        FIXME: Is it necessery?
    """
    def __init__(self, value):
        self._v = value
    def __lt__(self, x):
        return self._v < x
    def __le__(self, x):
        return self._v <= x
    def __gt__(self, x):
        return self._v > x
    def __ge__(self, x):
        return self._v >= x
    def __eq__(self, x):
        return self._v == x
    def __ne__(self, x):
        return self._v != x


class LocalQueue(object):
    """ Custom Queue object. Not thread-safe atm (!).
    """
    _queue = OrderedDict()
    _lock  = Lock()
    _log   = dict()
    def __init__(self, maxitems):
        self.maxitems = maxitems
        pass

    def put(self, job, sort=True):
        """ Puts new item into a queue and sort it by
            item['priority'] value.
        """
        if not isinstance(job, type({})) \
        and not isinstance(job, HaFarmParms)\
        or len(self._queue) >= self.maxitems:
            return 
        # TODO: Type checking on job_candidate 
        # NOTE: currently HAFARM priority spawns -1024 <--> 1024 (SGE style), 
        priority = 1 - ((job['priority'] + 1024) / 2048.0)
        self._lock.acquire()
        self._queue[job['job_name']] = job
        if sort:
            self.sort_queue()
        self._lock.release()
        return True

    def puts(self, jobs):
        """ Multi-insert.
        """
        for job in jobs:
            self.put(job, False)
        self.reorder_queue()
        return True

    def get(self, run_tests=True):
        """ Get job with hightest priority possibly passing 
            some tests. Warning: job won't be removed from queue. 
            Use pop() instead.
        """
        # self._lock.acquire()
        if self._queue.keys():
            if not run_tests:
                return self._queue.values()[-1]
            else:
                return self.pop(remove_from_queue=False)


    def pop(self, running_jobs=None, remove_from_queue=True, run_tests=True):
        """ Returns job with hightest priority removing it from
            the queue at once. Optional remove_from_queue downgrade pop()
            to getting item to allow scheduler perform other tests.
            run_tests = False disables any scheduler logic except priority.
            running_jobs: list of job_names currently in progress passed here
            from the scheduler.
        """
        self._running_jobs = running_jobs
        # FIXME: temporal workaround...
        def get_value_from_field(item, field): 
            return item, item[field]
        def none_of_in_queue(dependencies, tmp):
            inqueue = [job for job in dependencies if job in self._queue.keys()]
            return not inqueue
        def none_of_in_progress(dependencies, tmp):
            progress_status = self._running_jobs
            # assert(progress_status.has_key['job_name'])
            inprogress = [job for job in dependencies if job in progress_status.keys()]
            inprogress = [job for job in inprogress if progress_status[job]['is_alive']]
            return not inprogress
        def run_test_cases(item, cases):
            """ Cases are: (field, value, job.callable=None, callable=None, 
                            alternator=None)
                If both callable are none basic comparision is performed (==).
                If both are functions(), they will be evaluated, and then combined with AND.
                Optional alternator(item, value) is pre-pass for a field/value.

                jcall() is typicly one of: __le__, __lt__, __gt__, 
                                           __ge__, __eq__, __nq__, __cmp__
                call() is any of bool = call(job[field], value).
            """
            from copy import deepcopy
            # TODO: Cache to amortize?
            if not item['job_name'] in self._log.keys():
                self._log[item['job_name']] = [None,]
            _cases = deepcopy(cases)
            while _cases:
                case = _cases.pop(0)
                assert(len(case) == 5)
                field, value, jcall, call, alternator = case
                assert(item.has_key(field))
                # Alternate value:
                if alternator:
                    assert(callable(alternator))
                    item, value = alternator(item, value)
                # Basic item[field], value comparision:
                # NOTE: Early quit on False (not checking other cases)
                if not jcall and not call:
                    if not item[field] == key:
                        self._log[item['job_name']] += [" ".join(str(x) \
                            for x in (field, jcall, call, value))]
                        return False
                # Both built-in comparision AND custom callable():
                elif jcall and call:
                    assert(hasattr(item[field], jcall))
                    assert(callable(call))
                    if not getattr(Cmp(item[field]), jcall)(value) and call(item[field], value):
                        self._log[item['job_name']] += [" ".join(str(x) \
                            for x in (field, jcall, call, value))]
                        return False
                # Test with method from Cmp() which are standard ><==!=:
                elif jcall:
                    assert(hasattr(Cmp(item[field]), jcall))
                    if not getattr(Cmp(item[field]), jcall)(value):
                        self._log[item['job_name']] += [" ".join(str(x) \
                            for x in (field, jcall, call, value))]
                        return False
                # Test with custom callable():
                elif call:
                    assert(callable(call))
                    if not call(item[field], value):
                        self._log[item['job_name']] += [" ".join(str(x) \
                            for x in (field, jcall, call, value))]
                        return False
            # All tests passed:
            self._log.pop(item['job_name'])
            return True

        def get_key_passing_cases_recursive(cases, idx=-1):
            """ Apply recursively conditional tests on queue's items.
                Return key of an item which passes the test or None,
                if no items pass the tests.
            """
            # Nothing left (we iterate from the last to first):
            if abs(idx) > len(self._queue): return None
            key = self._queue.keys()[idx]
            if run_test_cases(self._queue[key], cases):
                return key
            else:
                return get_key_passing_cases_recursive(cases, idx-1)

        # MAIN PART
        # We might want to proceed without any conditions...:
        if not run_tests:
            if self._queue.keys():
                self._lock.acquire()
                key = self._queue.keys()[-1]
                item = self._queue.pop(key)
                self._lock.release()
                return item
            else:
                return None

        # We will test items against following conditions:
        # TODO: Make TestCaseSuite external object.
        cases = []
        # Hold condition:
        cases += [('job_on_hold', False, '__eq__', None, None)]
        # Start time condition:
        cases += [('req_start_time', time.time(), '__le__', None, None)]
        # in-queue dependencies:
        cases += [('hold_jid', 'job_name', None, none_of_in_queue, get_value_from_field)]
        # NOTE: We have runtime dependency here (on running jobs), but queue doesn't know 
        # about running jobs, should we pass it to Queue like atm?
        # Overwise we would have to perform check on Scheduler side. That would imply
        # some sort of black list, as jobs conditionally assinged to pop() would have 
        # be ignored in second search... unless we remove them tempraray from queue and add
        # back after search, but that would require lots of redundand work. This is slow here
        # Anyway...
        if running_jobs:
            cases += [('hold_jid', 'job_name', None, none_of_in_progress, get_value_from_field)]

        item = None
        if self._queue.keys():
            self._lock.acquire()
            key = get_key_passing_cases_recursive(cases, -1)
            if key:
                if remove_from_queue: item = self._queue.pop(key)
                else: item = self._queue[key]
            self._lock.release()
            return item
        return None

    def sort_queue(self, key='priority'):
        """ Sorts queue based on items' key,
            assuming item are dictonaries. 
        """
        self._queue = OrderedDict(sorted(self._queue.items(), \
            key=lambda k: k[1][key]))

    def empty(self):
        return len(self._queue) == 0

    def qsize(self):
        return len(self._queue)

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
    _logger  = None
    _queue   = LocalQueue(QUEUE_MAXITEMS)
    _tasks   = []
    _rpc_methods_ = ['job_submit', 'job_get_status', 'get_queue_size', \
    'job_terminate', 'job_exists', 'get_queue_priority']

    def __init__(self, address=('', XMLRPC_SOCKET), **kwargs):
        """ Register xmlrpc functions for xmlrpc server.
            Initalize XMLRPC server wihtin its onw thread.
            Start listening on conneciton pipe for a new jobs.
        """
        # TODO: This used to be right bellow class LocalServer() which means
        # that was executed on module import. Check whether it works this way too.
        _manager = Manager()
        _status  = _manager.dict()
        _stdout  = _manager.dict()
        _stderr  = _manager.dict()
        # Logger:
        if kwargs.get("log", True) and not self._logger:
            self._logger = multiprocessing.log_to_stderr()
            self._logger.setLevel(logging.INFO)
        # Max # or tasks running sumultaniously...
        self.maxtasks = kwargs.get("maxtasks", 1)
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

    def queue_loop(self, interval=5):
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
            # TODO: Logging is needed here as we need to know the reason
            # Queue pops or refuses to use item.
            while not self._queue.empty():
                job_candidate = self._queue.pop(running_jobs=self._status)
                if not job_candidate:
                    time.sleep(interval)
                    continue
                # Limit the number of tasks running in the same time:
                # FIXME: Use process counting instead of home-brew stuff.
                if len([task for task in self._status.keys() \
                    if self._status[task]['is_alive']]) >= self.maxtasks:
                    time.sleep(interval)
                    continue
                status = self._manager.dict()
                self._status[job_candidate['job_name']] = status
                job_process   = LocalProcess(job_candidate, status)
                job_process.start()
                time.sleep(interval)
            time.sleep(interval)

    def job_submit(self, job_file):
        """ Remote method used for job submission.
        """
        if os.path.isfile(job_file):
            job_candidate = hafarm.HaFarm()
            job_candidate.load_parms_from_file(job_file, overwrite_name=False)
            return self._queue.put(job_candidate.parms)
        return

    def get_queue_size(self):
        """ Remote method returning all
            jobs currently queued.
        """
        return self._queue.qsize()

    def get_queue_priority(self):
        return [(self._queue._queue[x]['job_name'], \
            self._queue._queue[x]['priority']) for x in self._queue._queue.keys()]

    def get_jobs(self): pass
    def job_get_status(self, job_id): pass
    def job_terminate(self, job_id): pass
    def job_exists(self, job_id): pass


class LocalScheduler(RenderManager):
    _instance = None
    
    _logger   = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            # print "Creating instance of %s" % str(cls)
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

    def get_queue_priority(self):
        return self._proxy.get_queue_priority()


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


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()


        
