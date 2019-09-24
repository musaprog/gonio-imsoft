
import os
import msvcrt

import core


class TUI:
    '''
    A simple text based user interface pseudopupil imaging.
    '''

    def __init__(self):
        self.dynamic = core.Dynamic()

        self.menutext = "Pupil Imsoft TUI (Text user interface)"

        self.choices = {'Static imaging': self.loop_static,
                'Dynamic imaging': self.loop_dynamic,
                'Quit', self.quit}

        self.quit = False


    @staticmethod
    def _readKey():
        if msvcrt.kbhit():
            key = ord(msvcrt.getwch())
            return chr(key)
        return ''


    @staticmethod
    def _clearScreen():
        if os.name == 'posix':
            os.system('clear')
        elif os.name == 'nt':
            os.system('cls')


    def _selectItem(self, items):
        '''
        Select an item from a list.
        '''
        for i, item in enumerate(items):
            print('{}) {}'.format(i, item))
        
        selection + ''
        while True:
            selection += self._readKey()
            if selection.endswith('\r') or selection.endswith('\n'):
                try:
                    selection = int(selection)
                    break
                except ValueError:
                    print('Invalid input')
                    selection = ''
        return selection


    def loop_static(self):
        '''
        Running the static imaging protocol.
        '''
        raise NotImplementedError('Static imaging UI not yet implemeted in TUI')


    def loop_dynamic(self):
        '''
        Running the dynamic imaging protocol.
        '''

        self.dynamic.initialize(input('Name >> '), input('Sex >> '), input('Age >> '))

        while True:

            key = self._readKey()

            if key == ' ':
                self.dynamic.imageSeries()
            elif key == '0':
                self.dynamic.setZero()
            elif key == 's':
                self.dynamic.takeSnap(save=True)
            elif key == '\r':
                # If user hits enter we'll exit
                break
            elif key == '[':
                self.dynamic.focus_in()
            elif key == ']'
                self.dynamic.focus_out()
            elif key == '':
                # When there's no input just update the live feed
                self.dynamic.takeSnap(save=False)

            self.dynamic.tick()

        self.dynamic.finalize()

    
    def run():
        '''
        Run TUI until user quitting.
        '''
        
        self.quit = False
        while not self.quit:
            print(self.menutext)
            
            selection = self._selectItem(list(self.choices.keys()))
            self.choices[selection]()

            self._clearScreen()


    def quit():
        self.quit = True
