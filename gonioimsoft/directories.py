'''Places for saving and loading files.

Constants
---------
USERDATA_DIR : string
    Path to user data
PUPILDIR : string
    Deprecated. Equals to USERDATA_DIR.
'''

import os
import platform

CODE_ROOTDIR = os.path.dirname(os.path.realpath(__file__))
USER_HOMEDIR = os.path.expanduser('~')

if platform.system() == "Windows":
    PUPILDIR = os.path.join(USER_HOMEDIR, 'GonioImsoft')
else:
    PUPILDIR = os.path.join(USER_HOMEDIR, '.gonioimsoft')

USERDATA_DIR = PUPILDIR
