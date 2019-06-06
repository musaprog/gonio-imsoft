'''
A tool for dynamic and static imaging of Drosophila pseudopupils.

PRINCIPLE OF FUNCTION
A triggering pulse is sent every time when a new angle value pair is read
from Arduino attached 2 rotary encoders. The trigger then makes a camera
to take an image. The angle pairs are saved in a comma separated text file.

Currently controlling the camera and saving images is done in Micro-Manager's
GUI. Using the saved angle pairs one assing each image with an angle pair.


TECHNICAL DETAILS
Moving too fast may cause Arduino drop some angles. Moving too fast may
cause taking images using past angle pairs.

FEATURES TODO
- Coarsness to angles; Taking image every n:th degrees for example
- Mode to set relative zero position
- Use Micro-Manager Python bindings to manage image shooting
    * requires building MM from source
- Linux/OSX equivalent of nonblockin input read
- Graphical user interface? 

BUGS TOFIX
- angle plotter: Closing the plot window causes problems


'''

import os
import sys
import time
import datetime
import csv
import threading
import multiprocessing
import subprocess

import numpy as np
import matplotlib.pyplot as plt         # Plotting visited angles
#import cv2
#import MMCorePy
try:
    import nidaqmx                      # nidaqmx for sending trigger
    from nidaqmx.types import CtrTime
    HAS_NIDAQMX = True
except:
    HAS_NIDAQMX = False

import msvcrt                           # Non-blocking input reading on Windows

from arduino_serial import ArduinoReader
from camera_client import CameraClient
from dynamic_parameters import DEFAULT_DYNAMIC_PARAMETERS, ParameterEditor, getModifiedParameters

DEFAULT_TRIGGER_CHANNEL = "Dev1/ao0"
DEFAULT_IMAGING_DELAY = 0.03
DEFAULT_SAVEDIR = 'data'
STRESS_TEST = False


# DEPRECATED
# Dynamic imaging parameters
#DEFAULT_FLASH_CHANNEL = "Dev1/ao0"
#DEFAULT_IR_CHANNEL = ["Dev2/ao0", "Dev2/ao1"]
#DEFAULT_FLASH_BRIGHTNESS = [10]
#DEFAULT_IR_BRIGHTNESS = 5


# PARAMETERS EXPLAINED
# ISI           Inter stimulus interval                         seconds
# repeats       How many times the protocol is repeated
# stim          Stimulus (step pulse) length                    seconds
# post_stim     How long to image after the pulse               seconds
# frame_length  Exposure time / inter-frame interval            seconds
# ir_imaging    IR brightness during image acqusition           0-10 V to NI board
# ir_waiting    IR brightness when waiting ISI                  0-10 V to NI board
# ir_livefeed   IR brightness while updating the live image     0-10 V to NI board
# flash_on      Flash brightness during stim                    0-10 V to NI board
# flash_off     Flash brightness during image acqustition       0-10 V to NI board
# ir_channel    NI channel for IR                               for example ["Dev2/ao0", "Dev2/ao1"] or "Dev1/ao0"
# flash_channel NI channel for Flash                            for example ["Dev2/ao0", "Dev2/ao1"] or "Dev1/ao0"





# Paremeters for studying movements when there's background light
#BACKGROUND_ON_DYNAMIC_PARAMETERS['flash_off'] = self.dynamic_parameters['flash_on']/10


# Parameters for the longterm study
# ISI 10*60 s = 10 every 10 mins
# repeats 288 with that ISI means 24h
#self.dynamic_parameters = {'isi': 1*60.0, 'repeats': 5*288, 'pre_stim': 0.000,
#                              'stim': 0.200, 'post_stim': 0.00, 'frame_length' : 0.010}

# Parameters for ISI study
#self.dynamic_parameters = {'repeats': 20, 'pre_stim': 0.000,
#                              'stim': 0.200, 'post_stim': 0.00, 'frame_length' : 0.010}
#self.dynamic_parameters['isi'] = np.flip(np.logspace(0, 2, self.dynamic_parameters['repeats']))
#self.dynamic_parameters['isi'] = self.dynamic_parameters['isi'].tolist()

