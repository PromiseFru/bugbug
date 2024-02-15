import argparse
import json
import itertools
import os
from logging import INFO, basicConfig, getLogger
from datetime import datetime, timedelta

from tqdm import tqdm

from mozci.push import Push
from bugbug import bugzilla, db, repository, phabricator

basicConfig(level=INFO)
logger = getLogger(__name__)

PHABRICATOR_API_URL = "https://phabricator.services.mozilla.com/api/"
PHABRICATOR_API_KEY = ""


def group_commits_by_bug(source, start_date=None, limit=None):
    """Groups commits by bug ID."""
    commits = list(itertools.islice(source, limit))
    start_date = (
        datetime.strptime(start_date, "%Y-%m-%d")
        if start_date
        else datetime.now() - timedelta(days=365 * 2)
    )

    grouped_commits = {}

    for commit in commits:
        commit_date = datetime.strptime(commit["pushdate"], "%Y-%m-%d %H:%M:%S")
        if commit_date < start_date:
            continue

        bug_id = commit.get("bug_id", "Unknown")
        grouped_commits.setdefault(bug_id, [])
        commit_details = {
            key: commit[key]
            for key in [
                "node",
                "author",
                "bug_id",
                "desc",
                "pushdate",
                "backsout",
                "backedoutby",
                "author_email",
                "reviewers",
                "ignored",
                "source_code_added",
                "other_added",
                "test_added",
                "source_code_deleted",
                "other_deleted",
                "test_deleted",
                "types",
            ]
        }
        commit_details["backed_out"] = bool(commit["backedoutby"])
        grouped_commits[bug_id].append(commit_details)

    return grouped_commits


def extract_commits(grouped_commits, event_type, limit=None):
    """Extracts commits based on the specified events and saves periodically."""

    if event_type == "backouts":
        extracted_commits = {}

        if limit:
            limited_grouped_commits = dict(
                itertools.islice(grouped_commits.items(), limit)
            )
        else:
            limited_grouped_commits = grouped_commits

        bug_ids = limited_grouped_commits.keys()
        bugs = bugzilla.get(bug_ids)

        try:
            phabricator.set_api_key(
                url=PHABRICATOR_API_URL,
                api_key=PHABRICATOR_API_KEY,
            )

            for bug_id, bug_data in bugs.items():
                commits = limited_grouped_commits[str(bug_id)]

                if bug_data["status"] not in ["VERIFIED"] or len(commits) < 2:
                    continue

                commits_sorted = sorted(
                    commits,
                    key=lambda x: datetime.strptime(x["pushdate"], "%Y-%m-%d %H:%M:%S"),
                )

                # Check if any commits were backed out
                backed_out_commits = [
                    commit
                    for commit in commits_sorted
                    if commit["backed_out"]
                    and "backed out changeset" not in commit["desc"].lower()
                ]
                if not backed_out_commits:
                    # If no backed out commits, continue to the next bug
                    continue

                # Iterate over backed out commits
                for backed_out_commit in backed_out_commits:
                    # Find the index of the backed out commit
                    backed_out_index = commits_sorted.index(backed_out_commit)

                    # Check if there are subsequent non-backed-out commits
                    possible_fixes = []
                    for subsequent_commit in commits_sorted[backed_out_index + 1 :]:
                        if (
                            not subsequent_commit["backed_out"]
                            and "backed out changeset"
                            not in subsequent_commit["desc"].lower()
                            and repository.get_revision_id(commit=backed_out_commit)
                            == repository.get_revision_id(commit=subsequent_commit)
                        ):
                            possible_fixes.append(subsequent_commit)

                    if possible_fixes:
                        extracted_commits.setdefault(bug_id, [])
                        extracted_commits[bug_id].append(
                            {
                                "patch_backout": backed_out_commit,
                                "possible_fixes": possible_fixes,
                            }
                        )

            logger.info(f"Extracted commits for event type: {event_type}")

            with open("result.json", "w", encoding="utf-8") as file:
                json.dump(extracted_commits, file, indent=2)
        except Exception as e:
            logger.error(f"Error occurred while extracting commits: {e}")
    else:
        logger.warning("Event type not supported.")


def main():
    try:
        source = repository.get_commits(include_backouts=True)

        with open("commit_code_db.json", "r", encoding="utf-8") as json_file:
            grouped_commits = json.load(json_file)

        extract_commits(grouped_commits, "backouts", limit=2000)

        logger.info("Process completed.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
