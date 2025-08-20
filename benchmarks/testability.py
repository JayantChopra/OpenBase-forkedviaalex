import subprocess
import logging
import shutil
import json
import os
from typing import Tuple, List
from .utils import get_python_files

logger = logging.getLogger(__name__)

def _run_pytest(command: List[str], cwd: str) -> subprocess.CompletedProcess:
    """
    Run pytest as a subprocess with the given command and working directory.

    Returns the CompletedProcess instance from subprocess.run.
    """
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd
    )

def _read_coverage_report(report_path: str) -> Tuple[float, List[str]]:
    """
    Read a coverage JSON report and return a score and detail messages.

    Score is computed as coverage_percent / 10.0 to map 100% -> 10.0.
    """
    details: List[str] = []
    with open(report_path) as f:
        report = json.load(f)

    coverage_percent = report.get("totals", {}).get("percent_covered", 0.0)
    details.append(f"Test coverage: {coverage_percent:.2f}%")
    score = coverage_percent / 10.0

    if coverage_percent < 50:
        details.append("Low coverage. Consider adding more tests for critical paths.")

    return score, details

def _remove_file(path: str) -> None:
    """
    Remove a file if it exists. Logs a warning on failure.
    """
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning("Failed to remove file %s: %s", path, e)

def assess_testability(codebase_path: str) -> Tuple[float, List[str]]:
    """
    Assess the testability of a codebase by running its tests and measuring coverage.

    Returns a tuple of (score, details) where score is between 0.0 and 10.0 and
    details is a list of human-readable messages about the assessment.
    """
    details: List[str] = []
    
    # Validate input
    if not isinstance(codebase_path, str) or not codebase_path:
        logger.error("Invalid codebase_path provided: %r", codebase_path)
        return 0.0, ["Invalid codebase_path provided."]
    try:
        codebase_path = os.path.abspath(codebase_path)
    except Exception as e:
        logger.exception("Failed to resolve absolute path for codebase_path: %s", e)
        return 0.0, ["Invalid codebase_path provided."]
    if not os.path.isdir(codebase_path):
        logger.error("codebase_path is not a directory or does not exist: %s", codebase_path)
        return 0.0, ["codebase_path is not a directory or does not exist."]

    # Check for presence of test files
    try:
        python_files = get_python_files(codebase_path)
    except Exception as e:
        logger.exception("Error while getting python files: %s", e)
        return 0.0, ["Error while scanning codebase for Python files."]
    test_files = (f for f in python_files if "test" in os.path.basename(f).lower())
    # Use next to efficiently check for any test file without building a large list
    if next(test_files, None) is None:
        return 0.0, ["No test files found (e.g., files named test_*.py)."]

    json_report_path = os.path.join(codebase_path, "coverage.json")
    
    # Ensure pytest is available
    if shutil.which("pytest") is None:
        logger.error("pytest executable not found in PATH")
        return 0.0, ["Could not run pytest. Is it installed and in your PATH?"]

    # Run pytest with coverage
    try:
        # Note: This assumes the codebase's dependencies are installed in the environment.
        command = [
            "pytest",
            "--cov=" + codebase_path,
            "--cov-report=json:" + json_report_path,
            codebase_path
        ]
        # Use helper to run subprocess; cwd validated above.
        result = _run_pytest(command, codebase_path)
        if result.returncode != 0:
            logger.warning("pytest returned non-zero exit code %s. stderr: %s", result.returncode, result.stderr.strip())
    except FileNotFoundError as e:
        logger.exception("Could not execute pytest: %s", e)
        return 0.0, ["Could not run pytest. Is it installed and in your PATH?"]
    except PermissionError as e:
        logger.exception("Permission error when running pytest: %s", e)
        return 0.0, ["Insufficient permissions to run pytest."]
    except subprocess.SubprocessError as e:
        logger.exception("Subprocess error when running pytest: %s", e)
        return 0.0, ["Failed to run pytest due to a subprocess error."]
    except Exception as e:
        logger.exception("Unexpected error when running pytest: %s", e)
        return 0.0, ["Unexpected error when running pytest."]

    if not os.path.exists(json_report_path):
        logger.error("Coverage report (coverage.json) was not generated at expected path: %s", json_report_path)
        return 0.0, ["Coverage report (coverage.json) was not generated. Tests may have failed."]

    score = 0.0
    try:
        score, report_details = _read_coverage_report(json_report_path)
        details.extend(report_details)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.exception("Could not parse coverage report: %s", e)
        score = 0.0
        details.append("Could not parse coverage report.")
    except Exception as e:
        logger.exception("Unexpected error while processing coverage report: %s", e)
        score = 0.0
        details.append("Unexpected error while processing coverage report.")
    finally:
        _remove_file(json_report_path)

    return min(10.0, max(0.0, score)), details