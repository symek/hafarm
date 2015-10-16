#!/usr/bin/python
# Standard:
import os
import sys
import glob
import time
import smtplib
from email.mime.text import MIMEText
from optparse import OptionParser
import numpy
import json

# Custom:
import fileseq
from hafarm import utils
from hafarm import const


HEAD = """<!DOCTYPE html>
<html>

<head>
<style>
table {
    width:100%;
}
table, th, td {
    border: 1px solid black;
    border-collapse: collapse;
}
th, td {
    padding: 5px;
    text-align: left;
}
table#t01 tr:nth-child(even) {
    background-color: #eee;
}
table#t01 tr:nth-child(odd) {
   background-color:#fff;
}
table#t01 th    {
    background-color: black;
    color: white;
}

tr.small_frame td {
    background-color: #CC6600; color: black;
}
tr.bad_file td {
    background-color: #CC9900; color: black;
}
tr.missing_file td {
    background-color: #CC0000; color: black;

}
}
</style>
</head>"""


FOOT = """</body></html>"""
NTHUMBS = 8


TABLE_HEADER = """
<table id="t01">
  <tr>
    <th>Frame</th>
    <th>On disk?</th>        
    <th>Integrity OK?</th>
    <th>Nans</th>
    <th>Infs</th>
    <th>Size</th>
    <th>Small file?</th>
    <th>Hostname</th>
    <th>CPU time</th>
    <th>RAM used</th>
    <th>IFD Size</th>
  </tr>"""

ROW =  """
        <td>%s</td>
        <td>%s</td>       
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        </tr>"""

INFO_TABLE_HEADER = """
        <table table style="width:400px">
        <tr>
        <th>NAME</th>
        <th>VALUE</th>        
        </tr>"""

INFO_ROW = """
        <tr>
        <td>%s</td>
        <td>%s</td>
        </tr>"""

NORMAL_FILE_TAG = "<tr>"
MISSING_FILE_TAG = """<tr class="missing_file">"""
BAD_FILE_TAG     = """<tr class="bad_file">"""
SMALL_FILE_TAG   = """<tr class="small_frame">"""
LINK_FILE        = """<a href="%s">%s</a>"""
LINK_IMAGE       = """<a href="%s"><img src="%s" width="%s" height="%s" alt="%s"></a>"""




def help():
    return 'generate_render_report: Merge render reports from debug_images.py and present ot to audience\
        \n\tvia email/html etc.\
        \n\tusage: generate_render_report [] path/log/framename.*.json \
        \n '

def parseOptions():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-m", "--send_email", dest='send_email', action='store_true', default=False, help="Sends report via email.")
    parser.add_option(""  , "--save_html", dest='save_html', action='store_true', default=False, help="Save report as html file.")
    parser.add_option(""  , "--save_json", dest='save_json', action='store_true', default=False, help="Save report as json file.")
    parser.add_option("-p", "--print", dest='print_report', action='store_true', default=True, help="Prints report on stdout.")
    parser.add_option("-o", '--output', dest='output_dir', action='store', default=None, type='string', help='Output folder for a reports.')
    parser.add_option("",   '--ifd_path', dest='ifd_path', action='store', default=None, type='string', help='Path to look for IFD files when IFD stats are requested.')
    parser.add_option("-r", "--render_stats", dest='render_stats', action='store_true', default=True, help='Retrive render statistics from render manager.')
    parser.add_option("-d", "--display", dest='display_report', action='store_true', default=False, help="Displays report in web browser.")
    parser.add_option('',   "--mad_threshold", dest='mad_threshold', action='store', default=5.0, type=float, help='Threshold for Median-Absolute-Deviation based small frame estimator.')
    parser.add_option('',   "--resend_frames", dest='resend_frames', action='store_true', default=False, help="Tries to find jobs parms and send bad frames back on farm.")
    (opts, args) = parser.parse_args(sys.argv[1:])
    return opts, args



