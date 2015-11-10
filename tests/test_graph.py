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

import hafarm
from hafarm import const
from hafarm import HaFarm
from hafarm.hafarm import HaAction
from hafarm.hafarm import NullAction
from hafarm.hafarm import RootAction

from hafarm import HaFarmParms
from hafarm.const import hafarm_defaults
from hafarm.Batch import BatchFarm

root  = RootAction()
tail  = HaAction(name='tail')
tail2 = HaAction(name='tail2')
leaf1 = HaAction(name='leaf1')
leaf2 = HaAction(name='leaf2')
leaf3 = HaAction(name='leaf3')
leaf4 = HaAction(name='leaf4')
leaf5 = HaAction(name='leaf5')
leaf6 = HaAction(name='leaf6')
leaf7 = HaAction(name='leaf7')
leaf8 = HaAction(name='leaf8')
leaf9 = HaAction(name='leaf9')
null  = NullAction(name='ignore_me')


def clean_inputs(root):
    for node in root.nodes:
        node.inputs = []

class TestHaAction(unittest.TestCase):
    def test___init__(self):
     
        # This all should have the same root:
        self.assertEqual(root, tail.root)
        self.assertEqual(root, tail2.root)
        self.assertEqual(root, leaf1.root)
        self.assertEqual(root, leaf9.root)
        self.assertEqual(root, null.root)

        # Also number should match:
        self.assertEqual(len(root.nodes), 13 )

        # Names should be correct:
        self.assertEqual(tail.name, 'tail')

        # uuid different:
        uuids = [node.uuid for node in root.nodes]
        uuids_set = set(uuids)
        self.assertEqual(len(uuids), len(uuids_set))

    def test___repr__(self):
        ha_action = HaAction(name='name')
        self.assertEqual("'" + ha_action.name + "'" , ha_action.__repr__())
        
    def test_add_input(self):
        root.add_input(tail)
        self.assertEqual(root.get_direct_inputs(), [tail])
        self.assertEqual(tail.get_direct_outputs(), [root])

    def test_add_inputs(self):
        root.remove_input(tail)
        root.add_inputs((leaf1, leaf2, leaf3))
        self.assertEqual(root.get_direct_inputs(),[leaf1, leaf2, leaf3])

    def test_get_all_inputs(self):
        leaf2.add_input(leaf4)
        self.assertEqual(root.get_all_inputs(), [leaf1, leaf2, leaf4, leaf3])   

    # def test_get_all_parents(self):
    #     leaf5.add_input(leaf4)
    #     self.assertEqual([root, leaf5], root.get_all_parents())
    #     # assert False # TODO: implement your test here

    def test_get_direct_inputs(self):
        self.assertEqual([leaf1, leaf2, leaf3], root.get_direct_inputs(ignore_types=None))
        self.assertEqual([leaf4], leaf2.get_direct_inputs(ignore_types=None))

        root.add_input(null)
        self.assertNotEqual( root.get_direct_inputs(),\
            root.get_direct_inputs(ignore_types=NullAction))

    def test_get_direct_outputs(self):
        clean_inputs(root)
        root.add_input(leaf1)
        root.add_input(leaf2)
        leaf1.add_input(tail)
        leaf2.add_input(tail)
        self.assertEqual([leaf1, leaf2], tail.get_direct_outputs())

    def test_insert_input(self):
        clean_inputs(root)
        root.add_input(tail)
        root.insert_input(leaf1)
        self.assertEqual(tail.get_direct_outputs(), root.get_direct_inputs())

    def test_insert_output(self):
        clean_inputs(root)
        root.add_input(tail)
        root.add_input(tail2)
        tail.insert_output(leaf3)
        self.assertTrue(leaf3 in root.get_direct_inputs())
        # assert False # TODO: implement your test here

    def test_insert_inputs(self):
        clean_inputs(root)
        root.add_input(tail)
        root.add_input(tail2)
        children = root.get_direct_inputs()
        root.insert_inputs([leaf1, leaf2])

        # tail output == tail2 output == root inputs ?
        self.assertEqual(tail.get_direct_outputs(), root.get_direct_inputs())
        self.assertEqual(tail2.get_direct_outputs(), root.get_direct_inputs())
        self.assertEqual(root.get_direct_inputs(), [leaf1, leaf2])

        # New children should inheret parents old children:
        self.assertEqual(leaf1.get_direct_inputs(),children)
        self.assertEqual(leaf2.get_direct_inputs(), children)

    def test_insert_outputs(self):
        clean_inputs(root)
        root.add_input(tail)
        root.add_input(tail2)
        tail.insert_outputs([leaf1, leaf2])

        # Three connections from root?
        self.assertEqual(root.get_direct_inputs(), [tail2, leaf1, leaf2]) 

        # tail output == root input ?
        self.assertEqual(tail.get_direct_outputs(), [leaf1, leaf2])

        # tail2 should not be affected
        self.assertNotEqual(tail2.get_direct_outputs(), root.get_direct_inputs())

    def test_is_root(self):
        self.assertNotEqual(True, tail.is_root())
        self.assertEqual(True, root.is_root())

    def test_remove_input(self):
        clean_inputs(root)
        root.add_input(tail)
        root.add_input(tail2)
        root.remove_input(tail)
        self.assertEqual([tail2], root.get_direct_inputs())

#     def test_get_renderable_inputs(self):
#         # ha_action = HaAction(name)
#         # self.assertEqual(expected, ha_action.get_renderable_inputs())
#         assert False # TODO: implement your test here

#     def test_get_root_output(self):
#         # ha_action = HaAction(name)
#         # self.assertEqual(expected, ha_action.get_root_output())
#         assert False # TODO: implement your test here

class TestRootAction(unittest.TestCase):
    def test___init__(self):
        root_action  = RootAction()
        root_action2 = RootAction()
        self.assertEqual(root_action, root_action2)
        self.assertEqual(root_action, root)

    def test_get_all_nodes(self):
        self.assertEqual(root.nodes, root.get_all_nodes())

#     def test_add_node(self):
#         # root_action = RootAction(*args, **kwargs)
#         # self.assertEqual(expected, root_action.add_node(node))
#         assert False # TODO: implement your test here

#     def test_add_nodes(self):
#         # root_action = RootAction(*args, **kwargs)
#         # self.assertEqual(expected, root_action.add_nodes(nodes))
#         assert False # TODO: implement your test here


#     def test_is_root(self):
#         # root_action = RootAction(*args, **kwargs)
#         # self.assertEqual(expected, root_action.is_root())
#         assert False # TODO: implement your test here

#     def test_render(self):
#         # root_action = RootAction(*args, **kwargs)
#         # self.assertEqual(expected, root_action.render())
#         assert False # TODO: implement your test here

# class TestNullAction(unittest.TestCase):
#     def test___init__(self):
#         # null_action = NullAction()
#         assert False # TODO: implement your test here

#     def test_render(self):
#         # null_action = NullAction()
#         # self.assertEqual(expected, null_action.render())
#         assert False # TODO: implement your test here

if __name__ == '__main__':
    for test in unittest.TestCase.__subclasses__()[1:]:
         case = unittest.TestLoader().loadTestsFromTestCase(test)
         unittest.TextTestRunner(verbosity=3).run(case)
