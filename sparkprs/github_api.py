from google.appengine.api import urlfetch
import logging


BASE_URL = 'https://api.github.com/'
BASE_AUTH_URL = 'https://github.com/login/oauth/'
ISSUES_BASE = BASE_URL + "repos/apache/spark/issues"
PULLS_BASE = BASE_URL + "repos/apache/spark/pulls"


def github_request(resource, oauth_token=None, etag=None):
    return raw_github_request(BASE_URL + resource, oauth_token, etag)


def raw_github_request(url, oauth_token=None, etag=None):
    headers = {}
    if etag is not None:
        headers['If-None-Match'] = etag
    if oauth_token is not None:
        headers["Authorization"] = "token %s" % oauth_token
    logging.info("Requesting %s from GitHub with headers %s" % (url, headers))
    response = urlfetch.fetch(url, headers=headers, method="GET")
    if response.status_code == 304:
        return None
    elif response.status_code == 200:
        return response
    else:
        raise Exception("Unexpected status code: %i\n%s" % (response.status_code, response.content))