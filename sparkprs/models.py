from datetime import datetime
import re
from google.appengine.ext import ndb as ndb

from sqlalchemy_utils import JSONType

from sparkprs import db
from sparkprs.utils import parse_pr_title


prs_jiras = db.Table(
    "prs_jiras",
    db.Model.metadata,
    db.Column("fk_jira", db.String(64), db.ForeignKey("jira_issue.issue_id")),
    db.Column("fk_pull_request", db.Integer, db.ForeignKey("pull_request.number")),
)


class User(db.Model):

    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    github_username = db.Column(db.String(128), unique=True, nullable=False)
    github_access_token = db.Column(db.String(128), nullable=True)
    github_json = db.Column(JSONType, nullable=True)
    create_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    update_time = db.Column(
        db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    pull_requests = db.relationship("PullRequest")
    avatar_url = db.Column(db.String(256))

    def __init__(self, github_username):
        self.github_username = github_username

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

    @classmethod
    def get_or_create(cls, github_username, session):
        user = User.query.filter_by(github_username=github_username).first()
        if not user:
            user = User(github_username)
            session.add(user)
            session.flush()
        return user


class JIRAIssue(db.Model):

    __tablename__ = 'jira_issue'
    issue_id = db.Column(db.String(64), primary_key=True, nullable=False)
    issue_json = db.Column(JSONType, nullable=False)
    pull_requests = db.relationship(
        "PullRequest",
        backref="pull_requests",
        secondary=prs_jiras
    )

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


class IssueComment(db.Model):
    """
    Comments left on PRs themselves (e.g. the main discussion thread, not diff comments)
    """

    __tablename__ = 'issue_comment'
    pr = db.Column(db.Integer, db.ForeignKey("pull_request.number"),
                   primary_key=True, autoincrement=False, nullable=False)
    id = db.Column(db.Integer, primary_key=True, autoincrement=False, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", remote_side=[author_id])
    url = db.Column(db.String(512), nullable=False)
    body = db.Column(db.UnicodeText, nullable=False)
    creation_time = db.Column(db.DateTime, nullable=False)
    update_time = db.Column(db.DateTime, nullable=False)


class ReviewComment(db.Model):
    """
    Comments left on PR diffs
    """

    __tablename__ = 'review_comment'
    pr = db.Column(db.Integer, db.ForeignKey("pull_request.number"),
                   primary_key=True, autoincrement=False, nullable=False)
    id = db.Column(db.Integer, primary_key=True, autoincrement=False, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", remote_side=[author_id])
    url = db.Column(db.String(512), nullable=False)
    body = db.Column(db.UnicodeText, nullable=False)
    diff_hunk = db.Column(db.UnicodeText, nullable=False)
    update_time = db.Column(db.DateTime, nullable=False)


class PullRequest(db.Model):

    __tablename__ = 'pull_request'
    number = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    update_time = db.Column(db.DateTime, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", remote_side=[author_id])
    state = db.Column(db.String(64), nullable=False)
    pr_json = db.Column(JSONType, nullable=False)
    files_json = db.Column(JSONType)
    pr_json_etag = db.Column(db.String(128))
    pr_comments_etag = db.Column(db.String(128))
    pr_review_comments_etag = db.Column(db.String(128))
    pr_files_json_etag = db.Column(db.String(128))
    issue_comments = db.relationship("IssueComment")
    review_comments = db.relationship("ReviewComment")
    jira_issues = db.relationship(
        "JIRAIssue",
        backref="jira_issues",
        secondary=prs_jiras
    )

    _components = [
        # (name, pr_title_regex, filename_regex)
        ("Core", "core", "^core/"),
        ("Scheduler", "schedul", "scheduler"),
        ("Python", "python|pyspark", "python"),
        ("YARN", "yarn", "yarn"),
        ("Mesos", "mesos", "mesos"),
        ("Web UI", "webui|(web ui)", "spark/ui/"),
        ("Build", "build", "(pom\.xml)|project"),
        ("Docs", "docs", "docs|README"),
        ("EC2", "ec2", "ec2"),
        ("SQL", "sql", "sql"),
        ("MLlib", "mllib", "mllib"),
        ("GraphX", "graphx|pregel", "graphx"),
        ("Streaming", "stream|flume|kafka|twitter|zeromq", "streaming"),
        ]

    @property
    def components(self):
        """
        Returns the list of components used to classify this pull request.

        Components are identified automatically based on the files that the pull request
        modified and any tags added to the pull request's title (such as [GraphX]).
        """
        components = []
        title = ((self.pr_json and self.pr_json["title"]) or self.title or "")
        modified_files = [f["filename"] for f in (self.files_json or [])]
        for (component_name, pr_title_regex, filename_regex) in PullRequest._components:
            if re.search(pr_title_regex, title, re.IGNORECASE) or \
                    any(re.search(filename_regex, f, re.I) for f in modified_files):
                components.append(component_name)
        return components or ["Core"]

    @property
    def parsed_title(self):
        """
        Get a parsed version of this PR's title, which identifies referenced JIRAs and metadata.
        For example, given a PR titled
            "[SPARK-975] [core] Visual debugger of stages and callstacks""
        this will return
            {'jiras': [975], 'title': 'Visual debugger of stages and callstacks', 'metadata': ''}
        """
        return parse_pr_title(self.pr_json["title"])

    @property
    def is_mergeable(self):
        return self.pr_json and self.pr_json["mergeable"]

    @property
    def lines_added(self):
        if self.pr_json:
            return self.pr_json.get("additions")
        else:
            return ""

    @property
    def lines_deleted(self):
        if self.pr_json:
            return self.pr_json.get("deletions")
        else:
            return ""

    @property
    def lines_changed(self):
        if self.lines_added != "":
            return self.lines_added + self.lines_deleted
        else:
            return 0


class KVS(ndb.Model):
    """
    Simple key-value store, used for persisting ad-hoc things like fetch watermarks, etc.
    """
    key_str = ndb.StringProperty()
    value = ndb.PickleProperty()
    value_str = ndb.StringProperty()

    @classmethod
    def get(cls, key_str):
        key = str(ndb.Key("KVS", key_str).id())
        res = KVS.get_by_id(key, use_cache=False, use_memcache=False)
        if res is not None:
            return res.value

    @classmethod
    def put(cls, key_str, value):
        key = str(ndb.Key("KVS", key_str).id())
        kvs_pair = KVS.get_or_insert(key, key_str=key_str, value=value, value_str=str(value))
        kvs_pair.value = value
        kvs_pair.value_str = str(value)
        ndb.Model.put(kvs_pair)


db.create_all()
