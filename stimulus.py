
import os

import numpy as np
from biosystfiles import extract as bsextract

class StimulusBuilder:
    '''
    Get various stimulus waveforms
    - to the stimulus LED
    - and on pulse for illumination LED
    - and square wave for triggering the camera.
    
    
    '''

    def __init__(self, stim_time, prestim_time, poststim_time, frame_length,
            stimulus_intensity, illumination_intensity, fs,
            stimulus_finalval=0, illumination_finalval=0):
            '''
            stim_time               The time stimulus LED is on
            prestim_time            The time the camera is running and illumination is on before the stimulus
            poststim_time           The time the camera is running and illumination is on after the stimulus
            stimulus_intensity      From 0 to 1, the brightness of the stimulus
            illumination_intensity  From 0 to 1, the brightness of the illumination lights


            '''

            self.stim_time = stim_time
            self.prestim_time = prestim_time
            self.poststim_time = poststim_time
            self.frame_length = frame_length
            self.stimulus_intensity = stimulus_intensity
            self.illumination_intensity = illumination_intensity
            self.fs = fs
            self.stimulus_finalval = stimulus_finalval
            self.illumination_finalval = illumination_finalval

            self.N_frames = int(round((stim_time+prestim_time+poststim_time)/frame_length))

            self.overload_stimulus = None


    def overload_biosyst_stimulus(self, fn, channel=0):
        '''
        Loads a Biosyst stimulus that gets returned then at
        get_stimulus_pulse instead.

        Returns the overload stimulus and new fs
        '''
        ffn = os.path.join('biosyst_stimuli', fn)
        self.overload_stimulus, self.fs = bsextract(ffn, channel)
        self.overload_stimulus = self.overload_stimulus.flatten()
        print(self.overload_stimulus.shape)
        print(np.max(self.overload_stimulus))

        return self.overload_stimulus, self.fs
    
    def get_stimulus_pulse(self):
        '''
        Constant value pulse

                _________stimulus_intensity
                |       |
        ________|       |__________
        prestim   stim    poststim
        '''

        if self.overload_stimulus is not None:
            return self.overload_stimulus
        
        stimulus = np.concatenate( (np.zeros(int(self.prestim_time*self.fs)), np.ones(int(self.stim_time*self.fs)), np.zeros(int(self.poststim_time*self.fs))) )
        stimulus = self.stimulus_intensity * stimulus

   
        stimulus[-1] = self.stimulus_finalval
        
        return stimulus



    def get_illumination(self):
        '''
        Returns 1D np.array.
        '''
        illumination = np.ones( int((self.stim_time+self.prestim_time+self.poststim_time)*self.fs) )
        illumination = self.illumination_intensity * illumination

        illumination[-1] = self.illumination_finalval
        
        return illumination



    def get_camera(self):
        '''
        Get square wave camera triggering stimulus.
        
        Returns 1D np.array.
        '''
        
        samples_per_frame = int(frame_length * fs /2)
        
        camera = np.concatenate( ( np.ones((samples_per_frame, self.N_frames)), np.zeros((samples_per_frame, self.N_frames)) ) ).T.flatten()
        camera = 5*camera
    
        camera[-1] = 0

        return camera
