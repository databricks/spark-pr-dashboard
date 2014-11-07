import json
from collections import defaultdict
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from datetime import datetime
import logging
import urllib
import urlparse

from flask import render_template, redirect, session, make_response, url_for, g, request, abort, \
    Response
from gae_mini_profiler.templatetags import profiler_includes
from google.appengine.api import taskqueue, urlfetch

from sparkprs import app, VERSION
from sparkprs.models import Issue, KVS, User
from sparkprs.github_api import raw_github_request, github_request, ISSUES_BASE, BASE_AUTH_URL
from link_header import parse as parse_link_header


#  --------- Authentication and admin panel functionality -----------------------------------------#

@app.before_request
def before_request():
    g.user = None
    if 'github_login' in session:
        g.user = User.query(User.github_login == session['github_login']).get()


@app.route('/github-callback')
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
    access_token = data.get('access_token', None)
    if access_token is None:
        return redirect(next_url)
    access_token = access_token[0].decode('ascii')
    user_json = json.loads(github_request("user", oauth_token=access_token).content)
    user = User.query(User.github_login == user_json['login']).get()
    if user is None:
        user = User(github_login=user_json['login'])
    user.github_user_json = user_json
    user.github_access_token = access_token
    user.put()

    session['github_login'] = user.github_login
    return redirect(url_for('main'))


@app.route('/login')
def login():
    query = {
        'client_id': app.config['GITHUB_CLIENT_ID'],
        'redirect_uri': app.config['GITHUB_CALLBACK_URL'],
    }
    auth_url = BASE_AUTH_URL + 'authorize?' + urllib.urlencode(query)
    return redirect(auth_url)


@app.route('/logout')
def logout():
    session.pop('github_login', None)
    return redirect(url_for('main'))


#  --------- Task queue and cron jobs -------------------------------------------------------------#

