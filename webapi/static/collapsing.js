// jQuery UI plugin providing collapsing element
(function($) {
    $.fn.extend({
	collapsing: function(title, initial_state) {
	    return this.each(function () {
		var $this = $(this); // retain ref to $(this)
		var state = (initial_state != undefined && initial_state) ? 1 : 0;
		var e = $this.wrap('<div class="collapsing_content"></div>').parent()
		    .css('display',state ? 'block' : 'none')
		    .wrap('<div class="collapsing"></div>').parent();
		if(state) {
		    $(e).prepend('<div class="collapse_button collapse_button_open"> '+title+'</div>');
		} else {
		   $(e).prepend('<div class="collapse_button collapse_button_closed"> '+title+'</div>');
		}
		$(e).find('.collapse_button')
		    .click(function() {
			console.log('clicked collapse button');
			if(state == 0) {
			    $(e).find('.collapse_button').removeClass('collapse_button_closed')
				.addClass('collapse_button_open')
				.empty().append(' ' + title);
			    $(e).find('.collapsing_content').css('display','block');
			    state = 1;
			    $this.trigger('collapse_state', [state]);
			} else {
			    $(e).find('.collapse_button').removeClass('collapse_button_open')
				.addClass('collapse_button_closed')
				.empty().append(' ' +title);
			    $(e).find('.collapsing_content').css('display','none');
			    state = 0;
			    $this.trigger('collapse_state', [state]);
			}
		    });
	    });//each in collapsing
	}//collapsing
    });//$.fn.extend
})(jQuery);//end of plugin
