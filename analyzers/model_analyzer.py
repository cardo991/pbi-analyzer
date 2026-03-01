"""Data model analysis rules (DM-001 through DM-010)."""

import re
from models import SemanticModel, Finding
from config import DATE_TABLE_PATTERNS, AGGREGATION_FUNCTIONS


def analyze_model(model: SemanticModel) -> list[Finding]:
    """Run all data model rules against the semantic model."""
    findings = []

    findings.extend(_check_dm001(model))
    findings.extend(_check_dm002(model))
    findings.extend(_check_dm003(model))
    findings.extend(_check_dm004(model))
    findings.extend(_check_dm005(model))
    findings.extend(_check_dm006(model))
    findings.extend(_check_dm007(model))
    findings.extend(_check_dm008(model))
    findings.extend(_check_dm009(model))
    findings.extend(_check_dm010(model))

    return findings


def _check_dm001(model: SemanticModel) -> list[Finding]:
    """DM-001: Bidirectional cross-filtering."""
    results = []
    for r in model.relationships:
        if r.cross_filtering.lower() in ("bothdirections", "both"):
            results.append(Finding(
                rule_id="DM-001",
                category="data_model",
                severity="warning",
                message="DM-001",
                location=f"Relationship: {r.from_table}[{r.from_column}] -> {r.to_table}[{r.to_column}]",
                details={"from_table": r.from_table, "to_table": r.to_table},
            ))
    return results


def _check_dm002(model: SemanticModel) -> list[Finding]:
    """DM-002: Many-to-many relationships."""
    results = []
    for r in model.relationships:
        if r.from_cardinality == "many" and r.to_cardinality == "many":
            results.append(Finding(
                rule_id="DM-002",
                category="data_model",
                severity="warning",
                message="DM-002",
                location=f"Relationship: {r.from_table} <-> {r.to_table}",
                details={"from_table": r.from_table, "to_table": r.to_table},
            ))
    return results


def _check_dm003(model: SemanticModel) -> list[Finding]:
    """DM-003: Disconnected/orphan tables."""
    connected_tables = set()
    for r in model.relationships:
        connected_tables.add(r.from_table)
        connected_tables.add(r.to_table)

    results = []
    for table in model.tables:
        # Skip auto date tables and hidden tables with no visible columns
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        if _is_auto_date_table(table):
            continue

        if table.name not in connected_tables:
            results.append(Finding(
                rule_id="DM-003",
                category="data_model",
                severity="warning",
                message="DM-003",
                location=f"Table '{table.name}'",
                details={"table": table.name},
            ))
    return results


def _check_dm004(model: SemanticModel) -> list[Finding]:
    """DM-004: Missing dedicated date table."""
    for table in model.tables:
        name_lower = table.name.lower().strip()
        # Check name patterns
        for pattern in DATE_TABLE_PATTERNS:
            if name_lower == pattern or name_lower.startswith(pattern):
                return []

        # Check if any column is marked as date key
        for col in table.columns:
            if col.is_key and col.data_type in ("dateTime", "date"):
                return []

    return [Finding(
        rule_id="DM-004",
        category="data_model",
        severity="warning",
        message="DM-004",
        location="Model",
    )]


def _check_dm005(model: SemanticModel) -> list[Finding]:
    """DM-005: Calculated columns using aggregation functions."""
    results = []
    agg_pattern = re.compile(
        r'(?i)\b(' + '|'.join(AGGREGATION_FUNCTIONS) + r')\s*\('
    )

    for table in model.tables:
        for col in table.columns:
            if col.column_type == "calculated" and col.expression:
                match = agg_pattern.search(col.expression)
                if match:
                    results.append(Finding(
                        rule_id="DM-005",
                        category="data_model",
                        severity="error",
                        message="DM-005",
                        location=f"Table '{table.name}', Column '{col.name}'",
                        details={
                            "table": table.name,
                            "column": col.name,
                            "func": match.group(1).upper(),
                        },
                    ))
    return results


def _check_dm006(model: SemanticModel) -> list[Finding]:
    """DM-006: Snowflake schema detection (chained dimension tables)."""
    # Build relationship graph
    # Fact tables: appear on "many" side
    # Dimension tables: appear on "one" side
    many_side = set()  # Tables on many side (fact candidates)
    one_side = set()   # Tables on one side (dimension candidates)

    for r in model.relationships:
        if r.from_cardinality == "many":
            many_side.add(r.from_table)
        if r.to_cardinality == "one":
            one_side.add(r.to_table)

    # A dimension is in a snowflake if it's on the many side of another relationship
    # (i.e., it's both a dimension and references another dimension)
    snowflake_tables = many_side & one_side

    # Filter out fact tables (tables that have partitions with real data)
    results = []
    for table_name in snowflake_tables:
        # Only flag if this table is a lookup target for a fact table
        # and also references another dimension
        results.append(Finding(
            rule_id="DM-006",
            category="data_model",
            severity="info",
            message="DM-006",
            location=f"Table '{table_name}'",
            details={"table": table_name},
        ))

    return results


