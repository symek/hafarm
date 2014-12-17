import Nuke
from objects import ExObjectBase, XForm


knobs = ['matrix', 'focal', 'vaperture', 'haperture', 'near', 
		 'far', 'focal_point', 'fstop' ]

class Camera(ExObjectBase):
    @property
    def name(self):
        return "camera"

    def parse_object(self, obj, start, end):
        for knob in knobs:
        	self[knob] = []
        	for t in range(start, end):
        		sample = obj.knob(knob).getValueAt(t)
        		self[knob].append(sample)


    def apply_object(self, offset=0):
        print "Applying Object."

