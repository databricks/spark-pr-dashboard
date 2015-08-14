import json
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from datetime import datetime
import itertools
import logging

from flask import Blueprint
from google.appengine.api import taskqueue
import feedparser

from sparkprs import app
from sparkprs.models import Issue, JIRAIssue, KVS
from sparkprs.github_api import raw_github_request, ISSUES_BASE
from link_header import parse as parse_link_header


tasks = Blueprint('tasks', __name__)


@tasks.route("/update-github-prs")
def update_github_prs():
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
            taskqueue.add(url="/tasks/update-github-pr/%i" % pr['number'], queue_name=queue_name)
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


@tasks.route("/update-github-pr/<int:number>", methods=['GET', 'POST'])
def update_pr(number):
    Issue.get_or_create(number).update(app.config['GITHUB_OAUTH_KEY'])
    return "Done updating pull request %i" % number


@tasks.route("/update-jira-issues")
def update_jira_issues():
    feed_url = "%s/activity?maxResults=20&streams=key+IS+%s&providers=issues" % \
               (app.config['JIRA_API_BASE'], app.config['JIRA_PROJECT'])
    feed = feedparser.parse(feed_url)
    # To avoid double-processing of RSS feed entries, only process entries that are newer than
    # the watermark set during the last refresh:
    last_watermark = KVS.get("jira_sync_watermark")
    if last_watermark is not None:
        new_entries = [i for i in feed.entries if i.published_parsed > last_watermark]
    else:
        new_entries = feed.entries
    if not new_entries:
        return "No new entries to update since last watermark " + str(last_watermark)
    issue_ids = set(i.link.split('/')[-1] for i in new_entries)
    for issue in issue_ids:
        taskqueue.add(url="/tasks/update-jira-issue/" + issue, queue_name='jira-issues')
    KVS.put('jira_sync_watermark', new_entries[0].published_parsed)
    return "Queued JIRA issues for update: " + str(issue_ids)


@tasks.route("/update-jira-issues-for-all-open-prs")
def update_all_jiras_for_open_prs():
    """
    Used to bulk-load information from JIRAs for all open PRs.  Useful when upgrading
    from an earlier version of spark-prs.
    """
    prs = Issue.query(Issue.state == "open").order(-Issue.updated_at).fetch()
    jira_issues = set(itertools.chain.from_iterable(pr.parsed_title['jiras'] for pr in prs))
    for issue in jira_issues:
        taskqueue.add(url="/tasks/update-jira-issue/SPARK-%i" % issue, queue_name='jira-issues')
    return "Queued JIRA issues for update: " + str(jira_issues)


@tasks.route("/update-jira-issue/<string:issue_id>", methods=['GET', 'POST'])
def update_jira_issue(issue_id):
    JIRAIssue.get_or_create(issue_id).update()
    return "Done updating JIRA issue %s" % issue_id
