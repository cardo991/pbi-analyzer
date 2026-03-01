"""Naming convention checker for tables, columns, and measures."""

import re
from models import SemanticModel, Finding


def analyze_naming(model: SemanticModel, convention: str = "title_case") -> list[Finding]:
    """Check naming conventions across the model.

    Args:
        model: Parsed semantic model
        convention: "title_case" (default), "camelCase", "snake_case", or "none"

    Rules:
        NC-001: Measure naming convention violation
        NC-002: Column naming inconsistency within a table
        NC-003: Table name with special characters or starting with digits
    """
    findings = []

    if convention == "none":
        return findings

    skip_prefixes = ("DateTableTemplate", "LocalDateTable")

    for table in model.tables:
        if table.name.startswith(skip_prefixes):
            continue

        # NC-003: Table name issues
        if _has_special_chars(table.name):
            findings.append(Finding(
                rule_id="NC-003",
                category="data_model",
                severity="info",
                message="",
                location=f"Table '{table.name}'",
                details={"table": table.name},
            ))

        # NC-001: Measure naming
        for measure in table.measures:
            # Skip hidden measures (convention: prefixed with _)
            if measure.is_hidden or measure.name.startswith("_"):
                continue
            if not _matches_convention(measure.name, convention):
                findings.append(Finding(
                    rule_id="NC-001",
                    category="data_model",
                    severity="info",
                    message="",
                    location=f"Table '{table.name}', Measure '{measure.name}'",
                    details={"name": measure.name, "convention": convention},
                ))

        # NC-002: Column naming inconsistency
        if len(table.columns) >= 3:
            inconsistencies = _check_column_consistency(table.columns)
            if inconsistencies:
                for col_name in inconsistencies[:3]:  # Limit to 3 per table
                    findings.append(Finding(
                        rule_id="NC-002",
                        category="data_model",
                        severity="info",
                        message="",
                        location=f"Table '{table.name}', Column '{col_name}'",
                        details={"col": col_name, "table": table.name},
                    ))

    return findings


def _has_special_chars(name: str) -> bool:
    """Check if name has problematic characters."""
    if not name:
        return False
    # Starts with digit
    if name[0].isdigit():
        return True
    # Contains special chars (allow spaces, underscores, letters, digits)
    if re.search(r"[#@$%^&*!~`+=\[\]{}|\\/<>]", name):
        return True
    # Double spaces
    if "  " in name:
        return True
    # Leading/trailing spaces
    if name != name.strip():
        return True
    return False


def _matches_convention(name: str, convention: str) -> bool:
    """Check if a name matches the chosen convention."""
    name = name.strip()
    if not name:
        return True

    if convention == "title_case":
        # Title Case: each word starts with uppercase, allows spaces
        # e.g., "Total Sales", "Year Over Year Growth"
        words = name.split()
        if not words:
            return True
        # Check first word starts with uppercase
        if not words[0][0].isupper():
            return False
        # Leading/trailing spaces
        if name != name.strip():
            return False
        # ALL_CAPS is not title case
        if name == name.upper() and len(name) > 3:
            return False
        return True

    elif convention == "camelCase":
        # camelCase: starts with lowercase, no spaces
        if " " in name:
            return False
        if not name[0].islower():
            return False
        return True

    elif convention == "snake_case":
        # snake_case: lowercase with underscores
        return bool(re.match(r"^[a-z][a-z0-9_]*$", name))

    return True


def _check_column_consistency(columns) -> list[str]:
    """Find columns with inconsistent naming within a table.

    Detects mixed patterns: some with spaces, some camelCase, some PascalCase.
    """
    has_spaces = []
    has_camel = []
    has_pascal = []

    for col in columns:
        name = col.name
        # Skip RowNumber and auto columns
        if col.column_type == "rowNumber" or name.startswith("RowNumber"):
            continue

        if " " in name:
            has_spaces.append(name)
        elif name[0].islower() and any(c.isupper() for c in name[1:]):
            has_camel.append(name)
        elif name[0].isupper() and "_" not in name:
            has_pascal.append(name)

    # If there are multiple patterns, flag the minority pattern
    patterns = [(has_spaces, "spaces"), (has_camel, "camelCase"), (has_pascal, "PascalCase")]
    patterns.sort(key=lambda x: len(x[0]), reverse=True)

    # Only flag if there are at least 2 different patterns with >0 members
    active_patterns = [p for p in patterns if len(p[0]) > 0]
    if len(active_patterns) < 2:
        return []

    # Return columns from minority patterns
    minority = []
    for names, _ in active_patterns[1:]:
        minority.extend(names)

    return minority
