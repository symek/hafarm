#!/usr/bin/python2.6
import unittest
import sys, os, tempfile

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

def enableHouModule():
    '''Set up the environment so that "import hou" works.'''
    import sys, os

    # Importing hou will load in Houdini's libraries and initialize Houdini.
    # In turn, Houdini will load any HDK extensions written in C++.  These
    # extensions need to link against Houdini's libraries, so we need to
    # make sure that the symbols from Houdini's libraries are visible to
    # other libraries that Houdini loads.  So, we adjust Python's dlopen
    # flags before importing hou.
    if hasattr(sys, "setdlopenflags"):
        old_dlopen_flags = sys.getdlopenflags()
        import DLFCN
        sys.setdlopenflags(old_dlopen_flags | DLFCN.RTLD_GLOBAL)

    try:
        import hou
    except ImportError:
        # Add $HFS/houdini/python2.6libs to sys.path so Python can find the
        # hou module.
        sys.path.append(os.environ['HFS'] + "/houdini/python%d.%dlibs" % sys.version_info[:2])
        import hou
    finally:
        if hasattr(sys, "setdlopenflags"):
            sys.setdlopenflags(old_dlopen_flags)

enableHouModule()

try:
    import hou
except ImportError:
    print "Tests have to be run in presence of Houdini python module or by hython."
    sys.exit()

import hafarm
from hafarm import Houdini
from hafarm import const
from hafarm import utils
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
        self.assertEqual(['--ignore_tiles', '--generate_ifds', '', '-d /out/mantra2', '@SCENE_FILE/>'], \
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

    def test_mantra_render_with_tiles(self):
        tiles, merger = Houdini.mantra_render_with_tiles(self.hbatch_farm)
        self.assertEqual(len(tiles), 16)
        self.assertFalse(False in [merger == x.get_direct_outputs()[0] for x  in tiles])
        path, image = os.path.split(self.rop.parm("vm_picture").eval())
        path        = os.path.join(path, const.TILES_POSTFIX)

        for tile in range(16):
            self.assertTrue("--tiling 4%4%" + str(tile) in tiles[tile].parms['command'])
            self.assertTrue(tiles[tile].parms['job_name'].endswith("__TILE__%s" % str(tile)))


class TestMantraRenderFromIfd(unittest.TestCase):
    def setUp(self):
        hou.hipFile.clear()
        self.nt     = hou.node('/out')
        self.rop    = self.nt.createNode("ifd")
        self.farm   = self.nt.createNode("HaFarm")

        # Basic scene:
        obj = hou.node("/obj")
        geo = obj.createNode("geo")
        geo.node("file1").destroy()
        cam = obj.createNode("cam")
        grid= geo.createNode("grid")
        cam.parmTuple("t").set((5,5,5))
        cam.parmTuple("r").set((-45,45,0))

        # Create tmp ifds:
        self.tmppath   = tempfile.mkdtemp()
        self.ifdfile   = os.path.join(self.tmppath, "tmp.$F.ifd")
        self.vm_picture = os.path.join(self.tmppath, "image.$F4.exr")
        self.rop.parm('soho_outputmode').set(1)
        self.rop.parm('soho_diskfile').set(self.ifdfile)
        self.rop.parm("trange").set(1)
        self.rop.parm("f2").deleteAllKeyframes()
        self.rop.parm("f2").set(10)
        self.rop.parm("vm_picture").set(self.vm_picture)
        self.rop.render()


        # Set parms on HaFarm ROP:
        self.farm.parm("ifd_range1").set(1) 
        self.farm.parm("ifd_range2").set(10) 
        self.farm.parm("ifd_range3").set(1)
        self.farm.parm("ifd_files").set(self.ifdfile)
        
    def test_mantra_render_from_ifd(self):
        frames = None
        job_name = None
        image = os.path.join(self.tmppath, "image.0001.exr")
        mantras = Houdini.mantra_render_from_ifd(self.farm, frames, job_name)
        for mantra in mantras:
                self.assertEqual(mantra.parms['start_frame'], self.farm.parm("ifd_range1").eval())
                self.assertEqual(mantra.parms['end_frame'],   self.farm.parm("ifd_range2").eval())
                self.assertEqual(mantra.parms['step_frame'],  self.farm.parm("ifd_range3").eval())
                self.assertTrue(const.TASK_ID  in mantra.parms['scene_file'])
                self.assertEqual(mantra.parms['output_picture'],  image)


        frames = [1,3,5]
        mantras = Houdini.mantra_render_from_ifd(self.farm, frames, job_name)
        self.assertEqual(len(frames), len(mantras))

        for frame in frames:
            idx = frames.index(frame)
            self.assertEqual(mantras[idx].parms['start_frame'], frame)
            self.assertEqual(mantras[idx].parms['end_frame'], frame)
            self.assertTrue(const.TASK_ID  in mantras[idx].parms['scene_file'])
            self.assertEqual(mantras[idx].parms['output_picture'],  image)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmppath)


