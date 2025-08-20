from radon.visitors import ComplexityVisitor
import logging
from typing import Tuple, List
from io import StringIO

# Readability analysis is currently Python-specific
SUPPORTED_LANGUAGES = {"python"}
from pycodestyle import StyleGuide
from .utils import get_python_files

logger = logging.getLogger(__name__)

def _analyze_file_complexity(file_path: str) -> Tuple[int, int, List[str]]:
    """
    Analyze a single Python file for cyclomatic complexity.

    Returns a tuple:
    - total complexity across all functions in the file
    - number of functions found
    - list of detail messages (e.g., high complexity warnings)
    """
    complexity_sum = 0
    functions_count = 0
    messages_buffer = StringIO()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        visitor = ComplexityVisitor.from_code(code)
        for func in visitor.functions:
            functions_count += 1
            complexity_sum += func.complexity
            if func.complexity > 10:
                # Use the buffer to collect per-file messages efficiently
                messages_buffer.write(
                    f"High complexity ({func.complexity}) in function '{func.name}' at {file_path}:{func.lineno}\n"
                )
    except Exception:
        # Preserve original behavior of logging the exception and not raising
        logger.exception("Failed to analyze complexity for %s", file_path)

    # Split the buffer into individual lines (dropping any trailing newline)
    messages = [line for line in messages_buffer.getvalue().splitlines() if line]
    return complexity_sum, functions_count, messages

def assess_readability(codebase_path: str) -> Tuple[float, List[str]]:
    """
    Assess the readability of a codebase.

    Returns a tuple of (readability_score, details).
    - readability_score: float between 0.0 and 10.0 (higher is better)
    - details: list of human-readable messages about findings

    The assessment considers:
    - Cyclomatic complexity (via radon): lower is better.
    - PEP8 compliance (via pycodestyle): fewer errors is better.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    details: List[str] = []
    total_complexity = 0
    total_functions = 0

    for file_path in python_files:
        complexity_sum, functions_count, file_messages = _analyze_file_complexity(file_path)
        total_complexity += complexity_sum
        total_functions += functions_count
        # Extend details with any messages collected for this file
        if file_messages:
            details.extend(file_messages)

    avg_complexity = (total_complexity / total_functions) if total_functions > 0 else 0.0
    complexity_score = max(0.0, 10.0 - (avg_complexity - 5.0))
    details.append(f"Average cyclomatic complexity: {avg_complexity:.2f}")

    style_guide = StyleGuide(quiet=True)
    report = style_guide.check_files(python_files)
    pep8_errors = report.total_errors
    details.append(f"Found {pep8_errors} PEP8 style violations.")

    pep8_score = max(0.0, 10.0 - (pep8_errors / 5.0))

    readability_score = (0.6 * complexity_score + 0.4 * pep8_score)

    return min(10.0, max(0.0, readability_score)), details