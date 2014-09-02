import json
from collections import defaultdict
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from datetime import datetime
import logging
import os

from flask import Flask
from flask import render_template, session, make_response
from google.appengine.api import taskqueue

from sparkprs.models import Issue, KVS
from sparkprs.github_api import raw_request, ISSUES_BASE
from link_header import parse as parse_link_header


app = Flask(__name__)
app.config.from_pyfile('settings.cfg')


VERSION = os.environ['CURRENT_VERSION_ID']


@app.route("/tasks/update-issues")
def update_issues():
    def fetch_and_process(url):
        logging.debug("Following url %s" % url)
        response = raw_request(url, oauth_token=app.config['GITHUB_OAUTH_KEY'])
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


@app.route('/')
def main():
    issues = Issue.query(Issue.state == "open").order(-Issue.updated_at).fetch()
    issues_by_component = defaultdict(list)
    for issue in issues:
        for component in issue.components:
            issues_by_component[component].append(issue)
    # Display the groups in the order listed in Issues._components
    grouped_issues = [(c[0], issues_by_component[c[0]]) for c in Issue._components]
    homepage = render_template('index.html', session=session,
                               grouped_issues=grouped_issues)
    response = make_response(homepage)
    response.cache_control.max_age = 60
    return response
