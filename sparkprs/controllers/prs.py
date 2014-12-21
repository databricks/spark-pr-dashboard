import json

from flask import Blueprint, Response

from sparkprs import cache
from sparkprs.models import Issue
from sparkprs.models2 import JIRAIssue, PullRequest


prs = Blueprint('prs', __name__)


@prs.route('/search-open-prs')
#@cache.cached(timeout=60)
def search_open_prs():
    open_prs = PullRequest.query.filter_by(state="open").order_by(PullRequest.update_time.desc())
    json_dicts = []
    for pr in open_prs:
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
            #'commenters': [{'username': u, 'data': d} for (u, d) in pr.commenters],
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