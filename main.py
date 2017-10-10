import os
import random
import re

import email
import imaplib
import json

import webapp2
import jinja2

from google.appengine.ext import db

## TODO ###################################################
#
# - add cookie to prevent user from voting over and over
# - add "top rated" page
#
##

# to run test server from command line (from project dir):
# dev_appserver.py --port 8888 .
#
# to deploy the app from command line (from project dir):
# appcfg.py update .

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
    
###########################################################

class Vote(db.Model):
    votes = db.IntegerProperty(required = True)
    
    @staticmethod
    def parent_key(clip_id):
        return db.Key.from_path('clip', clip_id)

    @classmethod
    def by_clip(cls, clip_id):
        q = cls.all()
        q.ancestor(cls.parent_key(clip_id))
        return q.get()

###########################################################

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
        
    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)
        
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

class MainHandler(Handler):
    def get(self):
        clip_id = str(NUM_CLIPS)
        html = self.render_str(clip_path(clip_id))
        
        votes = 0
        v = Vote.by_clip(clip_id)
        if v:
            votes = v.votes
            
        self.render('front.html', 
            clip_id=clip_id,
            votes=votes,
            monkey_dialog=html,
            first=1,
            prev=max(1,int(clip_id)-1),
            next=min(NUM_CLIPS,int(clip_id)+1),
            last=NUM_CLIPS)

class ClipHandler(Handler):
    def get(self, clip_id):
        html = self.render_str(clip_path(clip_id))
        
        votes = 0
        v = Vote.by_clip(clip_id)
        if v:
            votes = v.votes
            
        self.render('front.html', 
            clip_id=clip_id,
            votes=votes,
            monkey_dialog=html,
            first=1,
            prev=max(1,int(clip_id)-1),
            next=min(NUM_CLIPS,int(clip_id)+1),
            last=NUM_CLIPS)

class RandomHandler(Handler):
    def get(self):
        clip_id = str(random.randint(1,NUM_CLIPS))
        self.redirect('/' + clip_id)
        
class AboutHandler(Handler):
    def get(self):
        self.render('about.html')

class DonateHandler(Handler):
    def get(self):
        self.redirect("https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=L4448FFX778T6")
        
class VoteHandler(Handler):
    def get(self, clip_id, vote_type):
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
            
            v = Vote.by_clip(clip_id)
            if not v:
                v = Vote(key_name=clip_id, votes=adj_vote, parent=Vote.parent_key(clip_id))
            else:
                v.votes += adj_vote
            v.put()
        
        self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.write(json.dumps(data))
        
app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/(\d+)', ClipHandler),
    ('/random', RandomHandler),
    ('/about', AboutHandler),
    ('/donate', DonateHandler),
    ('/vote/(\d+)/([a-z]+)', VoteHandler)
], debug=True)
