
import math

class Motor:
    '''
    Moving motors with limits.
    '''

    def __init__(self, ArduinoReader, i_motor, i_sensor):
        '''
        ArduinoReader
        i_motor             Index number of the motor
        #i_sensor            None or index number of the sensor
        '''
        self.reader = ArduinoReader
        self.i_motor = i_motor
        self.i_sensor = i_sensor
        
        # If no sensor is connected with the motor (i_sensor == None),
        # at least we keep track how many times have we moved.
        self.position = 0
        
        self.limits = [-math.inf, math.inf]

    
    def get_position(self):
        '''
        Returns the current position of the motor
        '''
        return self.position


    def move_raw(self, direction, time=1):
        
        curpos = get_position()

        # Only move so that we don't go over limits
        if ((self.limits[0] <= curpos and direction >= 0) or
                (curpos <= self.limits[1] and direction < 0) or
                (self.limits[0] < curpos < self.limits[1])):
            
            self.reader.move_motor(self.i_motor, direction, time=time)
            self.position += time*direction

    
    def move_to(self, motor_position):
        '''
        Move motor to specific position.
        '''
        time = position - motor_position
        if time >= 0:
            direction = 1
        else:
            direction = -1
            time = -time

        self.move_raw(direction, time=time)


    def set_upper_limit(self):
        '''
        Sets current position as the upper limit
        '''
        self.limits[0] = self.position


    def set_lower_limit(self):
        '''
        Sets current position as the lower limit
        '''
        self.limits[1] = self.position

    def get_limits(self):
        return self.limits
