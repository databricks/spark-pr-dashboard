import google.appengine.ext.ndb as ndb
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from github_api import raw_request, ISSUES_BASE
import json
import logging
import re
from sparkprs.utils import parse_pr_title


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


class Issue(ndb.Model):
    number = ndb.IntegerProperty(required=True)
    component = ndb.StringProperty()
    updated_at = ndb.DateTimeProperty()
    user = ndb.StringProperty()
    title = ndb.StringProperty()
    state = ndb.StringProperty()
    etag = ndb.StringProperty()
    comments_json = ndb.JsonProperty()

    TAG_REGEX = r"\[[^\]]*\]"

    @property
    def component(self):
        # TODO: support multiple components
        title = self.title.lower()
        if "sql" in title:
            return "SQL"
        elif "mllib" in title:
            return "MLlib"
        elif "graphx" in title or "pregel" in title:
            return "GraphX"
        elif "yarn" in title:
            return "YARN"
        elif ("stream" in title or "flume" in title or "kafka" in title
              or "twitter" in title or "zeromq" in title):
            return "Streaming"
        elif "python" in title or "pyspark" in title:
            return "Python"
        else:
            return "Core"

    @property
    def parsed_title(self):
        """
        Get this issue's title as a HTML fragment, with referenced JIRAs turned into links
        and the non-category / JIRA portion of the title linked to the issue itself.
        """
        return parse_pr_title(self.title)

    @property
    def commenters(self):
        res = {}  # Indexed by user, since we only display each user once.
        excluded_users = set(("SparkQA", "AmplabJenkins"))
        for comment in (self.comments_json or []):
            user = comment['user']['login']
            if user not in excluded_users:
                res[user] = {
                    'url': comment['html_url'],
                    'avatar': comment['user']['avatar_url'],
                    'date': comment['created_at'],
                    'body': comment['body'],
                }
        return sorted(res.items(), key=lambda x: x[1]['date'], reverse=True)

    @property
    def last_jenkins_outcome(self):
        status = None
        for comment in (self.comments_json or []):
            if comment['user']['login'] in ("SparkQA", "AmplabJenkins"):
                body = comment['body'].lower()
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
                    status = None  # So we display "Unknown" instead of an out-of-date status
        return status

    @classmethod
    def get_or_create(cls, number):
        key = str(ndb.Key("Issue", number).id())
        return Issue.get_or_insert(key, number=number)

    def update(self, oauth_token):
        logging.debug("Updating issue %i" % self.number)
        # Record basic information about this pull request
        issue_response = raw_request(ISSUES_BASE + '/%i' % self.number, oauth_token=oauth_token,
                                     etag=self.etag)
        if issue_response is None:
            logging.debug("Issue %i hasn't changed since last visit; skipping" % self.number)
            return
        issue_json = json.loads(issue_response.content)
        self.etag = issue_response.headers["ETag"]
        updated_at = \
            parse_datetime(issue_json['updated_at']).astimezone(tz.tzutc()).replace(tzinfo=None)
        self.user = issue_json['user']['login']
        self.updated_at = updated_at
        self.title = issue_json['title']
        self.state = issue_json['state']
        # Fetch the comments and search for Jenkins comments
        # TODO: will miss comments if we exceed the pagination limit:
        self.comments_json = json.loads(raw_request(ISSUES_BASE + '/%i/comments' % self.number,
                                        oauth_token=oauth_token).content)
        # Write our modifications back to the database
        self.put()
