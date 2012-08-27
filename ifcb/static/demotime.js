$(document).ready(function() {
    // add a title
    var title = 'MVCO data volume';
    $('body').append('<h1>'+title+'</h1>');
    function showNearest(date) {
	var ds = date.toISOString();
	$.getJSON('/api/feed/nearest/'+ds, function(r) { // find the nearest bin
	    console.log(JSON.stringify(r)); // FIXME need the date
	    // now draw a multi-page mosaic
	    var pid = r.pid;
	    var roi_scale = 0.333; // scaling factor per roi
	    var width = 600; // width of displayed mosaic
	    var height = 480; // height of displayed mosaic
	    // put 30 pages on the pager, just in case it's a huge bin
	    var images = []
	    for(page=1; page <= 30; page++) {
		images.push('/api/mosaic/size/'+width+'x'+height+'/scale/'+roi_scale+'/page/'+page+'/pid/'+pid+'.jpg');
	    }
	    // create an image pager
	    $('#mosaic_pager').empty().append('<div/><p class="bin_label">'+pid+'</p>')
		.find('div:last').imagePager(images, width, height);
	});
    }
    // add the timeline control
    $('body').append('<div id="timeline"></div>').find('div').timeline()
	/*
	.bind('dateHover', function(event, date, clientX) { // on hover, show the date
	    $('#date_label').empty().append(date.toISOString());
	    $('#date_label').css('margin-left',clientX);
	})
	.bind('dateClick', function(event, date, clientX) { // on click,
	});
	*/
	.timeline_bind('timechange', function(timeline, r) {
	    var date = r.time;
	    $('#date_label').empty().append(date.toISOString());
	}).timeline_bind('timechanged', function(timeline, r) {
	    showNearest(r.time);
	}).timeline_bind('select', function(t) {
	    var date = t.hoverDate;
	    $.each(t.getSelection(), function(ix, s) {
		//var date = t.getItem(s.row).start;
		$('#date_label').empty().append(date.toISOString());
		showNearest(date);
	    });
	});
    ;
    // now load the data volume series
    console.log('loading data series...');
    $.getJSON('/api/volume', function(volume) {
	// make a bar graph showing data volume
	var data = [];
	$.each(volume, function(ix, day_volume) {
	    // for each day/volume record, make a bar
	    // get the volume data for that day
	    var bin_count = day_volume.bin_count;
	    var date = day_volume.day; // FIXME key should be "date"
	    var gb = day_volume.gb; // FIXME currently ignored
	    // create a one-day time interval
	    var year = date.split('-')[0];
	    var month = date.split('-')[1];
	    var day = date.split('-')[2];
	    var start = new Date(year, month-1, day)
	    var end = new Date(year, month-1, day);
	    end.setHours(end.getHours() + 24);
	    // create a bar. here we need to scale GB to > 1px/GB or else the bars'll be tiny
	    var height = Math.round(gb * 15);
	    var style = 'height:' + height + 'px;'
	    var color = '#ff0000';
	    style = 'height:' + height + 'px;' +
		'margin-bottom: -25px;'+
		'background-color: ' + color + ';'+
		'border: 1px solid ' + color + ';';
	    var bar = '<div class="bar" style="' + style + '" ' +
		' title="'+gb.toFixed(2)+'GB"></div>';
	    var item = {
		'group': 'bytes/day', // "Group" is displayed on the left as a label
		'start': start,
		'end': end,
		'content': bar
	    };
	    // we're done with one bar
	    data.push(item);
	});
	// layout parameters accepted by showdata and passed to underlying widget
	var timeline_options = {
	    'width':  '100%',
	    'height': '150px',
	    'style': 'box',
	    'showCustomTime': true,
	    'showNavigation': true
	};
	// now tell the timeline plugin to draw it
	$('#timeline').trigger('showdata', [data, timeline_options]);
    });
    // our date label goes below the timeline
    $('body').append('<div id="date_label"></div>');
    // and the mosaic pager is below that
    $('body').append('<div id="mosaic_pager"></div>');
});
