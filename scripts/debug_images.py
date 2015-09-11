#!/usr/bin/python
# Standard:
import os
import sys
import glob
import smtplib
from email.mime.text import MIMEText
from optparse import OptionParser
#import numpy
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
    <th>CPU Cores time</th>
    <th>Max VMEM</th>
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


NORMAL_FILE_TAG = "<tr>"
MISSING_FILE_TAG = """<tr class="missing_file">"""
BAD_FILE_TAG     = """<tr class="bad_file">"""
SMALL_FILE_TAG   = """<tr class="small_frame">"""


def help():
    return 'debug_images: Run number of standard tests on sequence of images.\
        \n\tusage: debug_images [] -i path/to/image_{missing_part} \
        \n '


def parseOptions():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-i", "--image_pattern", dest="image_pattern",  action="store", type="string", default="", help="Bash patter for images to debug ('image.*.exr').")
    parser.add_option("-j", "--job", dest="job_name",  action="store", type="string", default="", help="Job name debug belongs to.")
    parser.add_option("-m", "--send_email", dest='send_email', action='store_true', default=False, help="Sends report via email.")
    parser.add_option(""  , "--save_html", dest='save_html', action='store_true', default=False, help="Save report as html file.")
    parser.add_option(""  , "--save_json", dest='save_json', action='store_true', default=False, help="Save report as json file.")
    parser.add_option("-p", "--print", dest='print_report', action='store_true', default=True, help="Prints report on stdout.")
    parser.add_option("-o", '--output', dest='output_dir', action='store', default=None, type='string', help='Output folder for a reports.')
    parser.add_option("",   '--ifd_path', dest='ifd_path', action='store', default=None, type='string', help='Path to look for IFD files when IFD stats are requested.')
    parser.add_option("-d", "--display", dest='display_report', action='store_true', default=False, help="Displays report in web browser.")
    parser.add_option("-e", "--errors_only", dest='errors_only', action='store_true', default=False, help="Focus only on errors in report.")
    parser.add_option("",   "--merge_reports", dest='merge_reports', action='store_true', default=False, help='Merge *.json files not generate one.')
    (opts, args) = parser.parse_args(sys.argv[1:])
    return opts, args



def generate_html(db, render_stats=None, ifd_stats=None, errors_only=False):
    """Interate over rows in db and generate html document from that.
    """
    def bytes_to_megabytes(bytes, rounded=3):
        return round(int(bytes) / (1024.0*1024.0), rounded)

    html = ""
    html += HEAD
    html += "<body>"
    html += TABLE_HEADER

    # Fallbacks:
    r_stat = {'hostname': '', 'cpu': 0.0, 'maxvmem': 0.0}
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
            html += MISSING_FILE_TAG
        elif not frame['integrity']:
            html += BAD_FILE_TAG
        elif frame['small_frame']:
            html += SMALL_FILE_TAG
        else:
            html += NORMAL_FILE_TAG

        # Generate row:
        html += ROW % (frame_num, 
                       frame['exists'], 
                       frame['integrity'], 
                       frame['nans'], 
                       frame['infs'], 
                       str(bytes_to_megabytes(frame['size'])) + ' MB', 
                       frame['small_frame'], r_stat['hostname'], 
                       str(round(float(r_stat['cpu'])/60, 3)) + " min", 
                       r_stat['maxvmem'],
                       str(bytes_to_megabytes(i_stat['ifd_size'], 5)) + ' MB')

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

def check_small_frames(db):
    """Check for suspecious differences in frames size.
    """
    # TODO: This approach doesn't work.
    # We should compute rate of change in frame size
    # and warn in image size overshoot expect change. 

    # Check if some files aren't too small:
    sizes     = db['file_sizes']
    # narray    = numpy.array(db['file_sizes'])
    # grad_array= numpy.gradient(narray)
    # numpy.savetxt("/tmp/narray.chan", grad_array)
    # numpy.savetxt("/tmp/narray2.chan", narray)
    # avg_rate  = numpy.mean(grad_array)
    # x         = numpy.array(range(len(sizes)))
    # pca_array = numpy.vstack((x, grad_array))

    # # Extend size array +1 1+ to compute gradients:
    # sizes.append(sizes[-1]+grad_array[-1])
    # sizes.insert(0, sizes[0]+grad_array[0])

    # x, y, eigenvectors, eigenvalues = pca(pca_array)
    # print x
    # print y
    # print eigenvalues
    # print eigenvectors

    db['small_frames'] = []

    index = 0
    for frame_num in db['frames']:
            frame = db['frames'][frame_num]
            size = frame['size']
            prev = sizes[index-1]
            next = sizes[index+1]
            x = size - prev
            y = size - next
            if abs(grad_array[index]) > abs(avg_rate) * 5:
                db['small_frames'].append(frame_num)
                db['frames'][frame_num]['small_frame'] = True
            index += 1
    return db

