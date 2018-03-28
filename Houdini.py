# Standard:
import os
import itertools
import time

# Host specific:
import hou

# Custom: 
import hafarm

import Batch
from hafarm import utils
from hafarm import const
from Batch import BatchFarm
from hafarm import NullAction
from hafarm import RootAction
from .Hbatch import HbatchFarm
import Mantra
import Redshift


def post_render_actions(node, actions, queue='3d'):
    # Proceed with post-render actions (debug, mp4, etc):
    # Debug images:
    post_renders = []
    if node.parm("debug_images").eval():
        for action in actions:
            # Valid only for Mantra renders;
            if not isinstance(action, MantraFarm):
               continue
            # Generate report per file:
            debug_render = BatchFarm(job_name = action.parms['job_name'] + "_debug", queue = queue)
            debug_render.debug_image(action.parms['output_picture'], 
                                     start = action.parms['start_frame'], 
                                     end   = action.parms['end_frame'])
            debug_render.node = action.node
            debug_render.insert_input(action)
            post_renders.append(debug_render)
            # Merge reports:
            merger   = BatchFarm(job_name = action.parms['job_name'] + "_mergeReports", queue = queue)
            ifd_path = os.path.join(os.getenv("JOB"), 'render/sungrid/ifd')
            merger.merge_reports(action.parms['output_picture'], ifd_path=ifd_path, resend_frames=node.parm('rerun_bad_frames').eval())
            merger.node = action.node
            merger.add_input(debug_render)
            post_renders.append(merger)

    # Make a movie from proxy frames:
    if node.parm("make_proxy").eval() and node.parm("make_movie").eval():
        for action in actions:
            # Valid only for Mantra renders:
            if not isinstance(action, MantraFarm):
                continue
            movie  = Batch.BatchFarm(job_name = action.parms['job_name'] + "_mp4", queue = queue)
            movie.make_movie(action.parms['output_picture'])
            movie.node = action.node
            movie.insert_input(action)
            post_renders.append(movie)

    return post_renders

def build_graph(hafarm_rop, verbose=False):
    '''Builds simple dependency graph from Rops.
    '''
    def is_supported(node):
        return  node.type().name() in const.HOUDINI_SINGLE_TASK_NODES + const.HOUDINI_MULTI_TASK_NODES

    def add_recursively(parent, actions, rops):
        for rop in parent.rop.inputs():
            # Houdini sometimes keeps None inputs...
            if not rop:
                continue

            BatchClass = HbatchFarm
            postfix    = ""
            if rop.type().name() == "Redshift_ROP":
                postfix      = "_redshift"
                RenderModule = Redshift
                BatchClass   = Redshift.RSBatchFarm
            # This rop was already hafarm'ed, so we just connect its hafarm class 
            # to our current node (parent)
            if rop.name() in rops.keys():
                parent.add_input(rops[rop.name()])
                continue
            if not is_supported(rop) or rop.isBypassed():
                if verbose:
                    print "Creating NullAction from %s" % rop.name()
                farm      = NullAction()
                farm.parms = {'job_name': rop.name() + postfix}
                farm.rop  = rop
                farm.node = parent.node
                farm.array_interdependencies  = False
                if rop.type().name() == "HaFarm":
                    farm.node  = rop
            else:
                # We may import node from different network:
                if rop.type().name() == 'fetch':
                    rop = hou.node(rop.parm("source").eval())

                farm = BatchClass(parent.node, rop)

            actions.append(farm)
            parent.add_input(farm)
            if verbose:
                print "Adding %s to %s inputs." % (farm.rop.name(), parent.rop.name())
            rops[rop.name()] = farm
            if rop.inputs():
                add_recursively(farm, actions, rops)
    
    # This is book-keeper while creating graph:
    actions = []
    rops    = {}
    # This is the only root we will have...
    root = RootAction()
    # NOTE: This is only for debugging:
    root.parms = {'job_name': hafarm_rop.name()}
    root.node   = hafarm_rop
    root.rop    = hafarm_rop
    root.array_interdependencies  = False
    # Go:
    add_recursively(root, actions, rops)

    return root,  actions
 

def render_recursively(root, dry_run=False, ignore_types=[]):
    """Executes render() command of actions in graph order (children first).
    """
    def render_children(action, submitted, ignore_types):
        for child in action.get_renderable_inputs():
            render_children(child, submitted, ignore_types)
            if True in [isinstance(child, t) for t in ignore_types]:
                continue
            if child not in submitted:
                names = [x.parms['job_name'] for x in child.get_renderable_inputs()]
                if dry_run:
                    print "Dry submitting: %s, settings: %s, children: \n\t%s" % (child.parms['job_name'], child.node.name(), ", ".join(names))
                else:
                    print "Submitting: %s, settings: %s, children: \n\t%s" % (child.parms['job_name'], child.node.name(), ", ".join(names))
                    child.render()
                submitted += [child]

    submitted = []
    render_children(root, submitted, ignore_types)
    return submitted



