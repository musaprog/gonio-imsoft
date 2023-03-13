'''Client code for the camera server/client division.
'''

import socket
import time
import os
import subprocess
import platform
import sys

from .directories import CODE_ROOTDIR
from .camera_communication import SERVER_HOSTNAME, PORT

MAX_RETRIES = 100
RETRY_INTERVAL = 1


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

    port_running_index = 0

    def __init__(self, host=None, port=None):
        '''
        Initialization of the CameraClient
        '''
        if host is None:
            self.host = SERVER_HOSTNAME
        if port is None:
            self.port = PORT + self.port_running_index
            self.port_running_index += 1

    

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
            
                
                return response


    def acquireSeries(self, exposure_time, image_interval, N_frames, label, subdir, trigger_direction):
        '''
        Acquire a time series of images.
        For more see camera_server.py.

        Notice that it is important to give a new label every time
        or to change data savedir, otherwise images may be written over
        each other (or error raised).
        '''
        function = 'acquireSeries;'
        parameters = "{}:{}:{}:{}:{}:{}".format(exposure_time, image_interval, N_frames, label, subdir, trigger_direction)
        message = function+parameters
        
        self.sendCommand(message)


    def acquireSingle(self, save, subdir):
        self.sendCommand('acquireSingle;0.1;{}:{}'.format(str(save), subdir))

    
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

        subprocess.Popen(
                [
                    sys.executable,
                    os.path.join(CODE_ROOTDIR, 'camera_server.py'),
                    '--port', str(self.port)
                    ],
                stdout=open(os.devnull, 'w'))


    def get_cameras(self):
        '''Lists available cameras (their names) on the server.
        '''
        return self.sendCommand(f'get_cameras', listen=True)

    def set_camera(self, name):
        '''Sets what camera to use on the server.
        '''
        self.sendCommand(f'set_camera;{name}')

    def close_server(self):
        '''
        Sends an exit message to the server, to which the server should respond
        by closing itself down.
        '''
        try:
            self.sendCommand('exit;'+'None', retries=0)
        except ConnectionRefusedError:
            pass
        


def main():

    client = CameraClient()

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
