'''Shared code between various servers.
'''

import socket
import time
import os

DEFAULT_SAVE_DIRECTORY = 'gonioimsoft_data'


class ServerBase:
    '''The base class for any server.

    Attributes
    ----------
    socket : obj
        The socket object.
    device : obj or None
        
    functions : dict
        Keys command names and values callables.
    responders : list
        Command names (a subset from functions) that also need to
        send a return value to the client.
    '''
    
    def __init__(self, host, port, device):
        
        print(f'Binding a socket (host {host}, port {port}')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('', port))
        self.socket.listen(1)
        
        if getattr(device, 'save_directory', None):
            device.save_directory = DEFAULT_SAVE_DIRECTORY
        self.device = device

        
        self.functions = {
                'ping': self.ping,
                'pong': self.pong,
                'exit': self.exit,
                'set_save_directory': self.set_save_directory,
                }

        self.responders = ['pong']

        self.run_exit = False



    def ping(self, message):
        '''Prints the client's message on the server.
        '''
        print(f'A client says: {message}')


    def pong(self, message):
        '''Sends the client's message back to the server with a greeting.
        '''
        return f'General Kenobi! (response to {message})'
    
    def set_save_directory(self, directory):
        '''Sets the location for the data saving
        '''
        abspath = os.path.abspath(directory)
        if not os.path.isdir(directory):
            print(f'Creating directory {abspath} for saving data')
            os.makedirs(directory)
        else:
            print(f'Setting directory {abspath} for saving data')
        
        if self.device is not None:
            self.device.save_directory = directory


    def wait_for_client(self):
        '''Waits for any command from the client and then discards it.
        '''
        print('Waiting for any command...')
        conn, addr = self.socket.accept()
        while True:
            data = conn.recv(1024)
            if not data: break
        conn.close()
        print('Got a command from the client, waiting done!')


    def run(self):
        '''Runs the server mainloop until receives an exit command.

        In each turn of the loop, waits for incoming connection and
        executes the clients wishes.
        '''
        print('Waiting clients to connect')
        while not self.run_exit:
            conn, addr = self.socket.accept()
            data = conn.recv(1024)
            string = data.decode()

            if not string:
                conn.close()
                continue

            print(f'Got command {string} at {time.time()}')

            # The char ';' is used as a delimiter between the
            # command name and the arguments. Parameters by ':'
            if ';' in string:
                func, parameters = string.split(';')
                parameters = parameters.split(':')
            else:
                func = string
                parameters = []

            if func not in self.functions:
                print(f'Skipping unkown command: {func}')
                conn.close()
                continue

            # If the client expects no response, then we can close the
            # connection early and let the client go.
            if not func in self.responders:
                conn.close()
            
            try:
                response = self.functions[func](*parameters)
            except Exception as e:
                print()
                print('Failure running the command')
                print(f'  Invocation (Python): {func}(*{parameters})')
                print('  Error below:')
                print(e)
                print()
                response = 'error'

                
            # Say back the response and close
            if func in self.responders:

                if isinstance(response, (list, tuple)):
                    response = ':'.join(response)

                conn.sendall(str(response).encode())
                conn.close()


    def exit(self, _=None):
        '''Makes the run function to exit from its mainloop.
        '''
        self.run_exit = True
