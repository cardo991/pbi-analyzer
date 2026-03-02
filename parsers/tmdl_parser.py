"""Parser for TMDL (Tabular Model Definition Language) files."""

import os
import re
from models import (
    SemanticModel, Table, Column, Measure, Partition,
    Relationship, Expression, Role,
)


def parse_tmdl(definition_dir: str) -> SemanticModel:
    """Parse a TMDL definition/ folder into a SemanticModel."""
    sm = SemanticModel()

    # Parse model.tmdl for model-level properties
    model_path = os.path.join(definition_dir, "model.tmdl")
    if os.path.exists(model_path):
        _parse_model_tmdl(model_path, sm)

    # Parse tables
    tables_dir = os.path.join(definition_dir, "tables")
    if os.path.isdir(tables_dir):
        for fname in os.listdir(tables_dir):
            if fname.endswith(".tmdl"):
                fpath = os.path.join(tables_dir, fname)
                table = _parse_table_tmdl(fpath)
                if table:
                    sm.tables.append(table)

    # Parse relationships
    rel_path = os.path.join(definition_dir, "relationships.tmdl")
    if os.path.exists(rel_path):
        sm.relationships = _parse_relationships_tmdl(rel_path)

    # Parse expressions
    expr_path = os.path.join(definition_dir, "expressions.tmdl")
    if os.path.exists(expr_path):
        sm.expressions = _parse_expressions_tmdl(expr_path)

    # Parse roles
    roles_dir = os.path.join(definition_dir, "roles")
    if os.path.isdir(roles_dir):
        for fname in os.listdir(roles_dir):
            if fname.endswith(".tmdl"):
                fpath = os.path.join(roles_dir, fname)
                role = _parse_role_tmdl(fpath)
                if role:
                    sm.roles.append(role)

    return sm


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def _unquote(name: str) -> str:
    """Remove surrounding single quotes from a TMDL name."""
    name = name.strip()
    if name.startswith("'") and name.endswith("'"):
        return name[1:-1].replace("''", "'")
    return name


def _parse_model_tmdl(path: str, sm: SemanticModel):
    """Extract model-level properties from model.tmdl."""
    content = _read_file(path)
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("culture:"):
            sm.culture = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("defaultMode:"):
            sm.default_mode = stripped.split(":", 1)[1].strip()


def _parse_table_tmdl(path: str) -> Table | None:
    """Parse a single table .tmdl file."""
    content = _read_file(path)
    lines = content.splitlines()
    if not lines:
        return None

    table = Table(name="")
    current_object = None  # 'column', 'measure', 'partition'
    current_column = None
    current_measure = None
    current_partition = None
    collecting_expression = False
    expression_lines = []
    expression_target = None  # 'measure', 'column', 'partition'
    in_backtick_block = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        raw_indent = len(line) - len(line.lstrip('\t'))

        # Handle triple-backtick blocks
        if stripped == "```":
            if in_backtick_block:
                in_backtick_block = False
                expr_text = "\n".join(expression_lines)
                _assign_expression(expr_text, expression_target,
                                   current_measure, current_column, current_partition)
                expression_lines = []
                collecting_expression = False
                expression_target = None
            else:
                in_backtick_block = True
                expression_lines = []
            continue

        if in_backtick_block:
            expression_lines.append(line)
            continue

        # Table declaration
        if stripped.startswith("table ") and raw_indent == 0:
            name = stripped[6:].strip()
            table.name = _unquote(name)
            continue

        # Description (///) on the line before an object
        if stripped.startswith("///"):
            continue

        # Column declaration
        col_match = re.match(r"^\tcolumn\s+(.+?)(?:\s*=\s*(.+))?$", line)
        if col_match:
            _flush_expression(expression_lines, expression_target,
                              current_measure, current_column, current_partition)
            expression_lines = []
            collecting_expression = False

            current_column = Column(name=_unquote(col_match.group(1)))
            current_object = "column"
            if col_match.group(2):
                current_column.column_type = "calculated"
                expr = col_match.group(2).strip()
                if expr:
                    collecting_expression = True
                    expression_target = "column"
                    expression_lines = [expr]
            table.columns.append(current_column)
            continue

        # Measure declaration
        meas_match = re.match(r"^\tmeasure\s+(.+?)\s*=\s*(.*)?$", line)
        if meas_match:
            _flush_expression(expression_lines, expression_target,
                              current_measure, current_column, current_partition)
            expression_lines = []

            current_measure = Measure(
                name=_unquote(meas_match.group(1)),
                table_name=table.name,
            )
            current_object = "measure"
            expr = (meas_match.group(2) or "").strip()
            if expr:
                collecting_expression = True
                expression_target = "measure"
                expression_lines = [expr]
            else:
                collecting_expression = True
                expression_target = "measure"
            table.measures.append(current_measure)
            continue

        # Partition declaration
        part_match = re.match(r"^\tpartition\s+(.+?)\s*=\s*(\w+)(.*)$", line)
        if part_match:
            _flush_expression(expression_lines, expression_target,
                              current_measure, current_column, current_partition)
            expression_lines = []
            collecting_expression = False

            current_partition = Partition(
                name=_unquote(part_match.group(1)),
                source_type=part_match.group(2).strip(),
            )
            current_object = "partition"
            table.partitions.append(current_partition)
            continue

        # Property lines (indented with tabs, contain ':')
        if raw_indent >= 2 and ":" in stripped and not collecting_expression:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            if current_object == "column" and current_column:
                _set_column_prop(current_column, key, val)
            elif current_object == "measure" and current_measure:
                _set_measure_prop(current_measure, key, val)
            elif current_object == "partition" and current_partition:
                _set_partition_prop(current_partition, key, val)
            continue

        # Boolean properties (just the name, no colon)
        if raw_indent >= 2 and stripped and ":" not in stripped and "=" not in stripped:
            if not collecting_expression or stripped.startswith("formatString"):
                if current_object == "column" and current_column:
                    if stripped == "isHidden":
                        current_column.is_hidden = True
                    elif stripped == "isKey":
                        current_column.is_key = True
                elif current_object == "measure" and current_measure:
                    if stripped == "isHidden":
                        current_measure.is_hidden = True
                continue

        # Source expression for partition
        source_match = re.match(r"^\t\tsource\s*=\s*$", line)
        if source_match and current_object == "partition" and current_partition:
            collecting_expression = True
            expression_target = "partition"
            expression_lines = []
            continue

        # Multi-line expression continuation
        if collecting_expression and raw_indent >= 2:
            # Check if this line is a property (key: value) that ends the expression
            if re.match(r"^\t\t\w+:", line) and not in_backtick_block:
                _flush_expression(expression_lines, expression_target,
                                  current_measure, current_column, current_partition)
                expression_lines = []
                collecting_expression = False
                expression_target = None
                # Re-process as property
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if current_object == "measure" and current_measure:
                    _set_measure_prop(current_measure, key, val)
                elif current_object == "column" and current_column:
                    _set_column_prop(current_column, key, val)
            else:
                expression_lines.append(stripped)
            continue

    # Flush any remaining expression
    _flush_expression(expression_lines, expression_target,
                      current_measure, current_column, current_partition)

    # Set table-level properties
    for line in lines:
        stripped = line.strip()
        if line.startswith("\t") and not line.startswith("\t\t"):
            if stripped.startswith("isHidden"):
                table.is_hidden = True
            if stripped.startswith("refreshPolicy"):
                table.refresh_policy = {"detected": True}

    return table


