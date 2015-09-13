#!/usr/bin/python
# Standard:
import os
import sys
import glob
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
    def isfloat(item):
        try:
            return float(item)
        except: pass

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
        res = oiiotool_output[0].split(":")[1]
        res = res.split()
        res = [isfloat(x) for x in res if isfloat(x)]
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
        return nans, infs, res

    missing_frames = []
    file_sizes = []

    # Main loop:
    for frame in range(first_frame, last_frame+1):
        # This file should exist:
        # FXIME: paddign() has _frame=40 for this.
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
            nans, infs, res = oiiotool_output(suspecet)
            
            # Get size in kbytes:
            size = os.path.getsize(suspecet)
            file_sizes.append(size)

        # Collect data:
        db['frames'][frame] = {'exists': exists,
                     'integrity': integrity,
                     'file': suspecet,
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

    
    # Run over all frames to gather per-frame information:
    db = proceed_sequence(sequence, db, first_frame, last_frame)


    # Present report:
    if options.save_json:
        path = const.hafarm_defaults['log_path']
        path = os.path.expandvars(path)

        # FIXME: This is little messy...
        tmp, report = os.path.split(sequence[0])
        # Single frame mode shouldn't strip off padding, like does version above:
        if single_frame: report  = os.path.split(images[0] + ".")[1]
        # Add log path, frame and the extension acording to requested save format:
        report = os.path.join(path, report + "%s")
        with open(report % 'json', 'w') as file:
            json.dump(db, file, indent=2)
    else:
        print db


if __name__ == "__main__": main()