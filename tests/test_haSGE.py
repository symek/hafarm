import unittest
import sys, os, tempfile, stat
sys.path.append("../")
import const
from haSGE import HaSGE
from parms import HaFarmParms, hafarm_defaults

_create_job_script_output =\
"""#!/bin/bash
#$ -t 1-1:1
LAST_FRAME=1
RANGE_FRAME=$[${SGE_TASK_ID}+1]
if ((${RANGE_FRAME}>${LAST_FRAME})); then RANGE_FRAME=${LAST_FRAME}; fi
echo Render start: `date`
echo Machine name: ${HOSTNAME}
echo User    name: ${USER}
echo Slots:        $NSLOTS
echo Processors  : `nproc`
NPROC=`nproc`
echo Memory stats: `egrep 'Mem|Cache|Swap' /proc/meminfo`
echo Scene file  : 
echo haSGE_unittest  
echo Render ends: `date`
echo Render target: 
echo Command was: echo haSGE_unittest [''] 
"""

_create_submit_command_output = ['qsub', '-N', 'haSGE_unittest', '-V', '-r', 'yes', '-o',\
                                '/PROD/dev/sandbox/user/symek/render/sungrid/log', \
                                '-e', '/PROD/dev/sandbox/user/symek/render/sungrid/log', \
                                '-q', 'dev', '-ac', 'OUTPUT_PICTURE=', '-p', '-500', '-hard', \
                                '-l', 'procslots=15', '-ckpt', 'check_suspend', '__PLACEHOLDER__']



class TestHaSGE(unittest.TestCase):

    def setUp(self):
        self.job_name = 'haSGE_unittest'
        self.path = tempfile.gettempdir()
        self.expected_path = os.path.join(self.path, self.job_name + '.job' )
        self.sge = HaSGE()
        # HaSge doesn't have default params!!!
        # This is why it's so good to write test cases, good chance to find own bugs
        # and stupid mistakes.... ouch!
        self.sge.parms = HaFarmParms()
        # Set params:
        self.sge.parms['script_path'] = self.path
        self.sge.parms['job_name'] = self.job_name
        self.sge.parms['queue'] = 'dev'
        self.sge.parms['end_frame'] = 1
        self.sge.parms['command'] = 'echo %s' % self.job_name


    def test__create_job_script(self):
        
        # Run
        script_path   = self.sge._create_job_script()

        # Check:
        self.assertEqual(script_path, self.expected_path)
        self.assertTrue(os.path.isfile(script_path))

        # File exists?
        with open(script_path) as file:
            script = file.read()
            self.assertEqual(script, _create_job_script_output)

        # Also raising errors is expected while attempt to write to protected file/location:
        os.chmod(script_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        self.assertRaises((IOError,), self.sge._create_job_script)

        # Cleanup:
        os.remove(script_path)


    def test__create_submit_command(self):

        command = self.sge._create_submit_command()
        _create_submit_command_output[-1] = self.expected_path
        self.assertEqual(command, _create_submit_command_output )
        self.assertEqual(command, self.sge.qsub_command)

        # subprocess is very fussy about arguments:
        for word in command:
            self.assertTrue(isinstance(word, type("")))
            self.assertTrue(word[0].isalnum() or word.startswith("-") or word.startswith(os.path.sep))
       



    # def test_get_group_list(self):
    #     # ha_sg_e = HaSGE()
    #     # self.assertEqual(expected, ha_sg_e.get_group_list())
    #     assert False # TODO: implement your test here

    # def test_get_queue_list(self):
    #     # ha_sg_e = HaSGE()
    #     # self.assertEqual(expected, ha_sg_e.get_queue_list())
    #     assert False # TODO: implement your test here

    # def test_render(self):
    #     # ha_sg_e = HaSGE()
    #     # self.assertEqual(expected, ha_sg_e.render())
    #     assert False # TODO: implement your test here

if __name__ == '__main__':
    unittest.main()
