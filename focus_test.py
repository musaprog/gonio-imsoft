'''
Just a brief test to see the focusing works/
'''

import time

from arduino_serial import ArduinoReader

r = ArduinoReader()

r.focus('closer', 4)
time.sleep(5)

r.focus('furhter', 4)




