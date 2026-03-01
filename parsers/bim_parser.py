"""Parser for model.bim (TMSL/JSON) files."""

import json
from models import (
    SemanticModel, Table, Column, Measure, Partition,
    Relationship, Expression, Role,
)


def parse_bim(bim_path: str) -> SemanticModel:
    """Parse a model.bim JSON file into a SemanticModel."""
    with open(bim_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    model_data = data.get("model", data)

    sm = SemanticModel(
        culture=model_data.get("culture", "en-US"),
        default_mode=model_data.get("defaultMode", "import"),
    )

    # Parse tables
    for t in model_data.get("tables", []):
        table = Table(
            name=t.get("name", ""),
            is_hidden=t.get("isHidden", False),
            description=t.get("description", ""),
            data_category=t.get("dataCategory", ""),
        )

        # Parse columns
        for c in t.get("columns", []):
            col = Column(
                name=c.get("name", ""),
                data_type=c.get("dataType", "string"),
                source_column=c.get("sourceColumn", ""),
                column_type=c.get("type", "data"),
                expression=_join_expression(c.get("expression", "")),
                is_hidden=c.get("isHidden", False),
                is_key=c.get("isKey", False),
                format_string=c.get("formatString", ""),
                description=c.get("description", ""),
                display_folder=c.get("displayFolder", ""),
                summarize_by=c.get("summarizeBy", "default"),
                sort_by_column=c.get("sortByColumn", ""),
            )
            table.columns.append(col)

        # Parse measures
        for m in t.get("measures", []):
            measure = Measure(
                name=m.get("name", ""),
                table_name=t.get("name", ""),
                expression=_join_expression(m.get("expression", "")),
                format_string=m.get("formatString", ""),
                description=m.get("description", ""),
                display_folder=m.get("displayFolder", ""),
                is_hidden=m.get("isHidden", False),
            )
            table.measures.append(measure)

        # Parse partitions
        for p in t.get("partitions", []):
            source = p.get("source", {})
            partition = Partition(
                name=p.get("name", ""),
                mode=p.get("mode", "import"),
                source_type=source.get("type", "m"),
                expression=_join_expression(source.get("expression", "")),
            )
            table.partitions.append(partition)

        sm.tables.append(table)

    # Parse relationships
    for r in model_data.get("relationships", []):
        rel = Relationship(
            name=r.get("name", ""),
            from_table=r.get("fromTable", ""),
            from_column=r.get("fromColumn", ""),
            to_table=r.get("toTable", ""),
            to_column=r.get("toColumn", ""),
            from_cardinality=r.get("fromCardinality", "many"),
            to_cardinality=r.get("toCardinality", "one"),
            cross_filtering=r.get("crossFilteringBehavior", "oneDirection"),
            is_active=r.get("isActive", True),
        )
        sm.relationships.append(rel)

    # Parse expressions (shared/parameters)
    for e in model_data.get("expressions", []):
        expr = Expression(
            name=e.get("name", ""),
            expression=_join_expression(e.get("expression", "")),
            description=e.get("description", ""),
        )
        sm.expressions.append(expr)

    # Parse roles
    for r in model_data.get("roles", []):
        permissions = {}
        for tp in r.get("tablePermissions", []):
            permissions[tp.get("name", "")] = tp.get("filterExpression", "")
        role = Role(
            name=r.get("name", ""),
            table_permissions=permissions,
        )
        sm.roles.append(role)

    return sm


def _join_expression(expr) -> str:
    """Join expression that may be a string or list of strings."""
    if isinstance(expr, list):
        return "\n".join(expr)
    return str(expr) if expr else ""