class TestPostRenderActions(unittest.TestCase):
    def setUp(self):
        hou.hipFile.clear()
        self.nt     = hou.node('/out')
        self.rop    = self.nt.createNode("ifd")
        self.rop.setName('test')
        self.rop.parm("vm_picture").set("$JOB/render/mantra/images/$USER/$OS.$F4.exr")
        self.farm   = self.nt.createNode("HaFarm")
        self.farm.setFirstInput(self.rop)

        self.farm.parm("debug_images").set(1)
        self.farm.parm("make_proxy").set(1)
        self.farm.parm("make_movie").set(1)

        self.end_frame = 10
        self.rop.parm('trange').set(1)
        self.rop.parm('f2').deleteAllKeyframes()
        self.rop.parm('f2').set(self.end_frame)

    def test_post_render_actions(self):
        self.hbatch_farm = Houdini.HbatchFarm(self.farm, self.rop)
        job_name         = self.hbatch_farm.parms['job_name'] + "_mantra"
        self.mantra_farm = Houdini.MantraFarm(self.farm, self.rop, job_name)

        posts = Houdini.post_render_actions(self.farm, [self.hbatch_farm, self.mantra_farm], '3d')
        self.assertTrue(len(posts), 3)
        debuger, merger, moviem = posts

        # mp4:
        image       = utils.padding(self.rop.parm('vm_picture').eval(), 'nuke')[0]
        base, ext   = os.path.splitext(image)
        path, file  = os.path.split(base)
        path        = os.path.join(path,  const.PROXY_POSTFIX)
        proxy       = os.path.join(path, file +'.jpg')
    
        self.assertTrue(proxy in moviem.parms['command_arg'][0])
        self.assertEqual('ffmpeg ', moviem.parms['command'])
        self.assertTrue(moviem.parms['start_frame'] == moviem.parms['end_frame'] == 1)

        # merger
        image      = utils.padding(self.rop.parm('vm_picture').eval(), 'shell')[0]
        path, file = os.path.split(image)
        path       = os.path.join(path, const.DEBUG_POSTFIX)
        report     = os.path.join(path, file + '.json')

        self.assertEqual(report, merger.parms['scene_file'])
        self.assertTrue('$HAFARM_HOME/scripts/generate_render_report.py' in merger.parms['command'])
        self.assertTrue(merger.parms['start_frame'] == merger.parms['end_frame'] == 1)
               
        #debuger
        self.assertTrue('$HAFARM_HOME/scripts/debug_images.py' in debuger.parms['command'])
        self.assertTrue(const.TASK_ID_PADDED in debuger.parms['scene_file'])
        self.assertEqual(debuger.parms['start_frame'], self.rop.parm('f1').eval())
        self.assertEqual(debuger.parms['end_frame'], self.rop.parm('f2').eval())