#sys.setswitchinterval(0.0005)
#print(sys.getswitchinterval())


def saveAnglePairs(fn, angles):
    '''
    Saving angle pairs to a file.
    '''
    with open(fn, 'w') as fp:
        writer = csv.writer(fp)
        for angle in angles:
            writer.writerow(angle)

def loadAnglePairs(fn):
    '''
    Loading angle pairs from a file.
    '''
    angles = []
    with open(fn, 'r') as fp:
        reader = csv.reader(fp)
        for row in reader:
            if row:
                angles.append([int(a) for a in row])
    return angles

def toDegrees(angles):
    '''
    Transform 'angles' (that here are just the steps of rotary encoder)
    to actual degree angle values.
    '''
    for i in range(len(angles)):
        angles[i][0] *= (360/1024)
        angles[i][1] *= (360/1024)



class Triggerer:
    '''
    Triggering a camera to take images based on angle value pairs read from Arduino.

    Every time when a new angle pair is read, its appended to a list of angle pairs
    and triggering pulse is sent to the camera.
    '''

    def __init__(self, trigger_channel=DEFAULT_TRIGGER_CHANNEL, imaging_delay=DEFAULT_IMAGING_DELAY,
            savedir=DEFAULT_SAVEDIR):
        '''
        EXAMPLES
        trigger_channel     'Dev1/ao0'
        imaging_delay       0.1
        '''
        self.trigger_channel = trigger_channel
        self.imaging_delay = imaging_delay
        self.savedir = DEFAULT_SAVEDIR

        self.timestamp = datetime.datetime.now().strftime('%y-%m-%d_%H%M') 

        self.reader = ArduinoReader()
        
        self.lastshot_time = time.time()
        self.angles = []

        self.running = False
        self.triggering = True
        self.image_now = False

        self.dynamic_parameters = DEFAULT_DYNAMIC_PARAMETERS
        
        self.single_trigger = 5*np.ones(150)
        self.single_trigger[-1] = 0

        self.save_interval = 5
        self.last_save_time = 0

        self.camera = CameraClient()
        if not self.camera.isServerRunning():
            self.camera.startServer()
            
        # Details about preparation (name, sex) can be saved in this
        self.preparation = {}


    def sendTrigger(self):
        '''
        Just send the trigger to the camera.
        '''
        if HAS_NIDAQMX:
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.trigger_channel)
                task.write(self.single_trigger, auto_start=True)

                #task.co_channels.add_co_pulse_chan_time("Dev2/ctr0")
                #sample = CtrTime(high_time=0.001, low_time=0.001)
                #task.write(sample)
                

        else:
            print('Sent virtual trigger')
        print('Length of angles {}'.format(len(self.angles)))
        self.lastshot_time = time.time()
        #self.cmanager.takeImage(self.angles[-1])
        
        

    def flashLED(self, flash_vector, fs):
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan('Dev1/ao0')
            task.timing.cfg_samp_clk_timing(fs)
            
            task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI0", trigger_edge=nidaqmx.constants.Edge.FALLING)

            task.write(flash_vector)
            
            #task.wait_until_done()
            #print('task finished')
            

    def setLED(self, device, value, wait_trigger=False):
        '''
        Set an output channel to a specific voltage value.

        INPUT ARGUMENTS     DESCRIPTION
        device              A string (single device) or a list of strings (many devices at once)
        '''
        with nidaqmx.Task() as task:
            
            if type(device) == type('string'):
                # If there's only a single device
                task.ao_channels.add_ao_voltage_chan(device)
            else:
                # If device is actually a list of devices
                for dev in device:
                    task.ao_channels.add_ao_voltage_chan(dev)
                value = [value for i in range(len(device))]
            
            if wait_trigger:
                task.timing.cfg_samp_clk_timing(10000)
                task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI0", trigger_edge=nidaqmx.constants.Edge.FALLING)
            task.write(value)



    def sendTrigger(self):
        with nidaqmx.Task() as trigger_task:
            trigger_task.ao_channels.add_ao_voltage_chan(self.trigger_channel)
            trigger_task.write(self.single_trigger, auto_start=True)


    def waitForTrigger(self):
        '''
        Doesn't return until trigger signal is received.
        '''
        with nidaqmx.Task() as task:
            device = nidaqmx.system.device.Device('Dev1')
            
            task.ai_channels.add_ai_voltage_chan('Dev1/ai0' )
            
            task.timing.cfg_samp_clk_timing(10000)
            
            task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI0", trigger_edge=nidaqmx.constants.Edge.FALLING)
            task.read(number_of_samples_per_channel=1)
            #task.wait_until_done()
        
        
    def imageSeries(self):
        '''
        For dynamic imaging of pseudopupil movements.

        How this works?
        CameraClient (self.camera) send message to CameraServer to start image acquisition. Starting
        image acquistion takes some time, so to synchronize, we wait a trigger signal from the camera
        before turning the LED on. What is done is essentially half software half hardware triggering.
        Not ideal but seems to work.
        '''
        
        print('Starting dynamic imaging')

        self.angles.append(self.reader.getLatest())

        # To speed things up, for the last repeat we didn't wait the ISI. Now here, if the user
        # is very fast, we wait the ISI time.
        try:
            if time.time() < self.isi_slept_time: 
                print('Waiting ISI to be fullfilled from the last run...')
                time.sleep(self.isi_slept_time - time.time())
                print('READY')
        except AttributeError:
            pass

        # If isi is not a list of isi times but a single number,
        # make a list where the single number is repeated repeats times
        if type(self.dynamic_parameters['isi']) != type([]):
            self.dynamic_parameters['isi'] = [self.dynamic_parameters['isi']] * self.dynamic_parameters['repeats']
                    
        for i in range(self.dynamic_parameters['repeats']):

            imaging_angle = self.reader.getLatest()      
            frame_length = self.dynamic_parameters['frame_length']
            N_frames = int((self.dynamic_parameters['pre_stim']+self.dynamic_parameters['stim']+self.dynamic_parameters['post_stim'])/frame_length)

            label = 'im_pos{}_rep{}'.format(imaging_angle, i)
            print('  Imaging {}'.format(label))

            
            self.setLED(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_imaging'])
            time.sleep(0.5)
            
            self.camera.acquireSeries(frame_length, 0, N_frames, label, os.path.join(self.preparation['name'], 'pos{}'.format(imaging_angle)))
            
            self.waitForTrigger()
            time.sleep(self.dynamic_parameters['pre_stim'])
            
            self.setLED(self.dynamic_parameters['flash_channel'], self.dynamic_parameters['flash_on'])
            time.sleep(self.dynamic_parameters['stim'])

            self.setLED(self.dynamic_parameters['flash_channel'], self.dynamic_parameters['flash_off'])
            
            time.sleep(self.dynamic_parameters['post_stim'])
            
            self.setLED(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_waiting'])
            
            if i+1 == self.dynamic_parameters['repeats']:
                self.isi_slept_time = time.time() + self.dynamic_parameters['isi'][i]
            else:
                time.sleep(self.dynamic_parameters['isi'][i]-0.5)

            #self.angles.extend([imaging_angle]*N_frames)

        self.setLED(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
        print('DONE!')
        

    def angleIsNew(self):
        '''
        Read the current angle and check it's novel.
        If so, trigger.
        '''
        if not STRESS_TEST:
            current_angle = self.reader.readAngles()
        else:
            current_angle = "0,0"
            
        if time.time() > self.lastshot_time + self.imaging_delay:
            if not current_angle in self.angles or STRESS_TEST:
                self.angles.append(current_angle)
                
                return True
        
        return False
    
    def loop(self):
        '''
        Loop the triggerer logic until self.stop() is called.
        '''
        self.running = True

        while self.running:
            if self.angleIsNew():
                if self.triggering:
                    self.sendTrigger()
                    self.save()

    def loopDynamic(self):
        '''
        Dynamic imaging of pseudopupil movements
        '''

        # Preparations, ask droso name
        if self.preparation == {}:
            print('Preparation name (for example DrosoM42)')
            self.preparation['name'] = input('>>: ')
            self.preparation['sex'] = input('Sex >>: ')
            self.preparation['age'] = input('Age >>: ')
        print('Preparation name set as {}, sex {}, age {} days.'.format(self.preparation['name'], self.preparation['sex'], self.preparation['age']))

        # Saving description file
        desc_string = "name {}\nsex {}\nage {}".format(self.preparation['name'], self.preparation['sex'], self.preparation['age'])
        desc_string += "\n\n#DYNAMIC PROTOCOL PARAMETERS\n"
        for name, value in self.dynamic_parameters.items():
            desc_string += '{} {}\n'.format(name, value)
        print(desc_string)
        self.camera.saveDescription(self.preparation['name'], desc_string)
        
        self.setLED(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
        self.setLED(self.dynamic_parameters['flash_channel'], self.dynamic_parameters['flash_off'])
        previous_angle = None
        self.running = True
        while self.running:
            while True:
                current_angle = [list(self.reader.readAngles())]
                toDegrees(current_angle)
                if previous_angle != current_angle:
                    print("Horizontal-vertical is {}".format(current_angle))
                    previous_angle = current_angle
                else:
                    break
            
            if msvcrt.kbhit():
                a = ord(msvcrt.getwch())
                if a == 32:
                    # Space pressed
                    self.image_now = True
                elif a == 13:
                    # Enter pressed
                    self.running = False
                    break 
                elif a == ord('s'):
                    self.setLED(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_imaging'])
                    time.sleep(0.3)
                    self.camera.acquireSingle(True, os.path.join(self.preparation['name'], 'snaps'))
                    self.setLED(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
                    time.sleep(0.2)
                elif a == ord('0'):
                    if input('Set new zero-point (y/n)? >> ').lower() in ['y', 'yes']:
                        self.reader.currentAsZero()


            if self.image_now and self.triggering:
                self.imageSeries()
                self.image_now = False
            else:
                self.camera.acquireSingle(False, '')
                time.sleep(0.1)

        self.setLED(self.dynamic_parameters['ir_channel'], 0)

    
    def run(self, mode):
        '''
        Run self.loop but from a thread.
        '''
        if not self.running:
            
            if mode == 'static':
                target = self.loop
                t = threading.Thread(target=target)
                t.start()
                
            elif mode == 'dynamic':
                
                self.dynamic_parameters = getModifiedParameters()
                self.loopDynamic()

    def stop(self):
        self.save(force=True)
        self.running = False

    def toggleTriggering(self):
        if self.triggering:
            self.triggering = False
        else:
            self.triggering = True

    def focus(self):
        state_before = self.running
        self.running = False

        for i in range(10):
            self.angles.append('focusing')
            self.sendTrigger()
            time.sleep(0.4)


    def save(self, force=False):
        if force or time.time() > self.last_save_time + self.save_interval:
            print('Saved')
            fn = os.path.join(self.savedir, 'anglepairs{}.txt'.format(self.timestamp))
            saveAnglePairs('anglepairs.txt', self.angles)
            self.last_save_time = time.time()


class AnglePlotter:
    '''
    Creates a plot that shows the angles recorded.

    TECHNICAL DETAILS
    Updating the recorded angle values (reading the values from Triggerer)
    happens in a thread in the main process, while the actual plotting
    using matplotlib happens in a separate, child process.

    This is due to matplotlib's thread-unsafety but fortunately distributes
    CPU load on 2 cores (performance gains!).
    '''
    
    def __init__(self, Triggerer):
        self.triggerer = Triggerer
        self.running = False

        self.X = []
        self.Y = []
        self.plotted_length = 0

        self.lock = threading.Lock()
    
    def loop(self):

        self.queue.put((self.X, self.Y))
        
        self.running = True
        while self.running:
            N = len(self.triggerer.angles)
            if N > self.plotted_length:
                angles = self.triggerer.angles[self.plotted_length:N]
                self.plotted_length += N-self.plotted_length
                
                angles = [[int(angle[0]), int(angle[1])] for angle in angles if angle!='focusing']
                self.plotted_length -= (self.plotted_length-N) - len(angles)
                toDegrees(angles)
                
                x= ( [z[0] for z in angles] )
                y= ( [z[1] for z in angles] )
                self.X.extend(x)
                self.Y.extend(y)
                
                self.queue.put((x, y))
                
            time.sleep(0.2)
        
        self.queue.put(('exit',''))

    @staticmethod
    def plotter(q):
        '''
        Doing the actual plotting using matplotlib.
        Is to be spanned to a new process because
        matplotlib is not thread safe, and inter-process
        communication is done using Queue.
        '''
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ln, = ax.plot([],[], linestyle='', marker='x')
        fig.canvas.draw()
        plt.show(block=False)

        while True:
            try:
                X, Y = q.get(timeout=0.01)
            except:
                if plt.get_fignums():
                    plt.pause(0.05)
                continue
            if X == 'exit':
                break
            
            ln.set_xdata(np.append(ln.get_xdata(), X))
            ln.set_ydata(np.append(ln.get_ydata(), Y))
            ax.relim()
            ax.autoscale_view(True,True,True)
            fig.canvas.draw()
            
        plt.close()
        
    def run(self):
        if not self.running:
            self.queue = multiprocessing.Queue()
            p = multiprocessing.Process(target=self.plotter, args=(self.queue,))
            p.start()
            t = threading.Thread(target=self.loop)
            t.start()

    def toggleRun(self):
        '''
        Calling this method 
        '''
        if not self.running:
            self.run()
        elif self.running:
            print('Set plotter off')
            self.running = False




class ImagingTerminalUI:
    '''
    Simplistic imaging process controls using a terminal based user interface.
    
    Uses Triggerer class.
    '''
    def __init__(self):
        
        self.triggerer = Triggerer()
        self.plotter = AnglePlotter(self.triggerer)

        self.menu = [['Static imaging (new orientation -> trigger)', lambda: self.triggerer.run('static')],
                ['Dynamic imaging (space -> trigger time series)', lambda: self.triggerer.run('dynamic')],
                ['Pause/Stop', self.triggerer.stop],
                ['Triggering', self.triggerer.toggleTriggering], ['Focus (10 images per 4 s)', self.triggerer.focus],
                ['Show angles', self.plotter.toggleRun],
                ['Print status', self.printStatus]]
        self.menu.append( ['Exit', self.close] )
        self.close = False
        self.__clearScreen()

    def __nonBlockingInput(self):
        '''
        Ask user input without blocking the execution the whole program.

        Space is a special character, it is reserved for manual triggering/execution.
        '''
        string = ''
        done = False
        while not done:
            if msvcrt.kbhit():
                a = ord(msvcrt.getwch())
                if a == 13:
                    done = True
                elif a == 32:
                    self.triggerer.image_now = True
                else:
                    string += str(chr(a))
                print(string)
            time.sleep(0.2)
        return string
    
    def __clearScreen(self):
        if os.name in ('linux', 'osx', 'posix'):
            os.system('clear')
        elif os.name in ('nt', 'dos'):
            os.system('cls')

    def __makeMenu(self, alist):
        print()
        print('imsoft.py - main menu')
        print()
        for i,item in enumerate(alist):
            print('{}) {}'.format(i, item[0]))
        print()
        #sel = input('>> ')
        sel = self.__nonBlockingInput()
        self.__clearScreen()
        try:
            func = alist[int(sel)][1]
        except:
            func = lambda: print('Invalid input')
        return func
    
    def printStatus(self):
        strings = [['Triggerer triggers', self.triggerer.triggering],
                ['Triggerer running', self.triggerer.running],
                ['Angle plotter running', self.plotter.running]]

        print('STATUS')
        for string in strings:
            print('{:30} {}'.format(*string))

    def run(self):
        '''
        Run the UI until user exists.
        '''
        while not self.close:
            func = self.__makeMenu(self.menu)
            func()

    def close(self):
        self.close = True


def main():

    ui = ImagingTerminalUI()
    ui.run()

def triggerTest():

    fs = 10000
    pre_stim = 0
    stim = 5
    post_stim = 0.1
    flash_vector = np.concatenate((np.zeros(int(pre_stim*fs)),10*np.ones(int(stim*fs)),np.zeros(int(post_stim*fs)))).tolist()
    print(flash_vector)
    t = Triggerer()
    t.flashLED(flash_vector, fs)
    time.sleep(60)

if __name__ == "__main__":
    main()
