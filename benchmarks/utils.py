import os
import ast
from typing import List, Optional

"""Utilities for discovering and parsing Python source files.

This module provides small, testable functions to:
- discover Python files under a filesystem path
- parse a Python source file into an AST, gracefully handling common errors

Refactor notes:
- The nested loop used to collect Python files has been extracted into helper
  functions to make the logic unit-testable and easier to maintain.
- Type hints and docstrings were added for clarity and to support static checking.
"""

def _is_python_file(filename: str) -> bool:
    """Return True if filename looks like a Python source file.

    This is a small, pure helper intended to be unit-tested in isolation.
    """
    return filename.endswith(".py")

def _collect_python_files(root: str, files: List[str]) -> List[str]:
    """Return a list of full paths to Python files given a root and filenames.

    Uses os.path.join to build full paths and performs filtering via
    _is_python_file. This isolates the per-directory processing so tests can
    exercise it without walking the filesystem.
    """
    return [os.path.join(root, f) for f in files if _is_python_file(f)]

def get_python_files(path: str) -> List[str]:
    """Walk the directory tree at `path` and return a list of Python file paths.

    The function delegates per-directory work to `_collect_python_files` so
    the core walking logic remains simple and unit-testable.

    Args:
        path: Root directory to walk.

    Returns:
        A list of absolute or relative file paths (depending on `path`) for
        files ending with the `.py` extension.
    """
    python_files: List[str] = []
    for root, _, files in os.walk(path):
        python_files.extend(_collect_python_files(root, files))
    return python_files

def parse_file(file_path: str) -> Optional[ast.AST]:
    """Parse a Python source file into an AST.

    Returns the AST on success, or None if the file cannot be decoded or
    contains a syntax error.

    Args:
        file_path: Path to the Python source file to parse.

    Returns:
        ast.AST on success, or None on failure.
    """
    with open(file_path, "r", encoding="utf-8") as source:
        try:
            return ast.parse(source.read(), filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            return None