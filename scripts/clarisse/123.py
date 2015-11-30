from optparse import OptionParser
import sys, os

# Clarisse doesn't allow command arguments to be passed to starup_script, what a shame...
# def parseOptions():
#     usage = "usage: %prog [options] arg"
#     parser = OptionParser(usage)
#     parser.add_option("", "--temp_folder", dest='temp_folder', action='store', default='/tmp', help="Temp folder for Clarisse session.")
#     (opts, args) = parser.parse_args(sys.argv[1:])
#     return opts, args



def main():
    """ Sets various things for Clarisse.
    """
    # opts, arg = parseOptions()
    # Sets custom TEMP:
    clarisse_tmp_dir = os.getenv("CLARISSE_TEMP_DIR", None)
    if clarisse_tmp_dir:
        if os.path.isdir(clarisse_tmp_dir):
            obj = ix.get_item("project://__prefs_vars.general").get_object()
            obj.attrs.temp_folder.attr.set_string(clarisse_tmp_dir)
            print "INFO: Setting temp_folder var. to: %s" % clarisse_tmp_dir
    else:
        print "WARNING: $CLARISSE_TEMP_DIR not specified."
        print "WARNING: Using %s instead." % \
        ix.get_item("project://__prefs_vars.general").get_object().attrs.temp_folder

if __name__ == "__main__": main()