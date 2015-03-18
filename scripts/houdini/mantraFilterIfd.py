#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

# Chanages:
# 15.09.14 Adding filename overwrites


import mantra
import sys, os
from optparse import OptionParser
from hashlib import md5
from time import time
from os import getenv
import ha.path
# Imports tiling constant
from ha.hafarm import const

gilight = False
ha_instance_num = 0
ha_objects           = []
ha_lights            = []
ha_materials         = []


basic_colors = ("1 0 0", "0 1 0", "0 0 1", "1 1 0", "0 1 1", "1 0 1", ".5 0 0", "0 .5 0", "0 0 .5" , '.5 .5 0', '0 .5 .5', '.5 0 .5')


def parseOptions():
	usage = "usage: %prog [options] arg"
	parser = OptionParser(usage)
	parser.add_option("-i", "--irradiance", dest="irradiance",  action="store", type="string", help="perform irradiance pass.")
	parser.add_option("-m", "--matte", dest="matte",  action="store", type="string", help="Matte shading on listed objects.")
	parser.add_option("-p", "--phantom", dest="phantom",  action="store", type="string", help="Invisible for primary rays.")
	parser.add_option("-s", "--special", dest="special",  action="store",  help="Various settings like shadow pass, ids etc.")
	parser.add_option("-l", "--lights", dest="lights",  action="store",  help="Per light mask (up to four components).")
	parser.add_option("-d", "--do_shadows", dest="shadows_in_light_pass",  action="store_true",  help="Compute shadows in per light mask.")
	parser.add_option("-c", "--crop", dest="crop",  action="store",  help="Crop image.")
	parser.add_option('-t', "--tiling", dest='tiling', action='store', help="Performs autocrop from tiling paramters (htiles, vtiles, current tile)")
	parser.add_option("--globalSurfaceShader", dest="globalSurfaceShader",  action="store", type="string", help="assign a global surface shader")
	parser.add_option("--globalDispShader", dest="globalDispShader",  action="store", type="string", help="assign a global displacement shader")
	parser.add_option("--proxy", dest='make_proxy', action="store_true", help="Create a proxy file.")
	parser.add_option("--mpeg", dest='make_mpeg', action="store", help="Create mpeg preview file.")
	parser.add_option("--mp4", dest='make_mp4', action="store", help="Create mp4 preview file.")
	parser.add_option("--frameRange", dest='frameRange', action="store", help="sequence frame range START-END")
	parser.add_option("--database", dest='database', action="store", type='string', help="Log frame in cdb.")
	parser.add_option("--filename", dest='filename', action='store', type='string', help='Overwrites output file.')
	(opts, args) = parser.parse_args(sys.argv[1:])
	return opts, args


options, args     = parseOptions()




def compute_crop(tile_parms):
	'''Computes Houdini specific camera crop paramters from provided tiling parameters:
		(horizontal tiles, vertical tiles, current tile)
	'''
	hsize = 1.0 / int(tile_parms[0])
	vsize = 1.0 / int(tile_parms[1])
	h = int(tile_parms[2]) % int(tile_parms[0])
	v = int(tile_parms[2]) / int(tile_parms[0])
	left =   h * hsize
	right =  (1 + h) * hsize
	lower =  v * vsize
	upper =  (1 + v) * vsize
	return  left, right, lower, upper



