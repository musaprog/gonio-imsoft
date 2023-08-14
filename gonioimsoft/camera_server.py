'''The camera server for using the camera and save images.

Functionality
-------------
- Image acquisition using Micro-Manager's Python bindings (pymmcore)
- Live feed using matplotlib
- File saving using the tifffile module


Background
-----------
On Windows, MM builds came precompiled with Python 2 support only. The
camera server/client division here made it possible to run the server
calling MM using Python 2 (to control the camera and image saving) and
then the camera client run with Python 3.

It is still usefull; Because it uses (network) sockets, it is trivial
to use another (or multiple PC) to acqurie images. Or, in future, to
use another backends than MM.
'''

import os
import sys
import time
import datetime
import argparse
import threading
import multiprocessing

try:
    import pymmcore
except ImportError:
    pymmcore = None
    print('pymmcore not installed')
import tifffile
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import RectangleSelector

from .common import CAMERA_PORT
from .serverbase import ServerBase

DEFAULT_MICROMANAGER_DIR = 'C:/Program Files/Micro-Manager-2.0'

# Integer between 1-inf (1 = no downsampling), images for imageshower
LIVE_DOWNSAMPLE = 2

class ImageShower:
    '''Shows images on the screen in its own window.

    In future, may be used to select ROIs as well to allow
    higher frame rate imaging / less data.
    
    ------------------
    Working principle
    ------------------
    Image shower works so that self.loop is started as a separate process
    using multiprocessing library
    
    -------
    Methods
    -------
    self.loop       Set this as multiprocessing target
    '''
    def __init__(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111)
        self.close = False

        #self.cid = self.fig.canvas.mpl_connect('key_press_event', self.callbackButtonPressed)
        
        self.image_brightness = 0
        self.image_maxval = 1

        self.selection = None

        self.image_size = None

    def callbackButtonPressed(self, event):
        
        if event.key == 'r':
            self.image_maxval -= 0.05
            self._updateImage(strong=True)
        
        elif event.key == 't':
            self.image_maxval += 0.05
            self._updateImage(strong=True)

            

    def __onSelectRectangle(self, eclick, erelease):
        
        # Get selection box coordinates and set the box inactive
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        #self.rectangle.set_active(False)
        
        x = int(min((x1, x2)))
        y = int(min((y1, y2)))
        width = int(abs(x2-x1))
        height = int(abs(y2-y1))
        
        self.selection = [x, y, width, height]
        
    def _updateImage(self, i):
        
        data = None
        while not self.queue.empty():
            # Get the latest image in the queue
            data = self.queue.get(True, timeout=0.01)
        if data is None:
            return self.im, ''
        elif isinstance(data, str) and data == 'close':
            self.close = True
            return self.im, ''

        if self.selection and data.size != self.image_size:
            self.selection = None

        if self.selection:
            x,y,w,h = self.selection
            if w<1 or h<1:
                # If selection box empty (accidental click on the image)
                # use the whole image instead
                inspect_area = data
            else:
                inspect_area = data[y:y+h, x:x+w]
        else:
            inspect_area = data
        
        
        per95 = np.percentile(inspect_area, 95)
        per5 = np.percentile(inspect_area, 5)
        data = np.clip(data, per5, per95)
        
        data -= per5
        data /= (per95-per5)

        self.image_size = data.size
        
        self.im.set_array(data)
        self.fig.suptitle('Selection 95th percentile: {}'.format(per95), fontsize=10)
        text = ''
        return self.im, text
           
         
    def loop(self, queue, title):
        '''
        Runs the ImageShower by reading images from the given queue.
        Set this as a multiprocessing target.

        queue           Multiprocessing queue with a get method.
        '''
        self.queue = queue
        self.rectangle = RectangleSelector(self.ax, self.__onSelectRectangle, useblit=True)
        
        image = queue.get()
        self.im = plt.imshow(1000*image/np.max(image), cmap='gray', vmin=0, vmax=1, interpolation='none', aspect='auto')
        self.ani = FuncAnimation(plt.gcf(), self._updateImage, frames=range(100), interval=50, blit=False)

        self.fig.canvas.toolbar.winfo_toplevel().title(title)

        # Remove the toolbar; Gives more space when having many cameras
        self.fig.canvas.toolbar.pack_forget()
        
        # Take away all white space
        plt.subplots_adjust(top=1, bottom=0, right=1,left=0,
                            hspace=0, wspace=0)
        
        plt.show(block=True)


