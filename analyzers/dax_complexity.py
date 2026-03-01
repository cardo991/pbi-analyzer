"""DAX Complexity Score analyzer."""

import re
from models import SemanticModel


def analyze_dax_complexity(model: SemanticModel) -> list[dict]:
    """Analyze DAX complexity for all measures.

    Returns a sorted list of dicts:
        name, table, score, level, details
    """
    results = []

    for table in model.tables:
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        for m in table.measures:
            if not m.expression or not m.expression.strip():
                continue

            score, details = _compute_complexity(m.expression)
            level = _score_to_level(score)

            results.append({
                "name": m.name,
                "table": table.name,
                "score": round(score, 1),
                "level": level,
                "details": details,
            })

    # Sort by score descending
    results.sort(key=lambda x: -x["score"])
    return results


def _compute_complexity(expression: str) -> tuple[float, dict]:
    """Compute complexity score for a DAX expression.

    Formula: length/50 + nesting_depth*5 + function_count*2 + CALCULATE_count*3 - VAR_count*1
    """
    length = len(expression)
    nesting = _max_nesting_depth(expression)
    func_count = len(re.findall(r'(?i)\b[A-Z][A-Z0-9_]+\s*\(', expression))
    calculate_count = len(re.findall(r'(?i)\bCALCULATE\s*\(', expression))
    var_count = len(re.findall(r'(?i)\bVAR\b', expression))

    score = (length / 50) + (nesting * 5) + (func_count * 2) + (calculate_count * 3) - (var_count * 1)
    score = max(0, score)

    details = {
        "length": length,
        "nesting_depth": nesting,
        "function_count": func_count,
        "calculate_count": calculate_count,
        "var_count": var_count,
    }

    return score, details


def _max_nesting_depth(expression: str) -> int:
    """Calculate maximum parenthesis nesting depth."""
    depth = 0
    max_depth = 0
    for ch in expression:
        if ch == '(':
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == ')':
            depth = max(0, depth - 1)
    return max_depth


def _score_to_level(score: float) -> str:
    """Convert complexity score to level label."""
    if score < 10:
        return "low"
    elif score < 25:
        return "medium"
    elif score < 50:
        return "high"
    else:
        return "very_high"