class TestBuildGraph(unittest.TestCase):
    def setUp(self):
        def c(p, t, n, s, e): 
            node = p.createNode(t, n)
            node.parm('trange').set(1)
            node.parm('f1').set(s)
            node.parm('f2').set(e)
            return node

        hou.hipFile.clear()
        self.end_frame = 10
        n = hou.node('/out')

        self.teapot     = c(n, 'geometry', 'teapot', 1, 10)
        self.box        = c(n, 'geometry', 'box', 1, 1)  
        self.box_teapot = c(n, 'ifd', 'box_teapot', 1, 10) 
        self.alembic    = c(n, 'alembic', 'alembic', 1, 10)
        self.grid       = c(n, 'ifd', 'grid', 1, 10)
        self.hafarm1    = n.createNode('HaFarm')
        self.comp       = c(n, 'comp', 'comp', 1, 10)
        self.root       = n.createNode("HaFarm")

        self.root.setFirstInput(self.comp)
        self.comp.setNextInput(self.box_teapot)
        self.comp.setNextInput(self.hafarm1)
        self.box_teapot.setNextInput(self.teapot)
        self.box_teapot.setNextInput(self.box)
        self.hafarm1.setNextInput(self.grid)
        self.grid.setNextInput(self.box)
        self.grid.setNextInput(self.alembic)
        self.hafarm1.parm("group").set("renders")


    def test_build_graph(self):
        def check_graph(action, submitted):
            for child in action.get_renderable_inputs():
                check_graph(child, submitted)
                self.assertEqual([x.rop for x in child.get_direct_inputs()], list(child.rop.inputs()))
                for ginput in child.get_direct_inputs():
                    self.assertTrue(ginput.rop in child.rop.inputs())
                submitted += [child]
            return submitted

        # Number = Houdini nodes + single additional node per ifd rop = 8 nodes + 2:
        root = RootAction()     
        root.clear()
        root, actions = Houdini.build_graph(self.root)
        self.assertTrue(len(root.get_all_nodes()), 10)

        # graph matches network:
        submitted = []
        check_graph(root, submitted)
        
        # settigs overwrite:
        for node in root.get_all_nodes():
            if node.rop == self.grid:
                self.assertEqual(node.node, self.hafarm1)
            elif node.rop == self.alembic:
                self.assertEqual(node.node, self.hafarm1)
                self.assertEqual(node.parms['group'], self.hafarm1.parm('group').eval())


class TestRenderPressed(unittest.TestCase):
    def setUp(self):
        def c(p, t, n, s, e): 
            node = p.createNode(t, n)
            node.parm('trange').set(1)
            node.parm('f1').set(s)
            node.parm('f2').set(e)
            return node

        hou.hipFile.clear()
        self.end_frame = 10
        n = hou.node('/out')

        self.teapot     = c(n, 'geometry', 'teapot', 1, 10)
        self.box        = c(n, 'geometry', 'box', 1, 1)  
        self.box_teapot = c(n, 'ifd', 'box_teapot', 1, 10) 
        self.alembic    = c(n, 'alembic', 'alembic', 1, 10)
        self.grid       = c(n, 'ifd', 'grid', 1, 10)
        self.hafarm1    = n.createNode('HaFarm')
        self.comp       = c(n, 'comp', 'comp', 1, 10)
        self.root       = n.createNode("HaFarm")

        self.root.parm("debug_graph").set(1)
        self.root.setFirstInput(self.comp)
        self.comp.setNextInput(self.box_teapot)
        self.comp.setNextInput(self.hafarm1)
        self.box_teapot.setNextInput(self.teapot)
        self.box_teapot.setNextInput(self.box)
        self.hafarm1.setNextInput(self.grid)
        self.grid.setNextInput(self.box)
        self.grid.setNextInput(self.alembic)
        self.hafarm1.parm("group").set("renders")
        root = RootAction()
        root.clear()

    def test_render_pressed(self):
        # TODO: implement checks. For now run without raising makes it.
        Houdini.render_pressed(self.root)
        # assert False # TODO: implement your test here

if __name__ == '__main__':
    for test in unittest.TestCase.__subclasses__()[1:]:
         case = unittest.TestLoader().loadTestsFromTestCase(test)
         unittest.TextTestRunner(verbosity=3).run(case)
