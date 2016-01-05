# Constants and varibles
# TODO: We should have better way to deal with variables mangling.
# to be able to replace, switch it on the fly down the steam by plugins
# if required. 

TASK_ID = '@TASK_ID/>'
RAND_LEN = 6
TILE_ID  = '__TILE__'
OIIOTOOL = '/opt/packages/oiio-1.4.15/bin/oiiotool.sh'
MANTRA_FILTER = '/STUDIO/houdini/houdini13.0/scripts/python/HaFilterIFD_v01.py'
PROXY_POSTFIX = "proxy"
TILES_POSTFIX = 'tiles'
DEBUG_POSTFIX = 'debug'
MAX_CORES      = '@MAX_CORES/>'
IINFO          = '$HFS/bin/iinfo'
DEBUG          = 1
TASK_ID_PADDED = '@TASK_ID_PADDED/>'
SCENE_FILE     = '@SCENE_FILE/>'
RENDER_WRANGERS= ['renderfarm@human-ark.com']
HAFARM_DEFAULT_BACKEND = 'Slurm'



hafarm_defaults = {'start_frame': 1,
                   'end_frame'  : 48,
                   'step_frame' : 1,
                   'queue'      : '3d', # Queue to be used. FIXME: This should be list
                   'group'      : '' ,  # Group of a machines to be used (subset of queue or farm most of the case.) FIXME: This should be list.
                   'slots'      : 15,   # Consume slots. On SGE these are custom numbers, not necceserly cores.
                   'cpu_share'  : 1.0,  # Controls multithreading based on percentage of avaiable resources (cpus).
                   'priority'   : -500, # TODO: Shouldn't it be genereal 0-1 value translated into specific number by manager class?
                   'req_memory' : 4,    # Minimal free memory on rendernode.
                   'job_on_hold': False,#
                   'hold_jid'   : [],   # Job's names or ids which current job is depend on.
                   'hold_jid_ad': [],   # Job's names or ids which current array job is depend on. 
                   'target_list': [],   # Used in applications with multiply targets (cameras in Maya batch, Write node in Nuke)
                   'layer_list' : [],   # A subset of a scene to be rendered (used by Maya, in Houdini it would be takes for example.)
                   'command'    : "",   # Rendering command.
                   'command_arg': [],   # Rendering command arguments as list.
                   'email_list' : [],   # A list of emails for notification
                   'email_opt'  : '',   # Options for emails (job's states triggering notification)
                   'make_proxy' : False,# Optionally makes a proxy for output image. 
                   # Render farm settigs bellow:
                   'job_name'   : "",   # Render job name.
                   'log_path'   : "$JOB/render/sungrid/log", # Env. variables will be expanded by render manager. 
                   'script_path': "$JOB/render/sungrid/jobScript", # Rendermanager will execute that script.
                   'email_stdout': False, # Homebrew support for mailing.
                   'email_stderr': False, # Same as above.
                   'scene_file' : "",   # The scene file used for rendering. It always should be a copy of source scene file. 
                   'user'       : "",   # Login user.
                   'include_list':[],   # Explicite list of computers to be used for job's execution. 
                   'exclude_list':[],   # Explicite list of computers to be excluded from job's execution.
                   'ignore_check':False,# Ignore checkpoint used to find out, if machine is avaiable (user login in SGE).
                   'job_asset_name': "",
                   'job_asset_type': "",
                   'job_current'   : "",
                   'rerun_on_error': True,
                   'submission_time': 0.0,  # As a name implies. Not sure if this is essential to record it ourselfs, but still.
                   'req_start_time': 0.0,   # As a name implies. Time a job will unhold and scheduled according to free resources. 
                   'req_resources' : "",  # Request additional resources.
                   'req_license'   : "",  # Request the license in format: license=number (mayalic=1)
                   'output_picture': "",  # This file is referential for rendering output (for debugging etc)
                   'frame_range_arg':["%s%s%s", '', '', ''],  # It should be ["-flag %s -flag %s", parm_key, parm_key], to produce:
                                              # '-s %s -e' % (self.parms['start_frame'], self.parms['end_frame']) for example (Maya)
                   'frame_list'    :'',       # It is sometimes useful to render specific frames, not ranges of it. Supported format: 1,2,3,4-10,11-20x2
                   'max_running_tasks':1000,  # Max number of tasks in a job run at the same time (1000 considered to be non limit.)
                   'frame_padding_length': 4, # Sometimes we need to repersent task_id with padddign enabled (task 1 as 0001). This var is helpful ATM (to be removed?)
                   'pre_render_script':  "", # This will be prepend to execution script as sent to scheduler.
                   'post_render_script': "" # Thils will be appended to execution script as sent to scheduler. 
                                        }