#!/usr/bin/python
# Standard:
import os
import sys
import glob
import smtplib
from email.mime.text import MIMEText
from optparse import OptionParser
import numpy

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

tr.d0 td {
    background-color: #CC9999; color: black;
}
tr.d1 td {
    background-color: #9999CC; color: black;
}
tr.d2 td {
    background-color: red; color: black;

}
}
</style>
</head>"""


FOOT = """</body></html>"""


TABLE_HEADER = """
<table id="t01">
  <tr>
    <th>Frame</th>
    <th>On disk</th>        
    <th>Integrity</th>
    <th>Nans</th>
    <th>Infs</th>
    <th>Size</th>
    <th>Small file</th>
  </tr>"""

ROW =  """
        <td>%s</td>
        <td>%s</td>       
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        </tr>"""


NORMAL_FILE_TAG = "<tr>"
MISSING_FILE_TAG = """<tr class="d2">"""
BAD_FILE_TAG     = """<tr class="d1">"""
SMALL_FILE_TAG   = """<tr class="d0">"""


def help():
    return 'debug_images: Run number of standard tests on sequence of images.\
        \n\tusage: debug_images [] -i path/to/image_{missing_part} \
        \n '


def parseOptions():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-i", "--input", dest="image_pattern",  action="store", type="string", default="", help="Imge pattern to proceed.")
    parser.add_option("-m", "--send_email", dest='send_email', action='store_true', default=False, help="Sends report via email.")
    parser.add_option("-s", "--save_html", dest='save_html', action='store_true', default=False, help="Save report as html file.")
    parser.add_option("-p", "--print", dest='print_report', action='store_true', default=True, help="Prints report on stdout.")
    parser.add_option("-d", "--display", dest='display_report', action='store_true', default=False, help="Displays report in web browser.")
    parser.add_option("-e", "--errors_only", dest='errors_only', action='store_true', default=False, help="Focus only on errors in report.")
    # parser.add_option("-d", "--driver", dest="driver",  action="store", type="string", help="ROP driver to render.")
    # parser.add_option("-f", "--frame_range", dest="frame_range",  action="store", type="int", nargs=2, help="Frames range to render (-f 1 100)")
    # parser.add_option("-j", "--threads", dest="threads",  action="store", type="int", default=1, help="Controls multithreading.")
    # parser.add_option("-l", "--frame_list", dest="frame_list",  action="store",  help="Alternative ")
    # parser.add_option("", "--generate_ifds", dest='generate_ifds', action='store_true', default=False, help="Changes Rop setting to save IFD files on disk. ")
    # parser.add_option("", "--ifd_path", dest='ifd_path', action='store', default='$JOB/render/sungrid/ifd', help="Overwrites default IFD path.")
    (opts, args) = parser.parse_args(sys.argv[1:])
    return opts, args



def generete_html(db):
    html = ""
    html += HEAD
    html += "<body>"
    html += TABLE_HEADER


    for frame_num in db:
        if type(frame_num) != type(0):
            continue
        frame = db[frame_num]
        if not frame['exists']:
            html += MISSING_FILE_TAG
        elif frame['small_frame']:
            html += SMALL_FILE_TAG
        else:
            html += NORMAL_FILE_TAG

        frame = db[frame_num]
        html += ROW % (frame_num, frame['exists'], 
                       frame['integrity'], frame['nans'], 
                       frame['infs'], frame['size'], 
                       frame['small_frame'])

    html += FOOT

    return html


def send_debug(db, html):

    msg = MIMEText(html, 'html')

    # me == the sender's email address
    # you == the recipient's email address
    msg['Subject'] = 'Debug for %s' % db['pattern']
    msg['From'] = 'symek@grafika28'
    msg['To'] = 's.kapeniak@human-ark.com'

    me  = 's.kapeniak@human-ark.com'
    you = ['s.kapeniak@human-ark.com']

    s = smtplib.SMTP('ms1.human-ark.com')
    s.sendmail(me, you, msg.as_string())
    s.quit()

def check_small_frames(file_size, db):
    # Check if some files aren't too small:
    narray = numpy.array(file_size)
    avg_size = numpy.mean(narray)

    db['small_frames'] = []

    for frameNum in db.keys():
        if type(frameNum) == type(0):
            frame = db[frameNum]
            size = frame['size']
            x = size - avg_size
            if abs(x) > avg_size * 0.2:
                db['small_frames'].append(frameNum)
                db[frameNum]['small_frame'] = True
    return db


def main():

    options, args     = parseOptions()

    if not options.image_pattern:
        print help()
        sys.exit()

    image_pattern = options.image_pattern
    images        = glob.glob(image_pattern)
    images.sort()

    tmp      = utils.padding(images[0])
    sequence = utils.padding(images[-1])

    first_frame = tmp[1]
    last_frame  = sequence[1]

    db = {'first_frame': first_frame,
          'last_frame' : last_frame,
          'pattern'    : options.image_pattern}

    missing_frames = []
    file_size = []
    

    for frame in range(first_frame, last_frame+1):
        integrity = True
        nans = 0
        infs = 0

        # This file should exist:
        suspecet = sequence[0] + str(frame).zfill(sequence[2]) + sequence[3]
        exists = os.path.isfile(suspecet)

        if exists:
            # iinfo run:
            iinfo_output = os.popen(const.IINFO + " %s" % suspecet).readlines()
            for line in iinfo_output:
                if line.startswith("Integrity"):
                    if "File OK" in line:
                        integrity = True
                    else:
                        integrity = False
                    break

            # oiiotool run:
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

            # Get size to compute std dev of bytes:
            size = os.path.getsize(suspecet)
            file_size.append(size)

        # Frame is missing:
        else:
            missing_frames.append(frame)

        # Collect data:
        db[frame] = {'exists': exists,
                     'integrity': integrity,
                     'nans': nans,
                     'infs': infs,
                     'size': size,
                     'small_frame': False}

    # Save a shortcut info:
    db['missing_frames'] = missing_frames

    # Compute avarage size of file in sequence.
    # and 
    db = check_small_frames(file_size, db)


    if options.save_html or options.send_email:
        html = generete_html(db)
        if options.send_email:
            send_debug(db, html)
        if options.save_html:
            file = open('/home/symek/Desktop/test.html', 'w')
            file.write(html)
            file.close()

    if options.print_report:
        print db

    if options.display_report:
        os.popen("gnome-open /home/symek/Desktop/test.html")

if __name__ == "__main__": main()