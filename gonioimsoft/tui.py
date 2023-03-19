'''Terminal user interface for GonioImsoft.

It uses gonioimsoft.core to to manage the experiments
and libtui.SimpleTUI to make the user interface. 
'''

import os
import copy
import string
import time
import json
import inspect      # Inspect docs and source code

from gonioimsoft.version import __version__
from gonioimsoft.directories import USERDATA_DIR
import gonioimsoft.core as core
from gonioimsoft.imaging_parameters import (
        DEFAULT_DYNAMIC_PARAMETERS,
        ParameterEditor,
        )
from .libtui import SimpleTUI


class Console:
    '''Operation console for TUI or other user interfaces.

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
        '''Prints the coordinates of the motor i_motor.
        '''
        # Getting motor's position
        mpos = self.dynamic.motors[motor].get_position()
        print('  Motor {} at {}'.format(motor, mpos))


    def drive(self, i_motor, position):
        '''Drive i_motor to the given coordinates.
        '''
        self.dynamic.motors[i_motor].move_to(position)
        

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


    def set_roi(self, x,y,w,h, i_camera=None):
        if i_camera is None:
            for camera in self.dynamic.cameras:
                camera.set_roi((x,y,w,h))
        else:
            self.dynamic.cameras[i_camera].set_roi( (x,y,w,h) )


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



class GonioImsoftTUI:
    '''Terminal user interface for goniometric imaging.

    Attrubutes
    ----------
    console : object
    main_menu : list
        Main choices
    quit : bool
        If changes to True, quit.
    expfn : string
        Filename of the experiments.json file
    glofn : string
        Filename of the locked parameters setting name

    '''
    def __init__(self):
        
        self.libui = SimpleTUI()
        self.dynamic = core.Dynamic()

        self.console = Console(self.dynamic)
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
        

        # Get locked parameters
        self.glofn = os.path.join(USERDATA_DIR, 'locked_parameters.json')
        if os.path.exists(self.glofn):
            try:
                 with open(self.glofn, 'r') as fp: self.locked_parameters = json.load(fp)
            except:
                self.locked_parameters = {}
        else:
            self.locked_parameters = {}
            
   
        self.main_menu = [
                ['Imaging', self.loop_dynamic],
                ['Step-trigger imaging', self.loop_static],
                ['Step-trigger only (use external camera software)', self.loop_trigger],
                ['\n', None],
                ['Edit locked parameters', self.locked_parameters_edit],
                ['\n', None],
                ['Change experimenter', self._run_experimenter_select],
                ['Quit', self.quit],
                ['\n', None],
                ['Add local camera', self.add_local_camera],
                ['Add remote camera', self.add_remote_camera],
                ['Edit camera settings', self.camera_settings_edit]]
        #['Start camera server (local)', self.dynamic.camera.startServer],
        #['Stop camera server', self.dynamic.camera.close_server]

        self.experimenter = None    # name of the experimenter
        self.quit = False


    def _add_camera(self, client):
        cameras = client.get_cameras()
        camera = self.libui.item_select(
                cameras, 'Select a camera')
        client.set_camera(camera)
        
        try:
            client.load_state('previous')
        except FileNotFoundError:
            self.libui.print('Could not find previous settings for this camera')

    def add_local_camera(self):
        '''Add a camera from a local camera server.
        '''
        client = self.dynamic.add_camera_client(None, None)
        
        if not client.isServerRunning():
            client.startServer()
        
        self._add_camera(client)


    def add_remote_camera(self):
        host = self.libui.input('IP address or hostname: ')
        port = self.libui.input('Port (leave blank for default): ')
        
        if port == '':
            port = None
        else:
            port = int(port)

        client = self.dynamic.add_camera_client(host, port)
        
        if not client.isServerRunning:
            self.libui.print('Cannot connect to the server')
        else:
            self._add_camera(client)


    @property
    def menutext(self):
        cam = ''

        # Check camera server status
        for i_camera, camera in enumerate(self.dynamic.cameras):
            if camera.isServerRunning():
                cam_name = camera.get_camera()
                if cam_name:
                    cs = f'{cam_name}\n'
                else:
                    cs = 'No camera selected\n'
            else:
                cs = 'Offline'

            cam += f'Cam{i_camera} {cs}'

        if not self.dynamic.cameras:
            cam = 'No cameras'

        # Check serial (Arduino) status
        ser = self.dynamic.reader.serial
        if ser is None:
            ar = 'Serial UNAVAIBLE'
        else:
            if ser.is_open:
                ar = 'Serial OPEN ({} @{} Bd)'.format(
                        ser.port, ser.baudrate)
            else:
                ar = 'Serial CLOSED'

        # Check DAQ
        if core.nidaqmx is None:
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
        
        self.dynamic.locked_parameters = self.locked_parameters
        
        self.dynamic.set_savedir(os.path.join('imaging_data_'+self.experimenter), camera=camera)
        name = input('Name ({})>> '.format(self.dynamic.preparation['name']))
        sex = input('Sex ({})>> '.format(self.dynamic.preparation['sex']))
        age = input('Age ({})>> '.format(self.dynamic.preparation['age']))
        self.dynamic.initialize(name, sex, age, camera=camera)

        upper_lines = ['-','Dynamic imaging', '-', 'Help F1', 'Space ']

        while True:
            
            lines = upper_lines

            key = self.libui.read_key()

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


    
    def _run_firstrun(self):
        message = (
                '\nFIRST RUN\n---------'
                'GonioImsoft needs a location '
                'to save user files\n  - list of experimenters\n '
                '- settings'
                '\n  - created protocol files'
                'Imaging data will not be saved here (= no big files)'
                f'\nCreate {USERDATA_DIR}? (recommended)'
                )
        if self.libui.bool_select(message):
            os.makedirs(USERDATA_DIR)
            print('Success!')
            time.sleep(2)
        else:
            print('Warning! Cannot save any changes')
            time.sleep(2)


    def _run_experimenter_select(self):

        if self.experimenter is not None:
            self.libui.print(f'Current experimenter: {self.experimenter}')

        extra_options = [' (Add new)', ' (Remove old)', ' (Save current list)']

        self.libui.print('Select experimenter\n--------------------')
        while True:
            # Select operation
            selection = self.libui.item_select(self.experimenters+extra_options) 

            # add new
            if selection == extra_options[0]:
                name = self.libui.input('Name >>')
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
        if not os.path.isdir(USERDATA_DIR):
           self._run_firstrun()
           self.libui.clear_screen()
        
        self._run_experimenter_select()
        self.libui.clear_screen()

        self.quit = False
        while not self.quit:
            self.libui.clear_screen()
            
            menuitems = [x[0] for x in self.main_menu]
            
            # Blocking call here
            selection = self.libui.item_select(menuitems)
            self.main_menu[menuitems.index(selection)][1]()

            # Update status menu and clear screen
            self.libui.header = self.menutext

            time.sleep(1)
            

        self.dynamic.exit()
        time.sleep(1)


    def locked_parameters_edit(self):
        
        selections ['Add locked', 'Remove locked', 'Modify values', '.. back (and save)']
        
        while True:
            self.libui.clear_screen()
            self.libui.header = self.menutext

            messsage = (
                    'Here, any of the imaging parameters can be made locked,'
                    ' overriding any presets/values setat imaging time.'
                    '\nCurrent locked are'
                    )

            self.libui.print(message)

            if not self.locked_parameters:
                self.libui.print('  (NONE)')
            for name in self.locked_parameters:
                self.libui.print('  {}'.format(name))
            self.libui.print()

            sel = self.libui.item_select(selections)
            
            # Add locked
            if sel == selections[0]:
                lockable = list(DEFAULT_DYNAMIC_PARAMETERS.keys())
                to_lock = self.libui.item_select(lockable+[' ..back'])
                
                if to_lock in lockable:
                    self.locked_parameters[to_lock] = DEFAULT_DYNAMIC_PARAMETERS[sel2]
            
            # Remove locked
            elif sel == selections[1]:
                locked = list(self.locked_parameters.keys())
                to_unlock = self.libui_item_select(locked+[' ..back'])
                
                if to_unlock in locked:
                    del self.locked_parameters[to_unlock]
            
            # Modify locked values
            elif sel == selections[2]:
                self.locked_parameters = ParameterEditor(self.locked_parameters).getModified()

            # Back and save
            elif sel == selections[3]:
                if os.path.isdir(USERDATA_DIR):
                    with open(self.glofn, 'w') as fp: json.dump(self.locked_parameters, fp)
                break

    
    def camera_settings_edit(self):
        '''View to select a camera and edit it's settings
        '''
        
        while True:

            camera = self.libui.item_select(
                    self.dynamic.cameras+['..back'],
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
