'''
Image accusition using Micro-Manager's Python (2) bindings (Camera class)
and a server program (CameraServer class).

On Windows, MM builds come compiled with Python 2 support only, so in this solution
there is a Python 2 server program that controls the camera and image saving
and then the client end that can be run with Python 3.
'''

import os
import time
import datetime
import socket
import threading
import multiprocessing

import numpy as np

import MMCorePy

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import RectangleSelector

import tifffile


DEFAULT_SAVING_DIRECTORY = "D:\imaging_data"


class ImageShower:
    '''
    Liveimage to the screen
    '''
    def __init__(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111)
        self.exit = False

        #self.cid = self.fig.canvas.mpl_connect('key_press_event', self.callbackButtonPressed)

        
        self.image_brightness = 0
        self.image_maxval = 1

        self.selection = None

    def callbackButtonPressed(self, event):
        
        if event.key == 'z':
            self.image_maxval -= 0.05
            self.updateImage(strong=True)
        
        elif event.key == 'x':
            self.image_maxval += 0.05
            self.updateImage(strong=True)
        
        elif event.key == 'a':
            self.image_brightness += 0.1
            self.updateImage(strong=True)
        elif event.key == 'c':
            self.image_brightness += -0.1
            self.updateImage(strong=True)
            

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
        
    def updateImage(self, i):

        while True:
            try:
                data = self.queue.get(True, timeout=0.01)
                break
            except:
                plt.pause(0.05)
        
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
       
        
        self.im.set_array(data)
        self.fig.suptitle('Selection 95th percentile: {}'.format(per95), fontsize=10)
        text = ''
        return self.im, text
           
         
    def loop(self, queue):
        self.queue = queue
        self.rectangle = RectangleSelector(self.ax, self.__onSelectRectangle, useblit=True)
        
        image = queue.get()
        self.im = plt.imshow(1000*image/np.max(image), cmap='gray', vmin=0, vmax=1, interpolation='none', aspect='auto')
        self.ani = FuncAnimation(plt.gcf(), self.updateImage, frames=range(100), interval=5, blit=False)

        plt.show()

class DummyCamera:
    '''
    A dummy camera class, used when unable to load the real Camera class
    due to camera being off or something similar.
    '''
    def acquireSingle(self, save, subdir):
        pass
    def acquireSeries(self, exposure_time, image_interval, N_frames, label, subdir):
        pass
    def saveImages(images, label, metadata, savedir):
        pass
    def setSavingDirectory(self, saving_directory):
        pass
    def setBinning(self, binning):
        pass
    def saveDescription(self, filename, string):
        pass
    
