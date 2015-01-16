# -*- coding: iso-8859-1 -*-

import os
from time import localtime
from random import getrandbits

def add_me(formats , directory, files):
    for file in files:
        file = os.path.join(directory, file)
        if os.path.isfile(file):
            if os.path.splitext(file)[1][1:].lower() in formats:
                if 1 == 1:
                    if padding(file, False) not in uniques:
                        uniques.append(padding(file, True))
                        final_list.append(file)
                else: final_list.append(file)


def scan_for_files(formats, directory):
    global uniques, final_list
    uniques = []
    final_list = []
    os.path.walk(directory, add_me, formats)
    return final_list




def padding(file, full_name=True, details=False):
    pic_dir = os.path.dirname(file)
    base, ext = os.path.splitext(os.path.basename(file))
    list_base = list(base)
    list_base.reverse()
    count = 0
    for letter in list_base:
        if letter.isdigit(): count += 1
        else: break
    if full_name:
        if count != 0:
            if count == 1: base = base[0:-count] + "$F"
            else: base = base[0:-count] + "$F" + str(count)
        file = os.path.join(pic_dir, base + ext)
    else:
        if count != 0: base = base[0:-count]
        file = os.path.join(pic_dir, base)
    if file.endswith("."): file = file[:-1]
    if details: return (file, count, ext)
    return file



def getParentFolder(file, length=6):
  """ Returns parent folder for studio specific JOB setup."""
  path = os.path.sep.join(file.split(os.path.sep)[:length])
  return path


def getDateAsString():
  import time
  t = time.gmtime()
  t =  str(t.tm_year).zfill(2)  + "." + str(t.tm_mon).zfill(2) \
  + "." + str(t.tm_mday).zfill(2)
  return t


def makeDailiesFolder(dailies=None, subfolder='edit/dailies'):
    """Creates dailes folder for production."""
    if not dailies:
        current = os.getenv("JOB_CURRENT")
        asset   = os.getenv("JOB_ASSET_NAME")
        dailies = os.path.join(os.getenv("JOB_PROJECT_DIR"), \
        current, current, current, subfolder, getDateAsString(), asset)

    # Create folder if it doesn't already exist:
    if not os.path.exists(dailies):
        try:
            os.makedirs(dailies)
            os.popen("chmod g+w %s" % dailies)
            os.popen("chmod g+w %s" % os.path.join(dailies, "../"))
        except:
            print "Can't create %s. Exiting now." % dailies
        return False
    return True



def getJobId():
  from ha.path import getRandomName
  return getRandomName()
  #return str(hex(getrandbits(10))) + "_" + ''.join([str(s) for s in localtime()][:-3])


def sort_by_pattern(items, pattern="\\d{3}$", reverse=False, copy=True):
    """ Sorts a list of strings by its substring defined with regular expression.
    Default pattern sorts by version number expressed as a three trialling digits.

    Another useful example is to sort by shot number at the beginning of string: 
    "^shot[0-9]{4}", or to sort by pipeline stage:  "_[a-z]*?_v"
    """ 

    # Setup only once:
    import re
    prog = re.compile(pattern)

    def get_pattern(item):
        # Use compiled regex:
        match = prog.search(item)
        if match:
            return match.group(0)
        else:
            return None

    # Make a sorted copy of the list:
    if copy:
        items = sorted(items, key=get_pattern, reverse=reverse)
    else:
    # or sort in-place:
        items.sort(key=get_pattern, reverse=reverse)
    return items
  
  
  