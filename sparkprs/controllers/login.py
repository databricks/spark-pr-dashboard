import json
import logging
import urllib
import urlparse

from flask import redirect, session, url_for, g, request, Response
from google.appengine.api import urlfetch, users
from flask import Blueprint

from sparkprs import app, db
from sparkprs.models2 import User
from sparkprs.github_api import github_request, BASE_AUTH_URL


login = Blueprint('login', __name__)


@login.before_app_request
def before_request():
    g.user = None
    if 'github_username' in session:
        g.user = User.query.filter_by(github_username=session['github_username']).first()


@login.route('/github-callback')
def github_authorized_callback():
    # This is based loosely on https://github.com/cenkalti/github-flask
    # and http://stackoverflow.com/a/22275563
    if 'code' not in request.args:
        raise Exception("Got error from GitHub")
    next_url = request.args.get('next') or url_for('main')
    payload = {
        'code': request.args.get('code'),
        'client_id': app.config['GITHUB_CLIENT_ID'],
        'client_secret': app.config['GITHUB_CLIENT_SECRET'],
    }
    auth_url = BASE_AUTH_URL + 'access_token'
    logging.info("Auth url is %s" % auth_url)
    response = urlfetch.fetch(auth_url, method=urlfetch.POST, payload=urllib.urlencode(payload),
                              validate_certificate=True)
    if response.status_code != 200:
        raise Exception("Got %i response from GitHub:\n%s" %
                        (response.status_code, response.content))
    data = urlparse.parse_qs(response.content)
    github_access_token = data.get('access_token', None)
    if github_access_token is None:
        return redirect(next_url)
    github_access_token = github_access_token[0].decode('ascii')
    github_json = json.loads(github_request("user", oauth_token=github_access_token).content)
    github_username = github_json['login']
    user = User.query.filter_by(github_username=github_username).first() \
           or User(github_username, github_access_token)
    user.github_json = github_json
    user.github_access_token = github_access_token
    db.session.add(user)
    db.session.commit()
    session['github_username'] = github_username
    return redirect(next_url)


@login.route('/login')
def login_handler():
    query = {
        'client_id': app.config['GITHUB_CLIENT_ID'],
        'redirect_uri': app.config['GITHUB_CALLBACK_URL'],
        }
    auth_url = BASE_AUTH_URL + 'authorize?' + urllib.urlencode(query)
    return redirect(auth_url)


@login.route('/logout')
def logout():
    session.pop('github_username', None)
    return redirect(url_for('main'))


@login.route('/appengine-admin-login')
def appengine_admin_login():
    return redirect(users.create_login_url("/"))


@login.route('/appengine-admin-logout')
def appengine_admin_logout():
    return redirect(users.create_logout_url("/"))


@login.route('/user-info')
def user_info():
    """
    Returns JSON describing the currently-signed-in user.
    """
    if g.user:
        user_dict = {
            'github_login': g.user.github_username,
            'roles': [], # TODO: fix roles support  # g.user.roles,
            }
    else:
        user_dict = None
    return Response(json.dumps(user_dict, indent=2, separators=(',', ': ')),
                    mimetype='application/json')
