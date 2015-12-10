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
from more_itertools import chunked

from sparkprs.models import Issue, JIRAIssue, KVS
from sparkprs.github_api import raw_github_request, paginated_github_request, get_pulls_base, \
    get_issues_base
from sparkprs import app
from sparkprs.jira_api import start_issue_progress, link_issue_to_pr


tasks = Blueprint('tasks', __name__)


oauth_token = app.config['GITHUB_OAUTH_KEY']


@tasks.route("/github/backfill-prs")
def backfill_prs():
    """
    This method attempts to update every PR ever opened against the repository.
    As a result, this method should only be invoked by admins when trying to bootstrap a new
    deployment of the PR board.
    """
    # Determine the number of PRs:
    url = get_pulls_base() + "?sort=created&state=all&direction=desc"
    response = raw_github_request(url, oauth_token=oauth_token)
    latest_prs = json.loads(response.content)
    latest_pr_number = int(latest_prs[0]['number'])
    queue = taskqueue.Queue('old-prs')
    update_tasks = []
    for num in reversed(xrange(1, latest_pr_number + 1)):
        update_tasks.append(taskqueue.Task(url=url_for(".update_pr", pr_number=num)))
    # Can only enqueue up to 100 tasks per API call
    async_call_results = []
    for group_of_tasks in chunked(update_tasks, 100):
        async_call_results.append(queue.add_async(group_of_tasks))
    # Block until the async calls are finished:
    for r in async_call_results:
        r.get_result()
    return "Enqueued tasks to backfill %i PRs" % latest_pr_number


@tasks.route("/github/update-prs")
def update_github_prs():
    last_update_time = KVS.get("issues_since")
    if last_update_time:
        last_update_time = \
            parse_datetime(last_update_time).astimezone(tz.tzutc()).replace(tzinfo=None)
    else:
        # If no update has ever run successfully, store "now" as the watermark. If this update
        # task fails (because there are too many old PRs to load / backfill) then there's a chance
        # that this initial timestamp won't be the true watermark. If we are trying to bulk-load
        # old data then this should be done by calling /github/backfill-prs instead.
        last_update_time = datetime.min
        KVS.put('issues_since', datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))

    def fetch_and_process(url):
        logging.debug("Following url %s" % url)
        response = raw_github_request(url, oauth_token=oauth_token)
        prs = json.loads(response.content)
        now = datetime.utcnow()
        should_continue_loading = True
        update_time = last_update_time
        for pr in prs:
            updated_at = \
                parse_datetime(pr['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
            update_time = max(update_time, updated_at)
            if updated_at < last_update_time:
                should_continue_loading = False
                break
            is_fresh = (now - updated_at).total_seconds() < app.config['FRESHNESS_THRESHOLD']
            queue_name = ("fresh-prs" if is_fresh else "old-prs")
            taskqueue.add(url=url_for(".update_pr", pr_number=pr['number']), queue_name=queue_name)
        if should_continue_loading:
            link_header = parse_link_header(response.headers.get('Link', ''))
            for link in link_header.links:
                if link.rel == 'next':
                    fetch_and_process(link.href)
        return update_time
    update_time = \
        fetch_and_process(get_pulls_base() + "?sort=updated&state=all&direction=desc&per_page=100")
    KVS.put('issues_since', update_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return "Done fetching updated GitHub issues"


@tasks.route("/github/update-pr/<int:pr_number>", methods=['GET', 'POST'])
def update_pr(pr_number):
    logging.debug("Updating pull request %i" % pr_number)
    pr = Issue.get_or_create(pr_number)
    issue_response = raw_github_request(get_pulls_base() + '/%i' % pr_number,
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
            link_issue_to_pr("%s-%s" % (app.config['JIRA_PROJECT'], issue_number), pr)
        except:
            logging.exception("Exception when linking to JIRA issue %s-%s" %
                              (app.config['JIRA_PROJECT'], issue_number))
        try:
            start_issue_progress("%s-%s" % (app.config['JIRA_PROJECT'], issue_number))
        except:
            logging.exception(
                "Exception when starting progress on JIRA issue %s-%s" %
                (app.config['JIRA_PROJECT'], issue_number))

    pr.put()  # Write our modifications back to the database

    subtasks = [".update_pr_comments", ".update_pr_review_comments", ".update_pr_files"]
    for task in subtasks:
        taskqueue.add(url=url_for(task, pr_number=pr_number), queue_name='fresh-prs')

    return "Done updating pull request %i" % pr_number


@tasks.route("/github/update-pr-comments/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_comments(pr_number):
    pr = Issue.get(pr_number)
    comments_response = paginated_github_request(get_issues_base() + '/%i/comments' % pr_number,
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
        build_start_regex = r"Test build #(\d+) has started"
        build_end_regex = r"Test build #(\d+) (has finished|timed out)"
        for comment in (pr.comments_json or []):
            author = comment["user"]["login"]
            # Delete all comments from AmplabJenkins unless they are the comments that should be
            # displayed on the Spark PR dashboard.
            if author == "AmplabJenkins" and comment["url"] != jenkins_comment_to_preserve["url"]:
                raw_github_request(comment["url"], oauth_token=amplabjenkins_token, method="DELETE")
            elif author == "SparkQA":
                # Only delete build start notification comments from SparkQA and only delete them
                # after we've seen the corresponding build finished message.
                start_regex_match = re.search(build_start_regex, comment["body"])
                if start_regex_match:
                    sparkqa_start_comments[start_regex_match.groups()[0]] = comment
                else:
                    end_regex_match = re.search(build_end_regex, comment["body"])
                    if end_regex_match:
                        start_comment = sparkqa_start_comments.get(end_regex_match.groups()[0])
                        if start_comment:
                            raw_github_request(start_comment["url"], oauth_token=sparkqa_token,
                                               method="DELETE")
        return "Done updating comments for PR %i" % pr_number


@tasks.route("/github/update-pr-review-comments/<int:pr_number>", methods=['GET', 'POST'])
def update_pr_review_comments(pr_number):
    pr = Issue.get(pr_number)
    pr_comments_response = paginated_github_request(get_pulls_base() + '/%i/comments' % pr_number,
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
    files_response = paginated_github_request(get_pulls_base() + "/%i/files" % pr_number,
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
        taskqueue.add(url="/tasks/update-jira-issue/%s-%i" % (app.config['JIRA_PROJECT'], issue),
                      queue_name='jira-issues')
    return "Queued JIRA issues for update: " + str(jira_issues)


@tasks.route("/update-jira-issue/<string:issue_id>", methods=['GET', 'POST'])
def update_jira_issue(issue_id):
    JIRAIssue.get_or_create(issue_id).update()
    return "Done updating JIRA issue %s" % issue_id
