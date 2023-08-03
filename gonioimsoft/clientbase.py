'''Commond code for all client programs.
'''
import socket
import time
import subprocess
import sys
import atexit

class ClientBase:
    '''Base class for all clients.

    The client offers a stable API for the main software (GonioImsoft)
    to use. The client internals and the server can be then more freely
    changed without causing havoc.

    Attributes
    ----------
    host : string
        The server IP (v4) address or a hostname
    port : int
        The server port number
    local_server : Popen obj or None
        None if no local server started by the client
    '''

    def __init__(self, host, port, running_index=0):
        self.host = host
        self.port = port


    def send_command(self, command, listen=False,
                     n_retry=60, retry_interval=1):
        '''Sends an arbitrary command to the server.

        Opens a connection to the server, send the command string and
        then optionally waits for the server's response.

        Arguments
        ---------
        command : string
            Format: "{command_name};{arg1}:{arg2}:..."
            Example 1: "ping;hello there"
            Example 2: "acquireSeries;0:0.1:0:5:label"
        listen : bool
            Wheter to wait and listen the server's response. If used
            incorrectly (listen=True but server says nothing, or
            listen=False and server says back), hangs either the client
            or the server.
        n_retry : int
            How many times to try to recontact the server if it cannot
            be reached (the server is off or the network is down etc.)
            Default is 60.
        retry_interval : int or float
            In seconds, how long to sleep between between the connection
            retries. Default is 1.
        '''
        if not isinstance(command, str):
            typ = type(command)
            raise TypeError(f'command must be a string, not {typ}')
        

        tries = 0
        host = self.host
        port = self.port

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soc:

            while True:
                try:
                    soc.connect((host, port))
                    break
                except ConnectionRefusedError:
                    tries += 1
                    if tries > n_retry:
                        raise ConnectionRefusedError(
                                f'Cannot connect to {host}:{port}')

                        print('Server connection unavailable, retrying...')
                        time.sleep(retry_interval)

            soc.sendall(command.encode())
            
            if listen:
                response = []
                while True:
                    data = soc.secv(1024)
                    if not data: break
                    response.append(data.decode())
                response = ''.join(response)
                if ':' in response:
                    response = response.split(':')
                return response


    def is_server_running(self):
        '''Returns True if the server responds to ping.
        '''
        try:
            self.send_command(
                    'ping;Hello there!', n_retry=0)
        except ConnectionRefusedError:
            return False
        return True

    def set_save_directory(self, directory):
        '''For any data saving that the server can do, set the directory.
        '''
        self.send_command(f'set_save_directory;{directory}')

    def start_server(self, name):
        '''Starts a local server if it is not running.

        Starts a new subprocess for the server.
        
        Arguments
        ---------
        name : string
            Name of the server. "camera" or "vio"
        '''
        if name not in ['camera', 'vio']:
            raise ValueError(
                    f'name has to be "camera" or "vio" not {name}')

        if self.is_server_running():
            print(f'Local server on port {self.port} already runs')
            print('-> Not starting another')
            return

        print(f'Starting a local server on port {self.port}')

        self.local_server = subprocess.Popen(
                [
                    sys.executable,
                    '-m', f'gonioimsoft.{name}_server',
                    '--port', str(self.port),
                    ],
                stdout=subprocess.DEVNULL)

        atexit.register(self.close_server)


    def close_server(self):
        '''Sens a closeure message for the server.

        If the server was started by this client (a local server), also
        waits the subprocess finish for 10 seconds unil terminates it.
        '''
        try:
            self.send_command('exit;parakalo', n_retry=0)
        except ConnectionRefusedError:
            pass
        
        if self.local_server is None:
            return

        atexit.unregister(self.close_server)

        if self.local_server is not None:
            try:
                self.local_server.wait(10)
            except subprocess.TimeoutExpired:
                self.local_server.terminate()
            self.local_server = None


def run_client(client):
    '''Runs the client from terminal without the main GonioImsoft program.
    '''
    import argparse

    parser = argparse.ArgumentParser(
            prog=f'GonioImsoft {client.__class__.__name__}',
            description=f'{client.__doc__}')

    parser.add_argument('-p', '--port')
    parser.add_argument('-a', '--address')

    args = parser.parse_args()

    client = client(args.address, args.port)

    print('Welcome to this interactive test program')
    print('Type in commands (or "help") and press enter')

    while True:
        cmd = input('#').split(' ')

        if not cmd:
            continue

        if cmd[0] == 'help':
            if len(cmd) == 1:
                help(client)
            else:
                method = getattr(client, cmd[1], None)
                if method is None:
                    print(f'No such command as "{cmd[1]}"')
                    continue
                
                print(method.__doc__)

        else:
            method = getattr(client, cmd[0], None)

            if method is None:
                print(f'No such command as "{cmd[0]}"')
                continue
            
            try:
                if len(cmd) == 1:
                    message = method()
                else:
                    message = method(*cmd[1:])
            except Exception as e:
                print('Given command casued an error in the client:')
                print(e)
                continue
            
            print(message)
