'''
Pupil Imsoft's core module; Classes for static and dynamic imaging
'''

import os
import sys
import time
import datetime

import numpy as np

import nidaqmx

from anglepairs import saveAnglePairs, loadAnglePairs, toDegrees
from arduino_serial import ArduinoReader
from camera_client import CameraClient
from motors import Motor
from imaging_parameters import DEFAULT_DYNAMIC_PARAMETERS, ParameterEditor, getModifiedParameters


class Static:
    '''
    Static imaging core Class.
    '''
    pass


class Dynamic:
    '''
    Dynamic imaging procedures.
    '''

    def __init__(self, dynamic_parameters=DEFAULT_DYNAMIC_PARAMETERS):
        '''
        Sets up ArduinoReader, CameraClient/Server.
        '''

        # Angle pairs reader (rotary encoder values)
        self.reader = ArduinoReader()
        
        # Initiate camera client/server
        self.camera = CameraClient()
        if not self.camera.isServerRunning():
            self.camera.startServer()
        
        # Details about preparation (name, sex, age) are saved in this
        self.preparation = {}

        self.dynamic_parameters = dynamic_parameters
        
        self.previous_angle = None

        # Set up motors followingly
        # 0)    Horizontal + sensor
        # 1)    Vertical + sensor
        # 2)    Microscope focus (no sensor)
        self.motors = []
        for i_motor, i_sensor in zip([0,1,2],[0,1,None]):
            self.motors.append(Motor(self.reader, i_motor, i_sensor))


    def set_led(self, device, value, wait_trigger=False):
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
    
    #
    # IMAGING METHODS
    #

    def take_snap(self, save=False):
        '''
        Takes a snap image.
        
        save        Whether to save the image directly or not.
        '''
        if save:
            self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_imaging'])
            time.sleep(0.3)
            self.camera.acquireSingle(True, os.path.join(self.preparation['name'], 'snaps'))
            self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
            time.sleep(0.2)
        else:
            self.camera.acquireSingle(False, '')
            time.sleep(0.1)


    
    def image_series(self):
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

            
            self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_imaging'])
            time.sleep(0.5)
            
            self.camera.acquireSeries(frame_length, 0, N_frames, label, os.path.join(self.preparation['name'], 'pos{}'.format(imaging_angle)))
            
            self.waitForTrigger()
            time.sleep(self.dynamic_parameters['pre_stim'])
            
            self.set_led(self.dynamic_parameters['flash_channel'], self.dynamic_parameters['flash_on'])
            time.sleep(self.dynamic_parameters['stim'])

            self.set_led(self.dynamic_parameters['flash_channel'], self.dynamic_parameters['flash_off'])
            
            time.sleep(self.dynamic_parameters['post_stim'])
            
            self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_waiting'])
            
            if i+1 == self.dynamic_parameters['repeats']:
                self.isi_slept_time = time.time() + self.dynamic_parameters['isi'][i]
            else:
                time.sleep(self.dynamic_parameters['isi'][i]-0.5)

            #self.angles.extend([imaging_angle]*N_frames)

        self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
        print('DONE!')
    
 

    def initialize(self, name, sex, age):
        '''
        Call this to initialize the experiments.
        '''
        # Preparations, ask droso name
        self.preparation['name'] = name
        self.preparation['sex'] = sex
        self.preparation['age'] = age
        
        print('Preparation name set as {}, sex {}, age {} days.'.format(self.preparation['name'], self.preparation['sex'], self.preparation['age']))


        # Saving description file
        desc_string = "name {}\nsex {}\nage {}".format(self.preparation['name'], self.preparation['sex'], self.preparation['age'])
        desc_string += "\n\n#DYNAMIC PROTOCOL PARAMETERS\n"
        for name, value in self.dynamic_parameters.items():
            desc_string += '{} {}\n'.format(name, value)
        print(desc_string)
        self.camera.saveDescription(self.preparation['name'], desc_string)
        
        self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
        self.set_led(self.dynamic_parameters['flash_channel'], self.dynamic_parameters['flash_off'])




    def tick(self):
        '''
        Updates the current angle. In the future may do other houskeeping functions also.
        
        Call this once while in a loop that the angles have to be updated.
        '''
        
        while True:
            current_angle = [list(self.reader.readAngles())]
            toDegrees(current_angle)

            if self.previous_angle != current_angle:
                print("Horizontal-vertical is {}".format(current_angle[0]))
                self.previous_angle = current_angle
            else:
                break


    def set_zero(self):
        '''
        Define the current angle pair as the zero point
        (Like tar button on scales)
        '''
        self.reader.currentAsZero()



    def finalize(self):
        self.set_led(self.dynamic_parameters['ir_channel'], 0)
        self.set_led(self.dynamic_parameters['flash_channel'], 0)
    

    #
    # CONTROLLING LEDS, MOTORS ETC
    #
    
    def move_motor(*args, **kwargs):
        self.reader.move_motor(*args, **kwargs)