def _set_column_prop(col: Column, key: str, val: str):
    props = {
        "dataType": "data_type",
        "sourceColumn": "source_column",
        "formatString": "format_string",
        "description": "description",
        "displayFolder": "display_folder",
        "summarizeBy": "summarize_by",
        "sortByColumn": "sort_by_column",
    }
    if key in props:
        setattr(col, props[key], val)


def _set_measure_prop(m: Measure, key: str, val: str):
    props = {
        "formatString": "format_string",
        "description": "description",
        "displayFolder": "display_folder",
    }
    if key in props:
        setattr(m, props[key], val)


def _set_partition_prop(p: Partition, key: str, val: str):
    if key == "mode":
        p.mode = val


def _flush_expression(lines, target, measure, column, partition):
    if not lines or not target:
        return
    expr_text = "\n".join(lines).strip()
    _assign_expression(expr_text, target, measure, column, partition)


def _assign_expression(text, target, measure, column, partition):
    if not text:
        return
    if target == "measure" and measure:
        measure.expression = text
    elif target == "column" and column:
        column.expression = text
        column.column_type = "calculated"
    elif target == "partition" and partition:
        partition.expression = text


def _parse_relationships_tmdl(path: str) -> list[Relationship]:
    """Parse relationships.tmdl file."""
    content = _read_file(path)
    relationships = []
    current = None

    for line in content.splitlines():
        stripped = line.strip()

        if stripped.startswith("relationship "):
            if current:
                relationships.append(current)
            name = stripped[13:].strip()
            current = Relationship(name=_unquote(name))
            continue

        if current and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            if key == "fromColumn":
                # Format: Table.'Column' or Table.Column
                parts = val.split(".", 1)
                if len(parts) == 2:
                    current.from_table = _unquote(parts[0])
                    current.from_column = _unquote(parts[1])
            elif key == "toColumn":
                parts = val.split(".", 1)
                if len(parts) == 2:
                    current.to_table = _unquote(parts[0])
                    current.to_column = _unquote(parts[1])
            elif key == "fromCardinality":
                current.from_cardinality = val
            elif key == "toCardinality":
                current.to_cardinality = val
            elif key == "crossFilteringBehavior":
                current.cross_filtering = val

        if current and stripped == "isActive: false":
            current.is_active = False

    if current:
        relationships.append(current)

    return relationships


def _parse_expressions_tmdl(path: str) -> list[Expression]:
    """Parse expressions.tmdl for shared M expressions and parameters."""
    content = _read_file(path)
    expressions = []
    current = None
    expr_lines = []
    in_backtick = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped == "```":
            if in_backtick:
                in_backtick = False
                if current:
                    current.expression = "\n".join(expr_lines)
                expr_lines = []
            else:
                in_backtick = True
                expr_lines = []
            continue

        if in_backtick:
            expr_lines.append(line)
            continue

        expr_match = re.match(r"^expression\s+(.+?)(?:\s*=\s*(.*))?$", stripped)
        if expr_match:
            if current:
                expressions.append(current)
            name = _unquote(expr_match.group(1))
            inline_expr = (expr_match.group(2) or "").strip()
            current = Expression(name=name, expression=inline_expr)
            continue

        if current and stripped.startswith("description:"):
            current.description = stripped.split(":", 1)[1].strip()

    if current:
        expressions.append(current)

    return expressions


def _parse_role_tmdl(path: str) -> Role | None:
    """Parse a single role .tmdl file."""
    content = _read_file(path)
    role = None
    permissions = {}

    for line in content.splitlines():
        stripped = line.strip()

        if stripped.startswith("role "):
            name = stripped[5:].strip()
            role = Role(name=_unquote(name))
            continue

        tp_match = re.match(r"tablePermission\s+(.+?)\s*=\s*(.+)", stripped)
        if tp_match:
            permissions[_unquote(tp_match.group(1))] = tp_match.group(2).strip()

    if role:
        role.table_permissions = permissions
    return role
