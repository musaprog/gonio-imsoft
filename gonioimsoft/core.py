'''GonioImsoft main components.
'''

import os
import sys
import time
import datetime
import copy

import numpy as np

try:
    import nidaqmx
except ModuleNotFoundError:
    nidaqmx = None

from gonioimsoft.anglepairs import saveAnglePairs, loadAnglePairs, toDegrees
from gonioimsoft.arduino_serial import ArduinoReader
from gonioimsoft.camera_client import CameraClient
from gonioimsoft.vio_client import VIOClient
from gonioimsoft.motors import Motor
from gonioimsoft.imaging_parameters import (
        DEFAULT_DYNAMIC_PARAMETERS,
        load_parameters,
        getModifiedParameters)
from gonioimsoft.stimulus import StimulusBuilder
import gonioimsoft.macro as macro

ENABLE_MOTORS = False

class GonioImsoftCore:
    '''Main interface to control GonioImsoft recordings.

    Attributes
    ----------
    reader : obj
        Reading rotary encoder values from the Arduino Board.
    cameras : list
        Camera client objects that each talk to a specific server
        over IPv4 sockets. The server's can be local (on the same
        machine) or remote.
    vios : list
        Analog voltage input/ouput clients. Similar to the cameras,
        they talk to a vio server.
    '''


    def __init__(self, dynamic_parameters=DEFAULT_DYNAMIC_PARAMETERS):
        '''
        Sets up ArduinoReader, CameraClient/Server.
        '''

        # Angle pairs reader (rotary encoder values)
        self.reader = ArduinoReader()
        
        self.cameras = []
        self.vios = []

        # Exposure times for snaps and livefeed
        self.snap_exposure_time = 0.01
        self.live_exposure_time = 0.01
        
        # Details about preparation (name, sex, age) are saved in this
        self.preparation = {'name': 'test', 'sex': '', 'age': ''}

        self.dynamic_parameters = dynamic_parameters

        self.previous_angle = None

        # Suffix to be appended in the subfolders, see set_subfolder_suffix method
        self.suffix = ''

        # Set up motors followingly
        # 0)    Horizontal + sensor
        # 1)    Vertical + sensor
        # 2)    Microscope focus (no sensor)
        self.motors = []
        if ENABLE_MOTORS:
            for i_motor, i_sensor in zip([0,1,2],[0,1,None]):
                self.motors.append(Motor(self.reader, i_motor, i_sensor))
        

        # Macro imaging: Automatically move motors and take images
        # self macro is a list of anglepairs where to move the horizontal/vertical,
        # take image "commands" (string 'image') and other functions.
        # For more details see the tick method of this class.
        self.macro = None
        self.i_macro = 0
        self.waittime = 0

        self.trigger_rotation = False

        self.trigger_signal = np.array([3,3,3,0])
        self.triggered_anglepairs = None

        self.data_savedir = None

        self.local_camera_servers_running_index = 0
        self.local_vio_servers_running_index = 0

        self.pause_livefeed = False
        self.vio_livefeed = False
        self.vio_livefeed_dur = 0.1

        self._last_vio = time.time()

    
    def _add_client(self, name, host, port):
        '''Adds a camera client to the given host and port.

        If host is None uses the localhost and starts a local
        server if no local server running at that port

        Arguments
        ---------
        name : string
            The name of the client. "camera" or "vio"
        '''
        if name == 'camera':
            Client = CameraClient
            register = self.cameras
            self.local_camera_servers_running_index += 1
            index = self.local_camera_servers_running_index
        elif name == 'vio':
            Client = VIOClient
            register = self.vios
            self.local_vio_servers_running_index += 1
            index = self.local_vio_servers_running_index
        else:
            raise ValueError

        client = Client(host, port, running_index=index-1)

        if host is None and not client.is_server_running():
            client.start_server()
        register.append(client)
        
        return client


    def add_camera_client(self, host, port):
        return self._add_client('camera', host, port)
        
    def add_vio_client(self, host, port):
        return self._add_client('vio', host, port)


    def _remove_client(self, name, i_client):
        if name == 'camera':
            register = self.cameras
        elif name == 'vio':
            reigster = self.vios
        # Popping is enough and the client should be garbage collected
        # by Python (the sockets are not kept alive so nothing is
        # left open etc. by the client)
        if isinstance(i_client, int):
            client = register.pop(i_client)
        elif isinstance(i_client, (CameraClient, VIOClient)):
            client = i_client
            register.remove(client)
        else:
            raise ValueError(f'Cannot remove {i_client} from clients')

        # If the client started a local server, close the server
        if client.local_server is not None:
            client.close_server()

        return client


    def remove_camera_client(self, client):
        '''Removes a camera client and closes its server if local server

        Arguments
        ---------
        client : object or int
            Index of the client in self.cameras or the CameraClient
            object to be removed
        '''
        return self._remove_client('camera', client)
   

    def remove_vio_client(self, client):
        '''Removes the vio client and closes its server if local server

        Arguments
        ---------
        client: object or int
            Index of the client in self.vios or the VIOClient
            object to be removed
        '''
        return self._remove_client('vio', client)



    def analog_output(self, channels, stimuli, fs, wait_trigger, camera=True):
        '''

        channels    List of channel names
        stimuli     List of 1D numpy arrays
        fs          Sampling frequency of the stimuli
        camera : bool
            If True, send the camera server a "ready" command
        '''
        
        if nidaqmx is None:
            print('    pretending analog_output on channels {}'.format(channels))
            return None

        # Pop off digital channels
        index_digi = []
        for i_channel, channel in enumerate(channels):
            if isinstance(channel, str) and 'port' in channel:
                index_digi.append(i_channel)

        if index_digi:
            dtask = nidaqmx.Task()
            dout = []
            for index in index_digi:
                channel = channels.pop(index)
                dout.append(stimuli.pop(index))
                # Dev1/port0/line8
                dtask.do_channels.add_do_chan(channel)
                
            dtask.timing.cfg_samp_clk_timing(float(fs), samps_per_chan=len(stimuli[0]))
            #dtask.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI0", trigger_edge=nidaqmx.constants.Edge.RISING)
            if len(dout) > 1:
                stimulus = dout[0]
                for s in dout[1:]:
                    stimulus = np.vstack((stimulus, s))
            else:
                stimulus = dout[0]
            dout = np.digitize(stimulus, [1]).astype(bool)
            dtask.write(dout)
        
        with nidaqmx.Task() as task:
            for i_channel, channel in enumerate(channels):
                if type(channel) == type('string'):
                    task.ao_channels.add_ao_voltage_chan(channel)
                else:
                    for subchan in channel:
                        task.ao_channels.add_ao_voltage_chan(subchan)
                        stimuli.insert(i_channel, stimuli[i_channel])
                    stimuli.pop(i_channel)

            task.timing.cfg_samp_clk_timing(float(fs), samps_per_chan=len(stimuli[0]))
            
            if len(stimuli) > 1:
                stimulus = stimuli[0]
                for s in stimuli[1:]:
                    stimulus = np.vstack((stimulus, s))
            else:
                stimulus = stimuli[0]

            task.write(stimulus)
            

            if wait_trigger:
                task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI0", trigger_edge=nidaqmx.constants.Edge.RISING)

            
            task.start()
            if index_digi:
                dtask.start()

            #if camera:
            #    for camera in self.cameras:
            #        camera.send_command('ready')
                
            task.wait_until_done(timeout=(len(stimuli[0])/fs)*1.5+20)

        if index_digi:
            dtask.wait_until_done(timeout=(len(stimuli[0])/fs)*1.5+20)
            dtask.close()

    def send_trigger(self):
        '''
        Sending trigger.
        '''

        chans = self.dynamic_parameters.get('trigger_out_channel', None)
        if isinstance(chans, str):
            chans = [chans]
        for chan in chans:
            if nidaqmx is None:
                print(f'    pretending to send trigger on chan {chan}')
                return None

            if chan:
                with nidaqmx.Task() as task:
                    task.ao_channels.add_ao_voltage_chan(chan)
                    task.timing.cfg_samp_clk_timing(1000., samps_per_chan=4)
                    task.write(self.trigger_signal)
                    task.start()
                    task.wait_until_done(timeout=1.)
            else:
                print('trigger_out_channel not specified, no trigger out')

            self.triggered_anglepairs.append(self.reader.get_latest())
            


    def set_led(self, device, value, wait_trigger=False, exclude=None):
        '''
        Set an output channel to a specific voltage value.

        INPUT ARGUMENTS     DESCRIPTION
        device              A string (single device) or a list of strings (many devices at once)
        '''
        if nidaqmx is None:
            print(f'    pretending to set {device} on value {value}')
            return None

        if isinstance(device, str) and device.lower() in ['none']:
            return

        excluded = 0

        with nidaqmx.Task() as task:
            
            if type(device) == type('string'):
                # If there's only a single device
                if '/port' in device:
                    task.do_channels.add_do_chan(device)
                    value = bool(value)
                else:
                    task.ao_channels.add_ao_voltage_chan(device)
            else:
                # If device is actually a list of devices
                for dev in device:
                    if exclude and dev in exclude:
                        excluded += 1
                        continue
                    task.ao_channels.add_ao_voltage_chan(dev)
                value = [value for i in range(len(device)-excluded)]
            
            if wait_trigger:
                task.timing.cfg_samp_clk_timing(10000)
                task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI0", trigger_edge=nidaqmx.constants.Edge.FALLING)
            task.write(value)
            


    def wait_for_trigger(self):
        '''
        Doesn't return until trigger signal is received.
        '''
        if nidaqmx is None:
            print(f'    waiting for trigger')
            return None

        with nidaqmx.Task() as task:
            device = nidaqmx.system.device.Device('Dev1')
            
            task.ai_channels.add_ai_voltage_chan('Dev1/ai0' )
            
            task.timing.cfg_samp_clk_timing(10000)
            
            task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI0", trigger_edge=nidaqmx.constants.Edge.RISING)
            task.read(number_of_samples_per_channel=1)

    def do_trigger(self):
        chans = self.dynamic_parameters.get('trigger_out_channel', None)
        if isinstance(chans, str):
            chans = [chans]
        N = len(chans)
            
        trigwave = np.zeros(50)
        for i in range(40):
            trigwave[i] = 3.3
                
        stimuli = N*[trigwave]
        channels = [*chans]

        self.analog_output(channels, stimuli, 1000, wait_trigger=False)

        


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
            for i_camera, camera in enumerate(self.cameras):
                camera.acquireSingle(
                    True, os.path.join(self.preparation['name'], 'snaps'),
                    exposure_time=self.snap_exposure_time, suffix=f'cam{i_camera}'
                    )

            time.sleep(0.2)
            self.do_trigger()
            
            self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
            

            print(f'A snap image taken. Exposure time {self.snap_exposure_time} seconds')
        else:
            if self.pause_livefeed:
                return

            for camera in self.cameras:
                camera.acquireSingle(
                    False, '', exposure_time=self.live_exposure_time)
            
            time.sleep(0.1)
            self.do_trigger()




    
    def image_trigger_none(self, dynamic_parameters, builder, label, N_frames, image_directory, set_led=True):
        '''Full software no attempt to sync anything...
        '''
        return self.image_trigger_hard_cameramaster(
            dynamic_parameters, builder, label, N_frames, image_directory, set_led=set_led,
            wait_for_trigger=False)


    def image_trigger_hard_cameraslave(self, dynamic_parameters, builder, label, N_frames, image_directory, set_led=True):
        '''
        Where camera is triggered by square wave.
        Since the camera cannot be run this way at 100Hz at full frame,
        image_series3 is used instead.

        '''
        return self.image_trigger_hard_cameramaster(
            dynamic_parameters, builder, label, N_frames, image_directory, set_led=set_led,
            wait_for_trigger='from-NI')

      

    def image_series(self, trigger='from-NI', inter_loop_callback=None):
        '''
        Contains common steps for all image_series methods.

        ARGUMENTS
        ---------
        triggering_type : str
            "none", "from-NI", "to-NI"

        Returns True if finished properly and False if user cancelled.
        '''
        
        
        
        exit_imaging = False

        print('Starting dynamic imaging using {} triggering'.format(trigger))
        if trigger == 'none':
            imaging_function = self.image_trigger_none
        elif trigger == 'from-NI':
            imaging_function = self.image_trigger_hard_cameraslave
        elif trigger == 'to-NI':
            imaging_function = self.image_trigger_hard_cameramaster

        # Wait ISI period here, if it has not passed since the last series imaging
        # Otherwise, continue.
        try:
            if time.time() < self.isi_slept_time: 
                print('Waiting ISI to be fullfilled from the last run...')
                time.sleep(self.isi_slept_time - time.time())
                print('READY')
        except AttributeError:
            pass
        
        dynamic_parameters = copy.deepcopy(self.dynamic_parameters)

        # Check that certain variables are actually lists (used for intensity series etc.)
        # Check also for correct length if a list
        for param in ['isi', 'flash_on']:
            if type(dynamic_parameters[param]) != type([]):
                dynamic_parameters[param] = [dynamic_parameters[param]] * dynamic_parameters['repeats']
            
            elif len(dynamic_parameters[param]) != int(dynamic_parameters['repeats']):
                print('Warning! Dynamic parameter {} length is {} but repeats is set to {}'.format(param,
                    len(dynamic_parameters[param]), dynamic_parameters['repeats'] ))
                dynamic_parameters[param] = [dynamic_parameters[param][0]] * dynamic_parameters['repeats'] 

        # Set stack save option
        for camera in self.cameras:
            camera.set_save_stack(dynamic_parameters.get('save_stack', False))
        

        # Get the current rotation stage angles and use this through the repeating
        # (even if it would change during imaging)
        imaging_angle = self.reader.get_latest()

        spaceless_angle = str(imaging_angle).replace(' ', '')
        
        # Prepare some variables that stay constant over imaging
        image_directory = os.path.join(self.preparation['name'], 'pos{}{}'.format(spaceless_angle, dynamic_parameters['suffix']+self.suffix))
        N_frames = int((dynamic_parameters['pre_stim']+dynamic_parameters['stim']+dynamic_parameters['post_stim'])/dynamic_parameters['frame_length'])
       

        for i in range(dynamic_parameters['repeats']):

            label = 'im_pos{}_rep{}'.format(spaceless_angle, i)
            
            # INTER_LOOP_CALLBACK for showing info to the user and for exiting
            if callable(inter_loop_callback) and inter_loop_callback(label, i) == False:
                exit_imaging = True  
            if exit_imaging:
                break
            
            fs = 10000
            builder = StimulusBuilder(dynamic_parameters['stim'],
                dynamic_parameters['pre_stim'], dynamic_parameters['post_stim'],
                dynamic_parameters['frame_length'], dynamic_parameters['flash_on'][i],
                dynamic_parameters['ir_imaging'], fs,
                stimulus_finalval=dynamic_parameters['flash_off'],
                illumination_finalval=dynamic_parameters['ir_waiting'],
                wtype=dynamic_parameters['flash_type'])

            if dynamic_parameters.get('biosyst_stimulus', ''):
                bsstim, fs = builder.overload_biosyst_stimulus(
                    dynamic_parameters['biosyst_stimulus'], dynamic_parameters['biosyst_channel'],
                    multiplier=dynamic_parameters.get('biosyst_multiplier', 1))
                N_frames = int(round((len(bsstim)/fs) / dynamic_parameters['frame_length']))

            if i==0 and dynamic_parameters['avgint_adaptation']:
                self.set_led(dynamic_parameters['flash_channel'], np.mean(builder.get_stimulus_pulse()), exclude='Dev1/ao4')
                time.sleep(dynamic_parameters['avgint_adaptation'])
            
            imaging_function(dynamic_parameters, builder, label, N_frames, image_directory, set_led=bool(dynamic_parameters['isi'][i]))

            if i==0 and dynamic_parameters['avgint_adaptation']:
                self.set_led(dynamic_parameters['flash_channel'], np.mean(builder.get_stimulus_pulse()), exclude='Dev1/ao4')

            # Dirtyfix
            if dynamic_parameters['reboot_cameras']:
                print("Rebooting cameras")
                for i_camera, camera in enumerate(self.cameras):
                    print(f'  cam_{i_camera}...')
                    camera.reboot()

            # Wait the total imaging period; If ISI is short and imaging period is long, we would
            # start the second imaging even before the camera is ready
            # Better would be wait everything clear signal from the camera.
            #total_imaging_time = dynamic_parameters['pre_stim'] + dynamic_parameters['stim'] + dynamic_parameters['post_stim']
            #print("Total imaging time " + str(total_imaging_time))
            # Do the actual waiting together with ISI, see just below
            
            # WAITING ISI PERIOD
            if i+1 == dynamic_parameters['repeats']:
                self.isi_slept_time = time.time() + dynamic_parameters['isi'][i]
            else:
                wakeup_time = time.time() + dynamic_parameters['isi'][i] #+ total_imaging_time
                
                while wakeup_time > time.time():
                    if callable(inter_loop_callback) and inter_loop_callback(None, i) == False:
                        exit_imaging = True
                        break
                    time.sleep(0.01)

        self.set_led(dynamic_parameters['flash_channel'], dynamic_parameters['flash_off'])
        self.set_led(dynamic_parameters['ir_channel'], dynamic_parameters['ir_livefeed'])
        print('DONE!')

        if exit_imaging:
            return False
        else:
            return True


    def image_trigger_hard_cameramaster(self, dynamic_parameters, builder, label, N_frames, image_directory, set_led=True,
                                        wait_for_trigger='from-NI'):
        '''
        When starting the imaging, the camera sends a trigger pulse to NI board, leading to onset
        of the stimulus (hardware triggering by the camera).
        
        Illumination IR light is hardware triggered together with the stimulus.

        ARGUMENTS
        ---------
        set_led : bool
            Set IR to ir_waiting in between (if long enough ISI)
        wait_for_trigger : string or false
            If "to_NI", wait trigger to come from the camera to NI card (default)
            One camera has to be then configured to send trigger, others to wait for it
            If "from_NI", NI generates trigger.
            If False, does not wait for trigger.
        '''
        if wait_for_trigger == 'from-NI':
            # Trigger to release
            self.do_trigger()
            self.do_trigger()

        # If IR is used or not
        if dynamic_parameters['ir_channel'].lower() in ['none']:
            use_ir = False
        else:
            use_ir = True            
        
        if use_ir and set_led:
            self.set_led(dynamic_parameters['ir_channel'], dynamic_parameters['ir_imaging'])
            time.sleep(0.5)
        
        fs = builder.fs

        # Create stimulus
        stimulus = builder.get_stimulus_pulse()
        if isinstance(stimulus, list):
            NN = len(stimulus[0])
        else:
            NN = stimulus.shape

        if use_ir:
            irwave = dynamic_parameters['ir_imaging'] * np.ones(NN)
            #irwave = dynamic_parameters['ir_imaging'] * np.ones(stimulus.shape)
            if set_led:
                irwave[-1] = dynamic_parameters['ir_waiting']

        stimuli = []
        channels = []

        if isinstance(stimulus, list):
            # Many stimulus channels
            print('Many stimulus channels')
            stimuli = [*stimulus]
            channels = [*dynamic_parameters['flash_channel']]
        else:
            # One stimulus channel
            stimuli = [stimulus]
            channels = [dynamic_parameters['flash_channel']]

        if use_ir:
            stimuli.append(irwave)
            channels.append(dynamic_parameters['ir_channel'])


        # Arm analog input recording if any vio clients
        for i_vio, vio in enumerate(self.vios):
            vio.set_save_directory(os.path.join(self.data_savedir, image_directory))
            duration = N_frames * dynamic_parameters['frame_length']
            vio_label = f'vi{i_vio}{label[2:]}'
            vio.analog_input(duration, save=vio_label, wait_trigger=True)


        if len(self.cameras) == 1:
            self.cameras[0].acquireSeries(dynamic_parameters['frame_length'], 0, N_frames, label, image_directory)
        elif len(self.cameras) > 1:
            # With many cameras, add camN suffix to the label
            for i_camera, camera in enumerate(self.cameras):
                camera.acquireSeries(dynamic_parameters['frame_length'], 0, N_frames, f'{label}_cam{i_camera}', image_directory)


        # If no cameras, we should not wait for trigger to come from them.
        # Create own trigger on the trigger channel
        # - This is needed to sync two NI cards, one input one output
        # - If only one NI card then not needed?
        print(f'Wait for trigger is: {wait_for_trigger}')
        if not self.cameras:
            wait_trigger = False
            trigwave = np.zeros(len(stimuli[0]))
            for i in range(min(100, len(trigwave))):
                trigwave[i] = 3

            chans = self.dynamic_parameters.get('trigger_out_channel', None)
            if isinstance(chans, str):
                chans = [chans]
            N =len(chans)
            
            stimuli = [*stimuli, *(N*[trigwave])]
            channels = [*channels, *chans]
        elif wait_for_trigger == 'from-NI':
            wait_trigger = False
            

            chans = self.dynamic_parameters.get('trigger_out_channel', None)
            if isinstance(chans, str):
                chans = [chans]
            N=len(chans)

            trigwaves = builder.get_camera(N, interleaved=False)

            stimuli = [*stimuli, *trigwaves]
            channels = [*channels, *chans]

            #stimuli = [*stimuli, trigwave]
            #channels = [*channels, dynamic_parameters['trigger_out_channel']]

            # Give 1000 ms for the cameras to get ready for incoming trigger
            time.sleep(1)
        elif wait_for_trigger == 'to-NI':
            wait_trigger = True
        elif not wait_for_trigger:
            wait_trigger = False
        else:
            wait_trigger = True
        print(f'Wait trigger is: {wait_trigger}')

        
        self.analog_output(channels, stimuli, fs, wait_trigger=wait_trigger)
        if wait_for_trigger == 'from-NI':
            self.do_trigger()
            self.do_trigger()
            self.do_trigger()

    def set_savedir(self, savedir, camera=True):
        '''
        Set the directory where the taken images are saved.

        camera : bool
            If False, do not attempt to update save folder to the camera server
        '''
        if camera:
            for device in self.cameras+self.vios:
                device.set_save_directory(savedir)
        self.data_savedir = savedir


    def set_subfolder_suffix(self, suffix):
        '''
        Set any suffix to a data folder containing the images.
        For example
            pos(-14,0) would become pos(-14,0)_highmag if suffix == "highmag"
        '''
        if suffix:
            self.suffix = '_'+suffix
        else:
            self.suffix = ''

    def _update_descriptions_file(self):
        # Saving description file
        desc_string = "name {}\nsex {}\nage {}".format(self.preparation['name'], self.preparation['sex'], self.preparation['age'])
        desc_string += "\n\n#DYNAMIC PROTOCOL PARAMETERS\n"
        for name, value in self.dynamic_parameters.items():
            desc_string += '{} {}\n'.format(name, value)

        # Save information about cameras: What was the name of the camera number
        # 1, number 2 ans do on
        desc_string += '\n#CAMERA NUMBER-NAME RELATIONS\n'
        for i_camera, camera in enumerate(self.cameras):
            desc_string += f'cam_{i_camera} {camera.get_camera()}\n'
            
        for camera in self.cameras:
            camera.saveDescription(self.preparation['name'], desc_string)
        

    def initialize(self, name, sex, age, camera=False, libui=None):
        '''Call this to initialize the experiments.

        Returns True if worked or None if user cancelled.


        name, sex age       Can be '' (empty string)
        '''
        # Preparations, ask droso name
        if name != '':
            self.preparation['name'] = name
        if sex != '':
            self.preparation['sex'] = sex
        if age != '':
            self.preparation['age'] = age

        params = getModifiedParameters(libui=libui,
                                       parameters=self.dynamic_parameters)
        if params is None:
            return None 

        self.dynamic_parameters = params

        if camera:
            self._update_descriptions_file()
        else:
            self.triggered_anglepairs = []
        
        self.set_led(self.dynamic_parameters['ir_channel'], self.dynamic_parameters['ir_livefeed'])
        self.set_led(self.dynamic_parameters['flash_channel'], self.dynamic_parameters['flash_off'])
       
        roi = self.dynamic_parameters['ROI']
        if roi is not None:
            for camera in self.cameras:
                camera.set_roi(roi)

        return True

    def load_preset(self, preset_name):
        fn = os.path.join('presets', preset_name)
        self.dynamic_parameters = load_parameters(fn)
        self._update_descriptions_file()



    def tick(self, horizontal_trigger=True, vertical_trigger=False):
        '''Updates the current angle and performs all "houskeeping" duties also.
        
        Meant to be called repeatedly inside the UI loop.
        '''

        change = False

        if self.vio_livefeed:
            if time.time()-self._last_vio > max(self.vio_livefeed_dur+0.1, 0.1):
                for vio in self.vios:
                    vio.analog_input(self.vio_livefeed_dur)
                self._last_vio = time.time()
        
        while True:
            
            # Update current angle and echo it to the console
            current_angle = [list(self.reader.read_angles())]
            toDegrees(current_angle)

            if self.previous_angle != current_angle:
                horchanged = self.previous_angle and self.previous_angle[0][0] != current_angle[0][0]
                verchanged = self.previous_angle and self.previous_angle[0][1] != current_angle[0][1]
                if (horizontal_trigger and horchanged) or (vertical_trigger and verchanged):
                    self.trigger_rotation = True

                print("Horizontal-vertical is {}".format(current_angle[0]))
                self.previous_angle = current_angle
                change = True
            else:
                break

        if not change:
            self.trigger_rotation = False

        # Run macro if set
        if self.macro:
                
            next_macro_step = False

            action = self.macro[self.i_macro]
            print(action)

            
            if type(action) == type((0,0)):
                # Move motors only if they have reached their positions
                if self.motors and all([self.motors[i].reached_target() for i in [0,1]]):
                    self.motors[0].move_to(action[0])
                    self.motors[1].move_to(action[1])
                    next_macro_step = True
            if 'wait' in action:
                self.waittime = time.time() + float(action.split(' ')[-1])
                next_macro_step = True
            
            if next_macro_step and self.waittime < time.time():
                self.i_macro += 1
                if self.i_macro == len(self.macro):
                    self.macro = None
                    self.i_macro = 0

    def set_zero(self):
        '''
        Define the current angle pair as the zero point
        (Like tar button on scales)
        '''
        self.reader.current_as_zero()



    def finalize(self):
        '''
        Finalising the experiments, houskeeping stuff.
        '''
        self.set_led(self.dynamic_parameters['ir_channel'], 0)
        self.set_led(self.dynamic_parameters['flash_channel'], 0)
        
        for motor in self.motors:
            motor.move_to(0)

        if self.triggered_anglepairs:
            fn = os.path.join(self.data_savedir, self.preparation['name'], 'anglepairs.txt')
            os.makedirs(os.path.dirname(fn), exist_ok=True)

            print(fn)
            
            with open(fn, 'w') as fp:
                for line in self.triggered_anglepairs:
                    fp.write(str(line).strip('()').replace(' ', '')+'\n')

            self.triggered_anglepairs = None


    def exit(self):
        for camera in self.cameras:
            camera.close_server()

    #
    # CONTROLLING LEDS, MOTORS ETC
    #
    
    def move_motor(*args, **kwargs):
        self.reader.move_motor(*args, **kwargs)


    #
    # PROTOCOL QUEUE / MACRO
    #


    @staticmethod
    def list_macros():
        return macro.list_macros()


    def run_macro(self, macro_name):
        self.macro = macro.load(macro_name)
        self.i_macro = 0




