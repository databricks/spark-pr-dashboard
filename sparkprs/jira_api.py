"""
Functions for integrating with JIRA.
"""
import logging
import jira.client
from sparkprs import app


def get_jira_client():
    return jira.client.JIRA({'server': app.config['JIRA_API_BASE']},
                            basic_auth=(app.config['JIRA_USERNAME'],
                                        app.config['JIRA_PASSWORD']))


def link_issue_to_pr(issue, pr):
    """
    Create a link in JIRA to a pull request and add a comment linking to the PR.

    This method is idempotent; the links will only be created if they do not already exist.
    """
    jira_client = get_jira_client()
    url = pr['pr_json']['html_url']
    title = "[Github] Pull Request #%s (%s)" % (pr.number, pr.author.github_username)

    existing_links = map(lambda l: l.raw['object']['url'], jira_client.remote_links(issue))
    if url in existing_links:
        return

    icon = {"title": "Pull request #%s" % pr.number,
            "url16x16": "https://assets-cdn.github.com/favicon.ico"}
    destination = {"title": title, "url": url, "icon": icon}
    jira_client.add_remote_link(issue, destination)

    comment = "User '%s' has created a pull request for this issue:\n%s" % \
              (pr.author.github_username, url)
    jira_client.add_comment(issue, comment)
    logging.info("Linked PR %s to JIRA %s" % (pr.number, issue))