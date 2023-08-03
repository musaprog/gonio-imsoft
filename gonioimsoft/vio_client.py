
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


    def analog_input(self, device, channels, duration, fs):
        '''Makes the server to record analog signal and save it.
        '''
        self.send_command(
                f'analog_input;{device}:{channels}:{duration}:{fs}')


def main():
    run_client(VIOClient)

if __name__ == "__main__":
    main()
