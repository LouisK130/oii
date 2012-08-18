from flask import Flask, request, url_for, abort, session, Response, render_template
from unittest import TestCase
import json
import re
import sys
import os
from time import strptime
from StringIO import StringIO
from oii.config import get_config
from oii.times import iso8601
from oii.webapi.utils import jsonr
import urllib
from oii.utils import order_keys
from oii.ifcb.formats.adc import read_adc, read_target, ADC, ADC_SCHEMA, TARGET_NUMBER, WIDTH, HEIGHT, STITCHED
from oii.ifcb.formats.roi import read_roi, read_rois, ROI
from oii.ifcb.formats.hdr import read_hdr, HDR, CONTEXT, HDR_SCHEMA
from oii.resolver import parse_stream
from oii.ifcb.stitching import find_pairs, stitch
from oii.io import UrlSource, LocalFileSource
from oii.image.pil.utils import filename2format, thumbnail
from oii.image import mosaic
from oii.image.mosaic import Tile
import mimetypes
from zipfile import ZipFile
from PIL import Image

app = Flask(__name__)
app.debug = True

# importantly, set max-age on static files (e.g., javascript) to something really short
#app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 30
# FIXME this should be selected by time series somehow
rs = parse_stream('oii/ifcb/mvco.xml')
binpid2path = rs['binpid2path']
pid_resolver = rs['pid']
blob_resolver = rs['mvco_blob']

# string key constants
STITCH='stitch'
NAMESPACE='namespace'
TIME_SERIES='series'
SIZE='size'
SCALE='scale'
PAGE='page'
PID='pid'

def configure(config):
    # FIXME populate app.config dict
    pass

app.config[NAMESPACE] = 'http://demi.whoi.edu:5061/'
app.config[STITCH] = True

def major_type(mimetype):
    return re.sub(r'/.*','',mimetype)

def minor_type(mimetype):
    return re.sub(r'.*/','',mimetype)

# utilities

def get_target(bin,target_no):
    """Read a single target from an ADC file given the bin PID/LID and target number"""
    adc_path = binpid2path.resolve(pid=bin,format=ADC).value
    if not app.config[STITCH]: # no stitching, read one target
        return read_target(LocalFileSource(adc_path), target_no)
    else:
        # in the stitching case we need to read two targets and see if they overlap,
        # so we can set the STITCHED flag
        targets = list(read_adc(LocalFileSource(adc_path), target_no, limit=2))
        target = targets[0]
        if len(list(find_pairs(targets))) > 1:
            target[STITCHED] = 1
        else:
            target[STITCHED] = 0
        return target

def image_response(image,format,mimetype):
    """Construct a Flask Response object for the given image, PIL format, and MIME type."""
    buf = StringIO()
    im = image.save(buf,format)
    return Response(buf.getvalue(), mimetype=mimetype)

def resolve_pid(time_series,pid):
    # FIXME for now, ignore time_series, but it will be used to configure resolver
    return pid_resolver.resolve(pid=pid)

def resolve_file(time_series,pid,format):
    # FIXME for now, ignore time_series, but it will be used to configure resolver
    return binpid2path.resolve(pid=pid,format=format).value

def resolve_adc(time_series,pid):
    return resolve_file(time_series,pid,ADC)

def resolve_hdr(time_series,pid):
    return resolve_file(time_series,pid,HDR)

def resolve_roi(time_series,pid):
    return resolve_file(time_series,pid,ROI)

def resolve_files(time_series,pid,formats):
    # FIXME for now, ignore time_series, but it will be used to configure resolver
    return [resolve_file(time_series,pid,format) for format in formats]

def parse_params(path, **defaults):
    """Parse a path fragment and convert to dict.
    Slashes separate alternating keys and values.
    For example /a/3/b/5 -> { 'a': '3', 'b': '5' }.
    Any keys not present get default values from **defaults"""
    parts = re.split('/',path)
    d = dict(zip(parts[:-1:2], parts[1::2]))
    for k,v in defaults.items():
        if k not in d:
            d[k] = v
    return d

@app.route('/api/mosaic/pid/<path:pid>')
def serve_mosaic(pid):
    hit = pid_resolver.resolve(pid=pid)
    if hit.extension == 'html':
        return Response(render_template('mosaics.html',hit=hit),mimetype='text/html')
    else:
        serve_mosaic_image(pid)

