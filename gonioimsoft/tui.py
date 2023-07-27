'''Terminal user interface for GonioImsoft.

It uses a GonioImsoftCore instance to manage the experiments and
libtui.SimpleTUI to make the user interface.
'''

import os
import copy
import string
import time
import json
import inspect      # Inspect docs and source code

from gonioimsoft.version import __version__
from gonioimsoft.directories import (
        USERDATA_DIR,
        IS_USERDATA_INITIALIZED,
        initialize_userdata,
        )
from gonioimsoft.core import GonioImsoftCore, nidaqmx
from gonioimsoft.imaging_parameters import (
        DEFAULT_DYNAMIC_PARAMETERS,
        ParameterEditor,
        )
from .libtui import SimpleTUI


class Console:
    '''A command console for terminal user interface (tui).
    
    This console allows inputting commands with arguments within
    the tui. It is needed when simple keyboard shortcut is not enough.

    Attributes
    ----------
    core : obj
        The GonioImsoftCore instance this console operates on.
    '''
    def __init__(self, core):
        self.core = core


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
    

    def help(self, command_name=None):
        if command_name is None:
            print('List of commands and their options')
            
            for name, value in inspect.getmembers(self):
                
                if not inspect.ismethod(value):
                    continue

                print(f'{name}')

            print('For more, try retrieving the full help or the source code by')
            print('  help [command_name]')
            print('  source [command name]')
        else:
            value = getattr(self, command_name, None)

            if value is not None:
                print(inspect.getdoc(value))


    def source(self, command_name):
        print(f'Source code of the "{command_name}" command (Python)')
        
        print('End of source code.')

    def suffix(self, suffix):
        '''Set the suffix to add in the image folders' save name
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
        self.core.set_subfolder_suffix(legal_suffix)


    def limitset(self, side, i_motor):
        '''
        Sets the current position as a limit.

        action      "set" or "get"
        side        "upper" or "lower"
        i_motor     0, 1, 2, ...
        '''
        
        if side == 'upper':
            self.core.motors[i_motor].set_upper_limit()
        elif side == 'lower':
            self.core.motors[i_motor].set_lower_limit()
   

    def limitget(self, i_motor):
        '''
        Gets the current limits of a motor
        '''
        mlim = self.core.motors[i_motor].get_limits()
        print('  Motor {} limited at {} lower and {} upper'.format(i_motor, *mlim))


    def where(self, i_motor):
        '''Prints the coordinates of the motor i_motor.
        '''
        # Getting motor's position
        mpos = self.core.motors[motor].get_position()
        print('  Motor {} at {}'.format(motor, mpos))


    def drive(self, i_motor, position):
        '''Drive i_motor to the given coordinates.
        '''
        self.core.motors[i_motor].move_to(position)
        

    def macro(self, command, macro_name):
        '''
        Running and setting macros (automated imaging sequences.)
        '''
        if command == 'run':
            self.core.run_macro(macro_name)
        elif command == 'list':

            print('Following macros are available')
            for line in self.core.list_macros():
                print(line)

        elif command == 'stop':
            for motor in self.core.motors:
                motor.stop()


    def set_roi(self, x,y,w,h, i_camera=None):
        if i_camera is None:
            for camera in self.core.cameras:
                camera.set_roi((x,y,w,h))
        else:
            self.core.cameras[i_camera].set_roi( (x,y,w,h) )


    def eternal_repeat(self, isi):

        isi = float(isi)
        print(isi)
        
        suffix = "eternal_repeat_isi{}s".format(isi)
        suffix = suffix + "_rep{}"
        i_repeat = 0
        
        while True:
            self.suffix(suffix.format(i_repeat))

            start_time = time.time()
            
            if self.core.image_series(inter_loop_callback=self.image_series_callback) == False:
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
        original_parameters = copy.copy(self.core.dynamic_parameters)

        
        print('Repeating presets {}'.format(preset_names))
        for preset_name in preset_names:
            print('Preset {}'.format(preset_name))
            
            self.core.load_preset(preset_name)
            
            if self.core.image_series(inter_loop_callback=self.image_series_callback) == False:
                break

            time.sleep(delay)

        print('Finished repeating presets')
        self.core.dynamic_parameters = original_parameters

            
    def set_rotation(self, horizontal, vertical):
        ho = int(horizontal)
        ve = int(vertical)
        cho, cve = self.core.reader.latest_angle
        
        self.core.reader.offset = (cho-ho, cve-ve)



class GonioImsoftTUI:
    '''Terminal user interface for goniometric imaging.

    Attributes
    ----------
    core : obj
        The GonioImsoftCore instance
    console : object
    main_menu : list
        Main choices
    quit : bool
        If changes to True, quit.
    expfn : string
        Filename of the experiments.json file
    '''
    def __init__(self):
        
        self.libui = SimpleTUI()
        self.core = GonioImsoftCore()

        self.console = Console(self.core)
        self.console.image_series_callback = self.image_series_callback


        # Get experimenters list or if not present, use default
        self.expfn = os.path.join(USERDATA_DIR, 'experimenters.json')
        if os.path.exists(self.expfn):
            try:
                with open(self.expfn, 'r') as fp: self.experimenters = json.load(fp)
            except:
                self.experimenters = ['gonioims']
        else:
            self.experimenters = ['gonioims']
        


        self.experimenter = None    # name of the experimenter
        self.quit = False


    @property
    def main_menu(self):
        menu = [
                ['Normal imaging', self.loop_dynamic],
                ['Step-trigger imaging (takes an image on each goniometer step)', self.loop_static],
                ['Step-trigger (triggers only; use external camera software)', self.loop_trigger],
                ['\n', None],
                [f'Change savefolder (current: {self.experimenter})', self._run_experimenter_select],
                ['Quit', self.quit],
                ['\n', None],
                ['Add a local camera', self.add_local_camera],
                ['Add a remote camera', self.add_remote_camera],
                ['Edit camera settings', self.camera_settings_edit],
                ['Remove camera', self.remove_camera]]
        return menu


    def _add_camera(self, client):
        cameras = client.get_cameras()
        camera = self.libui.item_select(
                cameras, 'Select a camera')
        client.set_camera(camera)
        
        try:
            client.load_state('previous')
        except FileNotFoundError:
            self.libui.print('Could not find previous settings for this camera')
        
        # Part of the dirty fix
        client.set_roi((0,0,1024,1024))


    def add_local_camera(self):
        '''Add a camera from a local camera server.
        '''
        client = self.core.add_camera_client(None, None)
        self._add_camera(client)


    def add_remote_camera(self):
        cancels = 'back'
        self.libui.input(f'# Type in {cancels} to cancel')

        host = self.libui.input('IP address or hostname', cancels)
        if host is None:
            return
        port = self.libui.input('Port (leave blank for default): ', cancels)
        if port is None:
            return

        if port == '':
            port = None
        else:
            port = int(port)

        client = self.core.add_camera_client(host, port)
        
        if not client.is_server_running:
            self.libui.print('Cannot connect to the server')
        else:
            self._add_camera(client)

    def remove_camera(self):
        names = [cam.get_camera() for cam in self.core.cameras]
        selection = self.libui.item_select(
                names+['..back'], 'Select camera to remove')

        if selection != '..back':
            index = names.index(selection)
            self.core.remove_camera_client(index)

    @property
    def menutext(self):
        cam = ''

        # Check camera server status
        for i_camera, camera in enumerate(self.core.cameras):
            if camera.is_server_running():
                cam_name = camera.get_camera()
                if cam_name:
                    cs = f'{cam_name}\n'
                else:
                    cs = 'No camera selected\n'
            else:
                cs = 'Offline'

            cam += f'Cam{i_camera} {cs}'

        if not self.core.cameras:
            cam = 'No cameras'

        # Check serial (Arduino) status
        ser = self.core.reader.serial
        if ser is None:
            ar = 'Serial UNAVAIBLE'
        else:
            if ser.is_open:
                ar = 'Serial OPEN ({} @{} Bd)'.format(
                        ser.port, ser.baudrate)
            else:
                ar = 'Serial CLOSED'

        # Check DAQ
        if nidaqmx is None:
            daq = 'UNAVAILABLE'
        else:
            daq = 'AVAILABLE'

        status = "\n {} | {} | nidaqmx {}".format(cam, ar, daq)
        
        menutext = "GonioImsoft - Version {}".format(__version__)
        menutext += "\n" + max(len(menutext), len(status)) * "-"
        menutext += status
        return menutext + "\n"


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
        
        key = self.libui.read_key()

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
        
        self.core.set_savedir(os.path.join('imaging_data_'+self.experimenter), camera=camera)

        cancels = 'back'
        self.libui.print(f'# Enter specimen metadata (enter {cancels} to cancel)\n')

        name = self.libui.input(
                'Name ({})'.format(self.core.preparation['name']), cancels)
        if name is None: return

        sex = self.libui.input(
                'Sex ({})'.format(self.core.preparation['sex']), cancels)
        if sex is None: return

        age = self.libui.input(
                'Age ({})'.format(self.core.preparation['age']), cancels)
        if age is None: return

        if self.core.initialize(name, sex, age, camera=camera) is None:
            return

        upper_lines = ['-','Dynamic imaging', '-', 'Help F1', 'Space ']

        self.libui.clear_screen()


        help_string = "# This part of the program works by keyboard shortcuts\n"
        if static:
            help_string += '#   space      Toggle trigger-by-rotation on/off\n'
        else:
            help_string += "#   space      Run imaging\n"
        help_string += (
                '#   enter      Return back to the main menu\n'
                "#   0          Set current rotation as (0,0)\n"
                "#   s          Take a snap image\n"
                '#   e          Edit imaging parameters again\n'
                '#   h          Print this help again\n'
                "#   ` (tilde)  Open command console (type in help for help)\n"
                "# \n"
                "# Rotation stage changes will be printed here.\n"
                "# Separate windows for the added cameras should open\n"
                )
        if self.core.cameras:
            help_string += (
                    '# You have not added any cameras. Space only triggers.\n'
                    '# Return to the main menu to add local cameras.\n'
                    )
        else:
            help_string += (
                    '# Separate windows for the added cameras should open\n'
                    )


        self.libui.print(help_string)

        while True:
            
            lines = upper_lines

            key = self.libui.read_key()

            if static:
                if trigger and self.core.trigger_rotation:
                    if camera:
                        self.core.image_series(inter_loop_callback=self.image_series_callback)
                    else:
                        self.core.send_trigger()
                if key == ' ':
                    trigger = not trigger
                    print('Rotation triggering now set to {}'.format(trigger))
            else:
                if key == ' ':
                    if camera:
                        self.core.image_series(inter_loop_callback=self.image_series_callback)
                    else:
                        self.core.send_trigger()
            
            if key == 112:
                lines.append('')
            elif key == '0':
                self.core.set_zero()
            elif key == 's':
                if camera:
                    self.core.take_snap(save=True)
            elif key == '\r':
                # If user hits enter we'll exit
                break
            elif key == 'e':
                if self.core.initialize(name, sex, age, camera=camera) is None:
                    continue
            elif key == 'h':
                self.libui.print(help_string)
            elif self.core.motors:
                if key == '[':
                    self.core.motors[0].move_raw(-1)
                elif key == ']':
                    self.core.motors[0].move_raw(1)
                
                elif key == 'o':
                    self.core.motors[1].move_raw(-1)
                elif key == 'p':
                    self.core.motors[1].move_raw(1)

                elif key == 'l':
                    self.core.motors[2].move_raw(-1)
                elif key == ';':
                    self.core.motors[2].move_raw(1)
            elif key == '`':
                user_input = self.libui.input("Type command >> ", '')
                if user_input is None:
                    continue
                self.console.enter(user_input)

            elif key == '' and not (static and self.core.trigger_rotation):
                if camera:
                    # When there's no input just update the live feed
                    self.core.take_snap(save=False)
            
            
            #self._clearScreen()
            #self._print_lines(lines)

            self.core.tick()

        self.core.finalize()


    
    def _run_firstrun(self):
        message = (
                '\nHello and welcome! This is your first run.\n'
                '\n'
                'GonioImsoft needs a location '
                'to save user files\n- list of savefolders\n'
                '- camera states\n'
                '- macros\n'
                '- presets\n'
                '\n'
                f'The location is {os.path.abspath(USERDATA_DIR)}\n'
                'No imaging data or big files will be saved here.\n'
                f'\nCreate {USERDATA_DIR}? (yes recommended)\n'
                )
        if self.libui.bool_select(message):
            initialize_userdata()
            print('Success!')
            time.sleep(2)
        else:
            print('Warning! Cannot save any changes')
            time.sleep(2)


    def _run_experimenter_select(self):

        if self.experimenter is not None:
            self.libui.print(f'Current savefolder: {self.experimenter}')

        extra_options = [' (Add new)', ' (Remove old)', ' (Save current list)']

        self.libui.print('Select savefolder\n--------------------')
        while True:
            # Select operation
            selection = self.libui.item_select(self.experimenters+extra_options) 

            self.libui.clear_screen()
            
            # add new
            if selection == extra_options[0]:
                cancels = 'back'
                self.libui.print(f'# Adding new user (enter {cancels} to cancel)')
                name = self.libui.input('Name >>', cancels)
                if name is None:
                    continue
                self.experimenters.append(name)

            # remove old
            elif selection == extra_options[1]:
                self.libui.print('Select who to remove (data remains)')
                
                to_delete_name = self.libui.item_select(
                        self.experimenters+['..back (no deletion)'])

                if to_delete_name in self.experimenters:
                    self.experimenters.pop(self.experimenters.index(to_delete_name))

            # save current
            elif selection == extra_options[2]:
                if os.path.isdir(USERDATA_DIR):
                    with open(self.expfn, 'w') as fp: json.dump(self.experimenters, fp)
                    print('Saved!')
                else:
                    print(f'Saving failed (no {USERDATA_DIR})')
                time.sleep(2)
            else:
                # Got a name
                break

            self.libui.clear_screen()

        self.experimenter = selection
 

    def run(self):
        '''
        Run TUI until user quitting.
        '''
        
        self.libui.header = self.menutext
        self.libui.clear_screen()
 
        # Check if userdata directory settings exists
        # If not, ask to create it
        if not IS_USERDATA_INITIALIZED:
            self._run_firstrun()
            self.libui.clear_screen()
        else:
            # Already initialized, just check all subfolders present
            # in newer versions are also there
            initialize_userdata()
        
        self._run_experimenter_select()
        self.libui.clear_screen()

        self.quit = False
        while not self.quit:
            self.libui.clear_screen()
            
            menuitems = [x[0] for x in self.main_menu]
            
            # Blocking call here
            selection = self.libui.item_select(menuitems)

            self.libui.clear_screen()
            self.main_menu[menuitems.index(selection)][1]()

            # Update status menu and clear screen
            self.libui.header = self.menutext

        self.core.exit()

    
    def camera_settings_edit(self):
        '''View to select a camera and edit it's settings
        '''
        
        while True:

            camera = self.libui.item_select(
                    self.core.cameras+['..back'],
                    "Select the camera to edit")
            
            if camera == '..back':
                break
            
            while True:
                setting_name = self.libui.item_select(
                        camera.get_settings()+['..back'],
                        "Select the setting to edit")

                if setting_name == '..back':
                    break
                
                value = camera.get_setting(setting_name)
                value_type = camera.get_setting_type(setting_name)

                self.libui.print(f'{setting_name} ({value_type})')
                self.libui.print(f'Current value: {value}')
                new_value = self.libui.input('New value: ')

                camera.set_setting(setting_name, new_value)
                
                self.libui.clear_screen()
                
                camera.save_state('previous')

    def quit(self):
        self.quit = True



def main():
    imsoft = GonioImsoftTUI()
    imsoft.run()

if __name__ == "__main__":
    main()
