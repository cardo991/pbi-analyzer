"""Performance score estimator for Power BI models."""

import re
from models import SemanticModel, Finding
from config import GRADE_BOUNDARIES, AGGREGATION_FUNCTIONS


def analyze_performance(model: SemanticModel) -> dict:
    """Estimate performance characteristics of the model.

    Returns a dict with:
        perf_score: float (0-100)
        perf_grade: str (A-F)
        findings: list[Finding]
        details: dict with performance metrics

    Rules:
        PERF-001: Not a star schema (dimension-to-dimension relationships)
        PERF-002: Too many bidirectional relationships (>2)
        PERF-003: Too many columns per table (>100)
        PERF-004: Calculated column should be a measure (aggregates other tables)
        PERF-005: DirectQuery mixed with Import
    """
    findings = []

    skip_prefixes = ("DateTableTemplate", "LocalDateTable")
    real_tables = [t for t in model.tables if not t.name.startswith(skip_prefixes)]

    # Track details
    details = {
        "is_star_schema": True,
        "bidir_count": 0,
        "avg_columns_per_table": 0.0,
        "directquery_tables": 0,
        "import_tables": 0,
        "calc_columns_as_measures": 0,
    }

    # --- Analyze relationships ---
    bidir_count = 0
    # Build table relationship graph for star schema detection
    # In a star schema: fact table(s) at center, dimension tables connect to facts only
    # Dimension-to-dimension relationships break star schema
    one_side_tables = set()  # Tables on the "one" side (dimensions)
    many_side_tables = set()  # Tables on the "many" side (facts)

    for rel in model.relationships:
        if rel.cross_filtering == "bothDirections":
            bidir_count += 1

        # Track cardinality sides
        if rel.from_cardinality == "many":
            many_side_tables.add(rel.from_table)
            one_side_tables.add(rel.to_table)
        elif rel.to_cardinality == "many":
            many_side_tables.add(rel.to_table)
            one_side_tables.add(rel.from_table)

    details["bidir_count"] = bidir_count

    # PERF-002: Too many bidirectional relationships
    if bidir_count > 2:
        findings.append(Finding(
            rule_id="PERF-002",
            category="data_model",
            severity="warning",
            message="",
            location="Model relationships",
            details={"count": bidir_count},
        ))

    # PERF-001: Star schema check
    # Dimension tables that are also on the many-side (connecting to other dimensions)
    dim_on_many = one_side_tables & many_side_tables
    for table_name in sorted(dim_on_many):
        if table_name.startswith(skip_prefixes):
            continue
        details["is_star_schema"] = False
        findings.append(Finding(
            rule_id="PERF-001",
            category="data_model",
            severity="warning",
            message="",
            location=f"Table '{table_name}'",
            details={"table": table_name},
        ))

    # --- Analyze tables ---
    total_cols = 0
    storage_modes = {}

    for table in real_tables:
        col_count = len(table.columns)
        total_cols += col_count

        # PERF-003: Too many columns
        if col_count > 100:
            findings.append(Finding(
                rule_id="PERF-003",
                category="data_model",
                severity="info",
                message="",
                location=f"Table '{table.name}'",
                details={"table": table.name, "count": col_count},
            ))

        # Detect storage mode
        for p in table.partitions:
            mode = p.mode.lower()
            storage_modes.setdefault(mode, []).append(table.name)

        # PERF-004: Calculated columns that aggregate other tables
        for col in table.columns:
            if col.column_type == "calculated" and col.expression:
                expr_upper = col.expression.upper()
                # Check if references other tables via aggregation
                has_agg = any(fn in expr_upper for fn in AGGREGATION_FUNCTIONS)
                # Check for table references (Table[Column] pattern with different table)
                refs = re.findall(r"'?(\w+)'?\[", col.expression)
                references_other = any(
                    ref != table.name for ref in refs if ref
                )
                if has_agg and references_other:
                    details["calc_columns_as_measures"] += 1
                    findings.append(Finding(
                        rule_id="PERF-004",
                        category="dax",
                        severity="warning",
                        message="",
                        location=f"Table '{table.name}', Column '{col.name}'",
                        details={"col": col.name, "table": table.name},
                    ))

    # Average columns per table
    if real_tables:
        details["avg_columns_per_table"] = round(total_cols / len(real_tables), 1)

    # PERF-005: Mixed storage modes
    dq_tables = storage_modes.get("directquery", [])
    imp_tables = storage_modes.get("import", [])
    details["directquery_tables"] = len(dq_tables)
    details["import_tables"] = len(imp_tables)

    if dq_tables and imp_tables:
        for tname in dq_tables:
            findings.append(Finding(
                rule_id="PERF-005",
                category="data_model",
                severity="info",
                message="",
                location=f"Table '{tname}'",
                details={"table": tname, "count": len(imp_tables)},
            ))

    # --- Calculate performance score ---
    perf_score = 100.0

    # Deductions
    if not details["is_star_schema"]:
        perf_score -= 15
    perf_score -= min(bidir_count * 5, 20)
    perf_score -= min(details["calc_columns_as_measures"] * 3, 15)
    if details["directquery_tables"] > 0 and details["import_tables"] > 0:
        perf_score -= 10

    # High column count penalty
    high_col_tables = sum(1 for t in real_tables if len(t.columns) > 100)
    perf_score -= min(high_col_tables * 5, 15)

    perf_score = max(0.0, round(perf_score, 1))

    # Grade
    perf_grade = "F"
    for threshold, grade in GRADE_BOUNDARIES:
        if perf_score >= threshold:
            perf_grade = grade
            break

    return {
        "perf_score": perf_score,
        "perf_grade": perf_grade,
        "findings": findings,
        "details": details,
    }
