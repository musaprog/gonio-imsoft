
import numpy as np
import scipy.io as sio

EXAMPLE = '/home/joni/code/biosystfiles/empty_100ms.mat'

def stimulus_to_zero(mat, time_length):
    '''
    Replace STIMULUS and SWEEP_SEQ in Biosyst stimulusfile with zeros,
    creating a zero stimulus with length time_length.
    Sampling frequency is read from the original stimulus file.
    
    mat             Object returned by scipy.io.loadmat
    time_length     In seconds
    '''
    
    fs = float(mat['STIMRATE'])
    #mat = sio.loadmat(EXAMPLE, mat_dtype=True)
    
    # MAKE STIMULUS LONGER/SHORTER
    orglen = len(mat['STIMULUS'][0])
    orgchans = len(mat['STIMULUS'])
    
    mat['STIMULUS'] = np.zeros((orgchans, int(fs * time_length)))
    

    # MAKE SWEEPSEQ LONGER/SHORTER
    for i in range(orgchans):
        
        #print(mat['SWEEP_SEQ'][0][i]) 
    
        mat['SWEEP_SEQ'][0][i] = np.zeros((1, int(fs * time_length)))
    
        #print(mat['SWEEP_SEQ'][0][i]) 
    
    return mat

    

if __name__ == "__main__":
    longmat = empty(1)
    
    sio.savemat('longmattet.mat', longmat)

