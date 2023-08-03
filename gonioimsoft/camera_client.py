'''Client code for the camera server/client division.
'''

import socket
import time
import os
import subprocess
import platform
import sys
import json
import atexit

from .directories import CODE_ROOTDIR, USERDATA_DIR
from .common import SERVER_HOSTNAME, CAMERA_PORT
from .clientbase import ClientBase, run_client

MAX_RETRIES = 100
RETRY_INTERVAL = 1

SAVEDIR = os.path.join(USERDATA_DIR, 'camera_states')


class CameraClient(ClientBase):
    '''Local part of the camera server/client division.

    CameraClient runs on the same PC as GonioImsoft and it connects to
    a CameraServer instance (over network sockets, so using IP addressess).
    It works as a middleman.
    
    No big data is transmitted over the connection, only commands (strings).
    It is the CameraServer's job to store the images, and display them on
    screen (livefeed) if needed.
    
    See also clientbase.py and camera_server.py for more information.

    Attributes
    ----------
    modified_settings : set
    '''


    def __init__(self, host=None, port=None, running_index=0):
        
        if host is None:
            host = SERVER_HOSTNAME
        if port is None:
            port = int(CAMERA_PORT) + int(running_index)
        super().__init__(host, port)

        self.modified_settings = set()
        self._roi = None


    def acquireSeries(self, exposure_time, image_interval, N_frames, label, subdir):
        '''
        Acquire a time series of images.
        For more see camera_server.py.

        Notice that it is important to give a new label every time
        or to change data savedir, otherwise images may be written over
        each other (or error raised).
        '''
        function = 'acquireSeries;'
        parameters = "{}:{}:{}:{}:{}".format(exposure_time, image_interval, N_frames, label, subdir)
        message = function+parameters
        
        self.send_command(message)


    def acquireSingle(self, save, subdir):
        self.send_command('acquireSingle;0.1:{}:{}'.format(str(save), subdir))
    
    def saveDescription(self, filename, string):
        self.send_command('saveDescription;'+filename+':'+string)

    def set_roi(self, roi):
        self._roi = roi
        self.send_command('set_roi;{}:{}:{}:{}'.format(*roi))

    def set_save_stack(self, boolean):
        self.send_command('set_save_stack;{}'.format(boolean))


    def get_cameras(self):
        '''Lists available cameras (their names) on the server.
        '''
        return self.send_command('get_cameras', listen=True)

    
    def get_camera(self):
        '''Returns a name describing the current camera device.
        '''
        return self.send_command('get_camera', listen=True)


    def set_camera(self, name):
        '''Sets what camera to use on the server.
        '''
        self.send_command(f'set_camera;{name}')


    def get_settings(self):
        '''Retrieves available settings of the camera device.
        '''
        return self.send_command('get_settings', listen=True)
    
    def get_setting_type(self, setting_name):
        '''Returns the type of the setting.
        One of the following: "string", "float" or "integer"
        '''
        return self.send_command(f'get_setting_type;{setting_name}',
                                listen=True)

    def get_setting(self, setting_name):
        '''Returns the current value of the setting as a string.
        '''
        return self.send_command(f'get_setting;{setting_name}',
                                listen=True)
    
    def set_setting(self, setting_name, value):
        '''Sets the specified setting to the specified value.
        '''
        self.send_command(f'set_setting;{setting_name}:{value}')
        self.modified_settings.add(setting_name)


    def save_state(self, label, modified_only=True):
        '''Acquires the current camera state and saves it
        
        modified_only : bool
            If True, save only those settings that have been edited
            by the user during this session.
        '''
        state = {}
        state['settings'] = {}
        
        # Save camera device settings
        for setting in self.get_settings():
            if modified_only and setting not in self.modified_settings:
                continue
            state['settings'][setting] = self.get_setting(setting)

        savedir = os.path.join(SAVEDIR, self.get_camera())
        os.makedirs(savedir, exist_ok=True)

        with open(os.path.join(savedir, f'{label}.json'), 'w') as fp:
            json.dump(state, fp)


    def load_state(self, label):
        '''Loads a previously saved camera state.
        '''

        savedir = os.path.join(SAVEDIR, self.get_camera())
        fn = os.path.join(savedir, f'{label}.json')
        
        if not os.path.exists(fn):
            raise FileNotFoundError(f'{fn} does not exist')

        with open(fn, 'r') as fp:
            state = json.load(fp)

        for setting, value in state['settings'].items():
            self.set_setting(setting, value)


    def list_states(self):
        '''Lists saved states available for the current camera.
        '''
        savedir = os.path.join(SAVEDIR, self.get_camera())
        if not os.path.isdir(savedir):
            return []
        return [fn.removesuffix('.json') for fn in os.listdir(savedir) if fn.endswith('.json')]


    def start_server(self):
        super().start_server('camera')

    def reboot(self):
        '''Performs a "reboot" for the camera and restores settings.

        Can be used as a "dirty fix" when the first image acqusition
        works fine but the subsequent ones crash for unkown reasons.
        '''
        self.set_camera(self.get_camera())
        self.load_state('previous')
        if self._roi:
            self.set_roi(self._roi)


def main():
    run_client(CameraClient)

if __name__ == "__main__":
    main()