class DummyCamera:
    '''A dummy camera suitable for testing the server/client.
    '''
    def __init__(self):
        self.settings = {'setting1' : 'na', 'setting2': 0.0, 'setting3': 1}
        self.camera = None

    def acquire_single(self, save, subdir):
        pass
    def acquire_series(self, exposure_time, image_interval, N_frames, label, subdir):
        pass
    def save_images(images, label, metadata, savedir):
        pass
    def set_binning(self, binning):
        self.settings['binning'] = binning
    def set_roi(self, x,y,w,h):
        self.settings['roi'] = [x,y,w,h]
    def set_save_stack(self, boolean):
        self.settings['save-stack'] = boolean

    def save_description(self, filename, string):
        pass
    def close(self):
        pass
    def get_cameras(self):
        return ['dummy1', 'dummy2']
    def get_camera(self):
        return self.camera
    def set_camera(self, name):
        self.camera = name
    def get_settings(self):
        return list(self.settings.keys())
    def get_setting_type(self, setting_name):
        if setting_name == 'setting1':
            return 'string'
        elif setting_name == 'setting2':
            return 'float'
        elif setting_name == 'setting3':
            return 'integer'
        else:
            print('Invalid setting')
            return ''
    def get_setting(self, setting_name):
        value = self.settings.get(setting_name, None)
        if value is None:
            return ''
        return value
    def set_setting(self, setting_name, value):
        self.settings[setting_name] = value



