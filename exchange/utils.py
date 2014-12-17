

def build_operators_list(module):
	operators = {}
	for clsname in dir(module):
		cls = getattr(module, clsname)
		if hasattr(cls, 'kind') and clsname != 'ExObjectBase':
			operators[cls().kind] = clsname
	return operators