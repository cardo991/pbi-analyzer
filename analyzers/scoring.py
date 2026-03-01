"""Health score calculation engine."""

from collections import defaultdict
from models import Finding
from config import CATEGORY_WEIGHTS, SEVERITY_DEDUCTIONS, GRADE_BOUNDARIES


# Map rule prefixes to categories
RULE_CATEGORY_MAP = {
    "DAX": "dax",
    "PQ": "power_query",
    "DM": "data_model",
    "RP": "report",
    "SEC": "data_model",
    "NC": "data_model",
    "PERF": "data_model",
    "BK": "report",
}


def calculate_score(findings: list[Finding]) -> dict:
    """Calculate health score from findings.

    Returns dict with:
        total_score: float (0-100)
        grade: str (A-F)
        grade_key: str (grade_A, grade_B, etc.)
        category_scores: dict {category: score}
        category_max: dict {category: max_score}
        category_findings: dict {category: [findings]}
    """
    # Group findings by rule
    by_rule = defaultdict(list)
    for f in findings:
        by_rule[f.rule_id].append(f)

    # Calculate deductions per category
    category_deductions = {cat: 0.0 for cat in CATEGORY_WEIGHTS}

    for rule_id, rule_findings in by_rule.items():
        category = _get_category(rule_id)
        if category not in category_deductions:
            continue

        severity = rule_findings[0].severity
        config = SEVERITY_DEDUCTIONS.get(severity, SEVERITY_DEDUCTIONS["info"])

        deduction = min(
            len(rule_findings) * config["per_occurrence"],
            config["max_per_rule"],
        )
        category_deductions[category] += deduction

    # Calculate per-category scores
    category_scores = {}
    for cat, weight in CATEGORY_WEIGHTS.items():
        raw = weight - category_deductions[cat]
        category_scores[cat] = max(0.0, round(raw, 1))

    total = sum(category_scores.values())
    grade = _score_to_grade(total)

    # Group findings by category
    category_findings = defaultdict(list)
    for f in findings:
        category_findings[f.category].append(f)

    # Sort findings: errors first, then warnings, then info
    severity_order = {"error": 0, "warning": 1, "info": 2}
    for cat in category_findings:
        category_findings[cat].sort(key=lambda x: severity_order.get(x.severity, 3))

    return {
        "total_score": round(total, 1),
        "grade": grade,
        "grade_key": f"grade_{grade}",
        "category_scores": category_scores,
        "category_max": dict(CATEGORY_WEIGHTS),
        "category_findings": dict(category_findings),
    }


def _get_category(rule_id: str) -> str:
    """Map rule ID to category. E.g., 'DAX-001' → 'dax'."""
    prefix = rule_id.split("-")[0]
    return RULE_CATEGORY_MAP.get(prefix, "dax")


def _score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    for threshold, grade in GRADE_BOUNDARIES:
        if score >= threshold:
            return grade
    return "F"
