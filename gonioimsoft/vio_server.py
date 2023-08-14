'''Voltage input/output server.
'''

import os
import multiprocessing

import numpy as np
import matplotlib.pyplot as plt

try:
    import nidaqmx
except ImportError:
    nidaqmx = None
    print('nidaqmx not available')

from .common import VIO_PORT
from .serverbase import ServerBase


class Plotter:
         
    def loop(self, queue, title):
        
        fig = plt.figure()
        ax = fig.add_subplot(111)
        plt.show(block=False)

        fig.canvas.toolbar.winfo_toplevel().title(title)
        
        while True:
            if queue.empty():
                plt.pause(0.1)
                continue
            while not queue.empty():
                data = queue.get()
            if isinstance(data, str) and data == 'close':
                break

            ax.clear()
            ax.plot(data)
            plt.pause(0.1)
        


def run_plotter(queue, title):
    plotter = Plotter()
    plotter.loop(queue, title)


class DummyBoard:
    '''For testing the server without an NI board.

    For documentation, see the NIBoard class.
    '''
    def analog_input(self, duration, wait_trigger=False):
        print('DummyBoard.analog_input(...)')
        print(f'dur={duration} | wait_trigger={wait_trigger}')

    def set_settings(self, device, channels, fs):
        print('DummyBoard.set_settings(...)')
        print(f'dvs={device} | chs={channels} | fs={fs}')

class NIBoard:
    def __init__(self):
        
        self.channels = None
        self.fs = 1000

        self.live_queue = None
        self.title = 'Analog input'
    

    def set_settings(self, device, channels, fs):
        '''

        Arguments
        ---------
        dev : string
            The NI board name (usually "Dev1" or "Dev2").
        channels : string
            Channels names to record, separated by commas.
        fs : float or int
            The used sampling frequency in Hz (samples/second).
        '''
        self.device = device
        self.channels = channels.split(',')
        self.fs = float(fs)

        self.title = f'Analog input - {self.device} {self.channels} {self.fs} Hz'
        
   
    def analog_input(self, duration, save=None, wait_trigger=False):
        '''Records voltage input and saves it.

           
        duration : int or float
            In seconds, the recording's length.

        '''
        if save == 'None':
            save = None
            
        duration = float(duration)
        timeout = duration + 10

        N_channels = len(self.channels)
        N_samples = duration * self.fs
        

        if str(wait_trigger).lower() == 'true':
            wait_trigger = True
        else:
            wait_trigger = False


        with nidaqmx.Task() as task:
            
            for channel in self.channels:
                task.ai_channels.add_ai_voltage_chan(f'{device}/{channel}')

            task.timing.cfg_samp_clk_timing(
                    self.fs, samps_per_chan=N_samples)

            if wait_trigger:
                taks.triggers.start_trigger.cfg_dig_edge_start_trig(
                        f'/{device}/PFI0')

            task.start()

            task.read(timeout=timeout)


        if save is not None:
            fn = os.path.join(
                self.save_directory, f'{save}.npy')
            np.save(fn, np.array(data))


        if self.live_queue is None:
            self.live_queue = multiprocessing.Queue()
            self.live_queue.put(data)
            
            self.livep = multiprocessing.Process(
                    target=run_plotter,
                    args=(self.live_queue,self.title))
            self.livep.start()
            
        else:
            self.live_queue.put(data)


class VIOServer(ServerBase):
    '''Analog voltage input/output board server.
    '''

    def __init__(self, device, port=None):

        if port is None:
            port = VIO_PORT
        super().__init__('', port, device)
        
        self.functions['analog_input'] = self.device.analog_input
        self.functions['set_settings'] = self.device.set_settings



def main():
        
    if nidaqmx is None:
        board = DummyBoard()
    else:
        board = NIBoard()

    server = VIOServer(board)
    server.run()


if __name__ == "__main__":
    main()