class MMCamera:
    '''Controls any camera using MicroManager and its pymmcore bindings.
    '''

    def __init__(self):

        self.mmc = pymmcore.CMMCore() 
        self.mmc.setDeviceAdapterSearchPaths([DEFAULT_MICROMANAGER_DIR])

        self._device_name = None
        self._configuration_name = ''

        #self.mmc.loadDevice('Camera', 'HamamatsuHam', 'HamamatsuHam_DCAM')
        #self.mmc.initializeAllDevices()
        #self.mmc.setCameraDevice('Camera')
            
        self.settings = {'exposure_time_scaler': 1}
        
        #self.mmc.setCircularBufferMemoryFootprint(4000)
        self.live_queue= False

        self.shower = ImageShower()

        # Description file string
        self.description_string = ''

        self.save_stack = False
        self.save_directory = None

        self._startdir = os.getcwd()

        self.title = 'Camera not set'
        self.servertitle = ''


    def get_cameras(self):
        '''Lists available MicroManager configuration files in .
        '''
        return [fn for fn in os.listdir(DEFAULT_MICROMANAGER_DIR) if fn.endswith('.cfg')]


    def get_camera(self):
        '''Returns the label of the current camera.
        '''
        return self._configuration_name

    def set_camera(self, name):
        '''Set the provided configuration file.
        '''
        if not os.path.exists(name):
            path = os.path.join(DEFAULT_MICROMANAGER_DIR, name)
            
            if not os.path.exists(path):
                print(f'Couldnt open configuration file named: {path}')
                return

        self.mmc.loadSystemConfiguration(path)
        
        self._device_name = self.mmc.getCameraDevice()
        self._configuration_name = name
        self.mmc.prepareSequenceAcquisition(self._device_name)

        self.title = f'{name} ({self._device_name}) | {self.servertitle}'

    def get_settings(self):
        '''Returns device property names
        '''
        if self._device_name is None:
            return ''
        properties = self.mmc.getDevicePropertyNames(self._device_name)
        
        return list(properties) + list(self.settings.keys())


    def get_setting_type(self, setting_name):
        '''Returns "string", "integer" or "float".

        Returns an empty string if the setting does not exist.
        '''
        if setting_name in self.settings:
            return 'float'

        try:
            num = self.mmc.getPropertyType(self._device_name, setting_name)
        except RuntimeError as e:
            print(f'Error! No setting named: {setting_name}')
            return ''
        
        if num == 1:
            return 'string'
        elif num == 2:
            return 'float'
        elif num == 3:
            return 'integer'


    def get_setting(self, setting_name):
        if setting_name in self.settings:
            return self.settings[setting_name]
        return self.mmc.getProperty(self._device_name, setting_name)

    def set_setting(self, setting_name, value):
        
        # a) Internal setting
        if setting_name in self.settings:
            self.settings[setting_name] = value
            return
        
        # b) Camera device setting
        type_name = self.get_setting_type(setting_name)
        if type_name == 'float':
            value = float(value)
        elif type_name == 'integer':
            value = int(value)
        elif type_name == '':
            print('Error! No setting named: {setting_name}')
            return

        print(f'Changing {setting_name} to its new value {value}')
        try:
            self.mmc.setProperty(self._device_name, setting_name, value)
        except RuntimeError as e:
            print('Error! The set value likely out of range.')
            print(e)

    def acquire_single(self, exposure_time, save, subdir):
        '''
        Acquire a single image.

        save        'True' or 'False'
        subdir      Subdirectory for saving
        '''
        
        exposure_time = float(exposure_time)
        self.mmc.setExposure(exposure_time*1000)
        #binning = '2x2'

        #self.set_binning(binning)

        start_time = str(datetime.datetime.now())
 
        self.mmc.snapImage()
        image = self.mmc.getImage()
        
        if not self.live_queue:
            self.live_queue = multiprocessing.Queue()
            self.live_queue.put(
                    image[0::LIVE_DOWNSAMPLE, 0::LIVE_DOWNSAMPLE])
            
            self.livep = multiprocessing.Process(
                    target=self.shower.loop,
                    args=(self.live_queue,self.title))
            self.livep.start()
            
        self.live_queue.put(image[0::LIVE_DOWNSAMPLE, 0::LIVE_DOWNSAMPLE])

        if save == 'True':
            metadata = {'exposure_time_s': exposure_time, 'function': 'acquireSingle', 'start_time': start_time}

            save_thread = threading.Thread(target=self.save_images,args=([image],'snap_{}'.format(start_time.replace(':','.').replace(' ','_')), metadata,os.path.join(self.save_directory, subdir)))
            save_thread.start()



    def acquire_series(self, exposure_time, image_interval, N_frames, label, subdir):
        '''
        Acquire a series of images

        exposure_time       How many seconds to expose each image
        image_interval      How many seconds to wait in between the exposures
        N_frames            How many images to take
        label               Label for saving the images (part of the filename later)
        subdir
        '''

        exposure_time = float(exposure_time)
        image_interval = float(image_interval)
        N_frames = int(N_frames)
        label = str(label)

        print("Now aquire_series with label " + label)
        print("- IMAGING PARAMETERS -")
        print(" exposure time " + str(exposure_time) + " seconds")
        print(" image interval " + str(image_interval) + " seconds")
        print(" N_frames " + str(N_frames))
        print("- CAMERA SETTINGS")

        #self.set_binning('2x2')
        #print(" Pixel binning 2x2")
        
        device_name = self.mmc.getDeviceName(self._device_name)
        print(f'Device name {device_name}')

        #if 'hamamatsu' in device_name.lower():
        #    if trigger_direction == 'send':
        #        print(" Camera sending a trigger pulse")
        #        self.mmc.setProperty(self._device_name, "OUTPUT TRIGGER KIND[0]","EXPOSURE")
        #        self.mmc.setProperty(self._device_name, "OUTPUT TRIGGER POLARITY[0]","NEGATIVE")
        #    elif trigger_direction== 'receive':
        #        print(" Camera recieving / waiting for a trigger pulse")
        #        self.mmc.setProperty(self._device_name, "TRIGGER SOURCE","EXTERNAL")
        #        self.mmc.setProperty(self._device_name, "TriggerPolarity","POSITIVE")
        #    elif trigger_direction == 'none':
        #        pass
        #    else:
        #        raise ValueError('trigger_direction has to be send, receive or none, not {trigger_direction}')

        
        print("Circular buffer " + str(self.mmc.getCircularBufferMemoryFootprint()) + " MB")

        scaler = float(self.settings['exposure_time_scaler'])
        exposure = scaler*exposure_time*1000
        self.mmc.setExposure(exposure)

        self.mmc.clearCircularBuffer()
        #self.mmc.prepareSequenceAcquisition(self._device_name)
        self.wait_for_client()
        
        start_time = str(datetime.datetime.now())
        self.mmc.startSequenceAcquisition(N_frames, image_interval+(1-scaler)*exposure, False)
        
        while self.mmc.isSequenceRunning():
            self.mmc.sleep(1000*exposure_time)

        self.mmc.sleep(1000)

        images = []

        for i in range(N_frames):
            while True:
                try:
                    image = self.mmc.popNextImage()
                    break
                except:
                    # Index error for example when circular buffer is still empty
                    self.mmc.sleep(1000*exposure_time)
            
            images.append(image)
            
            
        metadata = {'exposure_time_s': exposure_time, 'image_interval_s': image_interval,
                    'N_frames': N_frames, 'label': label, 'function': 'acquireSeries', 'start_time': start_time}
        metadata.update(self.settings)

        save_thread = threading.Thread(target=self.save_images, args=(images,label,metadata,os.path.join(self.save_directory, subdir)))
        save_thread.start()
        
        #if 'hamamatsu' in device_name.lower() and trigger_direction == 'receive':
        #    self.mmc.setProperty(self._device_name, "TRIGGER SOURCE","INTERNAL")
        
        print('acquired')

    
    def save_images(self, images, label, metadata, savedir):
        '''
        Save given images as grayscale tiff images.
        '''
        savedir = os.path.join(self._startdir, savedir)
        if not os.path.isdir(savedir):
            try:
                os.makedirs(savedir)
            except:
                # May fail if many local servers creating
                # the folders simultaneously
                pass

        if self.save_stack == False:
            # Save separate images
            for i, image in enumerate(images):
                fn = '{}_{}.tiff'.format(label, i)
                tifffile.imwrite(os.path.join(savedir, fn), image, metadata=metadata)
        else:
            # Save a stack
            fn = '{}_stack.tiff'.format(label)
            tifffile.imwrite(os.path.join(savedir, fn), np.asarray(images), metadata=metadata)
        
        self.save_description(os.path.join(savedir, 'description'), self.description_string, internal=True)


    def set_save_stack(self, boolean):
        '''
        If boolean == "True", save images as stacks instead of separate images.
        '''
        if boolean == 'True':
            self.save_stack = True
        elif boolean == 'False':
            self.save_stack = False
        else:
            print("Did not understand wheter to save stacks. Given {}".format(boolean))

    def set_binning(self, binning):
        '''
        Binning '2x2' for example.
        '''
        if not self.settings['binning'] == binning:
            self.mmc.setProperty(self._device_name, 'Binning', binning)
            self.settings['binning'] =  binning

    def set_roi(self, x,y,w,h):
        '''
        In binned pixels
        roi     (x,y,w,h) or None
        '''
        x = int(x)
        y = int(y)
        w = int(w)
        h = int(h)
        
        if w == 0 or h==0:
            self.mmc.clearROI()
        else:
            self.mmc.setROI(x,y,w,h)


    def save_description(self, specimen_name, desc_string, internal=False):
        '''
        Allows saving a small descriptive text file into the main saving directory.
        Filename should be the same as the folder where it's saved.

        Appends to the previous file.

        specimen_name           DrosoM42 for example, name of the specimen folder
        desc_string             String, what to write in the file
        internal                If true, specimen_name becomes filename of the file
        '''
        if internal:
            fn = specimen_name
        else:
            fn = os.path.join(self.save_directory, specimen_name, specimen_name)
        
        # Check if the folder exists
        if not os.path.exists(os.path.dirname(fn)):
            try:
                os.makedirs(os.path.dirname(fn), exist_ok=True)
            except:
                # My fail if many local servers. Let's not
                # care about it, another server has made it
                pass
        
        try:
            with open(fn+'.txt', 'w') as fp:
                fp.write(desc_string)

            print("Wrote file " + fn+'.txt') 
        except:
            pass
        
        self.description_string = desc_string


    def close(self):
        if self.live_queue:
            self.live_queue.put('close')

    def wait_for_client(self):
        pass


