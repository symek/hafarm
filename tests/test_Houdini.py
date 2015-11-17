#!$HFS/bin/hython
import unittest
import sys, os

# FIXME: Just Can't handle it. Studio installed version breaks tests. 
# Tests with relative paths break while running cases because tested 
# objects import our modules and expects proper paths...

# Remove studio-wide installation:
try:
    index = sys.path.index("/STUDIO/studio-packages")
    sys.path.pop(index)
except:
    pass

# make ../../ha/hafarm visible for tests:
sys.path.insert(0, os.path.join(os.getcwd(), "../.."))

try:
    import hou
except ImportError:
    print "Tests have to be run in presence of Houdini python module or by hython."
    sys.exit()

import hafarm
from hafarm import Houdini
from hafarm.Houdini import HbatchFarm
from hafarm.Houdini import MantraFarm
from hafarm.hafarm  import NullAction
from hafarm.hafarm  import RootAction


class TestHbatchFarm(unittest.TestCase):
    def setUp(self):
        self.nt     = hou.node('/out')
        self.rop    = self.nt.createNode("ifd")
        self.farm   = self.nt.createNode("HaFarm")
        self.farm.setFirstInput(self.rop)
        self.end_frame = 100
        self.rop.parm('trange').set(1)
        self.rop.parm('f2').deleteAllKeyframes()
        self.rop.parm('f2').set(self.end_frame)

    def test___init__(self):
        hbatch_farm = Houdini.HbatchFarm(self.farm, self.rop)
        self.assertEqual(Houdini.HbatchFarm, type(hbatch_farm))
        self.assertTrue('--generate_ifds' in hbatch_farm.parms['command_arg'])
        self.assertEqual(self.end_frame, hbatch_farm.parms['end_frame'])
        self.assertEqual(self.rop.parm("vm_picture").eval(), hbatch_farm.parms['output_picture'])
        self.assertEqual(self.rop.path(), hbatch_farm.parms['target_list'][0])
    

    def test_pre_schedule(self):
        hbatch_farm = Houdini.HbatchFarm(self.farm, self.rop)
        hbatch_farm.pre_schedule()
        hbatch_farm.parms['command_arg']
        self.assertEqual(['--ignore_tiles', '--generate_ifds', '', '-d /out/mantra2'], \
            hbatch_farm.parms['command_arg'])
        # assert False # TODO: implement your test here

class TestMantraFarm(unittest.TestCase):
    def setUp(self):
        hou.hipFile.clear()
        self.nt     = hou.node('/out')
        self.rop    = self.nt.createNode("ifd")
        self.farm   = self.nt.createNode("HaFarm")
        self.farm.setFirstInput(self.rop)
        self.end_frame = 100
        self.rop.parm('trange').set(1)
        self.rop.parm('f2').deleteAllKeyframes()
        self.rop.parm('f2').set(self.end_frame)

    def test___init__(self):
        hbatch_farm = Houdini.HbatchFarm(self.farm, self.rop)
        job_name    = hbatch_farm.parms['job_name'] + "_mantra"
        mantra_farm = Houdini.MantraFarm(self.farm, self.rop, job_name=job_name)
        self.assertEqual(Houdini.MantraFarm, type(mantra_farm))
        self.assertEqual(self.end_frame, mantra_farm.parms['end_frame'])
        self.assertEqual(self.rop.parm("vm_picture").eval(), mantra_farm.parms['output_picture'])
        self.assertEqual(self.rop, mantra_farm.rop)

    # def test_pre_schedule(self):
        # mantra_farm = MantraFarm(node, rop, job_name, crop_parms)
        # self.assertEqual(expected, mantra_farm.pre_schedule())
        # assert False # TODO: implement your test here





