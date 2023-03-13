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
import socket
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

from .camera_communication import PORT

DEFAULT_SAVING_DIRECTORY = "imaging_data"
DEFAULT_MICROMANAGER_DIR = 'C:/Program Files/Micro-Manager-2.0'


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
        elif data == 'close':
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
        data = np.clip(data, np.percentile(inspect_area, 5), per95)
        
        data = data - np.min(data)
        data_max = np.max(data)
        data = data.astype(float)/data_max

        self.image_size = data.size
       
        
        self.im.set_array(data)
        self.fig.suptitle('Selection 95th percentile: {}'.format(per95), fontsize=10)
        text = ''
        return self.im, text
           
         
    def loop(self, queue):
        '''
        Runs the ImageShower by reading images from the given queue.
        Set this as a multiprocessing target.

        queue           Multiprocessing queue with a get method.
        '''
        self.queue = queue
        self.rectangle = RectangleSelector(self.ax, self.__onSelectRectangle, useblit=True)
        
        image = queue.get()
        self.im = plt.imshow(1000*image/np.max(image), cmap='gray', vmin=0, vmax=1, interpolation='none', aspect='auto')
        self.ani = FuncAnimation(plt.gcf(), self._updateImage, frames=range(100), interval=5, blit=False)

        plt.show(block=False)
        
        while not self.close:
            plt.pause(1)


class DummyCamera:
    '''A dummy camera suitable for testing the server/client.
    '''
    def __init__(self):
        self.settings = {}
    def acquire_single(self, save, subdir):
        pass
    def acquire_series(self, exposure_time, image_interval, N_frames, label, subdir, trigger_direction):
        pass
    def save_images(images, label, metadata, savedir):
        pass
    def set_saving_directory(self, saving_directory):
        pass
    def set_binning(self, binning):
        self.settings['binning'] = binning
    def set_roi(self, x,y,w,h):
        self.settings['roi'] = [x,y,w,h]
    def set_save_stack(self, boolean):
        self.setttings['save-stack'] = boolean

    def save_description(self, filename, string):
        pass
    def close(self):
        pass
    def get_cameras(self):
        return ['dummy1', 'dummy2']
    def set_camera(self, name):
        self.camera = name