class CameraServer(ServerBase):
    '''Camera server listens incoming connections from the client and
    controls a camera class.
    '''

    def __init__(self, camera, port=None):
        
        if port is None:
            port = CAMERA_PORT
        
        super().__init__('', port, camera)
        
        
        print(f'Using the camera <{camera.__class__.__name__}>')
        self.cam = self.device
        self.cam.servertitle = f'Server on port {port}'
        self.cam.wait_for_client = self.wait_for_client
        
        added_functions = {'acquireSeries': self.cam.acquire_series,
                          'acquireSingle': self.cam.acquire_single,
                          'saveDescription': self.cam.save_description,
                          'set_roi': self.cam.set_roi,
                          'set_save_stack': self.cam.set_save_stack,
                          'get_cameras': self.cam.get_cameras,
                          'get_camera': self.cam.get_camera,
                          'set_camera': self.cam.set_camera,
                          'get_settings': self.cam.get_settings,
                          'get_setting_type': self.cam.get_setting_type,
                          'get_setting': self.cam.get_setting,
                          'set_setting': self.cam.set_setting,
                          }

        self.functions = {**self.functions, **added_functions}

        self.responders.extend(
                ['get_cameras', 'get_camera', 'get_settings',
                 'get_setting_type', 'get_setting']
                )

        

def test_camera():
    cam = Camera()
    images = cam.acquireSeries(0.01, 1, 5, 'testing')
    
    for image in images:
        plt.imshow(image, cmap='gray')
        plt.show()



def main():
    
    parser = argparse.ArgumentParser(
            prog='GonioImsoft Camera Server',
            description='Controls a MicroManager camera')

    parser.add_argument('-p', '--port')
    parser.add_argument('-c', '--camera')
    parser.add_argument('-s', '--save-directory')

    args = parser.parse_args()


    if args.camera == 'mm':
        Camera = MMCamera
    elif args.camera == 'dummy':
        Camera = DummyCamera
    else:
        # Default
        if pymmcore:
            Camera = MMCamera
        else:
            Camera = DummyCamera

    camera = Camera()

    if args.save_directory:
        self.set_save_directory(args.save_directory)

    if args.port:
        args.port = int(args.port)

    cam_server = CameraServer(camera, args.port)
    cam_server.run()
            
        
if __name__ == "__main__":
    main()
