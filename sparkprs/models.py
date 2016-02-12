import google.appengine.ext.ndb as ndb
from google.appengine.api import urlfetch
from collections import defaultdict
import json
import logging
import re
from sparkprs import app
from sparkprs.utils import parse_pr_title, is_jenkins_command, compute_last_jenkins_outcome


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
    # Raw JSON data
    pr_json = ndb.JsonProperty()
    comments_json = ndb.JsonProperty(compressed=True)
    pr_comments_json = ndb.JsonProperty(compressed=True)
    files_json = ndb.JsonProperty(compressed=True)
    # ETags for limiting our GitHub requests
    etag = ndb.StringProperty()
    comments_etag = ndb.StringProperty()
    pr_comments_etag = ndb.StringProperty()
    files_etag = ndb.StringProperty()
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
        ("MLlib", "mllib|ml", "mllib|/ml/|docs/ml"),
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
    def raw_title(self):
        return (self.pr_json and self.pr_json["title"]) or self.title or ""

    @property
    def parsed_title(self):
        """
        Get a parsed version of this PR's title, which identifies referenced JIRAs and metadata.
        For example, given a PR titled
            "[SPARK-975] [core] Visual debugger of stages and callstacks""
        this will return
            {'jiras': [975], 'title': 'Visual debugger of stages and callstacks', 'metadata': ''}
        """
        return parse_pr_title(self.raw_title)

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
            (outcome, comment) = compute_last_jenkins_outcome(self.comments_json)
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
            # If a user deletes their GitHub account, the 'user' field of their comments seems to
            # become 'null' in the JSON (although it points to the user info for the 'ghost' user
            # in other contexts). As a result, we have to guard against that here:
            user = (comment.get('user') or {}).get('login')
            if user is not None and user not in excluded_users:
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

    @classmethod
    def get_or_create(cls, number):
        key = str(ndb.Key("Issue", number).id())
        return Issue.get_or_insert(key, number=number)

    @classmethod
    def get(cls, number):
        key = str(ndb.Key("Issue", number).id())
        return Issue.get_by_id(key)


class JIRAIssue(ndb.Model):
    """
    Models an issue from JIRA.

    `issue_json` holds the JSON response returned from JIRA's REST API. The schema of this JSON is
    documented at https://docs.atlassian.com/jira/REST/latest/#d2e216.

    For custom fields that are specific to the Apache JIRA, you can find a mapping from field names
    to ids at https://issues.apache.org/jira/rest/api/latest/field.
    """

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
        # Some JIRAs which were imported from the old Spark JIRA (before it was an Apache project)
        # seem to have a null priority field value, so we need to guard against that here:
        return (self.issue_json["fields"].get('priority') or {}).get('name')

    @property
    def priority_icon_url(self):
        # Some JIRAs which were imported from the old Spark JIRA (before it was an Apache project)
        # seem to have a null priority field value, so we need to guard against that here:
        return (self.issue_json["fields"].get('priority') or {}).get('iconUrl')

    @property
    def issuetype_name(self):
        return self.issue_json["fields"]['issuetype']['name']

    @property
    def issuetype_icon_url(self):
        return self.issue_json["fields"]['issuetype']['iconUrl']

    @property
    def shepherd_display_name(self):
        shepherd = self.issue_json["fields"].get('customfield_12311620')
        if shepherd:
            return shepherd['displayName']

    @property
    def target_versions(self):
        versions = self.issue_json["fields"].get('customfield_12310320')
        if versions:
            return [v['name'] for v in versions]
        else:
            return []

    @classmethod
    def get_or_create(cls, issue_id):
        key = str(ndb.Key("JIRAIssue", issue_id).id())
        return JIRAIssue.get_or_insert(key, issue_id=issue_id)

    def update(self):
        logging.debug("Updating JIRA issue %s" % self.issue_id)
        url = "%s/rest/api/latest/issue/%s" % (app.config['JIRA_API_BASE'], self.issue_id)
        self.issue_json = json.loads(urlfetch.fetch(url).content)
        self.put()  # Write our modifications back to the database
