



class Config(dict):
	def __init__(self, *args, **kwargs):
		''' Read in configuration stored in multiply files
		    and locations.
		'''
		super(dict, self).__init__(*args, **kwargs)
