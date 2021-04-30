
import os


import numpy as np
import matplotlib.pyplot as plt
import tifffile
import scipy.misc
from skimage.filters.rank import entropy
from skimage.morphology import disk
from skimage.measure import shannon_entropy

def example():
    
    imdir = '/home/joni/smallbrains-nas1/array1/pseudopupil_imaging/DrosoTest2'
    image_fns = [os.path.join(imdir, fn) for fn in os.listdir(imdir) if fn.endswith('tif')]
    image_fns.sort()

    ent = []
    
    for i, fn in enumerate(image_fns):
        image = tifffile.imread(fn)
        image = scipy.misc.imresize(image, 0.5, interp='lanczos')

        ent.append(shannon_entropy(image))


    for i, fn in enumerate(image_fns):
        image = tifffile.imread(fn)
        image = scipy.misc.imresize(image, 0.5, interp='lanczos')

        #grad = np.gradient(image)
        #grad_mag = np.sqrt(grad[0]**2 + grad[1]**2)

        #grad_mag = (entropy(image, disk(5)))
        

        fig = plt.figure(figsize=(12,10))
        axes = fig.subplots(nrows=2, ncols=1)

        axes[0].imshow(image)
        axes[1].plot(ent)
        axes[1].scatter(i, ent[i])
        #axes[0][1].imshow(grad_mag)


        #axes[1][0].hist(image.flatten(), bins=100)
        #axes[1][1].hist(grad_mag.flatten(), bins=100)


        
        plt.savefig(os.path.join('focus_test', 'im_{:0>8}.jpg'.format(i)))
        plt.close()
    
    plt.show()

if __name__ == "__main__":
    example()


