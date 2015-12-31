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


def start_issue_progress(issue):
    """
    Given an issue key, e.g. SPARK-6481, mark the issue "In Progress".

    This will only happen if the issue's initial state is "Open" or "Reopened".
    """
    jira_client = get_jira_client()
    issue_info = jira_client.issue(issue)
    status = issue_info.fields.status.name
    assignee = issue_info.fields.assignee.name if issue_info.fields.assignee else None

    if status == "In Progress":
        return
    elif status not in ("Open", "Reopened"):
        logging.warn(("Could not start progress on JIRA issue {j}. "
                     "It's currently in an '{s}' state. "
                     "Issues must be in an 'Open' or 'Reopened' state.").format(j=issue, s=status))
        return

    try:
        # The PR dashboard user needs the issue assigned to itself in order to change
        # the issue's state.
        jira_client.assign_issue(issue=issue, assignee=app.config['JIRA_USERNAME'])
        transition_id = [transition['id']
                         for transition in jira_client.transitions(issue)
                         if transition['name'] == 'Start Progress'][0]
        # Passing transition by name doesn't work, though it should according to the docs...
        jira_client.transition_issue(issue=issue, transitionId=transition_id)
        logging.info("Started progress on JIRA issue {j}.".format(j=issue))
    finally:
        # Restore the original assignee.
        jira_client.assign_issue(issue=issue, assignee=assignee)


def link_issue_to_pr(issue, pr):
    """
    Create a link in JIRA to a pull request and add a comment linking to the PR.

    This method is idempotent; the links will only be created if they do not already exist.
    """
    jira_client = get_jira_client()
    url = pr.pr_json['html_url']
    title = "[Github] Pull Request #%s (%s)" % (pr.number, pr.user)

    existing_links = map(lambda l: l.raw['object']['url'], jira_client.remote_links(issue))
    if url in existing_links:
        return

    icon = {"title": "Pull request #%s" % pr.number,
            "url16x16": "https://assets-cdn.github.com/favicon.ico"}
    destination = {"title": title, "url": url, "icon": icon}
    jira_client.add_remote_link(issue, destination)

    comment = "User '%s' has created a pull request for this issue:\n%s" % (pr.user, url)
    jira_client.add_comment(issue, comment)
    logging.info("Linked PR %s to JIRA %s" % (pr.number, issue))