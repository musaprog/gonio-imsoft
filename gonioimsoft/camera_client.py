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
from .camera_communication import SERVER_HOSTNAME, PORT

MAX_RETRIES = 100
RETRY_INTERVAL = 1

SAVEDIR = os.path.join(USERDATA_DIR, 'camera_states')


class CameraClient:
    '''Local part of the camera server/client division.

    CameraClient runs on the same PC as GonioImsoft and it connects to
    a CameraServer instance (over network sockets, so using IP addressess).
    It works as a middleman.
    
    No big data is transmitted over the connection, only commands (strings).
    It is the CameraServer's job to store the images, and display them on
    screen (livefeed) if needed.
    
    See also camera_server.py for more information.

    Attributes
    -----------
    host : string
        The CameraServer IP address / hostname
    port : int
        The CameraServer port number
    '''


    def __init__(self, host=None, port=None, running_index=0):
        '''
        Initialization of the CameraClient
        '''
        if host is None:
            host = SERVER_HOSTNAME
        self.host = host

        if port is None:
            port = int(PORT) + int(running_index)
        self.port = port

        self.modified_settings = set()
    

    def sendCommand(self, command_string, retries=MAX_RETRIES, listen=False):
        '''
        Send an arbitrary command to the CameraServer.
        All the methods of the Camera class (see camera_server.py) are supported.

        INPUT ARGUMETNS     DESCRIPTION
        command_string      function;parameters,comma,separated
                            For example "acquireSeries;0,01,0,5,'label'"
        
        listen : bool
            If true, expect the server to return a message.

        This is where a socket connection to the server is formed. After the command_string
        has been send, the socket terminates.
        '''

        tries = 0
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            
            while True:
                try:
                    s.connect((self.host, self.port))
                    break
                except ConnectionRefusedError:
                    tries += 1
                    if tries > retries:
                        raise ConnectionRefusedError('Cannot connect to the camera server')
                    print('Camera server connection refused, retrying...')
                    time.sleep(RETRY_INTERVAL)
                
            s.sendall(command_string.encode())
            
            # Listen response
            if listen:
                response = ''
                while True:
                    data = s.recv(1024)
                    if not data: break
                    response += data.decode()
                if ':' in response:
                    response = response.split(':')
                return response


    def acquireSeries(self, exposure_time, image_interval, N_frames, label, subdir):
        '''
        Acquire a time series of images.
        For more see camera_server.py.

        Notice that it is important to give a new label every time
        or to change data savedir, otherwise images may be written over
        each other (or error raised).
        '''
        function = 'acquireSeries;'
        parameters = "{}:{}:{}:{}:{}:{}".format(exposure_time, image_interval, N_frames, label, subdir)
        message = function+parameters
        
        self.sendCommand(message)


    def acquireSingle(self, save, subdir):
        self.sendCommand('acquireSingle;0.1:{}:{}'.format(str(save), subdir))

    
    def setSavingDirectory(self, saving_directory):
        self.sendCommand('setSavingDirectory;'+saving_directory)


    def saveDescription(self, filename, string):
        self.sendCommand('saveDescription;'+filename+':'+string)

    def set_roi(self, roi):
        self.sendCommand('set_roi;{}:{}:{}:{}'.format(*roi))

    def set_save_stack(self, boolean):
        self.sendCommand('set_save_stack;{}'.format(boolean))

    def isServerRunning(self):
        try:
            self.sendCommand('ping;Client wants to know if server is running', retries=0)
        except ConnectionRefusedError:
            return False
        return True


    def startServer(self):
        '''
        Start a local camera server instance.
        '''
        if self.isServerRunning():
            print('Server already running, not starting again')
            return

        print(f'Starting a local server on port {self.port}')

        subprocess.Popen(
                [
                    sys.executable,
                    '-m', 'gonioimsoft.camera_server',
                    '--port', str(self.port)
                    ],
                stdout=open(os.devnull, 'w'))

        atexit.register(self.close_server)


    def get_cameras(self):
        '''Lists available cameras (their names) on the server.
        '''
        return self.sendCommand('get_cameras', listen=True)

    
    def get_camera(self):
        '''Returns a name describing the current camera device.
        '''
        return self.sendCommand('get_camera', listen=True)


    def set_camera(self, name):
        '''Sets what camera to use on the server.
        '''
        self.sendCommand(f'set_camera;{name}')


    def get_settings(self):
        '''Retrieves available settings of the camera device.
        '''
        return self.sendCommand('get_settings', listen=True)
    
    def get_setting_type(self, setting_name):
        '''Returns the type of the setting.
        One of the following: "string", "float" or "integer"
        '''
        return self.sendCommand(f'get_setting_type;{setting_name}',
                                listen=True)

    def get_setting(self, setting_name):
        '''Returns the current value of the setting as a string.
        '''
        return self.sendCommand(f'get_setting;{setting_name}',
                                listen=True)
    
    def set_setting(self, setting_name, value):
        '''Sets the specified setting to the specified value.
        '''
        self.sendCommand(f'set_setting;{setting_name}:{value}')
        self.modified_settings.add(setting_name)


    def close_server(self):
        '''
        Sends an exit message to the server, to which the server should respond
        by closing itself down.
        '''
        try:
            self.sendCommand('exit;'+'None', retries=0)
        except ConnectionRefusedError:
            pass

        atexit.unregister(self.close_server)

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


def main():
    import argparse

    parser = argparse.ArgumentParser(
            prog='GonioImsoft Camera Client',
            description='Controls the server')

    parser.add_argument('-p', '--port')
    parser.add_argument('-a', '--address')

    args = parser.parse_args()

    client = CameraClient(args.address, args.port)

    print("Welcome to GonioImsoft CameraClient's interactive test program")
    print('Type in commands and press enter.')

    while True:
        cmd = input('#').split(' ')
        
        if not cmd:
            continue

        if cmd[0] == 'help':
            if len(cmd) == 1:
                help(client)
            else:
                method = getattr(client, cmd[1], None)
                if method is None:
                    print(f'No such command as "{cmd[1]}"')
                    continue

                print(method.__doc__)

        else:
            method = getattr(client, cmd[0], None)
            
            if method is None:
                print(f'No such command as "{cmd[0]}"')
                continue

            if len(cmd) == 1:
                message = method()
            else:
                message = method(*cmd[1:])

            print(message)

if __name__ == "__main__":
    main()
