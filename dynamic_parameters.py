'''
Default dynamic parameters and ParameterEditor for letting the user
modify them in the program.
'''
import time
import ast

DEFAULT_DYNAMIC_PARAMETERS = {'isi': 20.0, 'repeats': 1, 'pre_stim': 0.000,
        'stim': 0.200, 'post_stim': 0.00, 'frame_length' : 0.010,
        'ir_imaging': 5, 'ir_waiting': 0, 'ir_livefeed': 1,
        'flash_on': 10, 'flash_off': 0,
        'ir_channel': ["Dev2/ao0", "Dev2/ao1"], 'flash_channel': "Dev1/ao0"}

DYNAMIC_PARAMETERS_TYPES = {'seconds': ['isi', 'pre_stim', 'stim', 'post_stim', 'frame_length'],
        'voltage': ['ir_imaging', 'ir_waiting', 'ir_livefeed', 'flash_on', 'flash_off'],
        'channel': ['ir_channel', 'flash_channel'],
        'integer': ['repeats']}


DYNAMIC_PARAMETERS_HELP = {'isi': 'Inter stimulus intervali[s]',
        'repeats': 'How many times the protocol is repeated',
        'pre_stim': 'How long to image before the pulse [s]',
        'stim': 'Stimulus (step pulse) length [s]',
        'post_stim': 'How long to image after the pulse [s]',
        'frame_length': 'Exposure time / inter-frame interval',
        'ir_imaging': 'IR brightness during image acqusition',
        'ir_waiting': 'IR brightness when waiting ISI',
        'ir_livefeed': 'IR brightness while updating the live image',
        'flash_on': 'Flash brightness during stim',
        'flash_off':' Flash brightness during image acqustition',
        'ir_channel': 'NI channel for IR',
        'flash_channel': 'NI channel for Flash'}


def getRightType(parameter_name, string_value):
    '''
    Convert user inputted string to correct parameter value based on
    DYNAMIC_PARAMETER_TYPES

    TODO    - channel checking, check that the channel is proper NI channel
    '''
    if parameter_name in DYNAMIC_PARAMETERS_TYPES['integer']:
        return int(string_value)

   
    if parameter_name in DYNAMIC_PARAMETERS_TYPES['seconds']:
        seconds = float(string_value)
        if seconds < 0:
            raise ValueError('Here time is required to be strictly positive.')
        return seconds

    if parameter_name in  DYNAMIC_PARAMETERS_TYPES['voltage']:
        voltage = float(string_value)
        if not -10<=voltage<=10:
            raise ValueError('Voltage value range -10 to 10 V exceeded.')
        return voltage

    if parameter_name in  DYNAMIC_PARAMETERS_TYPES['channel']:
        if type(string_value) == type(''):
            if string_value.startswith('[') and string_value.endswith([']']):
                return ast.literal_eval(string_value)
            else:
                return string_value

    raise NotImplementedError('Add {} correctly to DYNAMIC_PARAMETER_TYPES in dynamic_parameters.py')
    

class ParameterEditor:
    '''
    Dictionary editor on command line.
    '''
    def __init__(self, dynamic_parameters):
        '''
        dynamic_parameters      Dictionary of the dynamic imaging parameters.
        '''
        self.dynamic_parameters = dynamic_parameters
        self.parameter_names = sorted(self.dynamic_parameters.keys())


    def printCurrent(self):
        '''
        Prints the current parameters and the help strings.
        '''
        
        print()
        
        print('{:<20} {:<40} {}'.format('PARAMETER NAME', 'VALUE', 'DESCRIPTION'))
        for parameter in self.parameter_names:
            print('{:<20} {:<40} {}'.format(parameter, str(self.dynamic_parameters[parameter]), DYNAMIC_PARAMETERS_HELP[parameter]))
        print()

    def getModified(self):
        '''
        Ask user to edit the parameters until happy and then return
        the parameters.
        '''
        

        while True:
            print('MODIFYING DYMAIC IMAGING PARAMETERS')
            self.printCurrent()
            parameter = input('Parameter name (Enter to continue) >> ')

            if parameter == '':
                break
            
            try:
                self.dynamic_parameters[parameter]
            except KeyError:
                print('Invalid input, not a parameter name')
                time.sleep(1)
                continue

            while True:

                value = input('Value for {} >> '.format(parameter))
                
                if value == '':
                    break

                try:
                    value = getRightType(parameter, value)
                except ValueError as e:
                    print(str(e))
                    print('Could not convert the value to right type. Try againg or Enter to skip.')
                    continue

                self.dynamic_parameters[parameter] = value
                break

        return self.dynamic_parameters


def getModifiedParameters():
    '''
    Take in the DEFAULT parameters in the beginning of this code file
    and let the user modify them using text based ParameterEditor
    '''
    editor = ParameterEditor(DEFAULT_DYNAMIC_PARAMETERS)
    return editor.getModified()


if __name__ == "__main__":
    print(getModifiedParameters())