def proceed_sequence(sequence, db, first_frame, last_frame):
    """Power horse of the script. Use iinfo and oiiotool to find details about
    images. Stores result in dictonary 'db'
    """
    def iinfo_output(suspect):
        """$HFS/bin/iinfo loop."""
        integrity = False
        iinfo_output = os.popen(const.IINFO + " %s" % suspecet).readlines()
        for line in iinfo_output:
            if line.startswith("Integrity"):
                if "File OK" in line:
                    integrity = True
                break
        return integrity

    def oiiotool_output(suspecet):
        """oiiotool loop."""
        nans = 0
        infs = 0
        integrity = True
        oiiotool_output = os.popen(const.OIIOTOOL + " --stats %s " % suspecet).readlines()
        for line in oiiotool_output:
            if "NanCount:" in line:
                line = line.strip()
                line = line.split(":")[1]
                _nans= line.split()
                _nans= sum([int(x) for x in _nans])
                if _nans:
                    nans = _nans
            elif "InfCount" in line:
                line = line.strip()
                line = line.split(":")[1]
                _infs= line.split()
                _infs= sum([int(x) for x in _infs])
                if _infs:
                    infs = _infs
        return nans, infs



    missing_frames = []
    file_sizes = []

    # Main loop:
    for frame in range(first_frame, last_frame+1):
        # This file should exist:
        suspecet = sequence[0] + str(frame).zfill(sequence[2]) + sequence[3]
        exists   = os.path.isfile(suspecet)

        # Frame is missing:
        if not exists:
            # Shorcut to store list of missing frames. 
            missing_frames.append(frame)
        else:
            # iinfo run:
            integrity = iinfo_output(suspecet)
            # oiiotool run:
            nans, infs = oiiotool_output(suspecet)
            
            # Get size in kbytes:
            size = os.path.getsize(suspecet)
            file_sizes.append(size)

        # Collect data:
        db['frames'][frame] = {'exists': exists,
                     'integrity': integrity,
                     'nans': nans,
                     'infs': infs,
                     'size': size,
                     'small_frame': False}

    # Save a shortcut info:
    db['missing_frames'] = missing_frames
    db['file_sizes']     = file_sizes

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
    for frame in range(len(reports)):
        file = open(reports[frame])
        data = json.load(file)
        for key in data['frames']:
            db['frames'][int(key)] = data['frames'][key] # Json turns any key into string.
            keys.append(int(key))

    keys.sort()
    db['first_frame'] = keys[0]
    db['last_frame']  = keys[-1]
    db['pattern']     = utils.padding(data['pattern'], 'shell')[0]
    db['job_name']    = data['job_name']

    return db


def get_render_stats(job_name):
    """
    Retrives render statistics from render manager.
    """
    import hafarm
    farm = hafarm.HaFarm()
    return farm.get_job_stats(job_name)

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

def main():
    """Run over files that match pattern to scan their qualities with
    command line image tools chain. Stores result in html and sand optionally
    via email.
    """
    options, args = parseOptions()
    single_frame  = False
    render_stats  = None
    ifd_stats     = None

    if not options.job_name:
        options.job_name = os.getenv("JOB_NAME", "")

    # Image is required:
    if not options.image_pattern and not options.merge_reports:
        print help()
        sys.exit()

    # Find images matching pattern, 
    # the real sequence on disk:
    pattern       = os.path.abspath(options.image_pattern)
    images        = glob.glob(pattern)
    images.sort()

    # If pattern returned single frame, we assume user 
    # wants to examine single file from a siquence. 
    if len(images) == 1:
        single_frame = True
        print "Single frame found."
    if len(images) == 0:
        print "No images found: %s" % options.image_pattern
        sys.exit()

    # Get first and last frame on disk
    # TODO Add argument to overwrite framge range on disk.
    tmp         = utils.padding(images[0])
    sequence    = utils.padding(images[-1])
    first_frame = tmp[1]
    last_frame  = sequence[1]

    # Our main container:
    # TODO: Make it custom class Sequance(dict)
    db = {'first_frame': first_frame,
          'last_frame' : last_frame,
          'pattern'    : options.image_pattern,
          'job_name'   : options.job_name,
          'frames'     : {} }


    if options.merge_reports:
        # Merge json files previsouly generated:
        db = merge_reports(db, images)
        # Get render statistics:
        render_stats = get_render_stats(db['job_name'])
        # Get IFD (Mantra specific) statistics:
        if options.ifd_path:
            ifd_stats = get_ifd_stats(db['job_name'], options.ifd_path)

        # Get rid of .json at the end
        sequence = utils.padding(os.path.splitext(images[-1])[0])
    else:
        # First run over all frames to gather per-frame information:
        db = proceed_sequence(sequence, db, first_frame, last_frame)

    # # Compute avarage size of files in a sequence.
    # db = check_small_frames(db)


    # Present report:
    if options.save_html or options.send_email \
    or options.display_report or options.save_json:
        html = generate_html(db, render_stats, ifd_stats)

        # Send report by email:
        if options.send_email:
            send_debug(options.job_name, [utils.get_email_address()], html)

        # Saving on disk:
        if options.save_html or options.save_json:
            path = const.hafarm_defaults['log_path']
            path = os.path.expandvars(path)

            # FIXME: This is little messy...
            tmp, report = os.path.split(sequence[0])
            # Single frame mode shouldn't strip off padding, like does version above:
            if single_frame: report  = os.path.split(images[0] + ".")[1]
            # Add log path, frame and the extension acording to requested save format:
            report = os.path.join(path, report + "%s")
          

            # Write it down:
            if options.save_html: 
                with open(report % 'html', 'w') as file:
                    file.write(html)

            if options.save_json:
                with open(report % 'json', 'w') as file:
                    json.dump(db, file, indent=2)

            # if options.save_html and options.display_report: 
            #     os.popen("gnome-open %s " % report)



if __name__ == "__main__": main()