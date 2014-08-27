import google.appengine.ext.ndb as ndb
from dateutil.parser import parse as parse_datetime
from dateutil import tz
from github_api import raw_request, ISSUES_BASE
import json
import logging
import re


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
    last_jenkins_outcome = ndb.StringProperty()
    state = ndb.StringProperty()
    etag = ndb.StringProperty()

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
    def title_linked(self):
        """
        Get this issue's title as a HTML fragment, with referenced JIRAs turned into links
        and the non-category / JIRA portion of the title linked to the issue itself.
        """
        jira_regex = r"\[(SPARK-\d+)\]"
        tags = re.findall(Issue.TAG_REGEX, self.title)
        title = re.sub(Issue.TAG_REGEX, "", self.title).strip()
        title_html = []
        for tag in tags:
            jira_match = re.match(jira_regex, tag)
            if jira_match:
                jira = jira_match.groups(0)[0]
                title_html.append(
                    '<a href="http://issues.apache.org/jira/browse/%s">[%s]</a>' % (jira, jira))
            else:
                title_html.append(tag)
        title_html.append('<a href="https://www.github.com/apache/spark/pull/%i">%s</a>' %
                          (self.number, title))
        return ' '.join(title_html)

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
        comments_json = json.loads(raw_request(ISSUES_BASE + '/%i/comments' % self.number,
                                           oauth_token=oauth_token).content)
        for comment in comments_json:
            if comment['user']['login'] == "SparkQA":
                body = comment['body']
                if "This patch **passes** unit tests" in body:
                    self.last_jenkins_outcome = "Pass"
                elif "This patch **fails** unit tests" in body:
                    self.last_jenkins_outcome = "Fail"
        # Write our modifications back to the database
        self.put()
