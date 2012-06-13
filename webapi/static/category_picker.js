// mmm mm some tasty jQuery extensibility
(function($) {
    $.fn.extend({
        categoryPicker: function(scope, callback) {
	    return this.each(function() {
		var $this = $(this);
		$this.data('all_categories',[]);
		$this.data('recent',[]);
		function add_choice() {
		    var select = $this.append('<div><select class="category_choice"></select></div>').find('select');
		    $.each($this.data('all_categories'),function(ix,c) {
			$(select).append('<option value="'+c.pid+'">'+c.label+'</option>')
		    });
		    $this.find('.button').replaceWith('<a href="#" class="button">-</a>').end().find('.button').button().click(function() { $(this).parent().remove(); });
		    $this.find('div:last').append('<a href="#" class="button">+</a>').find('.button').button().click(add_choice);
		}
		$.getJSON('/list_categories/'+scope, function(c) {
		    $this.data('all_categories',c);
		    add_choice();
		});
	    });
	}
    });
})(jQuery);
$(document).ready(function() {
    $('#picker1').categoryPicker('QC_Fish',function(categories) {
	alert('yall selected '+JSON.stringify(categories));
    });
    $('#picker2').categoryPicker('QC_Fish',function(categories) {
	alert('talkin bout '+JSON.stringify(categories));
    });
});