def generate_html(db, render_stats=None, ifd_stats=None, errors_only=False):
    """Interate over rows in db and generate html document from that.
    """
    from time import ctime
    def bytes_to_megabytes(bytes, rounded=3):
        return round(int(bytes) / (1024.0*1024.0), rounded)

    html = ""
    html += HEAD
    html += "<body>"
    table = ""
    table += TABLE_HEADER

    #globals
    render_times = []

    # Fallbacks:
    r_stat = {'hostname': '', 
              'qsub_time': 'Sat Sep 12 17:24:32 2015', 
              'cpu': 0.0, 'mem': 0.0, 'owner': "", 
              'start_time': 'Sat Sep 12 17:24:32 2015', 
              'end_time': 'Sat Sep 12 17:24:32 2015'}
    i_stat = {'ifd_size': 0.0}

    # *_TAGS alter rows colors...
    for frame_num in sorted(db['frames']):
        frame = db['frames'][frame_num]
        # Get handle to per frame render stats
        if render_stats:
            if frame_num in render_stats['frames']:
                r_stat = render_stats['frames'][frame_num]
        # Get handle to per ifd render stats:
        if ifd_stats:
            if frame_num in ifd_stats['frames']:
                i_stat = ifd_stats['frames'][frame_num]

        # Set color for problematic fields:
        if not frame['exists']:
            table += MISSING_FILE_TAG
        elif not frame['integrity']:
            table += BAD_FILE_TAG
        elif frame['small_frame']:
            table += SMALL_FILE_TAG
        else:
            table += NORMAL_FILE_TAG

        # TODO: This is SGE specific.
        # Convert details returend by qaact into seconds and then compute render time
        # represented as pretty string.
        start_time  = utils.convert_asctime_to_seconds(r_stat['start_time'])
        end_time    = utils.convert_asctime_to_seconds(r_stat['end_time'])
        render_time = utils.compute_time_lapse(start_time, end_time)
        render_times += [start_time, end_time]

        # Generate row:
        table += ROW % (frame_num, 
                       frame['exists'], 
                       frame['integrity'], 
                       frame['nans'], 
                       frame['infs'], 
                       str(bytes_to_megabytes(frame['size'])) + ' MB', 
                       frame['small_frame'], 
                       r_stat['hostname'], 
                       render_time , 
                       str(round(float(r_stat['mem']) / 1024, 2)) + " GB",
                       str(bytes_to_megabytes(i_stat['ifd_size'], 5)) + ' MB')

    # More info for an user:
    render_times.sort()
    info   = ""
    thumbs = ""
    
    # Retrive mp4 if any:
    sequence = glob.glob(db['pattern'])
    sequence.sort()
    proxies =[]

    for image in sequence:
        path, image = os.path.split(image)
        image, ext = os.path.splitext(image)
        proxy = 'proxy/' + image + '.jpg'
        proxy = os.path.join(path, proxy)
        proxies.append(proxy)
    mp4  = utils.padding(sequence[0])[0] + "mp4"

    info += INFO_TABLE_HEADER
    info += INFO_ROW % ('Job', db['job_name'])
    info += INFO_ROW % ('User', r_stat['owner'])
    info += INFO_ROW % ('Submitted', r_stat['qsub_time'])
    info += INFO_ROW % ('Started', ctime(render_times[0]))
    info += INFO_ROW % ('Ended: ', ctime(render_times[-1]))
    info += INFO_ROW % ('Missing', ", ".join([str(f) for f in db['missing_frames']]))
    info += INFO_ROW % ('Resent', ", ".join([str(f) for f in db['resent_frames']]))
    info += INFO_ROW % ('Path', LINK_FILE % ('file://'+db['pattern'], db['pattern']))

    # Links to additional fiels on disk
    # Limit proxies to nthumbs
    nthumbs = max(len(proxies) / 10, 1)
    for thumb in proxies[::nthumbs]:
        if os.path.isfile(thumb):
            thumbs +=   LINK_IMAGE % ('file://' + thumb, 'file://'+ thumb, 17*3, 10*3, thumb)
    info += INFO_ROW % ('PROXY', thumbs)
    if os.path.isfile(mp4):
        info += INFO_ROW % ('MP4',  LINK_IMAGE % ('file://' + mp4, 'file://'+ thumb, 17*3, 10*3, mp4))

    # Finally add main table and return
    html += info
    html += table
    html += FOOT
    return html

def send_debug(job_name, address, html, _from=None, server='ms1.human-ark.com'):
    """Sends html report by email with provided smpt server. Address should be a list.
    """
    message = MIMEText(html, 'html')

    message['Subject'] = 'Debug for %s' % job_name
    message['From'] = address[0]
    message['To']   = address[0]

    smpt = smtplib.SMTP(server)
    smpt.sendmail(address[0], address, message.as_string())
    smpt.quit()

    # An algorithm to compute PCA. Not as fast as the NumPy implementation

def pca(data,nRedDim=0,normalise=1):
    import numpy as np
    
    # Centre data
    m = np.mean(data,axis=0)
    data -= m

    # Covariance matrix
    C = np.cov(np.transpose(data))

    # Compute eigenvalues and sort into descending order
    evals,evecs = np.linalg.eig(C) 
    indices = np.argsort(evals)
    indices = indices[::-1]
    evecs = evecs[:,indices]
    evals = evals[indices]

    if nRedDim>0:
        evecs = evecs[:,:nRedDim]
    
    if normalise:
        for i in range(np.shape(evecs)[1]):
            evecs[:,i] / np.linalg.norm(evecs[:,i]) * np.sqrt(evals[i])

    # Produce the new data matrix
    x = np.dot(np.transpose(evecs),np.transpose(data))
    # Compute the original data again
    y=np.transpose(np.dot(evecs,x))+m
    return x,y,evals,evecs

