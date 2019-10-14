
import os
import msvcrt

import core


class TextUI:
    '''
    A simple text based user interface pseudopupil imaging.
    '''

    def __init__(self):
        self.dynamic = core.Dynamic()

        self.menutext = "Pupil Imsoft TUI (Text user interface)"

        self.choices = {'Static imaging': self.loop_static,
                'Dynamic imaging': self.loop_dynamic,
                'Quit': self.quit}

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
    @staticmethod
    def _print_lines(lines):
        
        for text in lines:
            print(text)
        

    def _selectItem(self, items):
        '''
        Select an item from a list.
        '''
        for i, item in enumerate(items):
            print('{}) {}'.format(i, item))
        
        selection = ''
        while True:
            selection += self._readKey()
            if selection.endswith('\r') or selection.endswith('\n'):
                try:
                    selection = int(selection)
                    break
                except ValueError:
                    print('Invalid input')
                    selection = ''
        return items[selection]


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

        upper_lines = ['-','Dynamic imaging', '-', 'Help F1', 'Space ']

        while True:
            
            lines = upper_lines

            key = self._readKey()
            
            if key == 112:
                lines.append('')

            if key == ' ':
                self.dynamic.image_Series()
            elif key == '0':
                self.dynamic.set_zero()
            elif key == 's':
                self.dynamic.take_snap(save=True)
            elif key == '\r':
                # If user hits enter we'll exit
                break

            elif key == '[':
                self.dynamic.motors[0].move_raw(-1)
            elif key == ']':
                self.dynamic.motors[0].move_raw(1)
            
            elif key == 'o':
                self.dynamic.motors[1].move_raw(-1)
            elif key == 'p':
                self.dynamic.motors[1].move_raw(1)

            elif key == 'l':
                self.dynamic.motors[2].move_raw(-1)
            elif key == ';':
                self.dynamic.motors[2].move_raw(1)

            elif key == '`':
                command = input("Type command >> ").split(' ')
                
                # Setting and getting motor limits
                if command[0] == 'limit':
                    if command[1] == 'set':
                        if command[2] == 'upper':
                            self.dynamic.motors[int(command[3])].set_upper_limit()
                        elif command[2] == 'lower':
                            self.dynamic.motors[int(command[3])].set_lower_limit()
                    
                    if command[1] == 'get':
                        mlim = self.dynamic.motors[int(command[2])].get_limits()
                        print('  Motor {} limited at {} lower and {} upper'.format(command[2], *mlim))


                # Getting motor's position
                if command[0] == 'where':
                    mpos = self.dynamic.motors[int(command[1])].get_position()
                    print('  Motor {} at {}'.format(command[1], mpos))


                # Driving a motor to specific position
                if command[0] == 'drive':
                    self.dynamic.motors[int(command[1])].move_to(float(command[2]))
                
                if command[0] == 'macro':
                    if len(command) == 1:
                        print('Following macros are available')
                        for line in self.dynamic.list_macros():
                            print(line)
                    else:
                        self.dynamic.run_macro(command[1])


            elif key == '':
                # When there's no input just update the live feed
                self.dynamic.take_snap(save=False)
            
            
            #self._clearScreen()
            #self._print_lines(lines)

            self.dynamic.tick()

        self.dynamic.finalize()

    
    def run(self):
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

def main():
    tui = TextUI()
    tui.run()

if __name__ == "__main__":
    main()