class TestMantraRenderFrameList(unittest.TestCase):
    def setUp(self):
        hou.hipFile.clear()
        self.nt     = hou.node('/out')
        self.rop    = self.nt.createNode("ifd")
        self.farm   = self.nt.createNode("HaFarm")
        self.farm.setFirstInput(self.rop)
        self.end_frame = 100
        self.rop.parm('trange').set(1)
        self.rop.parm('f2').deleteAllKeyframes()
        self.rop.parm('f2').set(self.end_frame)
        self.farm.parm('use_frame_list').set(1)
        self.farm.parm('frame_list').set("1,3,5")
        self.hbatch_farm = Houdini.HbatchFarm(self.farm, self.rop)

    def test_mantra_render_frame_list(self):
        frames = [1,3,5]
        mframes = Houdini.mantra_render_frame_list(self.hbatch_farm, frames)
        self.assertEqual(mframes, self.hbatch_farm.get_direct_outputs())
        self.assertEqual(len(frames), len(mframes))
        self.assertTrue("-l 1,3,5" in self.hbatch_farm.parms['command_arg'])
        for frame in range(len(frames)):
            self.assertEqual(mframes[frame].parms['start_frame'], frames[frame])
            self.assertEqual(mframes[frame].parms['end_frame'], frames[frame])
            self.assertEqual(mframes[frame].get_direct_inputs()[0], self.hbatch_farm)



class TestMantraRenderWithTiles(unittest.TestCase):
    def setUp(self):
        hou.hipFile.clear()
        self.nt     = hou.node('/out')
        self.rop    = self.nt.createNode("ifd")
        self.farm   = self.nt.createNode("HaFarm")
        self.farm.setFirstInput(self.rop)
        self.end_frame = 100
        self.rop.parm('trange').set(1)
        self.rop.parm('f2').deleteAllKeyframes()
        self.rop.parm('f2').set(self.end_frame)
        self.rop.parm("vm_tile_render").set(1)
        self.hbatch_farm = Houdini.HbatchFarm(self.farm, self.rop)
        # job_name         = hbatch_farm.parms['job_name'] + "_mantra"
        # self.mantra_farm = Houdini.MantraFarm(self.farm, self.rop, job_name=job_name)

    def test_mantra_render_with_tiles(self):
        tiles, merger = Houdini.mantra_render_with_tiles(self.hbatch_farm)
        self.assertEqual(len(tiles), 16)
        self.assertFalse(False in [merger == x.get_direct_outputs()[0] for x  in tiles])
        for tile in range(16):
            self.assertTrue("--tiling 4%4%" + str(tile) in tiles[tile].parms['command'])
            self.assertTrue(tiles[tile].parms['job_name'].endswith("__TILE__%s" % str(tile)))

# class TestMantraRenderFromIfd(unittest.TestCase):
#     def test_mantra_render_from_ifd(self):
#         # self.assertEqual(expected, mantra_render_from_ifd(node, frames, job_name))
#         assert False # TODO: implement your test here

# class TestPostRenderActions(unittest.TestCase):
#     def test_post_render_actions(self):
#         # self.assertEqual(expected, post_render_actions(node, actions, queue))
#         assert False # TODO: implement your test here

# class TestBuildGraph(unittest.TestCase):
#     def test_build_graph(self):
#         # self.assertEqual(expected, build_graph(hafarm_rop, verbose))
#         assert False # TODO: implement your test here

# class TestRenderRecursively(unittest.TestCase):
#     def test_render_recursively(self):
#         # self.assertEqual(expected, render_recursively(root, dry_run, ignore_types))
#         assert False # TODO: implement your test here

# class TestBuildDebugGraph(unittest.TestCase):
#     def test_build_debug_graph(self):
#         # self.assertEqual(expected, build_debug_graph(parent, subnet))
#         assert False # TODO: implement your test here

# class TestRenderPressed(unittest.TestCase):
#     def test_render_pressed(self):
#         # self.assertEqual(expected, render_pressed(node))
#         assert False # TODO: implement your test here

if __name__ == '__main__':
    for test in unittest.TestCase.__subclasses__()[1:]:
         case = unittest.TestLoader().loadTestsFromTestCase(test)
         unittest.TextTestRunner(verbosity=3).run(case)
