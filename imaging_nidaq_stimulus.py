
import numpy as np

def get_pulse_stimulus(stim_time, prestim_time, poststim_time, frame_length,
        stimulus_intensity, illumination_intensity, fs,
        stimulus_finalval=0, illumination_finalval=0):
    '''
    Creates a rectangular stimulus pulse
    
    stim_time               The time stimulus LED is on
    prestim_time            The time the camera is running and illumination is on before the stimulus
    poststim_time           The time the camera is running and illumination is on after the stimulus
    stimulus_intensity      From 0 to 1, the brightness of the stimulus
    illumination_intensity  From 0 to 1, the brightness of the illumination lights

    end_in_zero             Makes sure all channels end in zero

    Returns following 1D numpy arrays
        stimulus_array, illumination_array, camera_array
    '''

    stimulus = np.concatenate( (np.zeros(int(prestim_time*fs)), np.ones(int(stim_time*fs)), np.zeros(int(poststim_time*fs))) )
    stimulus = stimulus_intensity * stimulus

    illumination = np.ones( int((stim_time+prestim_time+poststim_time)*fs) )
    illumination = illumination_intensity * illumination

    samples_per_frame = int(frame_length * fs /2)
    N_frames = int(round((stim_time+prestim_time+poststim_time)/frame_length))
    camera = np.concatenate( ( np.ones((samples_per_frame, N_frames)), np.zeros((samples_per_frame, N_frames)) ) ).T.flatten()
    camera = 5*camera
    
    stimulus[-1] = stimulus_finalval
    illumination[-1] = illumination_finalval
    camera[-1] = 0

    return stimulus, illumination, camera