class Camera:
    '''
    Controlling ORCA FLASH 4.0 camera using Micro-Manager's
    Python (2) bindings.
    '''

    def __init__(self, saving_directory=DEFAULT_SAVING_DIRECTORY):

        self.setSavingDirectory(saving_directory)
        
        self.mmc = MMCorePy.CMMCore() 
        self.mmc.loadDevice('Camera', 'HamamatsuHam', 'HamamatsuHam_DCAM')
        self.mmc.initializeAllDevices()
        self.mmc.setCameraDevice('Camera')
            
        self.settings = {'binning': '1x1'}
        

        self.mmc.prepareSequenceAcquisition('Camera')
        self.live_queue= False

        self.shower = ImageShower()



    def acquireSingle(self, save, subdir):

        
        exposure_time = 0.01
        binning = '2x2'

        self.setBinning(binning)
        self.mmc.setExposure(exposure_time*1000)

        start_time = str(datetime.datetime.now())
 
        self.mmc.snapImage()
        image = self.mmc.getImage()
        
        if not self.live_queue:
            self.live_queue = multiprocessing.Queue()
            self.live_queue.put(image)
            
            p = multiprocessing.Process(target=self.shower.loop, args=(self.live_queue,))
            p.start()
            
        self.live_queue.put(image)

        if save == 'True':
            metadata = {'exposure_time_s': exposure_time, 'binning': binning, 'function': 'acquireSingle', 'start_time': start_time}

            save_thread = threading.Thread(target=self.saveImages,args=([image],'snap_{}'.format(start_time.replace(':','.').replace(' ','_')), metadata,os.path.join(self.saving_directory, subdir)))
            save_thread.start()



    def acquireSeries(self, exposure_time, image_interval, N_frames, label, subdir):
        '''
        exposure_time  How many seconds to expose each image
        image_interval How many seconds to wait in between the exposures
        N_frames       How many images to take
        label          Label for saving the images (part of the filename later)
        '''
        print 'Now imagin'
        
        
        exposure_time = float(exposure_time)
        image_interval = float(image_interval)
        N_frames = int(N_frames)
        label = str(label)

        print exposure_time
        print image_interval
        print N_frames

        self.setBinning('2x2')

        #self.mmc.setProperty('Camera', "TRIGGER SOURCE","EXTERNAL")
        self.mmc.setProperty('Camera', "OUTPUT TRIGGER KIND[0]","EXPOSURE")
        self.mmc.setProperty('Camera', "OUTPUT TRIGGER POLARITY[0]","NEGATIVE")
        self.mmc.setExposure(exposure_time*1000)

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
                except MMCorePy.CMMError:
                    time.sleep(exposure_time)
                
            images.append(image)
            
            
        metadata = {'exposure_time_s': exposure_time, 'image_interval_s': image_interval,
                    'N_frames': N_frames, 'label': label, 'function': 'acquireSeries', 'start_time': start_time}
        metadata.update(self.settings)

        save_thread = threading.Thread(target=self.saveImages, args=(images,label,metadata,os.path.join(self.saving_directory, subdir)))
        save_thread.start()

        print('acquired')
        
    @staticmethod
    def saveImages(images, label, metadata, savedir):
        '''
        Save given images as grayscale tiff images.
        '''
        if not os.path.isdir(savedir):
            os.makedirs(savedir)

        for i, image in enumerate(images):
            fn = '{}_{}.tiff'.format(label, i)
            tifffile.imsave(os.path.join(savedir, fn), image, metadata=metadata)
            


    def setSavingDirectory(self, saving_directory):
        '''
        Sets where images are saved and if the directory
        does not yet exist, creates it.
        '''
        if not os.path.isdir(saving_directory):
            os.makedirs(saving_directory)
            
        self.saving_directory = saving_directory


    def setBinning(self, binning):
        '''
        Binning '2x2' for example.
        '''
        if not self.settings['binning'] == binning:
            self.mmc.setProperty('Camera', 'Binning', binning)
            self.settings['binning'] =  binning

    def saveDescription(self, filename, string):
        '''
        Allows saving a small descriptive text file into the main saving directory.
        '''
        fn = os.path.join(self.saving_directory, filename)

        if os.path.exists(fn):
            #raise OSError('File {} already exsits'.format(fn))
            pass
        
        with open(fn+'.txt', 'w') as fp:
            fp.write(string)
            

class CameraServer:
    '''
    Camera server listens incoming connections and
    controls the camera through Camera class
    '''
    def __init__(self):

        PORT = 50071
        HOST = ''

        self.running = False

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((HOST, PORT))
        self.socket.listen(1)

        try:
            self.cam = Camera()
        except:
            self.cam = DummyCamera()
        self.functions = {'acquireSeries': self.cam.acquireSeries,
                          'setSavingDirectory': self.cam.setSavingDirectory,
                          'acquireSingle': self.cam.acquireSingle,
                          'saveDescription': self.cam.saveDescription,
                          'ping': self.ping}

    def ping(self, message):
        print message

    def run(self):
        '''
        Loop waiting for incoming connections.
        Each established connection can give one command and then the connection
        is closed.
        '''
        self.running = True
        while self.running:
            conn, addr = self.socket.accept()
            string = ''
            while True:
                data = conn.recv(1024)
                if not data: break
                string += data
            
            conn.close()
            print('Recieved command "'+string+'" at time '+str(time.time()))
            if string:
                func, parameters = string.split(';')
                parameters = parameters.split(':')
                target=self.functions[func](*parameters)
            
    def stop(self):
        '''
        Stop running the camera server.
        '''
        self.running = False


def test_camera():
    cam = Camera()
    images = cam.acquireSeries(0.01, 1, 5, 'testing')
    
    for image in images:
        plt.imshow(image, cmap='gray')
        plt.show()



def runServer():
    '''
    Running the server.
    '''
    cam_server = CameraServer()
    cam_server.run()
            
        
if __name__ == "__main__":
    runServer()
