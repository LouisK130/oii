"""Define helper utilities for iPython for displaying images.
This is to avoid using the cumbersome matplotlib API"""
import os
from tempfile import mkstemp

import numpy as np

from scipy.ndimage import measurements
from skimage import img_as_float
from skimage.io import imsave
from skimage.color import hsv2rgb
from skimage.exposure import rescale_intensity
from skimage.segmentation import find_boundaries

from IPython.core import display

def tmp_img(extension='.png'):
    (o,f) = mkstemp(suffix=extension,dir='tmp')
    os.close(o)
    return f

def show_image(image):
    f = tmp_img()
    imsave(f,image)
    return display.Image(filename=f)

def as_spectrum(gray):
    One = np.ones_like(gray)
    Y = 1 - rescale_intensity(gray,out_range=(0,1))
    HSV = np.dstack([Y*0.66,One,One])
    return hsv2rgb(HSV)

def show_spectrum(gray):
    return show_image(as_spectrum(gray))

def show_masked(rgb,mask,outline=False):
    copy = img_as_float(rgb,force_copy=True)
    if outline:
        (labels,_) = measurements.label(mask)
        boundaries = find_boundaries(labels)
        copy[boundaries] = [1,0,0]
    else:
        copy[mask] = [1,0,0]
    return show_image(copy)