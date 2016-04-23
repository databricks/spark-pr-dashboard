import google.appengine.ext.ndb as ndb
import json
import logging
import datetime

from flask import Blueprint
from flask import Response
from natsort import natsorted

from sparkprs import cache, app
from sparkprs.models import Issue, JIRAIssue


prs = Blueprint('prs', __name__)


@prs.route('/search-open-prs')
@cache.cached(timeout=60)
def search_open_prs():
    prs = Issue.query(Issue.state == "open").order(-Issue.updated_at).fetch()
    return search_prs(prs)

@prs.route('/search-stale-prs')
@cache.cached(timeout=60)
def search_stale_prs():
    issueQuery = ndb.AND(Issue.state == "open",
                         Issue.updated_at < datetime.datetime.today() - datetime.timedelta(days=30))
    stalePrs = Issue.query(issueQuery).order(-Issue.updated_at).fetch()
    return search_prs(stalePrs)

def search_prs(prs):
    json_dicts = []
    for pr in prs:
        try:
            last_jenkins_comment_dict = None
            if pr.last_jenkins_comment:
                last_jenkins_comment_dict = {
                    'body': pr.last_jenkins_comment['body'],
                    'user': {'login': pr.last_jenkins_comment['user']['login']},
                    'html_url': pr.last_jenkins_comment['html_url'],
                    'date': [pr.last_jenkins_comment['created_at']],
                }
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
                'is_mergeable': pr.is_mergeable,
                'commenters': [{'username': u, 'data': d} for (u, d) in pr.commenters],
                'last_jenkins_outcome': pr.last_jenkins_outcome,
                'last_jenkins_comment': last_jenkins_comment_dict,
            }
            # Use the first JIRA's information to populate the "Priority" and "Issue Type" columns:
            jiras = pr.parsed_title["jiras"]
            if jiras:
                first_jira = JIRAIssue.get_by_id("%s-%i" % (app.config['JIRA_PROJECT'], jiras[0]))
                if first_jira:
                    d['jira_priority_name'] = first_jira.priority_name
                    d['jira_priority_icon_url'] = first_jira.priority_icon_url
                    d['jira_issuetype_name'] = first_jira.issuetype_name
                    d['jira_issuetype_icon_url'] = first_jira.issuetype_icon_url
                    d['jira_shepherd_display_name'] = first_jira.shepherd_display_name
                # If a pull request is linked against multiple JIRA issues, then the target
                # versions should be union of the individual issues' target versions:
                target_versions = set()
                for jira_number in jiras:
                    jira = JIRAIssue.get_by_id("%s-%i" % (app.config['JIRA_PROJECT'], jira_number))
                    if jira:
                        target_versions.update(jira.target_versions)
                if target_versions:
                    d['jira_target_versions'] = natsorted(target_versions)
            json_dicts.append(d)
        except:
            logging.error("Exception while processing PR #%i", pr.number)
            raise
    response = Response(json.dumps(json_dicts), mimetype='application/json')
    return response