def _check_dm007(model: SemanticModel) -> list[Finding]:
    """DM-007: High cardinality columns."""
    # Identify fact tables (many-side)
    fact_tables = set()
    for r in model.relationships:
        if r.from_cardinality == "many":
            fact_tables.add(r.from_table)

    high_card_pattern = re.compile(
        r'(?i)(id|key|guid|uuid|url|uri|path|description|comment|note|address|email|phone|detail)$'
    )

    # Columns used in relationships
    rel_columns = set()
    for r in model.relationships:
        rel_columns.add((r.from_table, r.from_column))
        rel_columns.add((r.to_table, r.to_column))

    results = []
    for table in model.tables:
        if table.name not in fact_tables:
            continue
        for col in table.columns:
            if col.data_type == "string" and col.column_type == "data":
                if (table.name, col.name) not in rel_columns:
                    if high_card_pattern.search(col.name):
                        results.append(Finding(
                            rule_id="DM-007",
                            category="data_model",
                            severity="info",
                            message="DM-007",
                            location=f"Column '{table.name}[{col.name}]'",
                            details={"table": table.name, "column": col.name},
                        ))
    return results


def _check_dm008(model: SemanticModel) -> list[Finding]:
    """DM-008: Mixed storage modes."""
    modes = set()
    tables_by_mode = {}

    for table in model.tables:
        for p in table.partitions:
            mode = p.mode.lower()
            modes.add(mode)
            tables_by_mode.setdefault(mode, []).append(table.name)

    if len(modes) > 1:
        mode_summary = ", ".join(sorted(modes))
        return [Finding(
            rule_id="DM-008",
            category="data_model",
            severity="info",
            message="DM-008",
            location="Model",
            details={"modes": mode_summary},
        )]
    return []


def _check_dm009(model: SemanticModel) -> list[Finding]:
    """DM-009: Inactive relationships (check if referenced by USERELATIONSHIP)."""
    # Collect all DAX expressions
    all_dax = ""
    for table in model.tables:
        for m in table.measures:
            all_dax += " " + m.expression
        for c in table.columns:
            if c.expression:
                all_dax += " " + c.expression

    results = []
    for r in model.relationships:
        if not r.is_active:
            # Check if USERELATIONSHIP references these columns
            pattern = re.compile(
                r'(?i)\bUSERELATIONSHIP\s*\(.*?' +
                re.escape(r.from_column) + r'.*?' +
                re.escape(r.to_column),
                re.DOTALL,
            )
            pattern2 = re.compile(
                r'(?i)\bUSERELATIONSHIP\s*\(.*?' +
                re.escape(r.to_column) + r'.*?' +
                re.escape(r.from_column),
                re.DOTALL,
            )
            is_used = bool(pattern.search(all_dax) or pattern2.search(all_dax))

            note = ("Used via USERELATIONSHIP" if is_used
                    else "Not referenced by any USERELATIONSHIP - consider removing")
            severity = "info" if is_used else "warning"

            results.append(Finding(
                rule_id="DM-009",
                category="data_model",
                severity=severity,
                message="DM-009",
                location=f"Relationship: {r.from_table}[{r.from_column}] -> {r.to_table}[{r.to_column}]",
                details={
                    "from_table": r.from_table,
                    "from_col": r.from_column,
                    "to_table": r.to_table,
                    "to_col": r.to_column,
                    "note": note,
                },
            ))
    return results


def _check_dm010(model: SemanticModel) -> list[Finding]:
    """DM-010: Fact table without measures."""
    fact_tables = set()
    for r in model.relationships:
        if r.from_cardinality == "many":
            fact_tables.add(r.from_table)

    results = []
    for table in model.tables:
        if table.name in fact_tables and not table.measures:
            results.append(Finding(
                rule_id="DM-010",
                category="data_model",
                severity="info",
                message="DM-010",
                location=f"Table '{table.name}'",
                details={"table": table.name},
            ))
    return results


def _is_auto_date_table(table) -> bool:
    """Check if a table is an auto-generated date table."""
    name = table.name
    if name.startswith("DateTableTemplate") or name.startswith("LocalDateTable"):
        return True
    # Check annotations if available
    return False
