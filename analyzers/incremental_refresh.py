"""Incremental refresh detection analyzer."""

from models import SemanticModel, Finding

# Source types that benefit from incremental refresh
_IR_ELIGIBLE_SOURCES = {
    "Sql.Database", "Sql.Databases", "Oracle.Database",
    "PostgreSQL.Database", "MySQL.Database", "Snowflake.Databases",
    "GoogleBigQuery.Database", "AnalysisServices.Database",
    "OData.Feed", "Web.Contents", "Odbc.DataSource", "OleDb.DataSource",
}

_DATE_TYPES = {"dateTime", "date", "datetime", "DateTime", "Date"}


def analyze_incremental_refresh(model: SemanticModel, lang: str = "en",
                                disabled_rules: set = None,
                                t=None) -> list[Finding]:
    """Detect incremental refresh configuration issues.

    Rules:
        IR-001: Large/eligible table without incremental refresh
        IR-002: IR configured but no date/datetime column
        IR-003: IR partition key column is not date type
    """
    disabled = disabled_rules or set()
    findings = []

    # Check if RangeStart/RangeEnd parameters exist (IR prerequisites)
    has_range_params = any(
        e.name in ("RangeStart", "RangeEnd") for e in model.expressions
    )

    for table in model.tables:
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue

        has_ir = bool(table.refresh_policy)

        # Determine if table is eligible for IR (has DB source)
        is_eligible = False
        for p in table.partitions:
            for source_func in _IR_ELIGIBLE_SOURCES:
                if source_func in p.expression:
                    is_eligible = True
                    break

        # IR-001: Eligible table without IR
        if "IR-001" not in disabled and is_eligible and not has_ir and not has_range_params:
            msg = t("IR-001", table=table.name) if t else (
                f"Table '{table.name}' uses a database source but has no incremental "
                f"refresh configured. Consider enabling IR for faster refreshes."
            )
            findings.append(Finding(
                rule_id="IR-001",
                category="data_model",
                severity="info",
                message=msg,
                location=f"Table '{table.name}'",
            ))

        # For tables WITH IR configured, validate the setup
        if has_ir:
            date_cols = [c for c in table.columns if c.data_type in _DATE_TYPES]

            # IR-002: No date column
            if "IR-002" not in disabled and not date_cols:
                msg = t("IR-002", table=table.name) if t else (
                    f"Table '{table.name}' has incremental refresh configured but "
                    f"no date/datetime column was found. IR requires a date column."
                )
                findings.append(Finding(
                    rule_id="IR-002",
                    category="data_model",
                    severity="warning",
                    message=msg,
                    location=f"Table '{table.name}'",
                ))

            # IR-003: Check if any partition key uses non-date type
            if "IR-003" not in disabled and table.refresh_policy.get("sourceExpression"):
                # sourceExpression may reference a column; check if it's date type
                source_expr = str(table.refresh_policy.get("sourceExpression", ""))
                for col in table.columns:
                    if col.name in source_expr and col.data_type not in _DATE_TYPES:
                        msg = t("IR-003", table=table.name, column=col.name) if t else (
                            f"Incremental refresh on '{table.name}' references column "
                            f"'{col.name}' which is type '{col.data_type}', not a date type."
                        )
                        findings.append(Finding(
                            rule_id="IR-003",
                            category="data_model",
                            severity="warning",
                            message=msg,
                            location=f"Table '{table.name}', Column '{col.name}'",
                        ))
                        break

    return findings
