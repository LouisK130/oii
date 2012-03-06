// globals (FIXME: make preferences)
var scalingFactor = 1;
var geometryColor = '#f00';
function gotoPage(page,size) {
    if(page < 1) page = 1;
    clog('going to page '+page);
    var images = $('#workspace').data('images')
    if(images == undefined) {
        return;
    }
    clearPage();
    var offset = (page-1) * size;
    var limit = offset + size;
    $.each(images, function(i,entry) {
        if(i >= offset && i < limit) {
            // append image with approprite URL
            var image_url = entry.image;
            var image_pid = entry.pid; // for now, pid = url
            // each cell has the following data associted with it:
            // image_pid: the pid of the image
            // scaledWidth: scaled width of image
            // scaledHeight: scaled height of image
            // ox: x origin of (new, not existing) bounding box
            // oy: y origin of (new, not existing) bounding box
            // rect: the bounding box rectangle (in *non-scaled* pixel coordinates)
            var cell = $('#images').append('<div class="thumbnail"><div class="spacer"></div><div class="caption ui-widget">&nbsp;</div><div class="subcaption ui-widget"></div></div>')
                .find('div.thumbnail:last')
                .data('image_pid',image_pid)
                .disableSelection();
            $(cell).prepend('<img style="display:none" src="'+image_url+'">')
                .find('img')
                .bind('load', {
                    cell: cell
                }, function() {
                    var iw = $(this).width();
                    var ih = $(this).height();
                    ih *= scalingFactor; /* we can apply arbitrary scaling factors here. */
                    iw *= scalingFactor;
                    $(cell).data('scaledWidth',iw);
                    $(cell).data('scaledHeight',ih);
                    $(cell).data('ox',-1);
                    $(cell).data('oy',-1);
                    $(cell).width(iw);
                    $(cell).find('div.spacer').height(ih+10);
                    var ctx = $(cell).append('<canvas width="'+iw+'px" height="'+ih+'px" class="image atorigin"></canvas>')
                        .find('canvas.image')[0].getContext('2d');
                    ctx.drawImage(this, 0, 0, iw, ih);
                    $(cell).append('<canvas width="'+iw+'px" height="'+ih+'px" class="existing atorigin"></canvas>');
                    showExistingAnnotations(cell);
                    //bindSelectedTool(cell);
                    var newCanvas = $(cell).append('<canvas width="'+iw+'px" height="'+ih+'px" class="new atorigin"></canvas>')
                        .find('canvas.new');
                    ctx = newCanvas[0].getContext('2d');
                    var env = { cell: cell, ctx: ctx, iw: iw, ih: ih };
                    boundingBoxTool.bindTo(newCanvas, env);
                }); // binding for load on cell
        } // paging condition in loop over images
    }); // loop over images
}
// cell - div with image in it
// ann - annotation
function showBoundingBox(cell,ctx,ann) {
    clog('showing bounding box ...' + JSON.stringify(ann));
    if('boundingBox' in ann.geometry && ann.geometry.boundingBox != undefined) {
        var ox = ann.geometry.boundingBox[0][0] * scalingFactor;
        var oy = ann.geometry.boundingBox[0][1] * scalingFactor;
        var w = (ann.geometry.boundingBox[1][0] * scalingFactor) - ox;
        var h = (ann.geometry.boundingBox[1][1] * scalingFactor) - oy;
        ctx.strokeStyle = geometryColor;
        ctx.strokeRect(ox,oy,w,h);
    }
}
function showPendingAnnotations(cell) {
    var image_pid = $(cell).data('image_pid');
    var p = pending()[image_pid];
    if(p != undefined) {
        var cat = categoryLabelForPid(p.category);
        var ctx = $(cell).find('canvas.new')[0].getContext('2d');
        showBoundingBox(cell,ctx,p);
        clog('selecting '+cat+' for '+image_pid);
        select(cell, cat);
    }
}
function showExistingAnnotations(cell) {
    var image_pid = $(cell).data('image_pid');
    var ctx = $(cell).find('canvas.existing')[0].getContext('2d');
    $.ajax({
        url: '/list_annotations/image/' + image_pid,
        dataType: 'json',
        success: function(r) {
	    showPendingAnnotations(cell);
            ctx.clearRect(0,0,$(cell).data('scaledWidth'),$(cell).data('scaledHeight'));
            var anns = {};
            $(r).each(function(ix,ann) {
                showBoundingBox(cell,ctx,ann);
                if(!(ann.category in anns)) {
                    anns[ann.category] = 1;
                } else {
                    anns[ann.category] += 1;
                }
            });
            // now we show which annotation has the most "votes"
            var max = 0;
            var theLabel = '';
            var ex = '';
            for(var cat in anns) {
                var label = categoryLabelForPid(cat);
                ex += ' ' + label;
                if(anns[cat] > max) {
                    max = anns[cat];
                    theLabel = label;
                }
                if(anns[cat] > 1) {
                    ex += '&nbsp;x' + anns[cat];
                }
            }
	    if(theLabel != '') {
		setLabel(cell,theLabel);
		$(cell).find('.subcaption').html(ex);
	    }
        }
    });
}
function clearPage() {
    $('#images').empty();
}
function setLabel(cell,label) {
    /* first convert undefined to '' */
    var previousLabel = $(cell).data('previous-label');
    previousLabel = previousLabel == undefined ? '' : previousLabel;
    $(cell).data('previous-label',previousLabel);
    /* now swap */
    $(cell).data('previous-label',$(cell).data('label'));
    $(cell).data('label',label);
    var p = $(cell).data('previous-label');
    clog('setting caption to '+label);
    $(cell).find('div.caption').html(label);
}
function unsetLabel(cell) {  /* cell = thumbnail div containing image */
    setLabel(cell,$(cell).data('previous-label'));
}
function select(cell,label) {  /* cell = thumbnail div containing image */
    /* select */
    if(label == '') { // if there's no class selected, clear everything
        $(cell).removeClass('selected');
        clearBoundingBox(cell);
    } else {
        setLabel(cell,label);
        $(cell).addClass('selected');
    }
}
function clearBoundingBox(cell) {
    var w = $(cell).data('scaledWidth');
    var h = $(cell).data('scaledHeight');
    $(cell).data('ox',-1);
    $(cell).data('oy',-1);
    var ctx = $(cell).find('canvas.new')[0].getContext('2d');
    ctx.clearRect(0,0,w,h);
}
function deselect(cell) {  /* cell = thumbnail div containing image */
    /* deselect */
    unsetLabel(cell);
    $(cell).removeClass('selected');
    clearBoundingBox(cell);
}
function toggleSelected(cell,label) { /* cell = thumbnail div containing image */
    if($(cell).hasClass('selected')) {
        deselect(cell);
    } else {
        select(cell,label);
    }
}
function commitCell(cell) {
    $(cell).removeClass('selected');
    clearBoundingBox(cell);
}
function pending() {
    return $('#workspace').data('pending');
}
function preCommit() {
    /* generate an ID for each annotation */
    var n = 0;
    for(var k in pending()) { n++; }
    var i = n-1;
    /* FIXME hardcoded namespace */
    with_json_request('/generate_ids/'+n+'/http://foobar.ns/ann_', function(r) {
        $.each(pending(), function(image_pid, ann) {
            pending()[image_pid].pid = r[i--];
        });
        commit();
    });
}
function queueAnnotation(ann) {
    ann.annotator = 'http://people.net/joeblow';
    ann.timestamp = iso8601(new Date());
    clog('enqueing '+JSON.stringify(ann));
    pending()[ann.image] = ann;
}
function commit() {
    clog('committing...');
    var as = [];
    $.each(pending(), function(image_pid, ann) {
        as.push(ann)
        clog(ann.image+' is a '+ann.category+' at '+ann.timestamp+', ann_id='+ann.pid);
    });
    $.ajax({
        url: '/create_annotations',
        type: 'POST',
        contentType: 'json',
        dataType: 'json',
        data: JSON.stringify(as),
        success: function() {
            $('div.thumbnail.selected').each(function(ix,cell) {
                commitCell(cell);
                showExistingAnnotations(cell);
            });
            postCommit();
        }
    });
}
function postCommit() {
    $('#workspace').data('pending',{});
}
function deselectAll() {
    $('#workspace').data('pending',{});
    $('div.thumbnail.selected').each(function(ix,cell) {
        toggleSelected(cell);
    });
}
function listAssignments() {
    with_json_request('/list_assignments', function(r) {
        $.each(r.assignments, function(i,a) {
            clog(a);
            $('#assignment').append('<option value="'+a.pid+'">'+a.label+'</option>')
        });
    });
}
function changeAssignment(ass_pid) {
    $('#label').val('');
    var ass_pid = $('#assignment').val();
    clog('user selected assignment '+ass_pid);
    with_json_request('/fetch_assignment/'+ass_pid, function(r) {
      clog('fetched assignment '+ass_pid);
        $('#workspace').data('assignment',r);
        $('#workspace').data('images',r.images);
        with_json_request('/list_categories/'+r.mode, function(c) {
            clog('fetched categories for mode '+r.mode);
            $('#workspace').data('categories',c);
            gotoPage(1,25);
        });
    });
}
function categoryPidForLabel(label) {
    var cats = $('#workspace').data('categories');
    if(cats == undefined) { return; }
    for(var i = 0; i < cats.length; i++) {
        if(cats[i].label==label) {
            return cats[i].pid;
        }
    }
}
function categoryLabelForPid(pid) {
    var cats = $('#workspace').data('categories');
    if(cats == undefined) { return; }
    for(var i = 0; i < cats.length; i++) {
        if(cats[i].pid==pid) {
            return cats[i].label;
        }
    }
}
$(document).ready(function() {
    page = 1;
    size = 20;
    $('#workspace').data('pending',{}); // pending annotations by pid
    // inputs are ui widget styled
    $('input').addClass('ui-widget');
    // images div is not text-selectable
    $('#images').disableSelection(); // note that this is a jQuery UI function
    // images are not draggable
    $('img').live('mousedown',function(event) {
        event.preventDefault();
    });
    $('a.button').button();
    $('#prev').click(function() {
        page--;
        if(page < 1) page = 1;
        gotoPage(page,25);
    });
    $('#next').click(function() {
        page++;
        gotoPage(page,25);
    });
    $('#commit').click(function() {
        preCommit();
    });
    $('#cancel').click(function() {
        deselectAll();
    });
    $('#assignment').change(function() {
        changeAssignment($('#assignment').val());
    });
    listAssignments();
    gotoPage(page,size);
    $('#label').autocomplete({
        source: function(req,resp) {
            var ass = $('#workspace').data('assignment');
            if(ass == undefined) {
                return;
            }
            with_json_request('/category_autocomplete/'+ass.mode+'?term='+req.term, function(r) {
                resp($.map(r,function(item) {
                    return {
                        'label': item.label,
                        'value': item.value
                    }
                }));
            });
        },
        minLength: 2
    });
    $('#closeRight').bind('click', function() {
        $('#openRight').show();
        $('#rightPanel').hide(100);
    });
    $('#openRight').bind('click', function() {
        $('#openRight').hide();
        $('#rightPanel').show(100, resizeAll);
    });
});
function resizeAll() {
    // resize the right panel
    if($('#rightPanel').is(':visible')) {
        var rp = $('#rightPanel');
        rp.height($(window).height() - ((rp.outerHeight() - rp.height()) + (rp.offset().top * 2)));
    }
}