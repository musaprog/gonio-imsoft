'''
Reading rotation encoder signals from an Arduino Board.
'''

import serial

DEFAULT_PORT_NAME = 'COM4'

class ArduinoReader:
    '''
    Class for reading  angle pairs (states of the rotation encoders) from Arduino.
    '''

    def __init__(self, port=DEFAULT_PORT_NAME):
        '''
        port        On Windows, "COM4" or similar. May change if other serial devices
                    are addded or removed?
        '''
        
        self.serial = serial.Serial(port=port, baudrate=9600, timeout=0.1)

        self.latest_angle = (0,0)

    def readAngles(self):
        '''
        Read the oldest unread angles that Arduino has sent to the serial.

        Returns angle pair, (horizontal_angle, vertical_angle).
        '''
        read_string = self.serial.readline().decode("utf-8")
        if read_string:
            angles = read_string.split(',')
            self.latest_angle = tuple(map(int, angles))

        return self.latest_angle

    def getLatest(self):
        '''
        Returns the latest angle that has been read from Arduino.
        (Arduino sends an angle only when it has changed)
        '''
        return self.latest_angle
    
    def closeConnection(self):
        '''
        If it is required to manually close the serial connection.
        '''
        serial.close()
