
import rea 
# Single root containing scheduling parameters
farmer  = rea.Manager(backend=rea.managers.Slurm)

# Default way, always should work:
# all parms taken from ifd node => no actions from farm )
cache1  = rea.Houdini.Geometry(hou.node('/out/geometry1'))
hbatch1 = rea.Houdini.Ifd(hou.node('/out/mantra1'))
mantra1 = rea.Houdini.Mantra(hou.node('/out/mantra1'))

hbatch1.add_dependency(cache1)
assert(cache1.children() == [hbatch1])
mantra1.add_dependency(hbatch1)
assert(hbatch1.children() == [mantra1])
hbatch1.add_child_job(mantra1)
assert(hbatch1.children() == [mantra1, mantra1]) # assuming we allow duplicates although we should not

farmer.render_all(mantra1) # any node will do since render_all() should traverse tree, find its root and process recursivelly
# render_all(node) == render(node, traverse=True)
farmer.render_childen(hbatch1) # all bellow hbatch1 -> cache1 will be omitted.
farmer.render(mantra1) # only provided job

# also 
farmer.add_job(cache1, traverse=True)
farmer.render_all()

# factory approach
# free functions thin wrappers:
# Say we want to modulate Houdini.Mantra initialization based on /out/ReaScheduler settings
rearop = hou.node('/out/ReaScheduler1')
jobs = rea.Houdni.create_mantra_job(rearop, hou.node('/out/mantra1'))
assert(rea.Houdini.Ifd in [type(node) for node in jobs] \
    and rea.Houdini.Mantra in [type(node) for node in jobs])
assert(hbatch1.children() == [hbatch1.get_child('/out/mantra1'),])

farmer.add_jobs(jobs)
farmer.render_all() # farmer knows the root already


def create_mantra_job(rea_node, rop_node):
    '''Creates series of jobs from ifd node and rea parameters'''
    assert(isinstance(rop_node, hou.RopNode.Ifd))
    if not rea_node.parm('use_existing_ifd'):
        batch  = rea.Houdini.Ifd(rop_node)

    render = rea.Houdini.Mantra(rop_node)


# Collection of free functions manipulating classes states.
# All logic should be here freeing classes from anything
# specific which will break sooner or later. 
def make_mp4(render):
    '''Addds mp4 (and possibly proxy) to provided render node.'''
    from os.path import splitext
    source = render
    ext, base = splitext(render.parms['output_picture'])
    proxies   = [item for item in render.children() \
        if isinstance(item, rea.Batch.Proxy)]
    if proxies:
        # NOTE: First proxy we take, 
        # perhaps we should check resolution or whatever.
        source = proxies[0]
    elif ext not in rea.Batch.SupportedFormats:
        source = rea.Batch.Proxy(filename=render.parms['output_picture'])
        render.add_child_job(source)

    mp4 = rea.Batch.Mp4(filename=source.parms['output_picture'])
    mp4.add_dependency(source)

    return mp4, source


def eval_parm(node, parm_name):
    if parm_name in node.parms():
        return node.parms(parm_name).eval()
    else:
        return HoudiniDafaults.get(parm_name)


