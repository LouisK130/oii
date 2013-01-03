import numpy as np
from scipy.ndimage.filters import convolve

def showim(im):
    imsave('fn.png',im * 1.)
    return display.Image(filename='fn.png')

def gray_world(a):
    (_,_,c) = a.shape
    means = [np.mean(a[:,:,n]) for n in range(0,c)]
    gray = np.mean(means)
    return (a * (gray / means)).clip(0.,1.)

def thumb(rgb,scale=0.5,gray=False):
    (h,w,_) = rgb.shape
    thumb = rgb
    if gray:
        thumb = gray_world(thumb)
    thumb = resize(thumb,(int(h*scale),int(w*scale)))
    return showim(thumb)

def demosaic_bilinear(cfa,pattern='rggb'):
    # pull color channels
    ch = dict((c,np.zeros_like(cfa)) for c in 'rgb')
    for c,(y,x) in zip(pattern,[(0,0),(0,1),(1,0),(1, 1)]):
        ch[c][y::2,x::2] = cfa[y::2,x::2]
    (r,g,b) = (ch[c] for c in 'rgb')
    # interpolate per-channel
    (_,a,A) = (0., 0.25, 0.5)
    # kernel for sparsely-sampled channels (R and B)
    sintpl = [[a, A, a],
              [A, _, A],
              [a, A, a]]
    # kernel for densely-sampled channel (G)
    dintpl = [[_, a, _],
              [a, _, a],
              [_, a, _]]
    # convolve with channel-appropriate kernels
    r = np.where(r > 0, r, convolve(r, weights=sintpl))
    g = np.where(g > 0, g, convolve(g, weights=dintpl))
    b = np.where(b > 0, b, convolve(b, weights=sintpl))
    return np.dstack((r,g,b))

def demosaic_gradient(cfa,pattern='rggb'):
    """Based on Laroche-Prescott"""

    # pull G channel
    offsets = [(0,0),(0,1),(1,0),(1,1)]
    g = np.zeros_like(cfa)
    for c,(m,n) in zip(pattern,offsets):
        if c == 'g':
            g[m::2,n::2] = cfa[m::2,n::2]
    # compute offets of R and B channels
    rb_offsets = [(rb,(m,n)) for rb,(m,n) in zip(pattern,offsets) if rb in 'rb']

    # edge-sensitive estimation of missing G channel
    for _,(m,n) in rb_offsets: # for R and B channels
        c = cfa[m::2,n::2] # pull color channel
        # detect edge orientation
        kernel = [[0.5, -1, 0.5]]
        a = np.abs(convolve(c,weights=kernel))
        b = np.abs(convolve(c,weights=np.rot90(kernel)))
        o = np.zeros_like(cfa)
        o[m::2,n::2] = (a < b)
        # produce two luminance estimates, one for each axis
        kernel = [[0.5, 0, 0.5]]
        h = convolve(cfa,weights=kernel)
        v = convolve(cfa,weights=np.rot90(kernel))
        # weight luminance estimates according to edge orientation
        e = (o * h) + ((1 - o) * v)
        g[m::2,n::2] = e[m::2,n::2]

    # interpolation kernel w for difference channel
    (a,A) = (0.25, 0.5)
    w = [[a, A, a],
         [A, 1, A],
         [a, A, a]]

    rb = {}
    # estimate R and B channel C by as g + (C - g) * w
    for ch,(m,n) in rb_offsets: # over R and B
        # pull color channel C
        c = np.zeros_like(cfa)
        c[m::2,n::2] = cfa[m::2,n::2]
        # generate difference channel C - g
        d = np.zeros_like(cfa)
        d[m::2,n::2] = (c - g)[m::2,n::2]
        # estimate C as g + (C - g) * w
        e = g + convolve(d, weights=w)
        # add back in originally sampled data
        e[m::2,n::2] = cfa[m::2,n::2]
        rb[ch] = e
    
    return np.dstack((rb['r'], g, rb['b']))

def demosaic_hq_linear(cfa,pattern='rggb'):
    # Malvar et al
    # pull color channels
    offsets = [(0,0),(0,1),(1,0),(1,1)]
    ch = dict((c,np.zeros_like(cfa)) for c in 'rgb')
    for c,(y,x) in zip(pattern,offsets):
        ch[c][y::2,x::2] = cfa[y::2,x::2]
    (R,G,B) = 'rgb'
    # compute offets of R and B channels
    rb_offsets = [(c,(m,n)) for c,(m,n) in zip(pattern,offsets) if c in 'rb']
    g_offsets = [(m,n) for c,(m,n) in zip(pattern,offsets) if c in 'g']
    
    # estimate green
    ck = np.array([[0,  0, -1,  0,  0],
                   [0,  0,  0,  0,  0],
                   [-1, 0,  4,  0, -1],
                   [0,  0,  0,  0,  0],
                   [0,  0, -1,  0,  0]]) / 8.
    gk = np.array([[0, 2, 0],
                   [2, 0, 2],
                   [0, 2, 0]]) / 8.;

    gc = convolve(ch[G],gk)
    for c,(m,n) in rb_offsets:
        ch[G][m::2,n::2] = convolve(ch[c],weights=ck)[m::2,n::2] + gc[m::2,n::2]

    # rb at br locations, other color
    rbk = np.array([[   0, 0, -1.5, 0,    0],
                    [   0, 0,    0, 0,    0],
                    [-1.5, 0,    6, 0, -1.5],
                    [   0, 0,    0, 0,    0],
                    [   0, 0, -1.5, 0,    0]]) / 8.
    # rb at br locations, same color
    brk = np.array([[2, 0, 2],
                    [0, 0, 0],
                    [2, 0, 2]]) / 8.
    # rb at g locations, other color (horizontal)
    cgck = np.array([[4, 0, 4]]) / 8.
    cgck_90 = np.rot90(cgck)
    # rb at g locations, g (horizontal)
    cgk = np.array([[ 0 , 0, 0.5,  0,  0],
                    [ 0, -1,   0, -1,  0],
                    [-1 , 0,   5,  0, -1],
                    [ 0, -1,   0, -1,  0],
                    [ 0,  0, 0.5,  0,  0]]) / 8.
    cgk_90 = np.rot90(cgk)

    for c,(i,j) in rb_offsets:
        cc = np.copy(ch[c])
        for (m,n) in g_offsets:
            # RB at green pixel
            wc, wg = (cgck,cgk) if m==i else (cgck_90,cgk_90)
            cc[m::2,n::2] = convolve(ch[c],weights=wc)[m::2,n::2] + convolve(ch[G],weights=wg)[m::2,n::2]
        # R at B, B at R
        (k,l) = (1-i, 1-j) # other offsets
        d = {R:B,B:R}[c] # other channel
        cc[k::2,l::2] = convolve(ch[d],weights=rbk)[k::2,l::2] + convolve(ch[c],weights=brk)[k::2,l::2]
        ch[c] = cc
    
    rgb = np.dstack(ch[c] for c in 'rgb')
    return rgb

def demosaic(cfa,method='hq_linear',pattern='rggb'):
    if method=='hq_linear':
        return demosaic_hq_linear(cfa,pattern)
    if method=='gradient':
        return demosaic_gradient(cfa,pattern)
    elif method=='bilinear':
        return demosaic_bilinear(cfa,pattern)
