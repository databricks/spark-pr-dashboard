from google.appengine.api import urlfetch
from collections import defaultdict
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from datetime import datetime
from github_api import raw_github_request, paginated_github_request, PULLS_BASE, ISSUES_BASE
import json
import logging
import re
from sparkprs import app, db
from sparkprs.utils import parse_pr_title, is_jenkins_command, contains_jenkins_command
from sparkprs.jira_api import link_issue_to_pr
from sqlalchemy_utils import JSONType


class User(db.Model):

    id = db.Column(db.Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    github_username = db.Column(db.String(128), unique=True, nullable=False)
    github_access_token = db.Column(db.String(128), nullable=True)
    github_json = db.Column(JSONType, nullable=True)
    create_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    update_time = db.Column(
        db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def __init__(self, github_username, github_access_token=None, github_json=None):
        self.github_username = github_username
        self.github_access_token = github_access_token
        self.github_json = github_json

    def __repr__(self):
        return 'User' + str(
            (self.id, self.github_username, self.github_access_token, self.github_json))

    def has_capability(self, capability):
        if "admin" in self.roles:
            return True
        elif capability == "jenkins":
            return "jenkins-admin" in self.roles
        else:
            return False


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