@app.route('/api/mosaic/<path:params>/pid/<path:pid>')
def serve_mosaic_image(pid, params='/'):
    """Generate a mosaic of ROIs from a sample bin.
    params include the following, with default values
    - series (mvco) - time series (FIXME: handle with resolver, clarify difference between namespace, time series, pid, lid)
    - size (1024x1024) - size of the mosaic image
    - page (1) - page. for typical image sizes the entire bin does not fit and so is split into pages.
    - scale - scaling factor for image dimensions """
    # parse params
    params = parse_params(params, size='1024x1024',page=1, series='mvco', scale=1.0)
    time_series = params[TIME_SERIES]
    (w,h) = tuple(map(int,re.split('x',params[SIZE])))
    scale = float(params[SCALE])
    page = int(params[PAGE])
    # resolve ADC
    hit = pid_resolver.resolve(pid=pid)
    adc_path = resolve_adc(time_series, hit.bin_lid)
    # read ADC and convert to Tiles in size-descending order
    def descending_size(t):
        (w,h) = t.size
        return 0 - (w * h)
    tiles = [Tile(t, (t[HEIGHT], t[WIDTH])) for t in read_adc(LocalFileSource(adc_path))]
    tiles.sort(key=descending_size)
    # perform layout operation
    scaled_size = (int(w/scale), int(h/scale))
    layout = mosaic.layout(tiles, scaled_size, page, threshold=0.05)
    # FIXME should serve tiles in JSON
    # resolve ROI
    roi_path = resolve_roi(time_series,hit.bin_lid)
    # read all images needed for compositing and inject into Tiles
    with open(roi_path,'rb') as roi_file:
        for tile in layout:
            target = tile.image
            for roi in read_rois([target], roi_file=roi_file):
                tile.image = roi # should only iterate once
    # produce and serve composite image
    mosaic_image = thumbnail(mosaic.composite(layout, scaled_size, mode='L', bgcolor=160), (w,h))
    (pil_format, mimetype) = image_types(hit)
    return image_response(mosaic_image, pil_format, mimetype)
    
@app.route('/api/blob/pid/<path:pid>')
def serve_blob(pid):
    hit = blob_resolver.resolve(pid=pid)
    zip_path = hit.value
    if hit.target is None:
        if hit.extension != 'zip':
            abort(404)
        return Response(file(zip_path), direct_passthrough=True, mimetype='application/zip')
    else:
        blobzip = ZipFile(zip_path)
        png = blobzip.read(hit.lid+'.png')
        blobzip.close()
        # now determine PIL format and MIME type
        (pil_format, mimetype) = image_types(hit)
        if mimetype == 'image/png':
            return Response(png, mimetype='image/png')
        else:
            # FIXME support more imaage types
            blob_image = Image.open(StringIO(png))
            return image_response(blob_image, pil_format, mimetype)

@app.route('/<time_series>/api/<path:ignore>')
def api_error(time_series,ignore):
    abort(404)

@app.route('/<time_series>/<path:lid>')
def resolve(time_series,lid):
    """Resolve a URL to some data endpoint in a time series, including bin and target metadata endpoints,
    and image endpoints"""
    # use the PID resolver (which also works for LIDs)
    hit = resolve_pid(time_series,lid)
    # construct the namespace from the configuration and time series ID
    hit.namespace = '%s%s/' % (app.config[NAMESPACE], time_series)
    hit.bin_pid = hit.namespace + hit.bin_lid
    hit.date = iso8601(strptime(hit.date, hit.date_format))
    # determine extension
    if hit.extension is None: # default is .rdf
        hit.extension = 'rdf'
    # determine MIME type
    filename = '%s.%s' % (hit.lid, hit.extension)
    (mimetype, _) = mimetypes.guess_type(filename)
    if mimetype is None:
        mimetype = 'application/octet-stream'
    # is the user requesting an image?
    if hit.target is not None:
        hit.target_no = int(hit.target) # parse target number
    if major_type(mimetype) == 'image':
        return serve_roi(hit)
    else:
        if hit.target is not None: # is this a target endpoint (rather than a bin endpoint?)
            hit.target_pid = hit.namespace + hit.lid # construct target pid
            return serve_target(hit,mimetype)
        else:
            return serve_bin(hit,mimetype)
    # nothing recognized, so return Not Found
    abort(404)

def list_targets(hit):
    adc_path = resolve_adc(hit.time_series, hit.bin_lid)
    targets = list(read_adc(LocalFileSource(adc_path)))
    if app.config[STITCH]:
        # in the stitching case we need to compute "stitched" flags based on pairs
        pairs = find_pairs(targets)
        As = [a for (a,_) in pairs]
        for target in targets:
            if target in As:
                target[STITCHED] = 1
            else:
                target[STITCHED] = 0
        # and we have to exclude the second of each pair from the list of targets
        Bs = [b for (_,b) in pairs]
        targets = filter(lambda target: target not in Bs, targets)
    return targets
    
