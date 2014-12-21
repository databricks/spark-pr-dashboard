from datetime import datetime
import itertools
import json
import logging

from google.appengine.api import taskqueue, urlfetch
import feedparser
from link_header import parse as parse_link_header
from flask import Blueprint, url_for
from dateutil.parser import parse as parse_datetime
from dateutil import tz

from sparkprs import app, db
from sparkprs.models import JIRAIssue, PullRequest, IssueComment, ReviewComment, User, KVS
from sparkprs.github_api import raw_github_request, paginated_github_request, PULLS_BASE, ISSUES_BASE
from sparkprs.jira_api import link_issue_to_pr


tasks = Blueprint('tasks', __name__)


oauth_token = app.config['GITHUB_OAUTH_KEY']


@tasks.route("/github/update-prs")
def update_github_prs():
    def fetch_and_process(url):
        logging.debug("Following url %s" % url)
        response = raw_github_request(url, oauth_token=oauth_token)
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
    pr = PullRequest.query.get(pr_number) or PullRequest(number=pr_number)
    issue_response = raw_github_request(PULLS_BASE + '/%i' % pr_number,
                                        oauth_token=oauth_token, etag=pr.pr_json_etag)
    if issue_response is None:
        logging.debug("PR %i hasn't changed since last visit; skipping" % pr_number)
        return "Done updating pull request %i (nothing changed)" % pr_number
    pr.pr_json = json.loads(issue_response.content)
    pr.pr_json_etag = issue_response.headers["ETag"]
    pr.state = pr.pr_json['state']
    pr.author = User.get_or_create(pr.pr_json['user']['login'], db.session)
    pr.update_time = \
        parse_datetime(pr.pr_json['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
    db.session.add(pr)
    db.session.commit()

    subtasks = [".update_pr_comments", ".update_pr_review_comments", ".update_pr_files"]
    for task in subtasks:
        taskqueue.add(url=url_for(task, pr_number=pr_number), queue_name='fresh-prs')

    for issue_number in pr.parsed_title['jiras']:
        try:
            link_issue_to_pr("SPARK-%s" % issue_number, pr)
        except:
            logging.exception("Exception when linking to JIRA issue SPARK-%s" % issue_number)

    return "Done updating pull request %i" % pr_number


@tasks.route("/github/update-pr-comments/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_comments(pr_number):
    pr = PullRequest.query.get(pr_number)
    comments_response = paginated_github_request(ISSUES_BASE + '/%i/comments' % pr_number,
                                                 oauth_token=oauth_token,
                                                 etag=pr.pr_comments_etag)
    if comments_response is None:
        return "Comments for PR %i are up-to-date" % pr_number
    comments, comments_etag = comments_response
    for comment_data in comments:
        comment_id = comment_data["id"]
        comment = IssueComment.query.get((pr.number, comment_id)) or \
                  IssueComment(pr=pr.number, id=comment_id)
        # TODO: check if comment has changed
        comment.author = User.get_or_create(comment_data['user']['login'], db.session)
        comment.author.avatar_url = comment_data['user']['avatar_url']
        comment.url = comment_data['html_url']
        comment.body = comment_data['body']
        comment.creation_time = \
            parse_datetime(comment_data['created_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
        comment.update_time = \
            parse_datetime(comment_data['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
        db.session.add(comment)
    pr.pr_comments_etag = comments_etag
    db.session.add(pr)
    db.session.commit()
    return "Done updating comments for PR %i" % pr_number



@tasks.route("/github/update-pr-review-comments/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_review_comments(pr_number):
    pr = PullRequest.query.get(pr_number)
    pr_comments_response = paginated_github_request(PULLS_BASE + '/%i/comments' % pr_number,
                                                    oauth_token=oauth_token,
                                                    etag=pr.pr_review_comments_etag)
    if pr_comments_response is None:
        return "Review comments for PR %i are up-to-date" % pr_number
    review_comments, review_comments_etag = pr_comments_response
    for comment_data in review_comments:
        comment_id = comment_data["id"]
        comment = ReviewComment.query.get((pr.number, comment_id)) or \
                  ReviewComment(pr=pr.number, id=comment_id)
        # TODO: check if comment has changed
        comment.author = User.get_or_create(comment_data['user']['login'], db.session)
        comment.author.avatar_url = comment_data['user']['avatar_url']
        comment.url = comment_data['html_url']
        comment.body = comment_data['body']
        comment.diff_hunk = comment_data['diff_hunk']
        comment.creation_time = \
            parse_datetime(comment_data['created_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
        comment.update_time = \
            parse_datetime(comment_data['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
        db.session.add(comment)
    pr.pr_review_comments_etag = review_comments_etag
    db.session.add(pr)
    db.session.commit()
    return "Done updating review comments for PR %i" % pr_number


@tasks.route("/github/update-pr-files/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_files(pr_number):
    pr = PullRequest.query.get(pr_number)
    files_response = paginated_github_request(PULLS_BASE + "/%i/files" % pr_number,
                                              oauth_token=oauth_token, etag=pr.pr_files_json_etag)
    if files_response is None:
        return "Files for PR %i are up-to-date" % pr_number
    pr.files_json, pr.pr_files_json_etag = files_response
    db.session.add(pr)
    db.session.commit()
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
        taskqueue.add(url=url_for('.update_jira_issue', issue_id=issue), queue_name='jira-issues')
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
        taskqueue.add(url=url_for('.update_jira_issue', issue_id="SPARK-%i" % issue),
                      queue_name='jira-issues')
    return "Queued JIRA issues for update: " + str(jira_issues)


@tasks.route("/update-jira-issue/<string:issue_id>", methods=['GET', 'POST'])
def update_jira_issue(issue_id):
    logging.debug("Updating JIRA issue %s" % issue_id)
    url = "%s/rest/api/latest/issue/%s" % (app.config['JIRA_API_BASE'], issue_id)
    issue = JIRAIssue.get_or_create(issue_id, db.session)
    issue.issue_json = json.loads(urlfetch.fetch(url).content)
    db.session.add(issue)
    db.session.commit()
    return "Done updating JIRA issue %s" % issue_id
