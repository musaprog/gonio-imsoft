'''A terminal user interface library. Small, custom.
'''

import os
import platform
import time
import inspect      # Inspect docs and source code

OS = platform.system()
if OS == 'Windows':
    import msvcrt   # reading pressed keys without blocking
else:
    import sys


class SimpleTUI:
    '''A terminal user interface (TUI) library.
    
    Attributes
    ----------
    header : string or None
        Text shown on on the top of the screen.
    '''
    
    def __init__(self):
        self.header = None


    @staticmethod
    def read_key():
        if OS == 'Windows':
            if msvcrt.kbhit():
                key = ord(msvcrt.getwch())
                return chr(key)
            return ''
        else:
            return sys.stdin.read(1)


    def clear_screen(self):
        '''Empties the screen and prints the header if any.
        '''
        if os.name == 'posix':
            os.system('clear')
        elif os.name == 'nt':
            os.system('cls')

        if self.header is not None:
            self.print(self.header)


    @staticmethod
    def print_lines(lines):
        for text in lines:
            print(text)
        
    @staticmethod
    def print(value):
        print(value)


    def item_select(self, items, message=None):
        '''Makes the user to select an item

        Arguments
        ---------
        items : iterable
            An iterable (eg. list) that returns printable items.
            If the item is newline, then prints a space and this
            space cannot be selected.

        Returns
        -------
        item : any
            The selected item

        Empty string items are converted to a space
        '''
        
        if message is not None:
            self.print(message)

        real_items = []
        i = 0
        for item in items:
            if item != '\n':
                print('{}) {}'.format(i+1, item))
                real_items.append(item)
                i += 1
            else:
                print()

        print()

        selection = ''
        while True:
            new_char = self.read_key()
            if new_char:
                selection += new_char
                self.print(selection)
            if selection.endswith('\r') or selection.endswith('\n'):
                try:
                    selection = int(selection)
                    real_items[selection-1]
                    break
                except ValueError:
                    self.print('Invalid input')
                    selection = ''
                except IndexError:
                    self.print('Invalid input')
                    selection = ''
        return real_items[selection-1]
    

    def bool_select(self, message=None, true='yes', false='no'):
        '''Ask the user yes/no.

        Uses input so it blocks.
        '''
        
        if message is not None:
            self.print(message)

        while True:
            sel = input('(yes/no) >> ').lower()
            if sel.startswith('yes') or sel == 'y':

                return True
            elif sel.startswith('no') or sel == 'n':
                return False
            
            self.print('What? Please try again')
            time.sleep(1)


    def input(self, message=None):
        '''Ask the user for text input.
        '''
        if message is not None:
            self.print(message)
        return input('>> ')



