from pathlib import Path

SUPPORTED_LANGUAGES = {"any"}
from datetime import datetime, timedelta
from collections import Counter
from typing import List, Tuple

from git import Repo, InvalidGitRepositoryError

from .utils import get_python_files

import logging
from io import StringIO

THRESHOLD_DAYS = 180  # 6 months

logger = logging.getLogger(__name__)


def _gather_commit_counters(repo: Repo, codebase_path: str, since_iso: str) -> Tuple[Counter, Counter]:
    """Collect file and author commit counts from the repository since the given ISO date.

    This helper consolidates commit processing into a single pass while using
    Counter.update for efficient aggregation of file counts for each commit.
    """
    commits = list(repo.iter_commits(paths=codebase_path, since=since_iso))
    file_counter: Counter = Counter()
    author_counter: Counter = Counter()

    for commit in commits:
        # Count one commit per author occurrence
        author_email = getattr(commit.author, "email", None)
        if author_email:
            author_counter[author_email] += 1
        else:
            logger.debug("Commit %s has no author email; skipping author count.", getattr(commit, "hexsha", "unknown"))

        # Collect python files changed in this commit that belong to the codebase path,
        # then update the Counter in bulk.
        files = commit.stats.files.keys()
        py_files = [f for f in files if f.endswith(".py") and f.startswith(codebase_path)]
        if py_files:
            file_counter.update(py_files)

    return file_counter, author_counter


def _build_details_lines(file_counter: Counter, avg_churn: float, bus_factor: int) -> List[str]:
    """Format the details lines describing churn, hotspots, and bus factor.

    Uses an in-memory buffer to efficiently build the multi-line text, then
    returns a list of individual lines for compatibility with callers.
    """
    buf = StringIO()
    buf.write(f"Average churn / file: {avg_churn:.1f} commits in last 6 months.\n")

    most_changed = file_counter.most_common(5)
    for fname, count in most_changed:
        buf.write(f"{fname} changed {count} times in last 6 months.\n")

    buf.write(f"Bus factor (unique committers): {bus_factor}\n")

    content = buf.getvalue().rstrip("\n")
    # Return as list of lines to preserve original function contract
    return content.split("\n")


# Primary entry point expected by dynamic loader
def assess_git_health(codebase_path: str):
    """Assess git-based code health: churn, age, hotspot identification.

    Returns a tuple of (score: float, details: List[str]).
    """
    try:
        repo = Repo(Path(codebase_path).resolve(), search_parent_directories=True)
    except InvalidGitRepositoryError:
        logger.error("Path %s is not a git repository; skipping git health checks.", codebase_path)
        return 5.0, ["Not a git repository; skipping git health checks."]

    now = datetime.utcnow()

    # Map file -> commits last THRESHOLD_DAYS
    since_date = now - timedelta(days=THRESHOLD_DAYS)
    since_iso = since_date.isoformat()

    try:
        file_counter, author_counter = _gather_commit_counters(repo, codebase_path, since_iso)
    except Exception as exc:
        logger.exception("Failed while gathering commits for %s: %s", codebase_path, exc)
        return 5.0, [f"Error while analyzing git history: {exc}"]

    if not file_counter:
        logger.info("No python file churn detected in %s over the last %d days.", codebase_path, THRESHOLD_DAYS)
        return 8.0, ["Low churn detected in the last 6 months."]

    avg_churn = sum(file_counter.values()) / len(file_counter)
    bus_factor = len(author_counter)

    details = _build_details_lines(file_counter, avg_churn, bus_factor)

    # Scoring: moderate churn is ok; very high churn => lower score
    if avg_churn < 3:
        score = 9.0
    elif avg_churn < 10:
        score = 7.0
    elif avg_churn < 20:
        score = 5.0
    else:
        score = 3.0

    # Reward higher bus factor (more contributors)
    score += min(2.0, bus_factor / 5.0)

    return min(10.0, score), details


# Backward compatibility alias
assess_githealth = assess_git_health