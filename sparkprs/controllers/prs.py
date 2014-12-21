import json
from collections import defaultdict
import re

from flask import Blueprint, Response

from sparkprs import db
from sparkprs.models import IssueComment, ReviewComment, PullRequest
from sparkprs.utils import is_jenkins_command, contains_jenkins_command


prs = Blueprint('prs', __name__)


ASKED_TO_CLOSE_REGEX = re.compile(r"""
        (mind\s+closing\s+(this|it))|
        (close\s+this\s+(issue|pr))
    """, re.I | re.X)



def compute_commenters(comments):
    res = defaultdict(dict)  # Indexed by user, since we only display each user once.
    excluded_users = set(("SparkQA", "AmplabJenkins"))

    for comment in comments:
        if is_jenkins_command(comment.body):
            continue  # Skip comments that solely consist of Jenkins commands
        user = comment.author.github_username
        if user not in excluded_users:
            user_dict = res[user]
            user_dict['url'] = comment.url
            user_dict['avatar'] = comment.author.avatar_url
            user_dict['date'] = str(comment.creation_time)
            user_dict['body'] = comment.body
            # Display at most 10 lines of context for comments left on diffs:
            user_dict['diff_hunk'] = '\n'.join(
                getattr(comment, 'diff_hunk', '').split('\n')[-10:])
            user_dict['said_lgtm'] = (user_dict.get('said_lgtm') or
                                      re.search("lgtm", comment.body, re.I) is not None)
            user_dict['asked_to_close'] = \
                (user_dict.get('asked_to_close')
                 or ASKED_TO_CLOSE_REGEX.search(comment.body) is not None)
    return sorted(res.items(), key=lambda x: x[1]['date'], reverse=True)


def compute_last_jenkins_outcome(comments):
    status = "Unknown"
    jenkins_comment = None
    for comment in (self.comments_json or []):
        if contains_jenkins_command(comment['body']):
            status = "Asked"
            jenkins_comment = comment
        elif comment['user']['login'] in ("SparkQA", "AmplabJenkins"):
            body = comment['body'].lower()
            jenkins_comment = comment
            if "pass" in body:
                status = "Pass"
            elif "fail" in body:
                status = "Fail"
            elif "started" in body:
                status = "Running"
            elif "can one of the admins verify this patch?" in body:
                status = "Verify"
            elif "timed out" in body:
                status = "Timeout"
            else:
                status = "Unknown"  # So we display "Unknown" instead of an out-of-date status
    return (status, jenkins_comment)

@prs.route('/search-open-prs')
#@cache.cached(timeout=60)
def search_open_prs():
    json_dicts = []
    prs = db.session.query(PullRequest).join(IssueComment).join(ReviewComment). \
        filter(PullRequest.state == "open"). \
        order_by(PullRequest.update_time.desc())
    for pr in prs:
        commenters = compute_commenters(pr.issue_comments)
        last_jenkins_comment_dict = None
        """
        if pr.last_jenkins_comment:
            last_jenkins_comment_dict = {
                'body': pr.last_jenkins_comment['body'],
                'user': {'login': pr.last_jenkins_comment['user']['login']},
                'html_url': pr.last_jenkins_comment['html_url'],
                }
        """
        d = {
            'parsed_title': pr.parsed_title,
            'number': pr.number,
            'updated_at': str(pr.update_time),
            'user': pr.author.github_username,
            'state': pr.state,
            'components': pr.components,
            'lines_added': pr.lines_added,
            'lines_deleted': pr.lines_deleted,
            'lines_changed': pr.lines_changed,
            'is_mergeable': pr.is_mergeable,
            'commenters': [{'username': u, 'data': d} for (u, d) in commenters],
            'last_jenkins_outcome': "Unknown", #pr.last_jenkins_outcome,
            'last_jenkins_comment': last_jenkins_comment_dict,
            }
        # Use the first JIRA's information to populate the "Priority" and "Issue Type" columns:
        jiras = []  # pr.jira_issues
        if jiras:
            first_jira = pr.jira_issues[0]
            if first_jira:
                d['jira_priority_name'] = first_jira.priority_name
                d['jira_priority_icon_url'] = first_jira.priority_icon_url
                d['jira_issuetype_name'] = first_jira.issuetype_name
                d['jira_issuetype_icon_url'] = first_jira.issuetype_icon_url
        json_dicts.append(d)
    response = Response(json.dumps(json_dicts), mimetype='application/json')
    return response