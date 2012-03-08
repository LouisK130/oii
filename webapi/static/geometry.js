// globals (FIXME: make preferences)
var scalingFactor = 2;
var geometryColor = '#f00';
// geometric tool support
var geometry = {};
geometry.boundingBox = {
    label: 'Bounding box',
    draw: function(ctx, boundingBox) {
        var left = scalingFactor * boundingBox[0][0];
        var top = scalingFactor * boundingBox[0][1];
        var right = scalingFactor * boundingBox[1][0]; 
        var bottom = scalingFactor * boundingBox[1][1];
        ctx.strokeStyle = geometryColor;
        ctx.strokeRect(left, top, right-left, bottom-top);
    }
};
geometry.line = {
    label: 'Line',
    draw: function(ctx, line) {
        var ox = scalingFactor * line[0][0];
        var oy = scalingFactor * line[0][1];
        var mx = scalingFactor * line[1][0]; 
        var my = scalingFactor * line[1][1];
        ctx.strokeStyle = geometryColor;
        ctx.beginPath();
        ctx.moveTo(ox,oy);
        ctx.lineTo(mx,my);
        ctx.stroke();
    }
};
geometry.point = {
    label: 'Point',
    draw: function(ctx, point) {
        var x = scalingFactor * point[0];
        var y = scalingFactor * point[1];
        var size = 5;
        ctx.strokeStyle = geometryColor;
        ctx.beginPath();
        ctx.moveTo(x-size,y);
        ctx.lineTo(x+size,y);
        ctx.moveTo(x,y-size);
        ctx.lineTo(x,y+size);
        ctx.stroke();
    }
}
//
function selectedTool(value) {
    if(value == undefined) {
        return $('#workspace').data('tool');
    } else {
        clog('setting tool to '+JSON.stringify(value));
        $('#workspace').data('tool',geometry[value].tool);
    }
}
function MeasurementTool(eventHandlers) {
    this.eventHandlers = eventHandlers;
}
function bindMeasurementTools(selector, env) {
    // env must include the following to be passed as event.data:
    // - cell: the div containing the image and carrying annotation data
    // - canvas: the canvas
    // - ctx: a context on the canvas
    // - scaledWidth: the scaled image width
    // - scaledHeight: the scaled image height
    selector.bind('mousedown', env, function(event) {
        var cell = event.data.cell;
        var canvas = event.data.canvas;
        var tool = selectedTool();
        if('mousedown' in tool.eventHandlers) {
            var mx = event.pageX - canvas.offset().left;
            var my = event.pageY - canvas.offset().top;
            event.data.mx = mx;
            event.data.my = my;
            event.data.ix = (mx/scalingFactor)|0;
            event.data.iy = (mx/scalingFactor)|0;
            // call the currently selected tool
            tool.eventHandlers.mousedown(event);
        }
    }).bind('mousemove', env, function(event) {
        var tool = selectedTool();
        var canvas = event.data.canvas;
        if('mousemove' in tool.eventHandlers) {
            var mx = event.pageX - canvas.offset().left;
            var my = event.pageY - canvas.offset().top;
            event.data.mx = mx;
            event.data.my = my;
            event.data.ix = (mx/scalingFactor)|0;
            event.data.iy = (mx/scalingFactor)|0;
            tool.eventHandlers.mousemove(event);
        }
    }).bind('mouseup', env, function(event) {
        var tool = selectedTool();
        if('mouseup' in tool.eventHandlers) {
            tool.eventHandlers.mouseup(event);
        }
    });
}
geometry.boundingBox.tool = new MeasurementTool({
    mousedown: function(event) {
        var cell = event.data.cell;
        var mx = event.data.mx;
        var my = event.data.my;
        $(cell).data('ox',mx);
        $(cell).data('oy',my);
    },
    mousemove: function(event) {
        var cell = event.data.cell;
        var ox = $(cell).data('ox');
        var oy = $(cell).data('oy');
        if(ox >= 0 && oy >= 0) {
            var ctx = event.data.ctx;
            var scaledWidth = event.data.scaledWidth;
            var scaledHeight = event.data.scaledHeight;
            var mx = event.data.mx;
            var my = event.data.my;
            var left = Math.min(ox,mx);
            var top = Math.min(oy,my);
            var w = Math.max(ox,mx) - left;
            var h = Math.max(oy,my) - top;
            /* compute a rectangle in original scale pixel space */
            var rect = [[(left/scalingFactor)|0, (top/scalingFactor)|0], [((left+w)/scalingFactor)|0, ((top+h)/scalingFactor)|0]]
            $(cell).data('boundingBox',rect);
            ctx.clearRect(0, 0, scaledWidth, scaledHeight);
            geometry.boundingBox.draw(ctx,rect);
        }
    },
    mouseup: function(event) {
        var cell = event.data.cell;
        $(cell).data('ox',-1);
        $(cell).data('oy',-1);
        queueAnnotation({
            image: $(cell).data('imagePid'),
            category: categoryPidForLabel($('#label').val()),
            geometry: { boundingBox: $(cell).data('boundingBox') }
        });
        toggleSelected(cell,$('#label').val());
    }
});
// allow the user to draw a line on a cell's "new annotation" canvas
geometry.line.tool = new MeasurementTool({
    mousedown: function(event) {
        var cell = event.data.cell;
        var mx = event.data.mx;
        var my = event.data.my;
        $(cell).data('ox',mx);
        $(cell).data('oy',my);
    },
    mousemove: function(event) {
        var cell = event.data.cell;
        var ox = $(cell).data('ox');
        var oy = $(cell).data('oy');
        if(ox >= 0 && oy >= 0) {
            var ctx = event.data.ctx;
            var mx = event.data.mx;
            var my = event.data.my;
            /* compute a rectangle in original scale pixel space */
            var line = [[(ox/scalingFactor)|0, (oy/scalingFactor)|0], [(mx/scalingFactor)|0, (my/scalingFactor)|0]]
            $(cell).data('line',line);
            ctx.clearRect(0,0,event.data.scaledWidth,event.data.scaledHeight);
            geometry.line.draw(ctx,line);
        }
    },
    mouseup: function(event) {
        var cell = event.data.cell;
        $(cell).data('ox',-1);
        $(cell).data('oy',-1);
        queueAnnotation({
            image: $(cell).data('imagePid'),
            category: categoryPidForLabel($('#label').val()),
            geometry: { line: $(cell).data('line') }
        });
        toggleSelected(cell,$('#label').val());
    }
});
//allow the user to draw a line on a cell's "new annotation" canvas
geometry.point.tool = new MeasurementTool({
    mousedown: function(event) {
        var cell = event.data.cell;
        var ctx = event.data.ctx;
        var mx = event.data.mx;
        var my = event.data.my;
        /* compute a rectangle in original scale pixel space */
        var line = [(mx/scalingFactor)|0, (my/scalingFactor)|0]
        $(cell).data('point',line);
        ctx.clearRect(0,0,event.data.scaledWidth,event.data.scaledHeight);
        geometry.point.draw(ctx,line);
        $(cell).data('inpoint',1);
    },
    mousemove: function(event) {
        var cell = event.data.cell;
        var point = $(cell).data('inpoint');
        if(point != undefined) {
            var ctx = event.data.ctx;
            var mx = event.data.mx;
            var my = event.data.my;
            /* compute a rectangle in original scale pixel space */
            var line = [(mx/scalingFactor)|0, (my/scalingFactor)|0]
            $(cell).data('point',line);
            ctx.clearRect(0,0,event.data.scaledWidth,event.data.scaledHeight);
            geometry.point.draw(ctx,line);
        }
    },
    mouseup: function(event) {
        var cell = event.data.cell;
        queueAnnotation({
            image: $(cell).data('imagePid'),
            category: categoryPidForLabel($('#label').val()),
            geometry: { point: $(cell).data('point') }
        });
        toggleSelected(cell,$('#label').val());
        $(cell).removeData('inpoint');
    }
});