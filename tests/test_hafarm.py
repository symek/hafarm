import unittest
import sys
sys.path.append("../")
import hafarm
import const
from hafarm import HaFarmParms, hafarm_defaults, HaFarm, BatchFarm
join_tiles_output = """ /tmp/tiles/test.%04d__TILE__0.exr /tmp/tiles/test.%04d__TILE__1.exr \
--over /tmp/tiles/test.%04d__TILE__2.exr --over /tmp/tiles/test.%04d__TILE__3.exr \
--over -o /tmp/test.%04d.exr --frames 1-3 """
join_tiles_output_proxy = """ /tmp/tiles/test.%04d__TILE__0.exr /tmp/tiles/test.%04d__TILE__1.exr \
--over /tmp/tiles/test.%04d__TILE__2.exr --over /tmp/tiles/test.%04d__TILE__3.exr \
--over -o /tmp/test.%04d.exr --frames 1-3 --tocolorspace "sRGB" -ch "R,G,B" -o /tmp/proxy/test.%04d.jpg """
debug_images_output = '`ls /tmp/test.*.exr | grep -v "__TILE__" ` | grep File '

class TestHaFarmParms(unittest.TestCase):
    def test___init__(self):
        ha_farm_parms = HaFarmParms(initilize=False, defaults=hafarm_defaults)
        for key in  hafarm_defaults:
            self.assertTrue(key in ha_farm_parms.keys())
            self.assertEqual(ha_farm_parms[key],  hafarm_defaults[key])

    def test___setitem__(self):
        ha_farm_parms = HaFarmParms(initilize=False, defaults=hafarm_defaults)
        # Wrongs scenarios:
        self.assertRaises(AssertionError, ha_farm_parms.__setitem__, 'NON_EXISTING_KEY', 15) # non existing in defaults
        self.failUnlessRaises(TypeError, ha_farm_parms.__setitem__, 'slots', '15') # Integer expected
        self.assertRaises(TypeError, ha_farm_parms.__setitem__, 'make_proxy', 1) # bool expected

        ha_farm_parms['slots'] = 15
        self.assertEqual(ha_farm_parms['slots'], 15)


    def test_has_entry(self):
        ha_farm_parms = HaFarmParms(initilize=True, defaults=hafarm_defaults)
        for key in hafarm_defaults:
            self.assertTrue(ha_farm_parms.has_entry(key))

        self.assertFalse(ha_farm_parms.has_entry("WRONG_ENTRY"))
        #assert False # TODO: implement your test here

    def test_initialize_env_parms(self):
        import os
        ha_farm_parms = HaFarmParms(initilize=False, defaults=hafarm_defaults)
        ha_farm_parms.initialize_env_parms()
        self.assertEqual(ha_farm_parms['job_asset_name'], os.getenv("JOB_ASSET_NAME"))
        self.assertEqual(ha_farm_parms['job_asset_type'], os.getenv("JOB_ASSET_TYPE"))
        self.assertEqual(ha_farm_parms['job_current'], os.getenv("JOB_CURRENT"))
        self.assertEqual(ha_farm_parms['user'], os.getenv("USER"))

    def test_merge_parms(self):
        ha_farm_parms = HaFarmParms(initilize=False, defaults={})
        # Bad scenario:
        for key in hafarm_defaults:
            self.assertRaises((AssertionError, KeyError), ha_farm_parms.__getitem__, key)
        # Good scenario:
        ha_farm_parms = HaFarmParms(initilize=False, defaults=hafarm_defaults)
        for key in hafarm_defaults:
            self.assertEqual(ha_farm_parms[key], hafarm_defaults[key])
            

#class TestFrameRangeParm(unittest.TestCase):
#    def test___init__(self):
        # frame_range_parm = FrameRangeParm()
#        assert False # TODO: implement your test here

