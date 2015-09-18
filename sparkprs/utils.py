"""
Utility functions, placed here for easy testing.
"""
import re

from sparkprs import app

JENKINS_COMMAND_REGEX = r"""
        (jenkins,?\s*)?                     # Optional address, followed by a command:
        ((add\s+to\s+whitelist)
       |((this\s+is\s+)?ok\s+to\s+test)
       |((re)?test\s+this\s+please)
       |(skip\s+ci))
       \.?
"""


def contains_jenkins_command(comment):
    """
    Returns True if the comment contains a command for Jenkins.

    >>> contains_jenkins_command("LGTM, pending Jenkins.  Jenkins, retest this please.")
    True
    """
    return re.search(JENKINS_COMMAND_REGEX, comment, re.I | re.X) is not None


def is_jenkins_command(comment):
    """
    Returns True if the comment consists solely of Jenkins commands.
    This is heuristic-based; it's easy to identify the presence of Jenkins commands,
    but trickier to also match surrounding context that's part of the command,
    such as "Jenkins, ...".

    Single commands:
    >>> is_jenkins_command("Jenkins, this is ok to test.")
    True

    Multiple commands:
    >>> is_jenkins_command(r"Jenkins, this is ok to test.\\nJenkins, test this please.")
    True
    >>> is_jenkins_command("ok to test add to whitelist test this please    skip ci")
    True

    Commands intermixed with other comments:
    >>> is_jenkins_command("LGTM.  ok to test")
    False
    >>> is_jenkins_command("ok to test.  This looks fine.")
    False
    """
    # Check that the comment string is one or more Jenkins commands:
    regex = "^(%s\s*)+$" % JENKINS_COMMAND_REGEX
    return re.match(regex, comment.strip().replace(r"\n", ' '), re.I | re.X) is not None


def parse_pr_title(pr_title):
    """
    Parse a pull request title to identify JIRAs, categories, and the
    remainder of the title.

    >>> parse_pr_title("[SPARK-975] [core] Visual debugger of stages and callstacks")
    {'jiras': [975], 'title': 'Visual debugger of stages and callstacks', 'metadata': ''}
    >>> parse_pr_title("Documentation update")
    {'jiras': [], 'title': 'Documentation update', 'metadata': ''}
    >>> parse_pr_title("[CUSTOM-tag] SPARK-1234 Title")
    {'jiras': [1234], 'title': 'Title', 'metadata': '[CUSTOM-tag]'}
    >>> parse_pr_title("Fix SPARK-1 & SPARK-2")
    {'jiras': [1, 2], 'title': 'Fix SPARK-1 & SPARK-2', 'metadata': ''}
    """
    # Usually, pull request titles reference JIRAs and categories at the start
    # of the title, followed by the actual issue title.  Attempt to identify the point
    # where this metadata ends and the actual title begins:
    (metadata, rest) = re.match(r"""((?:                  # The metadata consists of either:
                                    (?:\[[^\]]*\]\s*)     # Tags enclosed in brackets, like [CORE]
                                   |(?:%s-\d+\s*)         # JIRA issues, like SPARK-957
                                    )*)                   # The metadata is optional.
                                    (.*)                  # The rest is assumed to be the title.
                                """ % app.config['JIRA_PROJECT'],
                                pr_title, re.X | re.I).groups()
    # Strip punctuation that might have separated the JIRAs/tags from the rest of the title:
    rest = rest.lstrip(':-.')
    # Users might have included JIRAs elsewhere in the title, so we need to
    #  search the entire pull request title for JIRAs:
    jiras = [int(x) for x in re.findall(r"%s-(\d+)" % app.config['JIRA_PROJECT'], pr_title, re.I)]
    # Remove JIRAs from the metadata:
    metadata_without_jiras = re.sub(r"\[?%s-\d+\]?" % app.config['JIRA_PROJECT'],
                                    "", metadata, flags=re.I)
    # Remove certain tags, since they're generally noise once the PRs are categorized:
    tags_to_remove = app.config['JIRA_TAGS_TO_REMOVE']
    tags_to_remove_regex = "|".join(r"(?:\[?" + x + "\]?)" for x in tags_to_remove)
    metadata_without_jiras_or_tags = \
        re.sub(tags_to_remove_regex, "", metadata_without_jiras, flags=re.I).strip()
    return {
        'metadata': metadata_without_jiras_or_tags,
        'title': rest,
        'jiras': jiras,
    }


def compute_last_jenkins_outcome(comments_json):
    # Because the Jenkins GHPRB plugin isn't fully configurable on a per-project basis, each PR
    # ends up receiving comments from multiple bots on build failures. The SparkQA bot posts the
    # detailed build failure messages that mention the specific tests that failed; this bot is
    # controlled by the run-tests-jenkins.sh script in Spark. The AmplabJenkins bot is
    # controlled by the Jenkins GHPRB plugin and posts the generic build outcome comments. If
    # the plugin supported per-project configurations, then we could suppress these redundant
    # messages.
    #
    # The AmplabJenkins comments aren't useful except when the build fails in a way that
    # prevents SparkQA from being able to post an error message (e.g. if there's an error in
    # the run-tests-jenkins.sh script itself). Therefore, we ignore failure / success comments
    # from AmplabJenkins as long as the previous comment is from SparkQA.
    status = "Unknown"
    jenkins_comment = None
    prev_author = None
    for comment in (comments_json or []):
        author = comment['user']['login']
        body = comment['body'].lower()
        if contains_jenkins_command(body):
            status = "Asked"
            jenkins_comment = comment
        elif author == "AmplabJenkins":
            if "can one of the admins verify this patch?" in body:
                jenkins_comment = comment
                status = "Verify"
            elif "fail" in body and \
                    (prev_author != "SparkQA" or status not in ("Fail", "Timeout")):
                jenkins_comment = comment
                status = "Fail"
        elif author == "SparkQA":
            if "pass" in body:
                status = "Pass"
            elif "fail" in body:
                status = "Fail"
            elif "started" in body:
                status = "Running"
            elif "timed out" in body:
                status = "Timeout"
            else:
                status = "Unknown"  # So we display "Unknown" instead of out-of-date status
            jenkins_comment = comment
        prev_author = author
    return (status, jenkins_comment)
