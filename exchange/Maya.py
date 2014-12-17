import maya.cmds as cmds
from objects import ExObjectBase

class Camera(ExObjectBase):
    @property
    def name(self):
        return "camera"

    def parse_object(self, obj):
        print "parsing object."

    def apply_object(self):
        print "Applying Object."

