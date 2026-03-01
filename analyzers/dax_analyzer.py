"""DAX analysis rules (DAX-001 through DAX-011)."""

import re
from models import SemanticModel, Measure, Column, Finding
from config import COMPLEX_MEASURE_CHAR_THRESHOLD


def analyze_dax(model: SemanticModel) -> list[Finding]:
    """Run all DAX rules against the semantic model."""
    findings = []

    all_measures = []
    all_calc_columns = []
    for table in model.tables:
        for m in table.measures:
            m.table_name = m.table_name or table.name
            all_measures.append(m)
        for c in table.columns:
            if c.column_type == "calculated" and c.expression:
                all_calc_columns.append((table.name, c))

    for m in all_measures:
        expr = _strip_strings(m.expression)
        loc = f"Table '{m.table_name}', Measure '{m.name}'"

        findings.extend(_check_dax001(expr, loc))
        findings.extend(_check_dax002(expr, loc))
        findings.extend(_check_dax003(m, expr, loc))
        findings.extend(_check_dax004(expr, loc))
        findings.extend(_check_dax005(expr, loc))
        findings.extend(_check_dax006(m, expr, loc))
        findings.extend(_check_dax007(m, loc))
        findings.extend(_check_dax008_measure(m, loc))
        findings.extend(_check_dax009(expr, loc))
        findings.extend(_check_dax010(expr, loc))
        findings.extend(_check_dax011(expr, loc))

    for table_name, col in all_calc_columns:
        expr = _strip_strings(col.expression)
        loc = f"Table '{table_name}', Column '{col.name}'"
        findings.extend(_check_dax008_column(col, loc))

    return findings


def _strip_strings(expr: str) -> str:
    """Remove string literals from DAX to avoid false positive regex matches."""
    return re.sub(r'"[^"]*"', '""', expr)


def _check_dax001(expr: str, loc: str) -> list[Finding]:
    """DAX-001: Nested CALCULATE."""
    if re.search(r'(?i)\bCALCULATE\s*\(', expr):
        depth = 0
        max_depth = 0
        i = 0
        upper = expr.upper()
        while i < len(upper):
            if upper[i:i+9] == "CALCULATE" and (i == 0 or not upper[i-1].isalpha()):
                j = i + 9
                while j < len(upper) and upper[j] in " \t\n\r":
                    j += 1
                if j < len(upper) and upper[j] == "(":
                    depth += 1
                    max_depth = max(max_depth, depth)
                    i = j + 1
                    continue
            if upper[i] == "(":
                pass  # Only count CALCULATE parens
            if upper[i] == ")":
                if depth > 0:
                    depth -= 1
            i += 1

        if max_depth >= 2:
            return [Finding(
                rule_id="DAX-001",
                category="dax",
                severity="warning",
                message="DAX-001",
                location=loc,
            )]
    return []


def _check_dax002(expr: str, loc: str) -> list[Finding]:
    """DAX-002: Unnecessary iterator (SUMX/AVERAGEX/MINX/MAXX on simple column)."""
    pattern = re.compile(
        r"(?i)\b(SUMX|AVERAGEX|MINX|MAXX)\s*\(\s*'?([^',\)]+?)'?\s*,"
        r"\s*'?\2'?\s*\[([^\]]+)\]\s*\)",
    )
    matches = pattern.findall(expr)
    results = []
    for func, table, col in matches:
        alt_map = {"SUMX": "SUM", "AVERAGEX": "AVERAGE", "MINX": "MIN", "MAXX": "MAX"}
        results.append(Finding(
            rule_id="DAX-002",
            category="dax",
            severity="warning",
            message="DAX-002",
            location=loc,
            details={"func": func.upper(), "table": table.strip(), "col": col, "alt": alt_map.get(func.upper(), "SUM")},
        ))
    return results


def _check_dax003(m: Measure, expr: str, loc: str) -> list[Finding]:
    """DAX-003: Missing VAR for repeated subexpressions."""
    if re.search(r'(?i)\bVAR\b', m.expression):
        return []

    # Find measure references [MeasureName]
    refs = re.findall(r'\[[^\]]{3,}\]', expr)
    freq = {}
    for r in refs:
        freq[r] = freq.get(r, 0) + 1

    for ref, count in freq.items():
        if count >= 2:
            return [Finding(
                rule_id="DAX-003",
                category="dax",
                severity="info",
                message="DAX-003",
                location=loc,
            )]
    return []