def doubleMADsfromMedian(y,thresh=2.0):
    '''http://stackoverflow.com/questions/22354094/\
    pythonic-way-of-detecting-outliers-in-one-dimensional-observation-data'''
    import numpy as np
    m = np.median(y)
    abs_dev = np.abs(y - m)
    left_mad = np.median(abs_dev[y<=m])
    right_mad = np.median(abs_dev[y>=m])
    y_mad = np.zeros(len(y))
    y_mad[y < m] = left_mad
    y_mad[y > m] = right_mad
    modified_z_score = 0.6745 * abs_dev / y_mad
    modified_z_score[y == m] = 0
    return modified_z_score > thresh

def check_small_frames(db, threshold):
    """Check for suspecious differences in frames size.
       I currently look for outlies in siize derivatives.
       Not very  usefull...
    """
    # Check if some files aren't too small:
    sizes = db['file_sizes']
    slope = []
    db['small_frames'] = []
    _max =  10000.0 #/ max(sizes) * 1000.0
    for idx in range(len(sizes)):
        current = sizes[idx] / _max
        if idx == len(sizes) -1 :
            next =  (current + (current - sizes[idx-1] / _max) ) 
        else:
            next    = sizes[idx+1] /  _max
        slope.append(abs(next - current))

    # TODO: We need curve fittign, but the only way I know to do that requries scipy > 0.9.
    is_outlier = doubleMADsfromMedian(slope, threshold)
    for v in range(len(is_outlier)):
        if is_outlier[v]:
            db['frames'][v+1]['small_frame'] = True
            db['small_frames'] += [v]
    #
    return db

def merge_reports(db, reports):
    """ Instead of images to analize, use previously generated data in *.json format,
        and merge them to produce single report.
    """
    # TODO Partial report should have freedom to keep single or group of frames...
    # Whole report database should be little more generic, not hard coded.
    first = 1
    last  = 1
    keys = []
    # We want to retrieve data from segments:
    if not 'file_sizes' in db.keys():
        db['file_sizes'] = []
    if not 'missing_frames' in db.keys():
        db['missing_frames'] = []

    for frame in range(len(reports)):
        file = open(reports[frame])
        data = json.load(file)
        for key in data['frames']:
            db['frames'][int(key)] = data['frames'][key] # Json turns any key into string.
            db['file_sizes'] += data['file_sizes']
            db['missing_frames'] += data['missing_frames']
            keys.append(int(key))

    keys.sort()
    db['first_frame'] = keys[0]
    db['last_frame']  = keys[-1]
    db['pattern']     = utils.padding(data['pattern'], 'shell')[0]
    db['job_name']    = data['job_name']

    return db

def get_ifd_stats(job_name, ifd_path):
    stats={}
    stats['frames'] = {}
    # Lets find our ifd files:
    job_name = job_name.rstrip("_mantra")
    pattern  = os.path.join(ifd_path, job_name)
    pattern  += ".*.ifd" 
    ifds     = glob.glob(pattern)
    ifds.sort()
    for ifd in ifds:
        seq = utils.padding(ifd)
        stats['frames'][seq[1]] = {}
        size = os.path.getsize(ifd)
        stats['frames'][seq[1]]['ifd_size'] = size
    return stats

def get_render_stats(job_name):
    """
    Retrives render statistics from render manager.
    """
    import hafarm
    farm = hafarm.HaFarm()
    return farm.get_job_stats(job_name)

def find_last_jobScript(db, pattern='*_mantra.json'):
    '''Iterate over json parms files, find which ones were rendering into same
       image pattern, then choose the youngest one.
       This is something we would like to get rid of, once we
       will have database in place.
    '''
    import hafarm
    from operator import itemgetter

    #
    script_path = const.hafarm_defaults['script_path']
    script_path = os.path.expandvars(script_path)
    parms_files = os.path.join(script_path, pattern)
    # List of real files on disk:
    parms_files = glob.glob(parms_files)
    parms_dict  = {}

    # pattern like *.json 
    pattern_padded = db['pattern']
    print "Pattern to match: %s " % pattern_padded
    # Go through files on disk:
    for file_name in parms_files:
        with open(file_name, 'r') as file:
            print 'opening %s' % file_name
            jfile = json.load(file)
            if 'parms' in jfile.keys():
                if 'output_picture' in jfile['parms'].keys():
                    output_pattern = utils.padding(jfile['parms']['output_picture'], 'shell')[0]
                    if pattern_padded == output_pattern:
                        print 'Adding file %s to a list of candidates' % file_name
                        jfile['json_file_name'] = file_name
                        parms_dict[jfile['parms']['submission_time']] = jfile

    # 
    if not parms_dict:
        return None
        
    # Params sorted with submission time. The last one will be the youngest one.
    submissions = sorted(parms_dict.keys())
    candidate = parms_dict[submissions[-1]]
    print 'Assuming parms from %s ' % str(time.ctime(candidate['parms']['submission_time']))
    print candidate
    return candidate['json_file_name']



