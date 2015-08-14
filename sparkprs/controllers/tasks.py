from datetime import datetime
import itertools
import json
import logging
import re

from flask import Blueprint, url_for
from google.appengine.api import taskqueue
import feedparser
from link_header import parse as parse_link_header
from dateutil.parser import parse as parse_datetime
from dateutil import tz

from sparkprs.models import Issue, JIRAIssue, KVS
from sparkprs.github_api import raw_github_request, paginated_github_request, PULLS_BASE, \
    ISSUES_BASE
from sparkprs import app
from sparkprs.jira_api import start_issue_progress, link_issue_to_pr


tasks = Blueprint('tasks', __name__)


oauth_token = app.config['GITHUB_OAUTH_KEY']


@tasks.route("/github/update-prs")
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
            taskqueue.add(url=url_for(".update_pr", pr_number=pr['number']), queue_name=queue_name)
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


@tasks.route("/github/update-pr/<int:pr_number>", methods=['GET', 'POST'])
def update_pr(pr_number):
    logging.debug("Updating pull request %i" % pr_number)
    pr = Issue.get_or_create(pr_number)
    issue_response = raw_github_request(PULLS_BASE + '/%i' % pr_number,
                                        oauth_token=oauth_token, etag=pr.etag)
    if issue_response is None:
        logging.debug("PR %i hasn't changed since last visit; skipping" % pr_number)
        return "Done updating pull request %i (nothing changed)" % pr_number
    pr.pr_json = json.loads(issue_response.content)
    pr.etag = issue_response.headers["ETag"]
    pr.state = pr.pr_json['state']
    pr.user = pr.pr_json['user']['login']
    pr.updated_at = \
        parse_datetime(pr.pr_json['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)

    for issue_number in pr.parsed_title['jiras']:
        try:
            link_issue_to_pr("SPARK-%s" % issue_number, pr)
        except:
            logging.exception("Exception when linking to JIRA issue SPARK-%s" % issue_number)
        try:
            start_issue_progress("SPARK-%s" % issue_number)
        except:
            logging.exception(
                "Exception when starting progress on JIRA issue SPARK-%s" % issue_number)

    pr.put()  # Write our modifications back to the database

    subtasks = [".update_pr_comments", ".update_pr_review_comments", ".update_pr_files"]
    for task in subtasks:
        taskqueue.add(url=url_for(task, pr_number=pr_number), queue_name='fresh-prs')

    return "Done updating pull request %i" % pr_number


@tasks.route("/github/update-pr-comments/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_comments(pr_number):
    pr = Issue.get(pr_number)
    comments_response = paginated_github_request(ISSUES_BASE + '/%i/comments' % pr_number,
                                                 oauth_token=oauth_token)
    # TODO: after fixing #32, re-enable etags here: etag=self.comments_etag)
    if comments_response is None:
        return "Comments for PR %i are up-to-date" % pr_number
    else:
        pr.comments_json, pr.comments_etag = comments_response
        pr.cached_commenters = pr._compute_commenters()
        pr.cached_last_jenkins_outcome = None
        pr.last_jenkins_outcome  # force recomputation of Jenkins outcome
        pr.put()  # Write our modifications back to the database

        # Delete out-of-date comments from AmplabJenkins and SparkQA.
        jenkins_comment_to_preserve = pr.last_jenkins_comment
        sparkqa_token = app.config["SPARKQA_GITHUB_OAUTH_KEY"]
        amplabjenkins_token = app.config["AMPLAB_JENKINS_GITHUB_OAUTH_KEY"]
        sparkqa_start_comments = {}  # Map from build ID to build start comment
        for comment in (pr.comments_json or []):
            author = comment["user"]["login"]
            # Delete all comments from AmplabJenkins unless they are the comments that should be
            # displayed on the Spark PR dashboard.
            if author == "AmplabJenkins" and comment["url"] != jenkins_comment_to_preserve["url"]:
                raw_github_request(comment["url"], oauth_token=amplabjenkins_token, method="DELETE")
            elif author == "SparkQA":
                # Only delete build start notification comments from SparkQA and only delete them
                # after we've seen the corresponding build finished message.
                start_regex_match = re.search(r"Test build #(\d+) has started", comment["body"])
                if start_regex_match:
                    sparkqa_start_comments[start_regex_match.groups()[0]] = comment
                else:
                    end_regex_match = re.search(r"Test build #(\d+) has finished", comment["body"])
                    if end_regex_match:
                        start_comment = sparkqa_start_comments.get(end_regex_match.groups()[0])
                        if start_comment:
                            raw_github_request(start_comment["url"], oauth_token=sparkqa_token,
                                               method="DELETE")
        return "Done updating comments for PR %i" % pr_number


@tasks.route("/github/update-pr-review-comments/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_review_comments(pr_number):
    pr = Issue.get(pr_number)
    pr_comments_response = paginated_github_request(PULLS_BASE + '/%i/comments' % pr_number,
                                                    oauth_token=oauth_token)
    # TODO: after fixing #32, re-enable etags here: etag=self.pr_review_comments_etag)
    if pr_comments_response is None:
        return "Review comments for PR %i are up-to-date" % pr_number
    else:
        pr.pr_comments_json, pr.pr_comments_etag = pr_comments_response
        pr.cached_commenters = pr._compute_commenters()
        pr.put()  # Write our modifications back to the database
        return "Done updating review comments for PR %i" % pr_number


@tasks.route("/github/update-pr-files/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_files(pr_number):
    pr = Issue.get(pr_number)
    files_response = paginated_github_request(PULLS_BASE + "/%i/files" % pr_number,
                                              oauth_token=oauth_token, etag=pr.files_etag)
    if files_response is None:
        return "Files for PR %i are up-to-date" % pr_number
    else:
        pr.files_json, pr.files_etag = files_response
        pr.put()  # Write our modifications back to the database
        return "Done updating files for PR %i" % pr_number


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
