# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import argparse
import json
from logging import INFO, basicConfig, getLogger

from mozci.push import Push

from bugbug import repository

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
            result = {}
            if commit["backedoutby"]:
                print("Got one backout!")
                p = Push(commit["node"])
                result["bad"] = commit["node"]
                result["good"] = p.bustage_fixed_by

                commits.append(result)

                if limit and len(commits) >= limit:
                    break
    else:
        # Add implementation for other event types
        pass

    logger.info(f"Extracted {len(commits)} commits for event type: {event_type}")
    return commits


def main() -> None:
    description = "Retrieve good and bad code associated with commits."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--limit", type=int, help="Limit the number of commits to retrieve."
    )
    args = parser.parse_args()
    limit = args.limit

    logger.info(f"Starting with limit: {limit}")

    # assert db.download(repository.COMMITS_DB)

    source = repository.get_commits(include_backouts=True)
    commits = extract_commits(source, "backouts", limit)

    with open("commit_code_db.json", "w") as f:
        json.dump(commits, f)

    logger.info("Commits written to commit_code_db.json.")

    logger.info("Process completed.")


if __name__ == "__main__":
    main()
