import os
from const import hafarm_defaults


class HaFarmParms(dict):
    """Render manager agnostic job's parameters container.
    """
    def __init__(self, initilize=False, defaults=hafarm_defaults):
        super(HaFarmParms, self).__init__()

        # Init with defaults:
        self.merge_parms(defaults)

        # Set parms unrelated to host, like jobname, user etc:
        if initilize:
            self.initialize_env_parms()

    def __setitem__(self, key, value):
        """Custom item setter. Main reason fo it is type checking.
        """
        assert key in hafarm_defaults, "Key %s has to have default in hafarm_defaults" % key
        if isinstance(value, type(hafarm_defaults[key])):
            super(HaFarmParms, self).__setitem__(key, value)
        else:
            raise TypeError("Wrong type of value %s: %s" % (key, value))

    def initialize_env_parms(self):
        """Parameters to be derived without touching host app and not having defaults.
        """
        self['job_asset_name'] = os.getenv("JOB_ASSET_NAME", 'Not_Set')
        self['job_asset_type'] = os.getenv("JOB_ASSET_TYPE", 'Not_Set')
        self['job_current']    = os.getenv("JOB_CURRENT", 'Not_Set')
        self['user']           = os.getenv("USER", 'Not_Set')

    def merge_parms(self, parms_dict):
        """Copies a content of parms_dict into self.
        """
        for key, value in parms_dict.iteritems():
            self[key] = value

    def has_entry(self, entry):
        if entry in self.keys():
            return True
        return

   
# TODO think about this approach.
class FrameRangeParm(HaFarmParms):
  def __init__(self):
    self['start_frame'] = 1
    self['end_frame']   = 48
    self['frame_step']  = 1
    self['command']     = ["-s %s -e %s -i %s", 'start_frame', 'end_frame', 'frame_step']