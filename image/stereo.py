import numpy as np

from skimage.feature import match_template

"""Utilities for dealing with side-by-side stereo images"""

def get_L(img):
    try:
        (_,w) = img.shape
        return img[:,:w/2]
    except ValueError:
        (_,w,_) = img.shape
        return img[:,:w/2,:]

def get_R(img):
    try:
        (_,w) = img.shape
        return img[:,w/2:]
    except ValueError:
        (_,w,_) = img.shape
        return img[:,w/2:,:]

def swap_LR(img):
    try:
        (_,w) = img.shape
        return np.roll(img,w/2,axis=1)
    except ValueError:
        (_,w,_) = img.shape
        return np.roll(img,w/2,axis=1)

def align(g_LR,template_size=64):
    """
    Compute stereo alignment given a grayscale L/R image.
    Returns X offset.

    Parameters
    ----------
    g_LR : ndarray
        grayscale side-by-side L/R stereo pair
    template_size : int
        size of patch area to compare

    Returns
    -------
    dx : int
        x offset between the two images
    """
    # gather metrics
    (h,w) = g_LR.shape
    h2 = h/2 # half the height (center of image)
    w2 = w/2 # half the width (split between image pair)
    w4 = w/4 # 1/4 the width (center of left image)
    w34 = w2 + w4 # 3/4 the width (center of right image)
    template_size = 64
    ts = template_size
    ts2 = template_size / 2
    out = np.zeros((h,w2)) # FIXME
    for ox in [0,ts,0-ts]:
        for i in range(h/ts):
            y = (i * ts)
            # select the center pixels of the left image
            template = g_LR[y:y+ts,(w4+ox)-ts2:(w4+ox)+ts2]
            # now match the template to the corresponding horizontal strip of the right image
            # and accumulate into an output "strips" image
            strip = g_LR[y:y+ts,w2:]
            out[y:y+ts,:] += np.roll(match_template(strip,template,pad_input=True),0-ox,axis=1)
    # sum to horizontal scanline
    scanline = np.sum(out,axis=0)
    padding = w2/8 # ignore image edges
    max_x = np.argmax(scanline[padding:-padding]) + padding
    # offset is difference from half the width of each image in the pair
    # upscaled by a factor of 2
    dx = w4 - max_x
    return dx

def redcyan(g_LR,dx=None):
    """
    Convert a side-by-side grayscale image into a red/cyan image.

    Parameters
    ----------
    g_LR : ndarray
        side-by-side grayscale image
    dx : int
        x offset (if None, compute x offset with align())

    Returns
    -------
    redcyan : ndarray
        RGB image containing red/cyan composite
    """
    if dx is None:
        dx = align(g_LR)
    (h,w) = g_LR.shape
    cw = w/2-dx
    red = g_LR[:,dx:w/2]
    cyan = g_LR[:,w/2+dx:]
    return np.dstack([red,cyan,cyan])