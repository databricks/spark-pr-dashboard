"""
Utility functions, placed here for easy testing.
"""
import re


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
                                   |(?:SPARK-\d+\s*)      # JIRA issues, like SPARK-957
                                    )*)                   # The metadata is optional.
                                    (.*)                  # The rest is assumed to be the title.
                                """, pr_title, re.X | re.I).groups()
    # Strip punctuation that might have separated the JIRAs/tags from the rest of the title:
    rest = rest.lstrip(':-.')
    # Users might have included JIRAs elsewhere in the title, so we need to
    #  search the entire pull request title for JIRAs:
    jiras = [int(x) for x in re.findall(r"SPARK-(\d+)", pr_title, re.I)]
    # Remove JIRAs from the metadata:
    metadata_without_jiras = re.sub(r"\[?SPARK-\d+\]?", "", metadata, flags=re.I)
    # Remove certain tags, since they're generally noise once the PRs are categorized:
    tags_to_remove = ["MLLIB", "CORE", "PYSPARK", "SQL", "STREAMING", "YARN", "GRAPHX"]
    tags_to_remove_regex = "|".join(r"(?:\[?" + x + "\]?)" for x in tags_to_remove)
    metadata_without_jiras_or_tags = \
        re.sub(tags_to_remove_regex, "", metadata_without_jiras, flags=re.I).strip()
    return {
        'metadata': metadata_without_jiras_or_tags,
        'title': rest,
        'jiras': jiras,
    }