#!/usr/bin/python
# Standard:
import os
import sys
import glob
import subprocess
from optparse import OptionParser
import json

# Custom:
import fileseq
from hafarm import utils
from hafarm import const


def help():
    return 'debug_images: Run number of standard tests on sequence of images.\
        \n\tusage: debug_images [] -i path/to/image_{missing_part} \
        \n '


def parseOptions():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-i", "--image_pattern", dest="image_pattern",  action="store", type="string", default="", help="Bash patter for images to debug ('image.*.exr').")
    parser.add_option("-j", "--job", dest="job_name",  action="store", type="string", default="", help="Job name debug referes to. It should be job name of frames to be proceed.")
    parser.add_option(""  , "--save_json", dest='save_json', action='store_true', default=False, help="Save report as json file.")
    parser.add_option("-p", "--print", dest='print_report', action='store_true', default=True, help="Prints report on stdout.")
    parser.add_option("-o", '--output', dest='output_dir', action='store', default=None, type='string', help='Output folder for a reports.')
    parser.add_option("-s", '--start_frame', dest='start_frame', action='store', default=None, type='string', help='Overwrites start frame to process.')
    parser.add_option("-e", '--end_frame', dest='end_frame', action='store', default=None, type='string', help='Overwrites end fram to process.')

    (opts, args) = parser.parse_args(sys.argv[1:])
    return opts, args




def proceed_sequence(sequence, db, first_frame, last_frame):
    """Power horse of the script. Use iinfo and oiiotool to find details about
    images. Stores result in dictonary 'db'
    """
    nans = 0
    infs = 0
    res  = (0,0)
    missing_frames = []
    file_sizes = []

    def isfloat(item):
        try:
            return float(item)
        except: pass

    def iinfo_output(image):
        """$HFS/bin/iinfo loop."""
        integrity = True
        iinfo_bin = os.path.expandvars(const.IINFO)
        sp        = subprocess.Popen([iinfo_bin, '-b', '-i' , image], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = sp.communicate()

        if not output or error:
            print error
            return integrity

        for line in output:
            if line.startswith("Integrity"):
                if not "File OK" in line:
                    integrity = False
                break
        return integrity

    def oiiotool_output(image):
        """oiiotool loop."""
        nans = 0
        infs = 0
        integrity = True
        res  = (0,0)
        oiiotool_bin = os.path.expandvars(const.OIIOTOOL)
        sp = subprocess.Popen([oiiotool_bin, '--stats', image], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = sp.communicate()
        
        if error or not output:
            print error
            return nans, infs, res

        for line in output:
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
        return nans, infs, res



    # Main loop:
    for frame in range(first_frame, last_frame+1):
        # This file should exist:
        # FXIME: paddign() has _frame=40 for this.
        image = sequence[0] + str(frame).zfill(sequence[2]) + sequence[3]
        exists   = os.path.isfile(image)

        # Frame is missing:
        if not exists:
            # Shorcut to store list of missing frames. 
            missing_frames.append(frame)
        else:
            # iinfo run:
            integrity = iinfo_output(image)
            # oiiotool run:
            nans, infs, res = oiiotool_output(image)
            
            # Get size in kbytes:
            size = os.path.getsize(image)
            file_sizes.append(size)

        # Collect data:
        db['frames'][frame] = {'exists': exists,
                     'integrity': integrity,
                     'file': image,
                     'nans': nans,
                     'infs': infs,
                     'resolution': res,
                     'size': size,
                     'small_frame': False}

    # Save a shortcut info:
    db['missing_frames'] = missing_frames
    db['file_sizes']     = file_sizes

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
    pattern       = os.path.expandvars(pattern)
    images        = glob.glob(pattern)
    images.sort()

    # If pattern returned single frame, we assume user 
    # wants to examine single file from a siquence. 
    if len(images) == 1:
        single_frame = True
    if len(images) == 0:
        print "No images found: %s" % options.image_pattern
        sys.exit()

    # Some feedback to user. 
    print sys.argv[0] + " proceeds %s files: %s" % (len(images), images[0])

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

    
    # Run over all frames to gather per-frame information:
    db = proceed_sequence(sequence, db, first_frame, last_frame)


    # Present report:
    if options.save_json:
        path = const.hafarm_defaults['log_path']
        path = os.path.expandvars(path)

        # FIXME: This is little messy...
        tmp, report = os.path.split(options.image_pattern)
        # Single frame mode shouldn't strip off padding, like does version above:
        if single_frame: report  = os.path.split(images[0] + ".")[1]
        # Add log path, frame and the extension acording to requested save format:
        report = os.path.join(path, report + "%s")
        with open(report % 'json', 'w') as file:
            json.dump(db, file, indent=2)
    else:
        print db


if __name__ == "__main__": main()