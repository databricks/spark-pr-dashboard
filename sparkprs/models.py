from collections import defaultdict
import re

import google.appengine.ext.ndb as ndb

from sparkprs.utils import is_jenkins_command, contains_jenkins_command


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


class Issue(ndb.Model):

    ASKED_TO_CLOSE_REGEX = re.compile(r"""
        (mind\s+closing\s+(this|it))|
        (close\s+this\s+(issue|pr))
    """, re.I | re.X)

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