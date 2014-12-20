from google.appengine.api import urlfetch
from collections import defaultdict
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from github_api import raw_github_request, paginated_github_request, PULLS_BASE, ISSUES_BASE
import json
import logging
import re
from sparkprs import app, db
from sparkprs.utils import parse_pr_title, is_jenkins_command, contains_jenkins_command
from sparkprs.jira_api import link_issue_to_pr
from sqlalchemy_utils import JSONType


class JIRAIssue(db.Model):

    issue_id = db.Column(db.String(64), primary_key=True, nullable=False)
    issue_json = db.Column(JSONType, nullable=False)

    @property
    def status_name(self):
        return self.issue_json["fields"]['status']['statusCategory']['name']

    @property
    def status_icon_url(self):
        return self.issue_json["fields"]['status']['iconUrl']

    @property
    def priority_name(self):
        return self.issue_json["fields"]['priority']['name']

    @property
    def priority_icon_url(self):
        return self.issue_json["fields"]['priority']['iconUrl']

    @property
    def issuetype_name(self):
        return self.issue_json["fields"]['issuetype']['name']

    @property
    def issuetype_icon_url(self):
        return self.issue_json["fields"]['issuetype']['iconUrl']

    @classmethod
    def get_or_create(cls, issue_id):
        return cls.query.get(issue_id) or JIRAIssue(issue_id=issue_id)


db.create_all()
