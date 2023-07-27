'''Places for saving and loading files.

Constants
---------
USERDATA_DIR : string
    Path to the user data that contains small files
    such as settings.
'''

import os
import platform

CODE_ROOTDIR = os.path.dirname(os.path.realpath(__file__))
USER_HOMEDIR = os.path.expanduser('~')

if platform.system() == "Windows":
    USERDATA_DIR = os.path.join(USER_HOMEDIR, 'GonioImsoft')
else:
    USERDATA_DIR = os.path.join(USER_HOMEDIR, '.gonioimsoft')

if os.path.isdir(USERDATA_DIR):
    IS_USERDATA_INITIALIZED = True
else:
    IS_USERDATA_INITIALIZED = False

def initialize_userdata():
    '''Create all user data diretories used by GonioImsoft

    It is good to ask for the user's consent before running this
    function unless USERDATA_DIR exists already.
    '''
    dirs = [
            USERDATA_DIR,
            os.path.join(USERDATA_DIR, 'macros'),
            os.path.join(USERDATA_DIR, 'biosyst_stimuli'),
            os.path.join(USERDATA_DIR, 'presets')
            ]
    for adir in dirs:
        os.makedirs(adir, exist_ok=True)
