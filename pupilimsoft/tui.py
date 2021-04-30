
import os
import copy
import platform
import string
import time
import json

OS = platform.system()
if OS == 'Windows':
    import msvcrt
else:
    import sys

from pupilimsoft.directories import PUPILDIR
import pupilimsoft.core as core


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

            
    def set_rotation(self, horizontal, vertical):
        ho = int(horizontal)
        ve = int(vertical)
        cho, cve = self.dynamic.reader.latest_angle
        
        self.dynamic.reader.offset = (cho-ho, cve-ve)
        

class TextUI:
    '''
    A simple text based user interface pseudopupil imaging.
    '''

    def __init__(self):
        self.dynamic = core.Dynamic()
        
        # Get experimenters list or if not present, use default
        self.expfn = os.path.join(PUPILDIR, 'experimenters.json')
        if os.path.exists(self.expfn):
            try:
                with open(self.expfn, 'r') as fp: self.experimenters = json.load(fp)
            except:
                self.experimenters = ['pupilims']
        else:
            self.experimenters = ['pupilims']

        # Main menu
        self.menutext = "Pupil Imsoft TUI (Text user interface)"
    
        self.choices = {'Static imaging': self.loop_static,
                'Dynamic imaging': self.loop_dynamic,
                'Trigger only (external software for camera)': self.loop_trigger,
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
            return sys.stdin.read(1)

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


    def loop_trigger(self):
        '''
        Simply NI trigger when change in rotatory encoders, leaving camera control
        to an external software (the original loop static).
        
        Space to toggle triggering.
        '''
        self.loop_dynamic(static=True, camera=False)
                

    def loop_static(self):
        '''
        Running the static imaging protocol.
        '''
        self.loop_dynamic(static=True)
        


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

    def loop_dynamic(self, static=False, camera=True):
        '''
        Running the dynamic imaging protocol.

        static : bool
            If False, run normal imaging where pressing space runs the imaging protocol.
            If True, run imaging when change in rotary encoders (space-key toggled)
        camera : bool
            If True, control camera.
            If False, assume that external program is controlling the camera, and send trigger
        '''
        trigger = False

        self.dynamic.set_savedir(os.path.join('imaging_data_'+self.experimenter), camera=camera)
        name = input('Name ({})>> '.format(self.dynamic.preparation['name']))
        sex = input('Sex ({})>> '.format(self.dynamic.preparation['sex']))
        age = input('Age ({})>> '.format(self.dynamic.preparation['age']))
        self.dynamic.initialize(name, sex, age, camera=camera)

        upper_lines = ['-','Dynamic imaging', '-', 'Help F1', 'Space ']

        while True:
            
            lines = upper_lines

            key = self._readKey()

            if static:
                if trigger and self.dynamic.trigger_rotation:
                    if camera:
                        self.dynamic.image_series(inter_loop_callback=self.image_series_callback)
                    else:
                        self.dynamic.send_trigger()
                if key == ' ':
                    trigger = not trigger
                    print('Rotation triggering now set to {}'.format(trigger))
            else:
                if key == ' ':
                    if camera:
                        self.dynamic.image_series(inter_loop_callback=self.image_series_callback)
                    else:
                        self.dynamic.send_trigger()
            
            if key == 112:
                lines.append('')
            elif key == '0':
                self.dynamic.set_zero()
            elif key == 's':
                if camera:
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

            elif key == '' and not (static and self.dynamic.trigger_rotation):
                if camera:
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
        # Check if userdata directory settings exists
        if not os.path.isdir(PUPILDIR):
            print('\nFIRST RUN NOTICE\n------------------')
            print(('Pupil Imsoft needs a location where '
                'to save user files\n  - list of experimenters\n  - settings'
                '\n  - created protocol files'))
            print('This is not the location where imaging data gets saved (no big files)')
            print('\nCreate {}'.format(PUPILDIR))

            while True:
                sel = input ('(yes/no) >> ').lower()
                if sel == 'yes':
                    os.makedirs(PUPILDIR)
                    print('Sucess!')
                    time.sleep(2)
                    break
                elif sel == 'no':
                    print('Warning! Cannot save any changes')
                    time.sleep(2)
                    break
                else:
                    print('Whaat? Please try again')
                    time.sleep(1)
            
        
        self._clearScreen()
        
        print(self.menutext)
        
        print('\nSelect experimenter\n--------------------')
        while True:
            extra_options = [' (Add new)', ' (Remove old)', ' (Save current list)']
            experimenter = self._selectItem(self.experimenters+extra_options).lower()
            
            # Select operation
            if experimenter == '(add new)':
                name = input('Name >>')
                self.experimenters.append(name)

            elif experimenter == '(remove old)':
                print('Select who to remove (data remains)')
                name = self._selectItem(self.experimenters+['..back (no deletion)'])

                if name in self.experimenters:
                    self.experimenters.pop(self.experimenters.index(name))
            elif experimenter == '(save current list)':
                if os.path.isdir(PUPILDIR):
                    with open(self.expfn, 'w') as fp: json.dump(self.experimenters, fp)
                    print('Saved!')
                else:
                    print('Saving failed (no {})'.format(PUPILDIR))
                time.sleep(2)
            else:
                # Got a name
                break

            self._clearScreen()

        self.experimenter = experimenter
        self._clearScreen()

        self.quit = False
        while not self.quit:
            print(self.menutext)
            
            selection = self._selectItem(list(self.choices.keys()))
            self.choices[selection]()

            self._clearScreen()

        self.dynamic.exit()
        time.sleep(1)


    def quit(self):
        self.quit = True



def main():
    tui = TextUI()
    tui.run()

if __name__ == "__main__":
    main()
