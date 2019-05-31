'''
Camera client software.

Meant to be running using Python 3.
'''

import socket
import time
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
        
    def sendCommand(self, command_string):
        '''
        Send an arbitrary command to the CameraServer.
        All the methods of the Camera class (see camera_server.py) are supported.

        INPUT ARGUMETNS     DESCRIPTION
        command_string      function;parameters,comma,separated
                            For example "acquireSeries;0,01,0,5,'label'"

        This is where a socket connection to the server is formed. After the command_string
        has been send, the socket terminates.
        '''
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, self.port))
            s.sendall(command_string.encode())

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
        
        self.sendCommand(message)

    def acquireSingle(self):
        self.sendCommand('acquireSingle;none')

    def setSavingDirectory(self, saving_directory):
        self.sendCommand('setSavingDirectory;'+saving_directory)

    def saveDescription(self, filename, string):
        self.sendCommand('saveDescription;'+filename+':'+string)

def test():
    cam = CameraClient()
    cam.acquireSeries(0.01, 0, 5, 'test')

if __name__ == "__main__":
    test()
