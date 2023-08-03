'''Voltage input/output server.
'''

try:
    import nidaqmx
except ImportError:
    nidaqmx = None
    print('nidaqmx not available')

from .common import VIO_PORT
from .serverbase import ServerBase

class DummyBoard:
    '''For testing the server without an NI board.

    For documentation, see the NIBoard class.
    '''
    def analog_input(self, device, channels, duration, fs):
        print('DummyBoard.analog_input(...)')
        print(f'dvs={device} | chs={channels} | dur={duration} | fs={fs}')




class NIBoard:
    def __init__(self):
        pass

    
    def analog_input(self, device, channels, duration, fs):
        '''Records voltage input and saves it.

        dev : string
            The NI board name (usually "Dev1" or "Dev2").
        channels : string
            Channels names to record, separated by commas.
        duration : int or float
            In seconds, the recording's length.
        fs : float or int
            The used sampling frequency in Hz (samples/second).
        '''
        channels = channels.split(',')
        duration = float(duration)
        fs = float(fs)

        N_channels = len(channels)
        N_samples = duration * fs

        timeout = duration + 10

        with nidaqmx.Task() as task:
            
            for channel in channels:
                task.ai_channels.add_ai_voltage_chan(channel)

            task.timing.cfg_samp_clk_timing(
                    fs, samps_per_chan=N_samples)

            if wait_trigger:
                taks.triggers.start_trigger.cfg_dig_edge_start_trig(
                        f'/{device}/PFI0')

            task.start()

            task.read(timeout=timeout)



class VIOServer(ServerBase):
    '''Analog voltage input/output board server.
    '''

    def __init__(self, board, port=None):

        if port is None:
            port = VIO_PORT
        super().__init__('', port)
        
        self.board = board

        self.functions['analog_input'] = self.board.analog_input




def main():
        
    if nidaqmx is None:
        board = DummyBoard()
    else:
        board = NIBoard()

    server = VIOServer(board)
    server.run()


if __name__ == "__main__":
    main()