class TestHaFarm(unittest.TestCase):
    def test___init__(self):
        ha_farm = HaFarm()
        ha_farm_parms = HaFarmParms(True)
        for key in hafarm_defaults:
            self.assertEqual(ha_farm.parms[key], ha_farm_parms[key])
        
    def test_copy_scene_file(self):
        from time import time
        import os

        # Make tmp dir:
        tmp = os.tempnam()
        tmp_path, scene_file = os.path.split(tmp)
        if not os.path.isdir(os.path.join(tmp_path, 'source_dir')):
            os.mkdir(os.path.join(tmp_path, 'source_dir'))

        # Set parms:
        ha_farm = HaFarm()
        ha_farm.parms['script_path'] = tmp_path
        ha_farm.parms['job_name']    = scene_file
        ha_farm.parms['scene_file']  =  os.path.join(tmp_path, 'source_dir/%s.test' % ha_farm.parms['job_name'])

        # Create fake scene_file:
        with open(ha_farm.parms['scene_file'], 'w') as file:
            file.write('test')
            file.close()

        # We should expect something like:
        new_file = os.path.join(tmp_path, '%s.test' % ha_farm.parms['job_name'])
        # Execute:
        result   = ha_farm.copy_scene_file()
        # Check:
        self.assertTrue(os.path.isfile(new_file))
        self.assertEqual(result, new_file)


    def test_generate_unique_job_name(self):
        ha_farm = HaFarm()
        seed = "TEST_NAME"
        name1 = ha_farm.generate_unique_job_name(seed)
        name2 = ha_farm.generate_unique_job_name(seed)
        self.assertNotEqual(name1, name2)
        self.assertTrue(seed in name1)
        self.assertTrue(seed in name2)

    # def test_get_queue_list(self):
    #     # ha_farm = HaFarm()
    #     # self.assertEqual(expected, ha_farm.get_queue_list())
    #     assert False # TODO: implement your test here

    # def test_post_schedule(self):
    #     # ha_farm = HaFarm()
    #     # self.assertEqual(expected, ha_farm.post_schedule())
    #     assert False # TODO: implement your test here

    # def test_pre_schedule(self):
    #     # ha_farm = HaFarm()
    #     # self.assertEqual(expected, ha_farm.pre_schedule())
    #     assert False # TODO: implement your test here

    # def test_render(self):
    #     # ha_farm = HaFarm()
    #     # self.assertEqual(expected, ha_farm.render())
    #     assert False # TODO: implement your test here

class TestBatchFarm(unittest.TestCase):
    def test___init__(self):
        batch_farm = BatchFarm("Test", parent_job_name=[], queue='3d')
        self.assertEqual(batch_farm.parms['job_name'], "Test")
        self.assertEqual(batch_farm.parms['hold_jid'], [])
        self.assertEqual(batch_farm.parms['queue'], "3d")

    def test_debug_images(self):
        batch_farm = BatchFarm("Test", [], '3d')
        batch_farm.debug_images('/tmp/test.0001.exr')
        self.assertEqual(batch_farm.parms['command_arg'], [debug_images_output])

    def test_join_tiles(self):
        batch_farm = BatchFarm("Test", parent_job_name=[], queue='3d')
        sequence = '/tmp/test.0001.exr'
        result = batch_farm.join_tiles(sequence, 1, 3, 4)
        self.assertEqual([result], batch_farm.parms['command_arg'])
        self.assertEqual(result, join_tiles_output)
        self.assertEqual(batch_farm.parms['command'], const.OIIOTOOL)

    def test_join_tiles_proxy(self):
        import os
        batch_farm = BatchFarm("Test", parent_job_name=[], queue='3d')
        batch_farm.parms['make_proxy'] = True
        sequence = '/tmp/test.0001.exr'
        result = batch_farm.join_tiles(sequence, 1, 3, 4)
        self.assertEqual([result], batch_farm.parms['command_arg'])
        self.assertEqual(result, join_tiles_output_proxy)
        self.assertEqual(batch_farm.parms['command'], const.OIIOTOOL, 'batchfarm command should match const.OIIOTOOL')
        proxy_path = os.path.join('/tmp', const.PROXY_POSTFIX)
        self.assertTrue(os.path.exists(proxy_path), "This path should exist: %s" % proxy_path)
        



#     def test_make_movie(self):
#         # batch_farm = BatchFarm(job_name, parent_job_name, queue, command, command_arg)
#         # self.assertEqual(expected, batch_farm.make_movie(filename))
#         assert False # TODO: implement your test here

if __name__ == '__main__':
    unittest.main()