def build_debug_graph(parent, subnet):
    def build_recursive(parent, subnet, hnode):
        for child in parent.get_direct_inputs():
            if child.parms['job_name'] not in [node.name() for node in subnet.children()]:
                ch = subnet.createNode('merge')
                ch.setName(child.parms['job_name'])
            else:
                ch = subnet.node(child.parms['job_name'])
            print ch.name() + " connected to " + hnode.name()
            hnode.setNextInput(ch)
            build_recursive(child, subnet, ch)

    for child in subnet.children():
        child.destroy()

    null = subnet.createNode('merge')
    null.setName('root')
    build_recursive(parent, subnet, null)
    for node in subnet.children():
        node.moveToGoodPosition()

def safe_eval_parm(node, parm_name, value=None):
    """Eval paramater conditionally."""
    if node.parm(parm_name):
        value = node.parm(parm_name).eval()
        return value
    else:
        return None


def render_pressed(node):
    '''Direct callback from Render button on Hafarm ROP.'''

    # FIXME: This shouldn't be here?
    hou.hipFile.save()
    queue    = str(node.parm('queue').eval())
    job_name = node.name()
    parent_job_name = []
    output_picture = ''
    mantra_farm = None
    hscripts = []
    mantras  = []
    posts    = []
    debug_dependency_graph = node.parm("debug_graph").eval()

    # a) Ignore all inputs and render from provided ifds:
    if node.parm("render_from_ifd").eval():
        root = RootAction()
        frames = []
        # support selective frames as well:
        if  node.parm("use_frame_list").eval():
            ifds   = node.parm("frame_list").eval()
            frames = utils.parse_frame_list(ifds)

        # TODO Make validiation of submiting jobs...
        if ifds.endswith(".ifd"):
            RenderModule = hafarm.Mantra
        elif ifds.endswith(".rs"):
            RenderModule = hafarm.Redshift
        else:
            print "Wrong IFD/RS file extension?"
            return

        tasks = RenderModule.render_from_ifd(node, frames)
        root.add_inputs(tasks)
        posts = post_render_actions(node, tasks)
        root.add_inputs(posts)
        # End of story:
        render_recursively(root, debug_dependency_graph)
        root.clear()
        return 
        
    # b) Iterate over inputs 
    print
    print "Building dependency graph:"
    root, hscripts = build_graph(node)


    for action in hscripts:
        # This is not mantra node, we are done here:
        if action.rop.type().name() not in ("ifd", "baketexture", "baketexture::3.0", "Redshift_ROP"):
            continue

        if action.rop.type().name() == "ifd":
            postfix      = "_mantra"
            RenderModule = Mantra
            FrameClass   = Mantra.MantraFarm
        elif action.rop.type().name() == "Redshift_ROP":
            postfix      = "_redshift"
            RenderModule = Redshift
            FrameClass   = Redshift.RSRenderFarm


        # Render randomly selected frames provided by the user in HaFarm parameter:
        if  action.node.parm("use_frame_list").eval():
            frames      = action.node.parm("frame_list").eval()
            frames      = utils.parse_frame_list(frames)
            task_frames = RenderModule.render_frame_list(action, frames)
        else:
            # TODO: Move tiling inside MantraFarm class...
            # Custom tiling:
            if safe_eval_parm(action.rop, 'vm_tile_render'):
                task_frames, merger = RenderModule.render_with_tiles(action)
            else:
                # Proceed normally (no tiling required):
                task_frames = [FrameClass(action.node, action.rop, job_name = action.parms['job_name'] + postfix)]
                # Build parent dependency:
                action.insert_outputs(task_frames)

        # Posts actions
        posts = post_render_actions(action.node, task_frames)
        root.add_inputs(posts)
    


    # # Debug previous renders (ignore all rops but debugers) mode:
    # if node.parm('debug_previous_render'):
    #     if node.parm('debug_previous_render').eval():
    #         render_recursively(root, debug_dependency_graph, ignore_types=[MantraFarm, HbatchFarm])
    #         return
 
    
    # Again end of story:
    print "Submitting nodes in top-to-buttom from dependency graph:"
    render_recursively(root, debug_dependency_graph)

    # if debug_dependency_graph:
    #     subnet = node.parent().createNode("subnet")
    #     build_debug_graph(root, subnet)

    # Side effect of singelton root. It's not destroyed after run, so we need to clean it here.
    root.clear()