def resend_frames_on_farm(db):
    '''Tries to render bad/missing frames again.
    '''
    import hafarm
    script_path = const.hafarm_defaults['script_path']
    script_path = os.path.expandvars(script_path)
    job_name    = str(db['job_name'])
    parms_file = os.path.join(script_path, job_name + '.json')
    redebug    = False

    if not os.path.isfile(parms_file):
        print "Error: No parms file for %s job found." % job_name
        print "Trying to find proper parms file for: %s" % db['pattern']
        parms_file = find_last_jobScript(db)
        if not os.path.isfile(str(parms_file)):
            print "...Nothing found! Can't resubmit job without parms file."
            return None


    output_picture = ''
    job_ids = []
    for frame_num in db['frames']:
        frame = db['frames'][frame_num]
        if not frame['exists'] or not frame['integrity'] \
        or frame['small_frame']:
            redebug = True
            output_picture = str(frame['file'])
            farm = hafarm.HaFarm()
            farm.load_parms_from_file(parms_file)
            farm.parms['start_frame'] = frame_num
            farm.parms['end_frame']   = frame_num
            farm.render()
            job_ids.append(farm.parms['job_name'])
            db['resent_frames'] += [frame_num]


    # Lets rerun Debuger:
    if redebug:
        # Generate report per file:
        debug_render = hafarm.BatchFarm(job_name = job_name + "_debug", queue = '')
        debug_render.debug_image(output_picture)
        debug_render.parms['start_frame'] = db['first_frame']
        debug_render.parms['end_frame']   = db['last_frame']
        [debug_render.add_input(idx) for idx in job_ids]
        debug_render.render()
        # Merge reports:
        merger   = hafarm.BatchFarm(job_name = job_name + "_mergeReports", queue = '')
        merger.add_input(debug_render)
        ifd_path = os.path.join(os.getenv("JOB"), 'render/sungrid/ifd')
        merger.merge_reports(output_picture, ifd_path=ifd_path, resend_frames=False)
        merger.render()



def main():
    options, args = parseOptions()
    html          = ""
    render_stats  = None
    ifd_stats     = None

    # Early quit:
    if not args:
        print help()
        sys.exit()

    # Our main container:
    # TODO: Make it custom class Sequance(dict)
    db = {'first_frame': 0,
          'last_frame' : 0,
          'pattern'    : utils.padding(args[0], 'shell'),
          'job_name'   : '',
          'frames'     : {},
          'time_stamp' : time.time(),
          'resent_frames': []
          }


    # Merge json files previsouly generated:
    reports = [report for report in args if report.endswith('.json')]
    db      = merge_reports(db, reports)
    # Get render statistics:
    if options.render_stats:
        render_stats = get_render_stats(db['job_name'])
    # Find suspicion small files:
    #db = check_small_frames(db, options.mad_threshold)

    # TODO: This works atm but I'm disableing it for a sake of health care
    # Get IFD (Mantra specific) statistics:
    #if options.ifd_path:
    #    ifd_stats = get_ifd_stats(db['job_name'], options.ifd_path)

    if options.resend_frames:
        resend_frames_on_farm(db)

    # # Present report:
    if options.save_html or options.send_email:
        html = generate_html(db, render_stats, ifd_stats)

    # Send report by email:
    if options.send_email:
        send_debug(db['job_name'], [utils.get_email_address()] + const.RENDER_WRANGERS, html)
        
    # Saving to files:
    if options.save_html or options.save_json:
        path, report_file = os.path.split(reports[0])
        report_file       = os.path.join(path, db['job_name']) + ".%s"

        # Write it down:
        if options.save_html: 
            with open(report_file % 'html', 'w') as file:
                file.write(html)

        if options.save_json:
            with open(report_file % 'json', 'w') as file:
                json.dump(db, file, indent=2)

        if options.save_html and options.display_report: 
            os.popen("gnome-open %s " % report_file)



if __name__ == "__main__": main()