import ast

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

def assess_documentation(codebase_path: str):
    """
    Assess documentation quality for a Python codebase.

    This function scans Python files under the provided path and computes:
    - Documentation coverage: percentage of modules, classes and functions that have docstrings.
    - A simple quality metric for docstrings based on a heuristic.

    Parameters:
    - codebase_path (str): Path to the codebase directory to analyze.

    Returns:
    - tuple[float, list[str]]: A score between 0.0 and 10.0 and a list of detail messages.
      The detail messages include coverage, counts of "good" docstrings, and any missing docstring notices.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_entities = 0
    documented_entities = 0
    details = []

    good_docstrings = 0

    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue

        t_total, t_documented, t_good, t_details = _analyze_tree(tree, file_path)
        total_entities += t_total
        documented_entities += t_documented
        good_docstrings += t_good
        if t_details:
            details.extend(t_details)

    if total_entities == 0:
        return 0.0, ["No documentable entities (classes, functions) found."]

    doc_coverage = (documented_entities / total_entities) * 100
    quality_ratio = (good_docstrings / documented_entities) if documented_entities else 0

    # Score components
    coverage_score = doc_coverage / 10.0  # 100% ->10
    intrinsic_quality_score = quality_ratio * 10.0
    quality_score = intrinsic_quality_score

    final_score = (coverage_score + quality_score) / 2.0

    details.insert(0, "".join(["Documentation coverage: ", f"{doc_coverage:.2f}% (", f"{documented_entities}/{total_entities})"]))
    details.insert(1, "".join(["Good docstrings: ", f"{good_docstrings}/{documented_entities} (", f"{quality_ratio*100:.1f}% )"]))

    return min(10.0, max(0.0, final_score)), details 

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _analyze_tree(tree: ast.AST, file_path: str):
    """
    Analyze a parsed AST tree for a single file and collect documentation metrics.

    Returns:
    - total_entities (int)
    - documented_entities (int)
    - good_docstrings (int)
    - details (list[str])
    """
    total_entities = 0
    documented_entities = 0
    good_docstrings = 0
    details = []

    # Module docstring
    total_entities += 1
    module_ds = ast.get_docstring(tree)
    if module_ds:
        documented_entities += 1
        if _good_docstring(module_ds):
            good_docstrings += 1
    else:
        details.append("".join(["Missing docstring in module: ", file_path]))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            total_entities += 1
            ds = ast.get_docstring(node)
            if ds:
                documented_entities += 1
                if _good_docstring(ds):
                    good_docstrings += 1
            else:
                details.append("".join(["Missing docstring for '", node.name, "' in ", file_path, ":", str(node.lineno)]))

    return total_entities, documented_entities, good_docstrings, details

def _good_docstring(ds: str) -> bool:
    """Heuristic: multiline and contains Args/Parameters or Returns, or >50 chars."""
    raw_lines = ds.splitlines()
    non_blank_count = sum(1 for ln in raw_lines if ln.strip())

    # Must have at least summary + description lines
    if non_blank_count < 3:
        return False

    # Heuristic 2: reject if more than 5 consecutive blank lines (excessive vertical space)
    consecutive_blanks = 0
    excessive_blanks = False
    for ln in raw_lines:
        if ln.strip() == "":
            consecutive_blanks += 1
            if consecutive_blanks > 5:
                excessive_blanks = True
                break
        else:
            consecutive_blanks = 0

    if excessive_blanks:
        return False

    lowered = ds.lower()
    has_args = any(k in lowered for k in ("args:", "parameters:"))
    has_returns = "returns:" in lowered

    return has_args and has_returns