def _check_dax004(expr: str, loc: str) -> list[Finding]:
    """DAX-004: Redundant IF returning TRUE/FALSE."""
    pattern = re.compile(
        r"(?i)\bIF\s*\(\s*.+?\s*,\s*(TRUE\s*\(\s*\)|TRUE|1)\s*,\s*(FALSE\s*\(\s*\)|FALSE|0)\s*\)"
    )
    if pattern.search(expr):
        return [Finding(
            rule_id="DAX-004",
            category="dax",
            severity="info",
            message="DAX-004",
            location=loc,
        )]
    return []


def _check_dax005(expr: str, loc: str) -> list[Finding]:
    """DAX-005: COUNTROWS(VALUES()) or COUNTROWS(DISTINCT()) → DISTINCTCOUNT."""
    pattern = re.compile(
        r"(?i)\bCOUNTROWS\s*\(\s*(VALUES|DISTINCT)\s*\(\s*'?[\w\s]+'?\s*\[\w+\]\s*\)\s*\)"
    )
    if pattern.search(expr):
        return [Finding(
            rule_id="DAX-005",
            category="dax",
            severity="info",
            message="DAX-005",
            location=loc,
        )]
    return []


def _check_dax006(m: Measure, expr: str, loc: str) -> list[Finding]:
    """DAX-006: Complex measure without variables."""
    if len(m.expression) > COMPLEX_MEASURE_CHAR_THRESHOLD:
        if not re.search(r'(?i)\bVAR\b', m.expression):
            return [Finding(
                rule_id="DAX-006",
                category="dax",
                severity="info",
                message="DAX-006",
                location=loc,
            )]
    return []


def _check_dax007(m: Measure, loc: str) -> list[Finding]:
    """DAX-007: Missing format string."""
    if not m.format_string or not m.format_string.strip():
        return [Finding(
            rule_id="DAX-007",
            category="dax",
            severity="info",
            message="DAX-007",
            location=loc,
        )]
    return []


def _check_dax008_measure(m: Measure, loc: str) -> list[Finding]:
    """DAX-008: Naming convention violations for measures."""
    name = m.name
    if name.startswith(" ") or name.endswith(" "):
        return [Finding(
            rule_id="DAX-008",
            category="dax",
            severity="info",
            message="DAX-008",
            location=loc,
            details={"reason": "leading/trailing spaces"},
        )]
    if name == name.upper() and len(name) > 3 and "_" in name:
        return [Finding(
            rule_id="DAX-008",
            category="dax",
            severity="info",
            message="DAX-008",
            location=loc,
            details={"reason": "ALL_CAPS naming"},
        )]
    return []


def _check_dax008_column(col: Column, loc: str) -> list[Finding]:
    """DAX-008: Naming convention violations for columns."""
    name = col.name
    if name.startswith(" ") or name.endswith(" "):
        return [Finding(
            rule_id="DAX-008",
            category="dax",
            severity="info",
            message="DAX-008",
            location=loc,
            details={"reason": "leading/trailing spaces"},
        )]
    return []


def _check_dax009(expr: str, loc: str) -> list[Finding]:
    """DAX-009: FILTER on entire table in CALCULATE."""
    pattern = re.compile(
        r"(?i)\bCALCULATE\s*\([^,]+,\s*FILTER\s*\(\s*'?[A-Za-z][\w\s]*'?\s*,"
    )
    if pattern.search(expr):
        return [Finding(
            rule_id="DAX-009",
            category="dax",
            severity="warning",
            message="DAX-009",
            location=loc,
        )]
    return []


def _check_dax010(expr: str, loc: str) -> list[Finding]:
    """DAX-010: IF(ISBLANK(...)) → COALESCE."""
    pattern = re.compile(r"(?i)\bIF\s*\(\s*ISBLANK\s*\(")
    if pattern.search(expr):
        return [Finding(
            rule_id="DAX-010",
            category="dax",
            severity="info",
            message="DAX-010",
            location=loc,
        )]
    return []


def _check_dax011(expr: str, loc: str) -> list[Finding]:
    """DAX-011: Division without DIVIDE()."""
    # Check for / operator but not // (comments) or inside strings
    has_division = bool(re.search(r'(?<!/)/(?!/)', expr))
    has_divide_func = bool(re.search(r'(?i)\bDIVIDE\s*\(', expr))

    if has_division and not has_divide_func:
        return [Finding(
            rule_id="DAX-011",
            category="dax",
            severity="warning",
            message="DAX-011",
            location=loc,
        )]
    return []
