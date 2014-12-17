import sys
import hou
from objects import ExObjectBase


# Mappings from ha.exchange parameters into Houdini specific one. 
houdini_parm_mappings = \
           {
            'pixelAspect': 'aspect',
            'focal':       'focal',
            'resx':        'resx',
            'resy':        'resy',
            'haperture':   'aperture',
            'near':        'near',
            'far':         'far',
            'cropl':       'cropl',
            'cropr':       'cropr',
            'cropb':       'cropb',
            'cropt':       'cropt',
            'shutter':     'shutter',
            'focus':       'focus',
            'fstop':       'fstop'}



class Channel(ExObjectBase):
    def __init__(self):
        super(Channel, self).__init__()

    @property
    def kind(self):
        return 'channel'



class Camera(ExObjectBase):

    def __init__(self):
        super(Camera, self).__init__()

    @property
    def kind(self):
        return 'cam'

    def parse_object(self, obj):
        for parm in obj.parms():
            self[parm.name()] = parm.eval()

    def apply_object(self, obj):
        parm_names = [parm.name() for parm in obj.parms()]
        for parm in self.keys():
            if parm in parm_names:
                #print "Setting %s to %s" % (parm, self[parm])
                obj.parm(parm).set(self[parm][0])


class Asset(ExObjectBase):
    @property
    def kind(self):
        return 'asset'

    def parse_object(self, obj):
        pass

    def apply_object(self, obj):
        pass


class Null(ExObjectBase):
    
    @property
    def kind(self):
        return 'null'

    def parse_object(self, obj):
        for parm in obj.parms():
            self[parm.name()] = parm.eval()

    def apply_object(self):
        print "Applying Object."



def parse_scene(scene, operators):
    l = []
    for node in scene.children():
        kind = node.type().name()
        if kind in operators.keys():
            exobj = getattr(sys.modules[__name__], operators[kind])()
            exobj.parse_object(node)
            l.append(exobj)
    return l
