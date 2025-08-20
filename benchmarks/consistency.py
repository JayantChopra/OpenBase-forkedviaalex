import ast

SUPPORTED_LANGUAGES = {"python"}
import re
import io
from .utils import get_python_files, parse_file

SNAKE_CASE_REGEX = re.compile(r"^[a-z_][a-z0-9_]*$")
CAMEL_CASE_REGEX = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


def _format_detail(kind: str, name: str, file_path: str, lineno: int) -> str:
    """
    Build a standardized detail message for an inconsistent name.

    Uses list-join to efficiently concatenate the message parts.
    """
    if kind == "class":
        parts = ["Inconsistent class name: '", name, "' should be CamelCase. (", file_path, ":", str(lineno), ")"]
    elif kind == "function":
        parts = ["Inconsistent function name: '", name, "' should be snake_case. (", file_path, ":", str(lineno), ")"]
    else:  # variable
        parts = ["Inconsistent variable name: '", name, "' should be snake_case. (", file_path, ":", str(lineno), ")"]
    return "".join(parts)


def _assess_tree_names(tree: ast.AST, file_path: str):
    """
    Walk an AST tree and return counts and detail messages about naming inconsistencies.

    Returns a tuple: (total_names, inconsistent_names, details_list)
    """
    total_names = 0
    inconsistent_names = 0
    details = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            total_names += 1
            if not CAMEL_CASE_REGEX.match(node.name):
                inconsistent_names += 1
                details.append(_format_detail("class", node.name, file_path, getattr(node, "lineno", 0)))
        elif isinstance(node, ast.FunctionDef):
            total_names += 1
            # Ignore dunder methods
            if not node.name.startswith("__") and not SNAKE_CASE_REGEX.match(node.name):
                inconsistent_names += 1
                details.append(_format_detail("function", node.name, file_path, getattr(node, "lineno", 0)))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            total_names += 1
            if not SNAKE_CASE_REGEX.match(node.id):
                inconsistent_names += 1
                details.append(_format_detail("variable", node.id, file_path, getattr(node, "lineno", 0)))

    return total_names, inconsistent_names, details


def assess_consistency(codebase_path: str):
    """
    Assess the naming consistency of a Python codebase.

    Rules enforced:
    - Class names should be CamelCase.
    - Function and variable names should be snake_case.

    Returns a tuple: (score_out_of_10, details_list)
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_names = 0
    inconsistent_names = 0
    details = []

    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue

        t_total, t_inconsistent, t_details = _assess_tree_names(tree, file_path)
        total_names += t_total
        inconsistent_names += t_inconsistent
        if t_details:
            details.extend(t_details)

    if total_names == 0:
        return 10.0, ["No relevant names found to check."]

    consistency_ratio = (total_names - inconsistent_names) / total_names
    consistency_score = consistency_ratio * 10.0
    details.insert(0, f"Naming consistency: {consistency_ratio*100:.2f}% ({total_names - inconsistent_names}/{total_names} consistent)")

    return min(10.0, max(0.0, consistency_score)), details