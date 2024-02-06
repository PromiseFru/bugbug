# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import argparse
import json
from logging import INFO, basicConfig, getLogger

from mozci.push import Push

from bugbug import db, repository

basicConfig(level=INFO)
logger = getLogger(__name__)


def extract_commits(source, event_type, limit=None) -> list:
    """Extracts commits based on the specified events.

    Args:
        source (dict): Source of the commits (e.g., COMMIT_DB).
        event_type (str): Type of event to filter commits (e.g., backouts, review comments).
        limit (int): Maximum number of commits to extract.

    Returns:
        list: List of extracted commits.
    """
    assert source, "Source must be provided."

    commits = []

    if event_type == "backouts":
        for commit in source:
            if commit["backedoutby"]:
                commits.append(commit["node"])

                if limit and len(commits) >= limit:
                    break

        p = Push(commits)
        save_commit_result(p.bustage_fixed_by)

    else:
        # Add implementation for other event types
        pass

    logger.info(f"Extracted {len(commits)} commits for event type: {event_type}")
    return commits


def save_commit_result(commit_result):
    """Writes the commit result to a JSON file."""
    with open("commit_code_db.json", "a", encoding="utf-8") as f:
        json.dump(commit_result, f)
        f.write("\n")


def main() -> None:
    description = "Retrieve good and bad code associated with commits."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--limit", type=int, help="Limit the number of commits to retrieve."
    )
    args = parser.parse_args()
    limit = args.limit

    logger.info(f"Starting with limit: {limit}")

    assert db.download(repository.COMMITS_DB)

    source = repository.get_commits(include_backouts=True)
    extract_commits(source, "backouts", limit)

    logger.info("Process completed.")


if __name__ == "__main__":
    main()
