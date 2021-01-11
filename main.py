import json
import os
import random
import re

import flask
import jinja2

from google.cloud import datastore
from flask import Flask, redirect, request, url_for

# import update

app = Flask(__name__)


## TODO ###################################################
#
# - add cookie to prevent user from voting over and over
# - add "top rated" page
#
##

##
# to run test server from command line (from project dir):
# python main.py
#
# to deploy the app from command line (from project dir):
# gcloud app deploy
#
# to view live log of webserver from the command line:
# gcloud app logs tail -s default
##

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    extensions=['jinja2.ext.autoescape'])

NUM_CLIPS = sum([\
 len([x for x in os.listdir(os.path.join(template_dir,f)) if re.match('[0-9]+\.html', x)])\
 for f in os.listdir(template_dir) if os.path.isdir(os.path.join(template_dir,f))\
]) - 1 # base-0 numbering

def clip_path(clip_id):
    clip_id = int(clip_id)
    return "%d/%d.html" % (1 + clip_id/1000, clip_id%1000)

def render(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

def render_front(clip_id):
    dialog = render(clip_path(clip_id))
    return render('index.html',
        clip_id=clip_id,
        votes=0, #votes(clip_id),
        monkey_dialog=dialog,
        first=1,
        prev=max(1,int(clip_id)-1),
        next=min(NUM_CLIPS,int(clip_id)+1),
        last=NUM_CLIPS)

def votes(clip_id):
    client = datastore.Client()
    k = datastore.key.Key('clip', clip_id, 'Vote', clip_id, project='monkey-business')
    v = client.get(k)
    if v:
        return v['votes']
    return 0

###########################################################

@app.route('/')
def MainHandler():
    clip_id = str(NUM_CLIPS)
    return render_front(clip_id)

# @app.route('/robots.txt')
# def RobotHandler():
#     return "\n".join(["User-agent: *","Allow: /"])

@app.route('/<int:clip_id>')
def ClipHandler(clip_id):
    return render_front(clip_id)

@app.route('/random')
def RandomHandler():
    rand_id = random.randint(1,NUM_CLIPS)
    return redirect(url_for('ClipHandler', clip_id=rand_id))

@app.route('/about')
def AboutHandler():
    return render('about.html')

@app.route('/donate')
def DonateHandler():
    return redirect("https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=L4448FFX778T6")

@app.route('/vote/<clip_id>/<vote_type>')
def VoteHandler(clip_id, vote_type):
    client = datastore.Client()

    data = {}
    data['success'] = True

    if vote_type == 'up':
        adj_vote = 1
    elif vote_type == 'down':
        adj_vote = -1
    else:
        data['error_message'] = "Invalid vote command"
        data['success'] = False

    if data['success'] == True:
        data['commands'] = {
            'update_post_score': [clip_id, adj_vote],
            'update_user_post_vote': [clip_id, vote_type]
            }

    k = datastore.key.Key('clip', clip_id, 'Vote', clip_id, project='monkey-business')
    v = client.get(k)
    if not v:
        v = datastore.Entity(key=k)
        v['votes'] = adj_vote
    else:
        v['votes'] += adj_vote
    client.put(v)

    resp = flask.Response(json.dumps(data))
    resp.headers['Content-Type'] = 'application/json; charset=UTF-8'
    return resp

@app.route('/update')
def UpdateHandler():
    ret = False
    msg = "Invalid request"
    if True or request.headers.get('X-Appengine-Cron') == 'true':
        ret, msg = update.main()
    resp = flask.make_response(msg, 200 if ret else 500)
    return resp

@app.route('/favicon.ico')
def FaviconHandler():
    return url_for("static", filename="favicon.ico")

###########################################################

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
