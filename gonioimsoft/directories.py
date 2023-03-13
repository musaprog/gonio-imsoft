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
