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
    import select


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
        else:
            if select.select([sys.stdin], [], [], 0.1):
                return sys.stdin.read(1)
        return ''

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
    def print(value=''):
        print(value)


    def _convert_selection(self, selection):
        '''
        selection : string
            Raw string typed by the user.
        '''
        selection = selection.strip('\r\n')
        selection = selection.split(',')

        # Raises ValueError if fails
        selection = [int(string) for string in selection]
        
        return selection


    def item_select(self, items, message=None, multiselect=False):
        '''Makes the user to select an item

        Arguments
        ---------
        items : iterable
            An iterable (eg. list) that returns printable items.
            If the item is newline, then prints a space and this
            space cannot be selected.
        message : string
            Printed before the selection table as an instruction
        multiselect : bool
            If True, 

        Returns
        -------
        item : ?
            The selected item. If multiselect is True, returns a
            list of selected items

        Empty string items are converted to a space
        '''
        
        if message is not None:
            self.print(message)

        real_items = []
        i = 0
        for item in items:
            if item != '\n':
                self.print('{}) {}'.format(i+1, item))
                real_items.append(item)
                i += 1
            else:
                self.print()

        self.print()
        
        if multiselect:
            self.print('# Multiple selections possible, separate by commas (,)')
        else:
            self.print('# Select by number and hit enter')

        self.print()

        selection = ''
        while True:
            new_char = self.read_key()
            if new_char:
                if new_char == '\b':
                    # Backspace
                    selection = selection[:-1]
                elif new_char in "0123456789\n\r":
                    selection += new_char
                self.print(selection)
            if selection.endswith('\r') or selection.endswith('\n'):
                
                try:
                    selection = self._convert_selection(selection)
                except ValueError:
                    self.print('Invalid input (non-numbers inputted)')
                    selection = ''
                    continue
                
                try:
                    # Test that we can get the item; -1 comes from
                    # the difference between Python first index (0)
                    # and this selection program first index (1) 
                    [real_items[number-1] for number in selection]
                except IndexError:
                    self.print('Invalid input (index out of range)')
                    selection = ''
                    continue

                break


        to_return = [real_items[int(number)-1] for number in selection]
        if not multiselect:
            to_return = to_return[0]

        return to_return

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

        A blocking call.
        '''
        if message is not None:
            self.print(message)
        return input('>> ')



