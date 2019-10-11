# coding=UTF-8
# Flask routes program for Stk application
# @ Sss 2016
# JMä 29.12.2015 - 4.1.2019

import urllib

import logging 
logger = logging.getLogger('stkserver')
#import time

from flask import render_template, request #, g, redirect, url_for, flash
from flask_security import login_required, logout_user, current_user # ,roles_required

# i18n: https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xiv-i18n-and-l10n-legacy
#from flask_babelex import Babel
#from flask_babelex import _

import shareds

app = shareds.app
if not app:
    raise RuntimeError("Start this application in '..' from 'run.py' or 'runssl.py'")


@shareds.app.route('/')
def entry():
    if current_user.has_role("guest"):
#        print("Authenticated guest user at entry") 
        logout_user()
          
    return render_template('/entry_index.html')

""" -------------------------- Yleinen virhesivu ------------------------------
"""

#TODO Pitäisi korvata jollain ilmoituskentällä ...
@app.route('/virhe_lataus/<int:code>/<text>')
def virhesivu(code, text=''):
    """ Virhesivu näytetään """
    logging.debug('Virhesivu ' + str(code) )
    return render_template("virhe_lataus.html", code=code, text=text)
'''
babel = Babel(app)

@babel.localeselector
def get_locale():
    try:
        g.locale = current_user.language 
        return current_user.language
    except:
        pass
    return "fi"
    #return "en"
    #return request.accept_languages.best_match(get('LANGUAGES'))
    '''

@shareds.app.route('/help')
@login_required
def app_help():
    url = request.args.get("url")
    path = urllib.parse.urlparse(url)
    return "Help for {}".format(path.path)

# ------------------------------ Filters ---------------------------------------
from templates import jinja_filters
