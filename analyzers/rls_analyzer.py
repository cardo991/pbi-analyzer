"""Row-Level Security (RLS) analyzer."""

import re
from models import SemanticModel, Finding

# Expensive DAX functions in RLS filters
EXPENSIVE_RLS_FUNCTIONS = [
    "LOOKUPVALUE", "PATHCONTAINS", "PATHITEM", "PATHITEMREVERSE",
    "EARLIER", "EARLIEST", "USERELATIONSHIP", "CROSSFILTER",
    "CALCULATETABLE", "SUMMARIZE",
]


def analyze_rls(model: SemanticModel) -> list[Finding]:
    """Analyze Row-Level Security configuration.

    Rules:
        SEC-001: Tables without RLS when other tables are protected
        SEC-002: Empty role (no table permissions)
        SEC-003: Expensive DAX functions in RLS filters
    """
    findings = []

    if not model.roles:
        return findings

    # SEC-002: Empty roles
    for role in model.roles:
        if not role.table_permissions:
            findings.append(Finding(
                rule_id="SEC-002",
                category="data_model",
                severity="warning",
                message="",
                location=f"Role '{role.name}'",
                details={"role": role.name},
            ))

    # Collect tables that have RLS filters
    protected_tables = set()
    for role in model.roles:
        for table_name in role.table_permissions:
            if role.table_permissions[table_name].strip():
                protected_tables.add(table_name)

    if not protected_tables:
        return findings

    # SEC-001: Tables in relationships with protected tables but not protected themselves
    # Build set of tables connected to protected tables
    related_tables = set()
    for rel in model.relationships:
        if rel.from_table in protected_tables:
            related_tables.add(rel.to_table)
        if rel.to_table in protected_tables:
            related_tables.add(rel.from_table)

    # Skip auto-generated tables
    skip_prefixes = ("DateTableTemplate", "LocalDateTable")
    model_table_names = {
        t.name for t in model.tables
        if not t.name.startswith(skip_prefixes) and not t.is_hidden
    }

    unprotected = (model_table_names & related_tables) - protected_tables
    for table_name in sorted(unprotected):
        findings.append(Finding(
            rule_id="SEC-001",
            category="data_model",
            severity="warning",
            message="",
            location=f"Table '{table_name}'",
            details={"table": table_name, "count": len(protected_tables)},
        ))

    # SEC-003: Expensive functions in RLS expressions
    pattern = re.compile(
        r"\b(" + "|".join(EXPENSIVE_RLS_FUNCTIONS) + r")\b",
        re.IGNORECASE,
    )
    for role in model.roles:
        for table_name, expr in role.table_permissions.items():
            if not expr:
                continue
            match = pattern.search(expr)
            if match:
                findings.append(Finding(
                    rule_id="SEC-003",
                    category="data_model",
                    severity="info",
                    message="",
                    location=f"Role '{role.name}', Table '{table_name}'",
                    details={"table": table_name, "func": match.group(1), "role": role.name},
                ))

    return findings
