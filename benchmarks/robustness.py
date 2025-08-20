import ast
import os
import io

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

def _analyze_tree_for_logging_and_handlers(tree, file_path):
    """
    Walks an AST tree and detects:
    - whether the 'logging' module is imported in the tree
    - counts of exception handlers and how many are specific vs generic/bare
    - returns (uses_logging, total_handlers, good_handlers, messages)
    This helper avoids deep nesting by keeping the single AST walk focused.
    """
    if tree is None:
        raise ValueError("AST tree must not be None")

    uses_logging = False
    total_handlers = 0
    good_handlers = 0
    messages = []

    for node in ast.walk(tree):
        # Detect imports of the logging module
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    if alias.name == "logging":
                        uses_logging = True
                        break
                except Exception:
                    # Defensive: continue walking even if alias inspection fails
                    continue
        elif isinstance(node, ast.ImportFrom):
            try:
                if node.module == "logging":
                    uses_logging = True
            except Exception:
                # Defensive: ignore malformed ImportFrom nodes
                continue

        # Analyze exception handlers
        if isinstance(node, ast.ExceptHandler):
            total_handlers += 1
            try:
                if node.type:
                    # Specific exception type provided
                    if isinstance(node.type, ast.Name) and node.type.id == "Exception":
                        sb = io.StringIO()
                        sb.write("Generic 'except Exception' used in ")
                        sb.write(file_path)
                        sb.write(":")
                        sb.write(str(getattr(node, "lineno", "unknown")))
                        messages.append(sb.getvalue())
                    else:
                        good_handlers += 1
                else:
                    sb = io.StringIO()
                    sb.write("Bare 'except:' used in ")
                    sb.write(file_path)
                    sb.write(":")
                    sb.write(str(getattr(node, "lineno", "unknown")))
                    messages.append(sb.getvalue())
            except Exception as exc:
                # Targeted handling: record that analysis of this handler failed
                sb = io.StringIO()
                sb.write("Failed to analyze ExceptHandler in ")
                sb.write(file_path)
                sb.write(":")
                sb.write(str(getattr(node, "lineno", "unknown")))
                sb.write(" — ")
                sb.write(repr(exc))
                messages.append(sb.getvalue())

    return uses_logging, total_handlers, good_handlers, messages

def assess_robustness(codebase_path: str):
    """
    Assesses the robustness of a codebase.
    - Checks for specific exception handling vs. generic `except:`.
    - Checks for the use of logging.

    Input validation:
    - codebase_path must be a non-empty string and point to an existing path.

    Returns:
    - score (float between 0 and 10)
    - details (list of strings describing findings)
    """
    # Explicit input validation
    if not isinstance(codebase_path, str) or not codebase_path.strip():
        raise ValueError("codebase_path must be a non-empty string")
    if not os.path.exists(codebase_path):
        raise ValueError(f"codebase_path does not exist: {codebase_path}")

    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_handlers = 0
    good_handlers = 0
    uses_logging = False
    details = []

    for file_path in python_files:
        try:
            tree = parse_file(file_path)
        except Exception as exc:
            sb = io.StringIO()
            sb.write("Failed to parse file ")
            sb.write(file_path)
            sb.write(" — ")
            sb.write(repr(exc))
            details.append(sb.getvalue())
            # Skip further analysis for this file but continue processing others
            continue

        if not tree:
            sb = io.StringIO()
            sb.write("No AST produced for ")
            sb.write(file_path)
            details.append(sb.getvalue())
            continue

        try:
            file_uses_logging, file_total, file_good, file_msgs = _analyze_tree_for_logging_and_handlers(tree, file_path)
        except Exception as exc:
            sb = io.StringIO()
            sb.write("Error analyzing AST for ")
            sb.write(file_path)
            sb.write(" — ")
            sb.write(repr(exc))
            details.append(sb.getvalue())
            continue

        if file_uses_logging:
            uses_logging = True
        total_handlers += file_total
        good_handlers += file_good
        if file_msgs:
            details.extend(file_msgs)

    if uses_logging:
        details.insert(0, "Codebase appears to use the 'logging' module.")
    else:
        details.insert(0, "Codebase does not appear to use the 'logging' module.")

    if total_handlers == 0:
        return 5.0 if uses_logging else 2.0, details

    # Defensive calculation to avoid ZeroDivisionError (though handled above)
    handler_quality = (good_handlers / total_handlers) if total_handlers else 0.0
    handler_score = handler_quality * 8.0  # Max 8 points from handlers

    if uses_logging:
        handler_score += 2.0  # Bonus points for logging

    # Build quality message using StringIO to avoid repeated string concatenation
    sb = io.StringIO()
    sb.write("Error handling quality: ")
    sb.write(f"{handler_quality*100:.2f}%")
    sb.write(" (")
    sb.write(str(good_handlers))
    sb.write("/")
    sb.write(str(total_handlers))
    sb.write(" specific handlers)")
    details.insert(1, sb.getvalue())

    return min(10.0, max(0.0, handler_score)), details