def filterInstance():
	global ha_instance_num
	global ha_objects

	# Global Surface Shader
	if options.globalSurfaceShader or options.globalSurfaceShader == "":
		if os.path.isfile(options.globalSurfaceShader):
			#if the passed string is a path to a VEX shader
			mantra.setproperty('object:surface',options.globalSurfaceShader.split("%"))
		else:
			#if the pass string is a shader string with object scope
			if mantra.property('object:name')[0] in options.globalSurfaceShader.split("%")[1].split(" "):
				mantra.setproperty('object:surface', options.globalSurfaceShader.split("%")[0].split(" "))
		
		
	#	# If irradiance pass was enabled:
	if options.irradiance:
		mantra.setproperty('object:surface', 'opdef:/Shop/v_constant'.split("%"))

	#  if matte rendering:
	if options.matte:
		if options.matte == "*": pass
		else:
			objects = options.matte.split("%")
			print objects
			if name in objects:
				mantra.setproperty('object:surface', 'matte')

	# Phantom mode:
	if options.phantom:
		if options.phantom == "*": pass
		else:
			objects = options.phantom.split("%")
			if name in objects:
				mantra.setproperty('object:phantom', "true")

	# Special mode:
	if options.special:
		if options.special == "shadow_matte":
			mantra.setproperty('object:surface', 'opdef:/Shop/v_shadowmatte alpha 0'.split())
		elif options.special == "object_matte":
			mantra.setproperty('object:surface', 'opdef:/Shop/haSpecialPasses type object_matte'.split())
		elif options.special == 'object_id':
			_id = mantra.property('object:id')[0]
			mantra.setproperty('object:surface', 'opdef:/Shop/v_constant alpha 0 clr '.split() + [_id,0,0])
		elif options.special == 'object_n':
			mantra.setproperty('object:surface', 'opdef:/Shop/haSpecialPasses type object_n'.split())
		elif options.special == 'zdepth':
			mantra.setproperty('object:surface', 'opdef:/Shop/haSpecialPasses type zdepth'.split())
		elif options.special == 'lambert':
			mantra.setproperty('object:surface', 'opdef:/Shop/v_plastic spec 0 0 0'.split())
			print 'Should be lambert on %s' % name
		elif options.special == 'motion':
			mantra.setproperty('object:surface',  'opdef:/Shop/haSpecialPasses type motion'.split())




	# Light masking:
	if options.lights:
		do_shadows = []
		if options.shadows_in_light_pass: do_shadows = ['do_shadows',1]
		lights = get_lights()
		if len(lights) > 3: lights = ["light_to_alpha", lights[3][0]]
		else: lights = []
		mantra.setproperty('object:surface', 'opdef:/Shop/haSpecialPasses type light_mask '.split()  + do_shadows + lights)
		



def filterLight():
	# Global Irradiance Pass:
	global ha_lights
	ha_lights.append(mantra.property("light:name")[0])
    
	if options.irradiance:
		global gilight
		if not gilight: 
			print 'GI light from: ' + mantra.property('light:name')[0]
			mantra.setproperty("light:shadow", "opdef:/Shop/v_rayshadow shadowtype none".split())
			mantra.setproperty('light:shader', 'opdef:/Shop/v_gilight '.split() + options.irradiance.split("%"))
			gilight = True
		else:
			mantra.setproperty('light:shader', 'opdef:/Shop/v_asadlight lightcolor 0 0 0'.split())	
	
	# Light masking:
	elif options.lights:
		colors = ["1 0 0", "0 1 0", "0 0 1", "1 1 1"]
		lights = get_lights()
		light = mantra.property('light:name')[0]
		
		for light_group in lights:
			if light in light_group:
				print light
				mantra.setproperty('light:shader', 'opdef:/Shop/v_asadlight lightcolor '.split() + colors[lights.index(light_group)].split())
				return	
			
		# Disable anything else:
		mantra.setproperty('light:shader', 'opdef:/Shop/v_asadlight lightcolor 0 0 0 '.split())
					

