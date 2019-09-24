'''
Just a brief test to see the focusing works/
'''

import time

from arduino_serial import ArduinoReader

r = ArduinoReader()

time.sleep(2)

r.focus('further', 4)

r.focus('closer', 4)