@app.route("/tasks/update-issues")
def update_issues():
    def fetch_and_process(url):
        logging.debug("Following url %s" % url)
        response = raw_github_request(url, oauth_token=app.config['GITHUB_OAUTH_KEY'])
        link_header = parse_link_header(response.headers.get('Link', ''))
        prs = json.loads(response.content)
        now = datetime.utcnow()
        for pr in prs:
            updated_at = \
                parse_datetime(pr['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
            is_fresh = (now - updated_at).total_seconds() < app.config['FRESHNESS_THRESHOLD']
            queue_name = ("fresh-prs" if is_fresh else "old-prs")
            taskqueue.add(url="/tasks/update-issue/%i" % pr['number'], queue_name=queue_name)
        for link in link_header.links:
            if link.rel == 'next':
                fetch_and_process(link.href)
    last_update_time = KVS.get("issues_since")
    url = ISSUES_BASE + "?sort=updated&state=all&per_page=100"
    if last_update_time:
        url += "&since=%s" % last_update_time
    fetch_and_process(url)
    KVS.put('issues_since', datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
    return "Done fetching updated GitHub issues"


@app.route("/tasks/update-issue/<int:number>", methods=['GET', 'POST'])
def update_issue(number):
    Issue.get_or_create(number).update(app.config['GITHUB_OAUTH_KEY'])
    return "Done updating issue %i" % number


#  --------- User-facing pages --------------------------------------------------------------------#

def build_response(template, max_age=60, **kwargs):
    num_open_prs = int(Issue.query(Issue.state == "open").count())
    navigation_bar = [
        # (href, id, label, badge_value)
        ('/', 'index', 'Open PRs by Component', num_open_prs),
        ('/all-open-prs', 'all-open-prs', 'All Open PRs', num_open_prs),
    ]
    if g.user and "admin" in g.user.roles:
        navigation_bar.append(('/admin', 'admin', 'Admin', None))
    default_context = {
        'profiler_includes': profiler_includes(),
        'navigation_bar': navigation_bar,
        'user': g.user,
        'APP_VERSION': VERSION,
    }
    rendered = render_template(template, **(dict(default_context.items() + kwargs.items())))
    response = make_response(rendered)
    response.cache_control.max_age = max_age
    return response


def build_pr_json_response(prs, max_age=60):
    json_dicts = []
    for pr in prs:
        d = {
            'parsed_title': pr.parsed_title,
            'number': pr.number,
            'updated_at': str(pr.updated_at),
            'user': pr.user,
            'state': pr.state,
            'components': pr.components,
            'lines_added': pr.lines_added,
            'lines_deleted': pr.lines_deleted,
            'lines_changed': pr.lines_changed,
            'files': (pr.files_json or {}),
            "github_pr_json": (pr.pr_json or {}),
            'is_mergeable': pr.is_mergeable,
            'commenters': pr.commenters,
            'last_jenkins_outcome': pr.last_jenkins_outcome,
        }
        json_dicts.append(d)
    response = Response(json.dumps(json_dicts, indent=2, separators=(',', ': ')),
                        mimetype='application/json')
    response.cache_control.max_age = max_age
    return response


@app.route("/all-prs.json")
def all_prs_json():
    offset = int(request.args.get('offset'))
    limit = 100
    prs = Issue.query(Issue.number > offset).order(Issue.number).fetch(limit)
    return build_pr_json_response(prs)


@app.route("/trigger-jenkins/<int:number>", methods=['GET', 'POST'])
def test_pr(number):
    """
    Triggers a parametrized Jenkins build for testing Spark pull requests.
    """
    if not (g.user and g.user.has_capability("jenkins")):
        return abort(403)
    pr = Issue.get_or_create(number)
    commit = pr.pr_json["head"]["sha"]
    # The parameter names here were chosen to match the ones used by Jenkins' GitHub pull request
    # builder plugin: https://wiki.jenkins-ci.org/display/JENKINS/Github+pull+request+builder+plugin
    # In the Spark repo, the https://github.com/apache/spark/blob/master/dev/run-tests-jenkins
    # script reads these variables when posting pull request feedback.
    query = {
        'token': app.config['JENKINS_PRB_TOKEN'],
        'ghprbPullId': number,
        'ghprbActualCommit': commit,
        # This matches the Jenkins plugin's logic; see
        # https://github.com/jenkinsci/ghprb-plugin/blob/master/src/main/java/org/jenkinsci/plugins/ghprb/GhprbTrigger.java#L146
        #
        # It looks like origin/pr/*/merge ref points to the last successful test merge commit that
        # GitHub generates when it checks for mergeability.  This API technically isn't documented,
        # but enough plugins seem to rely on it that it seems unlikely to change anytime soon
        # (if it does, we can always upgrade our tests to perform the merge ourselves).
        #
        # See also: https://developer.github.com/changes/2013-04-25-deprecating-merge-commit-sha/
        'sha1': ("origin/pr/%i/merge" % number) if pr.is_mergeable else commit,
    }
    trigger_url = "%sbuildWithParameters?%s" % (app.config["JENKINS_PRB_JOB_URL"],
                                                urllib.urlencode(query))
    logging.debug("Triggering Jenkins with url %s" % trigger_url)
    response = urlfetch.fetch(trigger_url, method="POST")
    if response.status_code not in (200, 201):
        logging.error("Jenkins responded with status code %i" % response.status_code)
        return response.content
    else:
        return redirect(app.config["JENKINS_PRB_JOB_URL"])


@app.route("/admin/add-role", methods=['POST'])
def add_role():
    if not g.user or "admin" not in g.user.roles:
        return abort(403)
    user = User.query(User.github_login == request.form["username"]).get()
    if user is None:
        user = User(github_login=request.form["username"])
    role = request.form["role"]
    if role not in user.roles:
        user.roles.append(role)
        user.put()
    return "Updated user %s; now has roles %s" % (user.github_login, user.roles)


@app.route('/admin')
def admin_panel():
    if not g.user or "admin" not in g.user.roles:
        return abort(403)
    return build_response('admin.html')


@app.route('/')
def main():
    issues = Issue.query(Issue.state == "open").order(-Issue.updated_at).fetch()
    issues_by_component = defaultdict(list)
    for issue in issues:
        for component in issue.components:
            issues_by_component[component].append(issue)
    # Display the groups in the order listed in Issues._components
    grouped_issues = [(c[0], issues_by_component[c[0]]) for c in Issue._components]
    return build_response('index.html', grouped_issues=grouped_issues)

@app.route('/all-open-prs')
def all_open_prs():
    prs = Issue.query(Issue.state == "open").order(-Issue.updated_at).fetch()
    return build_response('all_open_prs.html', prs=prs)


@app.route("/users/<username>")
def users(username):
    prs = Issue.query(Issue.state == "open").order(-Issue.updated_at).fetch()
    prs_authored = [p for p in prs if p.user == username]
    prs_commented_on = [p for p in prs if username in dict(p.commenters) and p.user != username]
    return build_response('user.html', username=username, prs_authored=prs_authored,
                          prs_commented_on=prs_commented_on)
