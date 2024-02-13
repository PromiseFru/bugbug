import argparse
import json
import itertools

from logging import INFO, basicConfig, getLogger
from datetime import datetime, timedelta
from tqdm import tqdm

from mozci.push import Push
from bugbug import bugzilla, db, repository, phabricator

basicConfig(level=INFO)
logger = getLogger(__name__)


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
        if bug_id not in grouped_commits:
            grouped_commits[bug_id] = []
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


def extract_commits(grouped_commits, event_type, limit=None) -> None:
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

        for bug_id, commits in limited_grouped_commits.items():
            bug_id = int(bug_id)
            bug = bugs[bug_id]

            if bug["status"] not in ["VERIFIED"] or len(commits) < 2:
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
                for subsequent_commit in commits_sorted[backed_out_index + 1 :]:
                    if (
                        not subsequent_commit["backed_out"]
                        and "backed out changeset"
                        not in subsequent_commit["desc"].lower()
                    ):
                        extracted_commits[bug_id] = {
                            "bad_commit": backed_out_commit,
                            "good_commit": subsequent_commit,
                        }

        logger.info(f"Extracted commits for event type: {event_type}")
        print(extracted_commits)
    else:
        # Add implementation for other event types
        pass


def main() -> None:
    source = repository.get_commits(include_backouts=True)

    with open("commit_code_db.json", "r", encoding="utf-8") as json_file:
        grouped_commits = json.load(json_file)

    extract_commits(grouped_commits, "backouts", limit=100)

    logger.info("Process completed.")


if __name__ == "__main__":
    main()