class MMCamera:
    '''Controls any camera using MicroManager and its pymmcore bindings.
    '''

    def __init__(self, saving_directory=DEFAULT_SAVING_DIRECTORY):

        self.set_saving_directory(saving_directory)
        
        self.mmc = pymmcore.CMMCore() 
        
        self._device_name = None

        #self.mmc.loadDevice('Camera', 'HamamatsuHam', 'HamamatsuHam_DCAM')
        #self.mmc.initializeAllDevices()
        #self.mmc.setCameraDevice('Camera')
            
        self.settings = {}
        
        #self.mmc.setCircularBufferMemoryFootprint(4000)
        self.live_queue= False

        self.shower = ImageShower()

        # Description file string
        self.description_string = ''

        self.save_stack = False


    def get_cameras(self):
        '''Lists available MicroManager configuration files in .
        '''
        return [fn for fn in os.listdir(DEFAULT_MICROMANAGER_DIR) if fn.endswith('.cfg')]


    def set_camera(self, name):
        '''Set the provided configuration file.
        '''
        if not os.path.exists(name):
            name = os.path.join(DEFAULT_MICRONAMAGER_DIR, name)
            
            if not os.path.exists(name):
                print(f'Couldnt open configuration file named: {name}')
                return

        self.mmc.loadSystemConfiguration(name)
        
        # Rename the current camera to Camera
        self._device_name = self.mmc.getDeviceName()
        self.mmc.prepareSequenceAcquisition(self._device_name)


    def acquire_single(self, save, subdir):
        '''
        Acquire a single image.

        save        'True' or 'False'
        subdir      Subdirectory for saving
        '''
        
        exposure_time = 0.01
        binning = '2x2'

        self.set_binning(binning)
        self.mmc.setExposure(exposure_time*1000)

        start_time = str(datetime.datetime.now())
 
        self.mmc.snapImage()
        image = self.mmc.getImage()
        
        if not self.live_queue:
            self.live_queue = multiprocessing.Queue()
            self.live_queue.put(image)
            
            self.livep = multiprocessing.Process(target=self.shower.loop, args=(self.live_queue,))
            self.livep.start()
            
        self.live_queue.put(image)

        if save == 'True':
            metadata = {'exposure_time_s': exposure_time, 'binning': binning, 'function': 'acquireSingle', 'start_time': start_time}

            save_thread = threading.Thread(target=self.save_images,args=([image],'snap_{}'.format(start_time.replace(':','.').replace(' ','_')), metadata,os.path.join(self.saving_directory, subdir)))
            save_thread.start()



    def acquire_series(self, exposure_time, image_interval, N_frames, label, subdir, trigger_direction):
        '''
        Acquire a series of images

        exposure_time       How many seconds to expose each image
        image_interval      How many seconds to wait in between the exposures
        N_frames            How many images to take
        label               Label for saving the images (part of the filename later)
        subdir
        trigger_direction   "send" (camera sends a trigger pulse when it's ready) or "receive" (camera takes an image for every trigger pulse)
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

        self.set_binning('2x2')
        print(" Pixel binning 2x2")

        if trigger_direction == 'send':
            print(" Camera sending a trigger pulse")
            self.mmc.setProperty(self._device_name, "OUTPUT TRIGGER KIND[0]","EXPOSURE")
            self.mmc.setProperty(self._device_name, "OUTPUT TRIGGER POLARITY[0]","NEGATIVE")
        elif trigger_direction== 'receive':
            print(" Camera recieving / waiting for a trigger pulse")
            self.mmc.setProperty(self._device_name, "TRIGGER SOURCE","EXTERNAL")
            self.mmc.setProperty(self._device_name, "TriggerPolarity","POSITIVE")
        else:
            raise ValueError('trigger_direction has to be {} or {}, not {}'.format('receive', 'send', trigger_direction))

        
        print("Circular buffer " + str(self.mmc.getCircularBufferMemoryFootprint()) + " MB")

        self.mmc.setExposure(exposure_time*1000)


        self.wait_for_client()
        

        start_time = str(datetime.datetime.now())
        self.mmc.startSequenceAcquisition(N_frames, image_interval, False)
        
        
        while self.mmc.isSequenceRunning():
            time.sleep(exposure_time)

        images = []

        for i in range(N_frames):
            while True:
                try:
                    image = self.mmc.popNextImage()
                    break
                except pymmcore.CMMError:
                    time.sleep(exposure_time)
                
            images.append(image)
            
            
        metadata = {'exposure_time_s': exposure_time, 'image_interval_s': image_interval,
                    'N_frames': N_frames, 'label': label, 'function': 'acquireSeries', 'start_time': start_time}
        metadata.update(self.settings)

        save_thread = threading.Thread(target=self.save_images, args=(images,label,metadata,os.path.join(self.saving_directory, subdir)))
        save_thread.start()
        
        self.mmc.setProperty(self._device_name, "TRIGGER SOURCE","INTERNAL")
        print('acquired')

    
    def save_images(self, images, label, metadata, savedir):
        '''
        Save given images as grayscale tiff images.
        '''
        if not os.path.isdir(savedir):
            os.makedirs(savedir)

        if self.save_stack == False:
            # Save separate images
            for i, image in enumerate(images):
                fn = '{}_{}.tiff'.format(label, i)
                tifffile.imsave(os.path.join(savedir, fn), image, metadata=metadata)
        else:
            # Save a stack
            fn = '{}_stack.tiff'.format(label)
            tifffile.imsave(os.path.join(savedir, fn), np.asarray(images), metadata=metadata)
        
        self.save_description(os.path.join(savedir, 'description'), self.description_string, internal=True)


    def set_saving_directory(self, saving_directory):
        '''
        Sets where the specimen folders are saved and if the directory
        does not yet exist, creates it.
        '''
        if not os.path.isdir(saving_directory):
            os.makedirs(saving_directory)
            
        self.saving_directory = saving_directory


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
            fn = os.path.join(self.saving_directory, specimen_name, specimen_name)
        
        # Check if the folder exists
        if not os.path.exists(os.path.dirname(fn)):
            #raise OSError('File {} already exsits'.format(fn))
            os.makedirs(os.path.dirname(fn))
        
        with open(fn+'.txt', 'w') as fp:
            fp.write(desc_string)

        print("Wrote file " + fn+'.txt')
        
        
        self.description_string = desc_string


    def close(self):
        self.live_queue.put('close')
        self.lifep.join()

    def wait_for_client(self):
        pass


class CameraServer:
    '''Camera server listens incoming connections from the client and
    controls a camera class.
    '''

    def __init__(self, camera, port=None):
        
        if port is None:
            port = PORT
        HOST = ''           # This is not cac.SERVER_HOSTNAME, leave empty

        self.running = False

        print(f'Binding a socket (host {HOST}, port {port}))')

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((HOST, port))
        self.socket.listen(1)
        
        print(f'Using the camera <{camera.__class__.__name__}>')
        self.cam = camera
        self.cam.wait_for_client = self.wait_for_client
        
        self.functions = {'acquireSeries': self.cam.acquire_series,
                          'setSavingDirectory': self.cam.set_saving_directory,
                          'acquireSingle': self.cam.acquire_single,
                          'saveDescription': self.cam.save_description,
                          'set_roi': self.cam.set_roi,
                          'set_save_stack': self.cam.set_save_stack,
                          'get_cameras': self.get_cameras,
                          'set_camera': self.set_camera,
                          'ping': self.ping,
                          'exit': self.stop}

        self.responding = set(['get_cameras'])


    def get_cameras(self):
        cameras = self.cam.get_cameras()
        return cameras

    def set_camera(self, name):
        self.cam.set_camera(name)


    def ping(self, message):
        print(message)



    def wait_for_client(self):
        '''
        Waits until client confirms that it is ready
        '''
        conn, addr = self.socket.accept()
        string = ''
        while True:
            data = conn.recv(1024)
            if not data: break
            string += data
        conn.close()
        print("Client ready")
        


    def run(self):
        '''
        Loop waiting for incoming connections.
        Each established connection can give one command and then the connection
        is closed.
        '''
        
        print('Waiting for clients to connect')

        self.running = True
        while self.running:
            conn, addr = self.socket.accept()
            string = ''
            while True:
                data = conn.recv(1024)
                #if not data: break
                string += data.decode()
                break

            if not string:
                conn.close()
                continue
            
            print('Recieved command "'+string+'" at time '+str(time.time()))
            if ';' in string:
                func, parameters = string.split(';')
                parameters = parameters.split(':')
            else:
                func = string
                parameters = None
        
            # Can close connection early, no response so let's not delay the client
            if not func in self.responding:
                conn.close()
            
            if parameters:
                response = self.functions[func](*parameters)
            else:
                response = self.functions[func]()

            # Say back the response and close because still open
            if func in self.responding:
                conn.sendall(str(response).encode())
                conn.close()


    def stop(self, placeholder):
        '''
        Stop running the camera server.
        '''
        self.cam.close()
        self.running = False


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
        camera.set_saving_directory(args.save_directory)

    cam_server = CameraServer(camera, args.port)
    cam_server.run()
            
        
if __name__ == "__main__":
    main()