def filterCamera():
	# Actually I don't have a clue what's that:
	filename = mantra.property('image:filename')[0]
	mantra.setproperty('plane:planefile',[filename])
 	variable = mantra.property("plane:variable")[0]
 	channel  = mantra.property('plane:channel')
 	mantra.setproperty('plane:channel',channel)
 	channel  = mantra.property('plane:channel')

 	# Perform explicite crop on the image:
	if options.crop:
		crop = options.crop.split("%")
		print 'Cropping camera to: %s' % str(crop) 
		mantra.setproperty("image:crop", crop)		

	# Overwrite mantra image output:
	if options.filename:
		print 'Overwriting mantra output to: %s' % options.filename
		filename = mantra.setproperty('image:filename', options.filename)

	# Create tiled image based on provided params ( horiz. tiles, vert. tiles, current tile).
	if options.tiling:
		tile_parms = options.tiling.split("%")
		crop = compute_crop([int(x) for x in tile_parms])
		mantra.setproperty('image:crop', crop)
		base, ext = os.path.splitext(filename)
		path, file = os.path.split(base)
		base       = os.path.join(path, const.TILES_POSTFIX)
		# FIXME: This shouldn't be here at all:
		if not os.path.isdir(base):
			os.mkdir(base)
		base = os.path.join(base, file)
		filename = base + "%s%s%s" % (const.TILE_ID, str(tile_parms[2]), ext)
		mantra.setproperty('image:filename', filename)
		print 'WARNING: Image is altered by tiling: %s with name %s' % (crop, filename)
			
				
def get_lights():
	lights = options.lights.split("%")
	lights = [light.split("&") for light in lights]
	return lights
	

def filterEndRender():
	#global gilight
	if options.database:
		db   = get_db()
		sig  = md5(mantra.property('image:filename')[0]).hexdigest()
		doc  = db[sig]
		doc['objects'] = ha_objects
		doc['lights']  = ha_lights
		doc['end_time']= time()
		db[doc.id]     = doc
    
    
def filterRender():
	if options.database:
		data = build_dictionary(options.database)
		result = log_cdb(data)
		if not result: print "Couldn't log frame:"
    
    
def build_dictionary(fields):
	store = {}
	fields = fields.split("%")
	# User specified fields:
	for field in fields: store[field] = mantra.property(field)[0]
	# Some stuff we always want to log:
	store['filename']   = mantra.property('image:filename')[0]
	store['hostname']   = os.popen('hostname').readlines()[0].strip()
	store['start_time'] = time()
	store['type']       = 'frame'
	store['asset_type'] = getenv("JOB_ASSET_TYPE", "")
	store['asset_name'] = getenv("JOB_ASSET_NAME", "")
	store['user']       = getenv("USER", "")
	store['insider']    = "HaFilterIFD"
	# Sequence id helps to find it in db,
	# Path + name -padding + extension:
	seed = ha.path.padding(store['filename'])
	store['seq_id'] = md5(seed[0][:-1] + seed[-1]).hexdigest()
	return store
    
def get_db():
    from couchdb import Server
    
    server = getenv("CDB_SERVER")
    db     = getenv("JOB_CURRENT")
    db     = str(db).strip().lower() + "_render_log"
    
    try:
        server = Server(server)
        if db in server: db = server[db]
        else: db = server.create(db)
    except: return 0
    return db
  
  
def log_cdb(data):
	db = get_db()
	sig  = md5(data['filename']).hexdigest()
	if not sig in db:
		db[sig] = data
		data    = db[sig] 
	else:
		doc     = db[sig]
		for key in data:
			doc[key]  = data[key]
			db[doc.id]= doc
	return data

def filterQuit():
	# Make a proxy jpeg on exit using tiit utility:
	if options.make_proxy:
		if os.path.isdir(os.path.split(mantra.property("image:filename")[0])[0]):
			filename = mantra.property("image:filename")[0]
			path, filename = os.path.split(filename)
			path           = os.path.join(path, "proxy")
			if not os.path.isdir(path):
				os.mkdir(path)
			filename       = os.path.splitext(filename)[0] + ".jpg"
			path           = os.path.join(path, filename)
			lut            = '/STUDIO/houdini/houdini11.1/luts/nuke_sRGB.blut'
			command        = 'LD_PRELOAD=/opt/packages/oiio-1.4.15/lib/libOpenImageIO.so.1.4 \
			/opt/packages/oiio-1.4.15/bin/oiiotool %s --tocolorspace "sRGB" -ch "R,G,B" -o %s' % (mantra.property("image:filename")[0], path)
			result         = os.popen(command).read()