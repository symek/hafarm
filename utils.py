import os
import pwd
import sys


def get_email_address(user=None):
	'''Here goes anything but not current hack.'''
	return get_email_address_from_uid()

def get_email_address_from_uid(uid=None):
	'''Returns email address of currenly logged user. 
	FIXME: Is should depend on ldap module instead if monkey patching...
	'''
	if not uid:
		uid = os.getuid()
	user = pwd.getpwuid(uid)[4]
	user = user.split()

	# FIXME: Remove this monkey patching, find better way to get emails from LDAP.
	if len(user) == 2:
		email = user[0][0] + "." + user[1] + "@human-ark.com"
	elif len(user) == 1:
		email = user[0][0] + "." + user[0][1:] + "@human-ark.com"
	else:
		email = ''

	return email.lower()



def parse_frame_list(frames):
	"""frames: 
			string of frames in usual form: 1 2 3 4-6 7-11:2
		return: list of frames [1,2,3,4,5,6,7,9,11]
	"""
	# Using external module https://github.com/sqlboy/fileseq
	from fileseq import FrameSet
	# Support colon and spaces:
	frames = frames.split()
	frames = ",".join(frames)
	fs = FrameSet(frames)
	return list(fs)



def get_ray_image_from_ifd(filename):
	'''grep ray_image from ifd file with gnu grep tool.
	Rather hacky.'''
	# TODO: only LINUX:
	image_name = ""
	if sys.platform in ("linux2", ):
		result = os.popen("grep -a ray_image %s" % filename).read()
		image_name = result.split()[-1]
		print image_name
	return image_name


def convert_seconds_to_SGEDate(seconds):
	'''Converts time in seconds to [[CC]YY]MMDDhhmm[.SS] format.'''
	from datetime import datetime
	from time import localtime, strftime
	date  = localtime(seconds)
	format = '%Y%m%d%H%M.%S'
	return strftime(format, date)


def compute_delay_time(hours, now=None):
	'''Computes delay from now to now+hours. Returns time in seconds from epoch.'''
	from datetime import datetime, timedelta
	from time import mktime
	if not now: 
		now = datetime.now()
	delta = timedelta(hours=hours)
	delay = now + delta
	return mktime(delay.timetuple())


def compute_crop(crop_parms):
	hsize = 1.0 / crop_parms[0]
	vsize = 1.0 / crop_parms[1]
	h = crop_parms[2] % crop_parms[0] 
	v = crop_parms[2] / crop_parms[0]
	left =   h * hsize
	right =  (1 + h) * hsize
	lower =  v * vsize
	upper =  (1 + v) * vsize
	return  left, right, lower, upper


def join_tiles(self, job_parent_name, filename, start, end, ntiles):
	'''Creates a command specificly for merging tiled rendering.'''
	from ha.path import padding

	# Retrive full frame name (without _tile%i)
	if "_tile" in filename:
	    base, rest = filename.split("_tile")
	    tmp, ext   = os.path.splitext(filename)
	    filename   = base + ext
	else:
	    base, ext  = os.path.splitext(filename)

	details = padding(filename, format='nuke')
	base    = os.path.splitext(details[0])[0]
	reads   = [base + '_tile%s' % str(tile) + ext for tile in range(ntiles)]

	# Reads:
	command = ' '
	for read in reads:
	    command += '--Read file=%s ' % read

	# Mereges:
	command += '--Merge over,0,1 ' 
	for read in range(2, len(reads)):
	    command += '--Merge over,%s ' % read

	# Final touch:
	command += '--Write file=%s ' % details[0]
	command += '--globals %s,%s,24 --hold %s -f' % (start, end, job_parent_name)
	return command

    

