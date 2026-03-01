"""Security and data exposure audit analyzer."""

import re
from models import SemanticModel, ReportDefinition, Finding

# Sensitive column name patterns
SENSITIVE_PATTERNS = {
    "email": re.compile(r"(?i)\b(e[-_]?mail|correo|email.?address)\b"),
    "ssn": re.compile(r"(?i)\b(ssn|social.?security|nss|cpf|dni|nif|rut)\b"),
    "phone": re.compile(r"(?i)\b(phone|tel[eé]fono|celular|mobile|fax)\b"),
    "credit_card": re.compile(r"(?i)\b(credit.?card|card.?number|tarjeta|cc.?num)\b"),
    "password": re.compile(r"(?i)\b(password|contrase[ñn]a|pwd|passwd|secret|token|api.?key)\b"),
    "address": re.compile(r"(?i)\b(address|direcci[oó]n|street|domicilio|zip.?code|postal)\b"),
}

# Credential patterns in M expressions
CREDENTIAL_PATTERNS = re.compile(
    r"(?i)(password\s*=|pwd\s*=|secret\s*=|token\s*=|apikey\s*=|api_key\s*=|"
    r"authorization\s*=|credentials?\s*=)",
)

# HTTP (non-HTTPS) connection pattern
HTTP_PATTERN = re.compile(r"\"http://[^\"]+\"", re.IGNORECASE)


def analyze_security(model: SemanticModel, report: ReportDefinition) -> list[Finding]:
    """Audit security and data exposure risks.

    Rules:
        SEC-004: Sensitive column not hidden
        SEC-005: HTTP (not HTTPS) data source
        SEC-006: Credentials in M expression
        SEC-007: Table exposed without filtering
    """
    findings = []

    skip_prefixes = ("DateTableTemplate", "LocalDateTable")

    # --- SEC-004: Sensitive columns not hidden ---
    for table in model.tables:
        if table.name.startswith(skip_prefixes) or table.is_hidden:
            continue
        for col in table.columns:
            if col.is_hidden or col.column_type == "rowNumber":
                continue
            for data_type, pattern in SENSITIVE_PATTERNS.items():
                if pattern.search(col.name):
                    findings.append(Finding(
                        rule_id="SEC-004",
                        category="data_model",
                        severity="error",
                        message="",
                        location=f"Table '{table.name}', Column '{col.name}'",
                        details={
                            "table": table.name,
                            "col": col.name,
                            "type": data_type,
                        },
                    ))
                    break  # One match per column is enough

    # --- SEC-005 & SEC-006: M expression analysis ---
    for table in model.tables:
        if table.name.startswith(skip_prefixes):
            continue
        for partition in table.partitions:
            expr = partition.expression
            if not expr:
                continue

            # SEC-005: HTTP connections
            if HTTP_PATTERN.search(expr):
                findings.append(Finding(
                    rule_id="SEC-005",
                    category="data_model",
                    severity="warning",
                    message="",
                    location=f"Table '{table.name}'",
                    details={"table": table.name},
                ))

            # SEC-006: Credential patterns
            if CREDENTIAL_PATTERNS.search(expr):
                findings.append(Finding(
                    rule_id="SEC-006",
                    category="data_model",
                    severity="warning",
                    message="",
                    location=f"Table '{table.name}'",
                    details={"table": table.name},
                ))

    # Also check shared expressions
    for expression in model.expressions:
        expr = expression.expression
        if not expr:
            continue
        if HTTP_PATTERN.search(expr):
            findings.append(Finding(
                rule_id="SEC-005",
                category="data_model",
                severity="warning",
                message="",
                location=f"Expression '{expression.name}'",
                details={"table": expression.name},
            ))
        if CREDENTIAL_PATTERNS.search(expr):
            findings.append(Finding(
                rule_id="SEC-006",
                category="data_model",
                severity="warning",
                message="",
                location=f"Expression '{expression.name}'",
                details={"table": expression.name},
            ))

    # --- SEC-007: Tables exposed without filtering ---
    # Collect tables used in visuals
    visual_tables = set()
    for page in report.pages:
        for visual in page.visuals:
            for ref in visual.field_references:
                # field_references may contain table.column or just measure names
                visual_tables.add(ref)

    # Collect tables with RLS
    rls_tables = set()
    for role in model.roles:
        for tname, expr in role.table_permissions.items():
            if expr and expr.strip():
                rls_tables.add(tname)

    # Collect tables covered by page/report filters
    filtered_tables = set()
    # Report-level filters
    for f in report.filters:
        _extract_filter_tables(f, filtered_tables)
    # Page-level filters
    for page in report.pages:
        for f in page.filters:
            _extract_filter_tables(f, filtered_tables)

    # Check tables that have data (partitions) but no filtering
    for table in model.tables:
        if table.name.startswith(skip_prefixes) or table.is_hidden:
            continue
        if not table.partitions:
            continue
        # Only flag if table has actual data (not calculated)
        has_data = any(p.source_type == "m" for p in table.partitions)
        if not has_data:
            continue
        if table.name not in rls_tables and table.name not in filtered_tables:
            # Check if this table is actually used in visuals
            # (only warn about tables that are visible)
            table_in_use = any(
                table.name.lower() in ref.lower()
                for ref in visual_tables
            ) if visual_tables else True

            if table_in_use or not visual_tables:
                findings.append(Finding(
                    rule_id="SEC-007",
                    category="data_model",
                    severity="info",
                    message="",
                    location=f"Table '{table.name}'",
                    details={"table": table.name},
                ))

    return findings


def _extract_filter_tables(filter_def, tables_set: set):
    """Extract table names from a filter definition."""
    if isinstance(filter_def, dict):
        # Look for table references in filter
        target = filter_def.get("target", {})
        if isinstance(target, dict):
            table = target.get("table", "")
            if table:
                tables_set.add(table)
        # Recurse into nested structures
        for v in filter_def.values():
            if isinstance(v, (dict, list)):
                _extract_filter_tables(v, tables_set)
    elif isinstance(filter_def, list):
        for item in filter_def:
            _extract_filter_tables(item, tables_set)
