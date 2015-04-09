import google.appengine.ext.ndb as ndb
from google.appengine.api import urlfetch
from collections import defaultdict
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from github_api import raw_github_request, paginated_github_request, PULLS_BASE, ISSUES_BASE
import json
import logging
import re
from sparkprs import app
from sparkprs.utils import parse_pr_title, is_jenkins_command, contains_jenkins_command
from sparkprs.jira_api import start_issue_progress, link_issue_to_pr


class KVS(ndb.Model):
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
    comments_json = ndb.JsonProperty(compressed=True)
    comments_etag = ndb.StringProperty()
    pr_comments_json = ndb.JsonProperty(compressed=True)
    pr_comments_etag = ndb.StringProperty()
    files_json = ndb.JsonProperty(compressed=True)
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
        ("R", "SparkR", "(^r/)|src/main/r/|api/r/"),
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
        for (component_name, pr_title_regex, filename_regex) in Issue._components:
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
        return parse_pr_title((self.pr_json and self.pr_json["title"]) or self.title or "")

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
        all_comments = sorted((self.comments_json or []) + (self.pr_comments_json or []),
                              key=lambda c: c['created_at'])
        for comment in all_comments:
            if is_jenkins_command(comment['body']):
                continue  # Skip comments that solely consist of Jenkins commands
            user = comment['user']['login']
            if user not in excluded_users:
                user_dict = res[user]
                user_dict['url'] = comment['html_url']
                user_dict['avatar'] = comment['user']['avatar_url']
                user_dict['date'] = comment['created_at'],
                user_dict['body'] = comment['body']
                # Display at most 10 lines of context for comments left on diffs:
                user_dict['diff_hunk'] = '\n'.join(
                    comment.get('diff_hunk', '').split('\n')[-10:])
                user_dict['said_lgtm'] = (user_dict.get('said_lgtm') or
                                          re.search("lgtm", comment['body'], re.I) is not None)
                user_dict['asked_to_close'] = \
                    (user_dict.get('asked_to_close') or
                        Issue.ASKED_TO_CLOSE_REGEX.search(comment['body']) is not None)
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
        logging.debug("Updating pull request %i" % self.number)
        # Record basic information about this pull request
        issue_response = raw_github_request(PULLS_BASE + '/%i' % self.number,
                                            oauth_token=oauth_token, etag=self.etag)
        if issue_response is None:
            logging.debug("PR %i hasn't changed since last visit; skipping" % self.number)
            return
        self.pr_json = json.loads(issue_response.content)
        self.etag = issue_response.headers["ETag"]
        updated_at = \
            parse_datetime(self.pr_json['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
        self.user = self.pr_json['user']['login']
        self.updated_at = updated_at
        self.state = self.pr_json['state']

        comments_response = paginated_github_request(ISSUES_BASE + '/%i/comments' % self.number,
                                                     oauth_token=oauth_token,
                                                     etag=self.comments_etag)
        if comments_response is not None:
            self.comments_json, self.comments_etag = comments_response

        pr_comments_response = paginated_github_request(PULLS_BASE + '/%i/comments' % self.number,
                                                        oauth_token=oauth_token,
                                                        etag=self.pr_comments_etag)
        if pr_comments_response is not None:
            self.pr_comments_json, self.pr_comments_etag = pr_comments_response

        files_response = paginated_github_request(PULLS_BASE + "/%i/files" % self.number,
                                                  oauth_token=oauth_token, etag=self.files_etag)
        if files_response is not None:
            self.files_json, self.files_etag = files_response

        self.cached_last_jenkins_outcome = None
        self.last_jenkins_outcome  # force recomputation of Jenkins outcome
        self.cached_commenters = self._compute_commenters()

        for issue_number in self.parsed_title['jiras']:
            try:
                link_issue_to_pr("SPARK-%s" % issue_number, self)
            except:
                logging.exception("Exception when linking to JIRA issue SPARK-%s" % issue_number)
            try:
                start_issue_progress("SPARK-%s" % issue_number)
            except:
                logging.exception(
                    "Exception when starting progress on JIRA issue SPARK-%s" % issue_number)

        self.put()  # Write our modifications back to the database


class JIRAIssue(ndb.Model):

    issue_id = ndb.StringProperty(required=True)
    issue_json = ndb.JsonProperty(compressed=True)

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
        key = str(ndb.Key("JIRAIssue", issue_id).id())
        return JIRAIssue.get_or_insert(key, issue_id=issue_id)

    def update(self):
        logging.debug("Updating JIRA issue %s" % self.issue_id)
        url = "%s/rest/api/latest/issue/%s" % (app.config['JIRA_API_BASE'], self.issue_id)
        self.issue_json = json.loads(urlfetch.fetch(url).content)
        self.put()  # Write our modifications back to the database