def bin2csv(hit,targets):
    # get the ADC keys for this version of the ADC format
    schema_keys = [k for k,_ in ADC_SCHEMA[hit.schema_version]]
    def csv_iter():
        first = True
        for target in targets:
            # add a binID and pid what are the right keys for these?
            target['binID'] = '"%s"' % hit.bin_pid
            target['pid'] = '"%s_%05d"' % (hit.bin_pid, target['targetNumber'])
            # now order all keys even the ones not in the schema
            keys = order_keys(target, schema_keys)
            # fetch all the data for this row as strings
            row = [str(target[k]) for k in keys]
            if first: # if this is the first row, emit the keys
                yield ','.join(keys)
                first = False
            # now emit the row
            yield ','.join(row)
    return Response(render_template('bin.csv',rows=csv_iter()),mimetype='text/plain')

def serve_bin(hit,mimetype):
    hdr_path = resolve_hdr(hit.time_series, hit.bin_lid)
    props = read_hdr(LocalFileSource(hdr_path))
    context = props[CONTEXT]
    del props[CONTEXT]
    # sort properties according to their order in the header schema
    props = [(k,props[k]) for k,_ in HDR_SCHEMA]
    # get a list of all targets, taking into account stitching
    targets = list_targets(hit)
    target_pids = ['%s_%05d' % (hit.bin_pid, target['targetNumber']) for target in targets]
    template = dict(hit=hit,context=context,properties=props,target_pids=target_pids)
    if hit.extension == HDR:
        return Response(file(hdr_path), direct_passthrough=True, mimetype='text/plain')
    elif hit.extension == ADC:
        return Response(file(resolve_adc(hit.time_series, hit.bin_lid)), direct_passthrough=True, mimetype='text/csv')
    elif hit.extension == ROI:
        return Response(file(resolve_roi(hit.time_series, hit.bin_lid)), direct_passthrough=True, mimetype='application/octet-stream')
    elif minor_type(mimetype) == 'xml':
        return Response(render_template('bin.xml',**template), mimetype='text/xml')
    elif minor_type(mimetype) == 'rdf+xml':
        return Response(render_template('bin.rdf',**template), mimetype='text/xml')
    elif minor_type(mimetype) == 'csv':
        return bin2csv(hit,targets)
    elif mimetype == 'application/json':
        properties = dict(props)
        properties['context'] = context
        properties['targets'] = targets
        return jsonr(properties)
    else:
        abort(404)

def serve_target(hit,mimetype):
    target = get_target(hit.bin_lid, hit.target_no) # read the target from the ADC file
    # sort the target properties according to the order in the schema
    schema_keys = [k for k,_ in ADC_SCHEMA[hit.schema_version]]
    target = [(k,target[k]) for k in order_keys(target, schema_keys)]
    # now populate the template appropriate for the MIME type
    template = dict(hit=hit,target=target)
    if minor_type(mimetype) == 'xml':
        return Response(render_template('target.xml',**template), mimetype='text/xml')
    elif minor_type(mimetype) == 'rdf+xml':
        return Response(render_template('target.rdf',**template), mimetype='text/xml')
    elif mimetype == 'application/json':
        return jsonr(dict(target))
    print minor_type(mimetype)

def image_types(hit):
    # now determine PIL format and MIME type
    filename = '%s.%s' % (hit.lid, hit.extension)
    pil_format = filename2format(filename)
    (mimetype, _) = mimetypes.guess_type(filename)
    return (pil_format, mimetype)

def serve_roi(hit):
    """Serve a stitched ROI image given the output of the pid resolver"""
    # resolve the ADC and ROI files
    (adc_path, roi_path) = resolve_files(hit.time_series, hit.bin_lid, (ADC, ROI))
    if app.config[STITCH]:
        limit=2 # read two targets, in case we need to stitch
    else:
        limit=1 # just read one
    targets = list(read_adc(LocalFileSource(adc_path),target_no=hit.target_no,limit=limit))
    if len(targets) == 0: # no targets? return Not Found
        abort(404)
    # open the ROI file as we may need to read more than one
    with open(roi_path,'rb') as roi_file:
        if app.config[STITCH]:
            pairs = list(find_pairs(targets)) # look for stitched pairs
        else:
            pairs = targets
        if len(pairs) >= 1: # found one?
            (a,b) = pairs[0] # split pair
            images = list(read_rois((a,b),roi_file=roi_file)) # read the images
            (roi_image, mask) = stitch((a,b), images) # stitch them
        else:
            # now check that the target number is correct
            target = targets[0]
            if target[TARGET_NUMBER] != hit.target_no:
                abort(404)
            images = list(read_rois([target],roi_file=roi_file)) # read the image
            roi_image = images[0]
        # now determine PIL format and MIME type
        (pil_format, mimetype) = image_types(hit)
        # return the image data
        return image_response(roi_image,pil_format,mimetype)

if __name__=='__main__':
    port = 5061
    if len(sys.argv) > 1:
        config = get_config(sys.argv[1])
        try:
            configure(config)
        except KeyError:
            pass
        try:
            port = int(config.port)
        except KeyError:
            pass
    app.secret_key = os.urandom(24)
    app.run(host='0.0.0.0',port=port)
