'''
Camera client software.

Meant to be running using Python 3.
'''

import socket
import time
import os
import subprocess

MAX_RETRIES = 100
RETRY_INTERVAL = 1

class CameraClient:
    '''
    Connecting to the CameraServer and sending imaging commands.

    No data is transmitted over the socket connection, only commands (strings).
    It's CameraServer's job to store the images.
    '''
    def __init__(self):
        '''
        Initialization of the Camera Client 
        '''
        self.host = '127.0.0.1'
        self.port = 50071
        
    def sendCommand(self, command_string, retries=MAX_RETRIES):
        '''
        Send an arbitrary command to the CameraServer.
        All the methods of the Camera class (see camera_server.py) are supported.

        INPUT ARGUMETNS     DESCRIPTION
        command_string      function;parameters,comma,separated
                            For example "acquireSeries;0,01,0,5,'label'"

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
        self.sendCommand('acquireSingle;{}:{}'.format(str(save), subdir))

    def setSavingDirectory(self, saving_directory):
        self.sendCommand('setSavingDirectory;'+saving_directory)

    def saveDescription(self, filename, string):
        self.sendCommand('saveDescription;'+filename+':'+string)

    def isServerRunning(self):
        try:
            self.sendCommand('ping;Client wants to know if server is running', retries=0)
        except ConnectionRefusedError:
            return False
        return True

    def startServer(self):
        subprocess.Popen(['C:\Python27\python.exe', 'camera_server.py'], stdout=open(os.devnull, 'w'))

    def close_server(self):
        try:
            self.sendCommand('exit;'+'None', retries=0)
        except ConnectionRefusedError:
            pass
        

def test():
    cam = CameraClient()
    cam.acquireSeries(0.01, 0, 5, 'test')

if __name__ == "__main__":
    test()
