from google.appengine.api import urlfetch
from link_header import parse as parse_link_header
from urllib2 import HTTPError
import logging
import json

from sparkprs import app

BASE_URL = 'https://api.github.com/'
BASE_AUTH_URL = 'https://github.com/login/oauth/'


def get_issues_base():
    return BASE_URL + "repos/%s/issues" % app.config['GITHUB_PROJECT']


def get_pulls_base():
    return BASE_URL + "repos/%s/pulls" % app.config['GITHUB_PROJECT']


def github_request(resource, oauth_token=None, etag=None):
    return raw_github_request(BASE_URL + resource, oauth_token, etag)


def raw_github_request(url, oauth_token=None, etag=None, method="GET"):
    headers = {}
    if etag is not None:
        headers['If-None-Match'] = etag
    if oauth_token is not None:
        headers["Authorization"] = "token %s" % oauth_token
    logging.info("Requesting %s from GitHub with headers %s" % (url, headers))
    response = urlfetch.fetch(url, headers=headers, method=method)
    if response.status_code == 304:
        return None
    elif method.lower() == "delete":
        return response
    elif response.status_code == 200:
        return response
    elif response.status_code == 404:
        raise HTTPError(url, response.status_code, "404 Not Found", response.headers, None)
    else:
        raise Exception("Unexpected status code: %i\n%s" % (response.status_code, response.content))


def paginated_github_request(url, oauth_token=None, etag=None):
    """
    Retrieve and decode JSON from GitHub endpoints that use pagination.
    Automatically follows 'next' links.

    :return: (Decoded JSON, ETag) pair
    """
    # Grab the first page
    initial_response = raw_github_request(url, oauth_token, etag)
    if initial_response is None:
        return None
    result = json.loads(initial_response.content)
    etag = initial_response.headers["ETag"]

    # Continue following 'next' links, appending the decoded responses to 'result'

    def get_next_url(resp):
        link_header = parse_link_header(resp.headers.get('Link', ''))
        for link in link_header.links:
            if link.rel == 'next':
                return link.href

    next_url = get_next_url(initial_response)
    while next_url:
        response = raw_github_request(next_url, oauth_token)
        result.extend(json.loads(response.content))
        next_url = get_next_url(response)

    return result, etag
