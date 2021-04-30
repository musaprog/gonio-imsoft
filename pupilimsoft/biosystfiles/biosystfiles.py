'''
biosystfiles.py
Extract traces from Biosyst .mat datafiles.
'''


import os                   # for joining path names
import logging

import scipy.io as sio      # for reading .mat files
import numpy as np


LOGGER_NAME = 'plugins.biosystfiles'
module_logger = logging.getLogger(LOGGER_NAME)



def extract(fn, channel):
    '''
    Extracts data from biosyst datafiles of a specified channel.
    Returns data and fs
    '''


    # If fn is actually a list of filenames make a recursion
    if type(fn) == type([]) or type(fn) == type((0,0)):
        traces = []
        

        for single_fn in fn:
            print(single_fn)
            trace, fs = __extract_single(single_fn, channel)
            traces.append(trace)
        return traces, fs

    return __extract_single(fn, channel)



def __extract_single(fn, channel):
    '''
    Called from extract
    '''
    # Open a Biosyst generated file using scipy.io
    try:
        mat = sio.loadmat(os.path.join(os.getcwd(), fn))
    except FileNotFoundError:
        module_logger.error('Could not find file '+fn+'.') 
        raise


    # If DATAFILE field not found (ie. is not recorded response but 
    # a stimulus file) open STIMULUS
    for key in ['DATAFILE', 'STIMULUS']:
        try:
            alldata = mat[key]
            break
        except KeyError:
            continue
    
    if key == 'STIMULUS':
        alldata = alldata.T

    # Pick needed parameters from the file
    if key == 'DATAFILE':
        fs = int(mat['RECORD_INFO'][0][2])
        N_channels = int(np.sum(mat['SETTINGS_INFO'][0][5]))
    elif key == 'STIMULUS':
        fs = int(mat['STIMRATE'])
        N_channels = int(np.sum(mat['DA_STIM']))

    module_logger.debug('Recording sample rate: '+str(fs)+' Hz')
    module_logger.debug('Number of recorded channels: '+str(N_channels))

    NoT = alldata.shape[1]
    N = alldata.shape[0]
    

    # --------------------------------------
    limits = range(channel, NoT, N_channels)
        
    # Number of Extracted traces
    NoE = 0
    for i in limits:
        NoE += 1
    extract = np.zeros((N, NoE))

    for j, i in enumerate(limits):
        extract[:, j] = alldata[:,i]

    # --------------------------------------
    
    #if key == 'STIMULUS':
    #    extract = extract.T

    return extract, fs



def extract_many(fn, channels):
    '''
    If not SNR recording, extracting many channels may be wanted.
    '''
    
    ex, fs = extract(fn, channels[0])
    for channel in channels[1:]:
        curex, fs = extract(fn, channel)
        
        ex = np.hstack((ex, curex))   

    return ex, fs



def debug_test(plot=False):
    
    if plot:
        import matplotlib.pyplot as plt

    logging.basicConfig(level=logging.DEBUG)


    for fn in ['example_stimulus.mat', 'example_response2.mat']:
        trace, fs = extract(fn, 0)
        if plot:
            plt.plot(trace)
            plt.show()

    return 0

if __name__ == "__main__":
    debug_test(True)

