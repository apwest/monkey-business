$(document).ready(function(){
    $("a.ajax-command").click(function(evt) {
        if (running) return false;

        var el = $(this);

        var ajax_url = el.attr('href')
        ajax_url = ajax_url + "?nocache=" + new Date().getTime()

		start_command();
		$.getJSON(ajax_url, function(data) {
			process_ajax_response(data, evt);
		});

        return false
    });

//---------------------------------------------------------
  
	$("a.vote-up-off").click(function(){
		$.get("vote?v=up",function(data,status){
			alert("Data: " + data + "\nStatus: " + status);
			if (status == 'success'){
				x = $("span.vote-count-post").text();
				$("span.vote-count-post").text(Number(x) + 1);
			}
		});
	});

	$("a.vote-down-off").click(function(){
		$.get("vote?v=down",function(data,status){
			alert("Data: " + data + "\nStatus: " + status);
			if (status == 'success'){
				x = $("span.vote-count-post").text();
				$("span.vote-count-post").text(Number(x) - 1);
		  }
		});
	});

});

var response_commands = {
    update_post_score: function(id, inc) {
        var $score_board = $('#dialog-' + id + '-score');
        var current = parseInt($score_board.html())
        if (isNaN(current)){
            current = 0;
        }
        $score_board.html(current + inc)
    },

    update_user_post_vote: function(id, vote_type) {
        var $upvote_button = $('#dialog-' + id + '-upvote');
        var $downvote_button = $('#dialog-' + id + '-downvote');

        $upvote_button.removeClass('on');
        $downvote_button.removeClass('on');

        if (vote_type == 'up') {
            $upvote_button.addClass('on');
        } else if (vote_type == 'down') {
            $downvote_button.addClass('on');
        }
    }
}

var running = false;

function start_command() {
    $('body').append($('<div id="command-loader"></div>'));
    running = true;
}

function end_command(success) {
    if (success) {
        $('#command-loader').addClass('success');
        $('#command-loader').fadeOut("slow", function() {
            $('#command-loader').remove();
            running = false;
        });
    } else {
        $('#command-loader').remove();
        running = false;
    }
}

function process_ajax_response(data, evt) {
    if (!data.success && data['error_message'] != undefined) {
        alert("Event: " + evt + "\r\nMessage: " + data.error_message);
        end_command(false);
    }
    if (typeof data['commands'] != undefined){
        for (var command in data.commands) {
            response_commands[command].apply(null, data.commands[command])
        }

        if (data['message'] != undefined) {
            alert("Event: " + evt + "\r\nMessage: " + data.message);
        }
        end_command(true);
    }
}