import google.appengine.ext.ndb as ndb
from collections import defaultdict
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from github_api import raw_github_request, PULLS_BASE, ISSUES_BASE
import json
import logging
import re
from sparkprs.utils import parse_pr_title, is_jenkins_command, contains_jenkins_command


class KVS(ndb.Model):
    key_str = ndb.StringProperty()
    value = ndb.PickleProperty()
    value_str = ndb.StringProperty()

    @classmethod
    def get(cls, key_str):
        key = str(ndb.Key("KVS", key_str).id())
        res = KVS.get_by_id(key)
        if res is not None:
            return res.value

    @classmethod
    def put(cls, key_str, value):
        key = str(ndb.Key("KVS", key_str).id())
        kvs_pair = KVS.get_or_insert(key, key_str=key_str, value=value, value_str=str(value))
        kvs_pair.value = value
        kvs_pair.value_str = str(value)
        ndb.Model.put(kvs_pair)


class User(ndb.Model):
    github_login = ndb.StringProperty(required=True)
    github_access_token = ndb.StringProperty()
    github_user_json = ndb.JsonProperty()
    roles = ndb.StringProperty(repeated=True)

    def has_capability(self, capability):
        if "admin" in self.roles:
            return True
        elif capability == "jenkins":
            return "jenkins-admin" in self.roles
        else:
            return False


class Issue(ndb.Model):
    number = ndb.IntegerProperty(required=True)
    updated_at = ndb.DateTimeProperty()
    user = ndb.StringProperty()
    state = ndb.StringProperty()
    title = ndb.StringProperty()
    comments_json = ndb.JsonProperty()
    comments_etag = ndb.StringProperty()
    files_json = ndb.JsonProperty()
    files_etag = ndb.StringProperty()
    pr_json = ndb.JsonProperty()
    etag = ndb.StringProperty()
    # Cached properties, while we migrate away from on-the-fly computed ones:
    cached_commenters = ndb.PickleProperty()
    cached_last_jenkins_outcome = ndb.StringProperty()
    last_jenkins_comment = ndb.JsonProperty()

    ASKED_TO_CLOSE_REGEX = re.compile(r"""
        (mind\s+closing\s+(this|it))|
        (close\s+this\s+(issue|pr))
    """, re.I | re.X)

    _components = [
        # (name, pr_title_regex, filename_regex)
        ("Core", "core", "^core/"),
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
        title = ((self.pr_json and self.pr_json["title"]) or self.title)
        modified_files = [f["filename"] for f in (self.files_json or [])]
        for (component_name, pr_title_regex, filename_regex) in Issue._components:
            if re.search(pr_title_regex, title, re.IGNORECASE) or \
                    any(re.search(filename_regex, f, re.I) for f in modified_files):
                components.append(component_name)
        return components or ["Core"]

    @property
    def parsed_title(self):
        """
        Get this issue's title as a HTML fragment, with referenced JIRAs turned into links
        and the non-category / JIRA portion of the title linked to the issue itself.
        """
        return parse_pr_title((self.pr_json and self.pr_json["title"]) or self.title)

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

    @property
    def is_mergeable(self):
        return self.pr_json and self.pr_json["mergeable"]

    @property
    def commenters(self):
        if self.cached_commenters is None:
            self.cached_commenters = self._compute_commenters()
            self.put()
        return self.cached_commenters

    @property
    def last_jenkins_outcome(self):
        if self.cached_last_jenkins_outcome is None:
            (outcome, comment) = self._compute_last_jenkins_outcome()
            self.cached_last_jenkins_outcome = outcome
            self.last_jenkins_comment = comment
            self.put()
        return self.cached_last_jenkins_outcome

    def _compute_commenters(self):
        res = defaultdict(dict)  # Indexed by user, since we only display each user once.
        excluded_users = set(("SparkQA", "AmplabJenkins"))
        for comment in (self.comments_json or []):
            if is_jenkins_command(comment['body']):
                continue  # Skip comments that solely consist of Jenkins commands
            user = comment['user']['login']
            if user not in excluded_users:
                user_dict = res[user]
                user_dict['url'] = comment['html_url']
                user_dict['avatar'] = comment['user']['avatar_url']
                user_dict['date'] = comment['created_at'],
                user_dict['body'] = comment['body']
                user_dict['said_lgtm'] = (user_dict.get('said_lgtm') or
                                          re.search("lgtm", comment['body'], re.I) is not None)
                user_dict['asked_to_close'] = \
                    (user_dict.get('asked_to_close')
                     or Issue.ASKED_TO_CLOSE_REGEX.search(comment['body']) is not None)
        return sorted(res.items(), key=lambda x: x[1]['date'], reverse=True)

    def _compute_last_jenkins_outcome(self):
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

    @classmethod
    def get_or_create(cls, number):
        key = str(ndb.Key("Issue", number).id())
        return Issue.get_or_insert(key, number=number)

    def update(self, oauth_token):
        logging.debug("Updating issue %i" % self.number)
        # Record basic information about this pull request
        issue_response = raw_github_request(PULLS_BASE + '/%i' % self.number,
                                            oauth_token=oauth_token, etag=self.etag)
        if issue_response is None:
            logging.debug("Issue %i hasn't changed since last visit; skipping" % self.number)
            return
        self.pr_json = json.loads(issue_response.content)
        self.etag = issue_response.headers["ETag"]
        updated_at = \
            parse_datetime(self.pr_json['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
        self.user = self.pr_json['user']['login']
        self.updated_at = updated_at
        self.state = self.pr_json['state']

        # TODO: will miss comments if we exceed the pagination limit:
        comments_response = raw_github_request(ISSUES_BASE + '/%i/comments' % self.number,
                                               oauth_token=oauth_token, etag=self.comments_etag)
        if comments_response is not None:
            self.comments_json = json.loads(comments_response.content)
            self.comments_etag = comments_response.headers["ETag"]

        files_response = raw_github_request(PULLS_BASE + "/%i/files" % self.number,
                                            oauth_token=oauth_token, etag=self.files_etag)
        if files_response is not None:
            self.files_json = json.loads(files_response.content)
            self.files_etag = files_response.headers["ETag"]

        self.cached_last_jenkins_outcome = None
        self.last_jenkins_outcome  # force recomputation of Jenkins outcome
        self.cached_commenters = self._compute_commenters()

        # Write our modifications back to the database
        self.put()
