
from .clientbase import ClientBase, run_client
from .common import SERVER_HOSTNAME, VIO_PORT

class VIOClient(ClientBase):
    '''Analog voltage input/output client.
    '''

    def __init__(self, host=None, port=None, running_index=0):

        if host is None:
            host = SERVER_HOSTNAME
        if port is None:
            port = int(VIO_PORT)
        super().__init__(host, port)


    def analog_input(self, duration, wait_trigger=False):
        '''Makes the server to record analog signal and save it.
        '''
        self.send_command(
                f'analog_input;{duration}:{wait_trigger}')

    
    def set_settings(self, device, channels, fs):
        '''Configures the setttings in use.
        '''
        self.send_command(
                f'set_settings;{device}:{channels}:{fs}')
        
    
    def start_server(self):
        super().start_server('vio')
       

def main():
    run_client(VIOClient)

if __name__ == "__main__":
    main()
