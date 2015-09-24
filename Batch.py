import os, sys


# Custom: 
import hafarm
from hafarm import utils
from hafarm import const


# For some reason this can't be in its own module for now and we'd like to
# use it across the board, so I put it here. At some point, we should remove haSGE inheritance
# making it more like a plugin class. At that point, this problem should be reviewed.
class BatchFarm(hafarm.HaFarm):
    '''Performs arbitrary script on farm. Also encapsulates utility functions for handling usual tasks.
    like tile merging, dubuging renders etc.'''
    def __init__(self, job_name='', parent_job_name=[], parent_array_name=[], queue='', command='', command_arg=''):
        super(BatchFarm, self).__init__()
        self.parms['queue']          = queue
        self.parms['command']        = command
        self.parms['command_arg']    = [command_arg]
        self.parms['hold_jid']       = parent_job_name
        self.parms['hold_jid_ad']    = parent_array_name
        self.parms['ignore_check']   = True
        self.parms['slots']          = 1
        self.parms['req_resources'] = ''
        self.parms['end_frame']     = 1
        if not job_name:
            job_name = self.generate_unique_job_name()
        self.parms['job_name']       = job_name

    def join_tiles(self, filename, start, end, ntiles):
        '''Creates a command specificly for merging tiled rendering with oiiotool.'''

        # Retrive full frame name (without _tile%i)
        if const.TILE_ID in filename:
            base, rest = filename.split(const.TILE_ID)
            tmp, ext   = os.path.splitext(filename)
            filename   = base + ext
        else:
            base, ext  = os.path.splitext(filename)

        details = utils.padding(filename, format='nuke')
        base    = os.path.splitext(details[0])[0]
        base, file = os.path.split(base)
        base    = os.path.join(base, const.TILES_POSTFIX, file)
        reads   = [base + const.TILE_ID + '%s' % str(tile) + ext for tile in range(ntiles)]

        # Reads:
        command = ' '
        command += '%s ' % reads[0]
        command += '%s ' % reads[1]
        command += '--over ' 

        for read in reads[2:]:
            command += "%s " % read
            command += '--over ' 

        # Final touch:
        command += '-o %s ' % details[0]
        command += '--frames %s-%s ' % (start, end)

        # Additional path for proxy images (to be created from joined tiles)
        if self.parms['make_proxy']:
            path, file = os.path.split(details[0])
            path = os.path.join(path, const.PROXY_POSTFIX)

            # FIXME: It shouldn't be here at all. 
            if not os.path.isdir(path): os.mkdir(path)

            proxy    = os.path.join(path, os.path.splitext(file)[0] + '.jpg')
            command += '--tocolorspace "sRGB" -ch "R,G,B" -o %s ' % proxy

        self.parms['command_arg'] = [command]
        self.parms['command']     = const.OIIOTOOL      
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1 
        return command

    def iinfo_images(self, filename):
        '''By using iinfo utility inspect filename (usually renders).
        '''
        details = utils.padding(filename, 'shell')
        self.parms['command'] = const.IINFO
        self.parms['command_arg'] =  ['`ls %s | grep -v "%s" ` | grep File ' % (details[0], const.TILE_ID)]
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1
        self.parms['email_stdout'] = True

    def debug_image(self, filename, start=None, end=None):
        '''By using iinfo utility inspect filename (usually renders).
        '''
        # TODO: Need to rethink that
        job_name = self.parms['job_name'].replace("_debug", "")
        details = utils.padding(filename)
        self.parms['scene_file'] =  details[0] + const.TASK_ID_PADDED + details[3]
        self.parms['command']    = '$HAFARM_HOME/scripts/debug_images.py --job %s --save_json -i ' % job_name
        if start and end:
            self.parms['start_frame'] = start
            self.parms['end_frame']   = end
       

    def merge_reports(self, filename, ifd_path=None, send_email=True, mad_threshold=5.0, resend_frames=False):
        ''' Merges previously generated debug reports per frame, and do various things
            with that, send_emials, save on dist as json/html etc.
        '''
        # 
        send_email    = '--send_email' # ON BY DEFAULT if send_email else ""
        ifd_path      = '--ifd_path %s' % ifd_path if ifd_path else ""
        resend_frames = '--resend_frames' if resend_frames else ""
        # 
        path, filename = os.path.split(filename)
        details = utils.padding(filename, 'shell')
        log_path = os.path.expandvars(self.parms['log_path'])
        self.parms['scene_file'] =  os.path.join(log_path, details[0]) + '.json'
        self.parms['command']    = '$HAFARM_HOME/scripts/generate_render_report.py %s %s %s --mad_threshold %s --save_html ' % (send_email, ifd_path, resend_frames, mad_threshold)
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1


    def make_movie(self, filename):
        '''Make a movie from custom files. 
        '''
        # Input filename with proxy correction:
        details = utils.padding(filename, 'nuke')
        base, file = os.path.split(details[0])
        file, ext  = os.path.splitext(file)
        inputfile  = os.path.join(base, const.PROXY_POSTFIX, file + '.jpg')
        outputfile = os.path.join(base, utils.padding(filename)[0] + 'mp4')
        command = "-y -r 25 -i %s -an -vcodec libx264 -vpre slow -crf 26 -threads 1 %s" % (inputfile, outputfile)
        self.parms['command'] = 'ffmpeg '
        self.parms['command_arg'] = [command]
        self.parms['start_frame'] = 1
        self.parms['end_frame']   = 1