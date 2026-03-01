"""Power Query (M) analysis rules (PQ-001 through PQ-007)."""

import re
from models import SemanticModel, Finding
from config import (
    MAX_STEPS_PER_QUERY, FOLDING_BREAKERS, DATA_SOURCE_FUNCTIONS,
)


def analyze_power_query(model: SemanticModel) -> list[Finding]:
    """Run all Power Query rules against the semantic model."""
    findings = []

    # Collect all M expressions from partitions and shared expressions
    queries = []
    for table in model.tables:
        for p in table.partitions:
            if p.source_type == "m" and p.expression:
                queries.append((table.name, p.name, p.expression))

    for expr_obj in model.expressions:
        if expr_obj.expression:
            queries.append(("(Shared)", expr_obj.name, expr_obj.expression))

    for table_name, query_name, m_code in queries:
        loc = f"Table '{table_name}', Query '{query_name}'"

        findings.extend(_check_pq001(m_code, loc))
        findings.extend(_check_pq002(m_code, loc))
        findings.extend(_check_pq003(m_code, loc))
        findings.extend(_check_pq004(m_code, loc))
        findings.extend(_check_pq005(m_code, loc))
        findings.extend(_check_pq006(m_code, loc, table_name))
        findings.extend(_check_pq007(m_code, loc))

    return findings


def _check_pq001(m_code: str, loc: str) -> list[Finding]:
    """PQ-001: Operations that break query folding."""
    results = []
    for func in FOLDING_BREAKERS:
        escaped = re.escape(func)
        if re.search(escaped + r'\s*\(', m_code):
            results.append(Finding(
                rule_id="PQ-001",
                category="power_query",
                severity="warning",
                message="PQ-001",
                location=loc,
                details={"func": func},
            ))
    return results


def _check_pq002(m_code: str, loc: str) -> list[Finding]:
    """PQ-002: Table.Buffer usage."""
    if re.search(r'Table\.Buffer\s*\(', m_code):
        return [Finding(
            rule_id="PQ-002",
            category="power_query",
            severity="warning",
            message="PQ-002",
            location=loc,
        )]
    return []


def _check_pq003(m_code: str, loc: str) -> list[Finding]:
    """PQ-003: Sort before filter."""
    sort_pos = _find_func_position(m_code, "Table.Sort")
    filter_pos = _find_func_position(m_code, "Table.SelectRows")

    if sort_pos is not None and filter_pos is not None and sort_pos < filter_pos:
        return [Finding(
            rule_id="PQ-003",
            category="power_query",
            severity="info",
            message="PQ-003",
            location=loc,
        )]
    return []


def _check_pq004(m_code: str, loc: str) -> list[Finding]:
    """PQ-004: Hardcoded connection values."""
    patterns = [
        (r'Sql\.Database\s*\(\s*"[^"]+"', "Sql.Database"),
        (r'Sql\.Databases\s*\(\s*"[^"]+"', "Sql.Databases"),
        (r'File\.Contents\s*\(\s*"[^"]+"', "File.Contents"),
        (r'Web\.Contents\s*\(\s*"[^"]+"', "Web.Contents"),
        (r'OleDb\.DataSource\s*\(\s*"[^"]+"', "OleDb.DataSource"),
        (r'Odbc\.DataSource\s*\(\s*"[^"]+"', "Odbc.DataSource"),
        (r'Excel\.Workbook\s*\(\s*File\.Contents\s*\(\s*"[^"]+"', "Excel.Workbook"),
    ]

    for pattern, func_name in patterns:
        if re.search(pattern, m_code):
            return [Finding(
                rule_id="PQ-004",
                category="power_query",
                severity="warning",
                message="PQ-004",
                location=loc,
                details={"func": func_name},
            )]
    return []


def _check_pq005(m_code: str, loc: str) -> list[Finding]:
    """PQ-005: Excessive step count."""
    # Count steps in a let..in block
    let_match = re.search(r'(?i)\blet\b', m_code)
    in_match = re.search(r'(?i)\bin\b(?!\s*")', m_code)

    if let_match and in_match:
        let_body = m_code[let_match.end():in_match.start()]
        # Count assignments (lines with = outside of string literals)
        steps = re.findall(r'^\s*[\w#"]+[^=]*=\s*', let_body, re.MULTILINE)
        count = len(steps)
        if count > MAX_STEPS_PER_QUERY:
            return [Finding(
                rule_id="PQ-005",
                category="power_query",
                severity="info",
                message="PQ-005",
                location=loc,
                details={"count": count, "threshold": MAX_STEPS_PER_QUERY},
            )]
    return []


def _check_pq006(m_code: str, loc: str, table_name: str) -> list[Finding]:
    """PQ-006: Data source type detection."""
    results = []
    detected = set()
    for func, source_name in DATA_SOURCE_FUNCTIONS.items():
        escaped = re.escape(func)
        if re.search(escaped, m_code) and source_name not in detected:
            detected.add(source_name)
            results.append(Finding(
                rule_id="PQ-006",
                category="power_query",
                severity="info",
                message="PQ-006",
                location=loc,
                details={"source": source_name},
            ))
    return results


def _check_pq007(m_code: str, loc: str) -> list[Finding]:
    """PQ-007: Multiple type conversion steps."""
    count = len(re.findall(r'Table\.TransformColumnTypes', m_code))
    if count > 1:
        return [Finding(
            rule_id="PQ-007",
            category="power_query",
            severity="info",
            message="PQ-007",
            location=loc,
            details={"count": count},
        )]
    return []


def _find_func_position(m_code: str, func_name: str) -> int | None:
    """Find the first position of a function call in M code."""
    match = re.search(re.escape(func_name) + r'\s*\(', m_code)
    return match.start() if match else None
