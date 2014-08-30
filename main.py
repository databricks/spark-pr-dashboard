import json
from datetime import datetime
import logging
import os

from flask import Flask
from flask import render_template, session
from google.appengine.api import taskqueue, memcache

from sparkprs.models import Issue, KVS
from sparkprs.github_api import raw_request, ISSUES_BASE
from link_header import parse as parse_link_header


app = Flask(__name__)
app.config.from_pyfile('settings.cfg')


IS_DEV_APPSERVER = os.environ['SERVER_SOFTWARE'].startswith('Development')
VERSION = os.environ['CURRENT_VERSION_ID']


@app.route("/tasks/update-issues")
def update_issues():
    def fetch_and_process(url):
        logging.debug("Following url %s" % url)
        response = raw_request(url, oauth_token=app.config['GITHUB_OAUTH_KEY'])
        link_header = parse_link_header(response.headers.get('Link', ''))
        prs = json.loads(response.content)
        for pr in prs:
            taskqueue.add(url="/tasks/update-issue/%i" % pr['number'])
        for link in link_header.links:
            if link.rel == 'next':
                fetch_and_process(link.href)
    last_update_time = KVS.get("issues_since")
    url = ISSUES_BASE + "?sort=updated&state=all&direction=desc&per_page=100"
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
    homepage = memcache.get("homepage", namespace=VERSION)
    if IS_DEV_APPSERVER or homepage is None:
        issues = Issue.query(Issue.state == "open").order(-Issue.updated_at).fetch()
        homepage = render_template('index.html', session=session, issues=issues)
        memcache.set("homepage", value=homepage, time=60, namespace=VERSION)
    return homepage
