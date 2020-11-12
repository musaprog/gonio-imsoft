
import os
import copy
import platform
import string
import time

OS = platform.system()
if OS == 'Windows':
    import msvcrt
else:
    pass

import core

help_string = """List of commands and their options\n
GENERAL
 help                       Prints this message
 suffix [SUFFIX]            Add a suffix SUFFIX to saved image folders
MOTORS
 where [i_motor]            Prints the coordinates of motor that has index i_motor
 drive [i_motor] [pos]      Drive i_motor to coordinates (float)


"""

help_limit = """Usage of limit command
limit []"""


class Console:
    '''
    Operation console for TUI or other user interfaces.

    Capabilities:
    - changing imaging parameters
    - setting save suffix
    - controlling motors and setting their limits
    
    In tui, this console can be opened by pressing ` (the keyboard button next to 1)
    '''
    def __init__(self, core_dynamic):
        '''
        core_dynamic        An instance of core.Dynamic class.
        '''
        self.dynamic = core_dynamic


    def enter(self, command):
        '''
        Calling a command 
        '''
        command_name = command.split(' ')[0]
        args = command.split(' ')[1:]

        if hasattr(self, command_name):
            method = getattr(self, command_name)
            try:
                method(*args)
            except TypeError as e:
                print(e)
                self.help()
                
        else:
            print('Command {} does not exit'.format(command_name))
            self.help()
    

    def help(self):
        '''
        Print the help string on screen.
        '''
        print(help_string)
    

    def suffix(self, suffix):
        '''
        Set suffix to the image folders being saved
        '''
        # Replaces spaces by underscores
        if ' ' in suffix:
            suffix = suffix.replace(' ', '_')
            print('Info: Replaced spaces in the suffix with underscores')
        
        # Replace illegal characters by x
        legal_suffix = ""
        for letter in suffix:
            if letter in string.ascii_letters+'_()-'+'0123456789.':
                legal_suffix += letter
            else:
                print('Replacing illegal character {} with x'.format(letter))
                legal_suffix += 'x'
        
        print('Setting suffix {}'.format(legal_suffix))
        self.dynamic.set_subfolder_suffix(legal_suffix)


    def limitset(self, side, i_motor):
        '''
        Sets the current position as a limit.

        action      "set" or "get"
        side        "upper" or "lower"
        i_motor     0, 1, 2, ...
        '''
        
        if side == 'upper':
            self.dynamic.motors[i_motor].set_upper_limit()
        elif side == 'lower':
            self.dynamic.motors[i_motor].set_lower_limit()
   

    def limitget(self, i_motor):
        '''
        Gets the current limits of a motor
        '''
        mlim = self.dynamic.motors[i_motor].get_limits()
        print('  Motor {} limited at {} lower and {} upper'.format(i_motor, *mlim))


    def where(self, i_motor):
        # Getting motor's position
        mpos = self.dynamic.motors[motor].get_position()
        print('  Motor {} at {}'.format(motor, mpos))

    def drive(self, i_motor, position):
        self.dynamic.motors[i_motor].move_to(position)
        

                # Driving a motor to specific position
    def macro(self, command, macro_name):
        '''
        Running and setting macros (automated imaging sequences.)
        '''
        if command == 'run':
            self.dynamic.run_macro(macro_name)
        elif command == 'list':

            print('Following macros are available')
            for line in self.dynamic.list_macros():
                print(line)

        elif command == 'stop':
            for motor in self.dynamic.motors:
                motor.stop()

    def set_roi(self, x,y,w,h):
        self.dynamic.camera.set_roi( (x,y,w,h) )


    def eternal_repeat(self, isi):

        isi = float(isi)
        print(isi)
        
        suffix = "eternal_repeat_isi{}s".format(isi)
        suffix = suffix + "_rep{}"
        i_repeat = 0
        
        while True:
            self.suffix(suffix.format(i_repeat))

            start_time = time.time()
            
            if self.dynamic.image_series(inter_loop_callback=self.image_series_callback) == False:
                break
            i_repeat += 1

            sleep_time = isi - float(time.time() - start_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def chain_presets(self, delay, *preset_names):
        '''
        Running multiple presets all one after each other,
        in a fixed (horizonta, vertical) location.

        delay       In seconds, how long to wait between presets
        '''
        delay = float(delay)
        original_parameters = copy.copy(self.dynamic.dynamic_parameters)

        
        print('Repeating presets {}'.format(preset_names))
        for preset_name in preset_names:
            print('Preset {}'.format(preset_name))
            
            self.dynamic.load_preset(preset_name)
            
            if self.dynamic.image_series(inter_loop_callback=self.image_series_callback) == False:
                break

            time.sleep(delay)

        print('Finished repeating presets')
        self.dynamic.dynamic_parameters = original_parameters

            

class TextUI:
    '''
    A simple text based user interface pseudopupil imaging.
    '''

    def __init__(self):
        self.dynamic = core.Dynamic()
        
        # Initial selection of the experimenter
        self.experimenters = ['Andra', 'James', 'Joni', 'Joni2']

        # Main menu
        self.menutext = "Pupil Imsoft TUI (Text user interface)"
    
        self.choices = {'Static imaging': self.loop_static,
                'Dynamic imaging': self.loop_dynamic,
                'Quit': self.quit,
                'Start camera server': self.dynamic.camera.startServer,
                'Stop camera server': self.dynamic.camera.close_server}

        self.quit = False

        self.console = Console(self.dynamic)
        self.console.image_series_callback = self.image_series_callback


    @staticmethod
    def _readKey():
        if OS == 'Windows':
            if msvcrt.kbhit():
                key = ord(msvcrt.getwch())
                return chr(key)
            return ''
        else:
            raise NotImplementedError("Linux nonblocking read not yet implemented")

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
            print('{}) {}'.format(i+1, item))
        
        selection = ''
        while True:
            new_char = self._readKey()
            if new_char:
                selection += new_char
                print(selection)
            if selection.endswith('\r') or selection.endswith('\n'):
                try:
                    selection = int(selection)
                    items[selection-1]
                    break
                except ValueError:
                    print('Invalid input')
                    selection = ''
                except IndexError:
                    print('Invalid input')
                    selection = ''
        return items[selection-1]


    def loop_static(self):
        '''
        Running the static imaging protocol.
        '''
        raise NotImplementedError('Static imaging UI not yet implemeted in TUI')

    def image_series_callback(self, label, i_repeat):
        '''
        Callback passed to image_series
        '''
        if label:
            print(label)
        
        key = self._readKey()

        if key == '\r':
            # If Enter presed return False, stopping the imaging
            print('User pressed enter, stopping imaging')
            return False
        else:
            return True

    def loop_dynamic(self):
        '''
        Running the dynamic imaging protocol.
        '''
        self.dynamic.set_savedir(os.path.join('imaging_data_'+self.experimenter))
        name = input('Name ({})>> '.format(self.dynamic.preparation['name']))
        sex = input('Sex ({})>> '.format(self.dynamic.preparation['sex']))
        age = input('Age ({})>> '.format(self.dynamic.preparation['age']))
        self.dynamic.initialize(name, sex, age)

        upper_lines = ['-','Dynamic imaging', '-', 'Help F1', 'Space ']

        while True:
            
            lines = upper_lines

            key = self._readKey()
            
            if key == 112:
                lines.append('')

            if key == ' ':
                self.dynamic.image_series(inter_loop_callback=self.image_series_callback)
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
                user_input = input("Type command >> ")
                self.console.enter(user_input)

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

        print('\nSelect experimenter')
        self.experimenter = self._selectItem(self.experimenters).lower()
        self._clearScreen()

        self.quit = False
        while not self.quit:
            print(self.menutext)
            
            selection = self._selectItem(list(self.choices.keys()))
            self.choices[selection]()

            self._clearScreen()

        self.core.exit()
        time.sleep(1)

    def quit(self):
        self.quit = True

def main():
    tui = TextUI()
    tui.run()

if __name__ == "__main__":
    main()
