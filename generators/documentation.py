"""Auto-generate model documentation from parsed PBIP data."""

from models import SemanticModel, ReportDefinition


def generate_documentation(model: SemanticModel, report: ReportDefinition) -> dict:
    """Generate structured documentation from the semantic model and report.

    Returns a dict with sections:
        overview: dict with counts and summary info
        tables: list of table info dicts
        measures: list of measure info dicts (sorted by table, then name)
        relationships: list of relationship info dicts
        sources: list of data source info dicts
    """
    doc = {
        "overview": _build_overview(model, report),
        "tables": _build_tables(model),
        "measures": _build_measures(model),
        "relationships": _build_relationships(model),
        "sources": _build_sources(model),
    }
    return doc


def _build_overview(model: SemanticModel, report: ReportDefinition) -> dict:
    total_columns = sum(len(t.columns) for t in model.tables)
    total_measures = sum(len(t.measures) for t in model.tables)
    total_calc_cols = sum(
        1 for t in model.tables for c in t.columns
        if c.column_type == "calculated"
    )
    total_pages = len(report.pages)

    # Detect storage modes
    modes = set()
    for t in model.tables:
        for p in t.partitions:
            modes.add(p.mode)

    return {
        "total_tables": len(model.tables),
        "total_columns": total_columns,
        "total_measures": total_measures,
        "total_calc_columns": total_calc_cols,
        "total_relationships": len(model.relationships),
        "total_pages": total_pages,
        "culture": model.culture,
        "default_mode": model.default_mode,
        "storage_modes": sorted(modes) if modes else ["import"],
        "roles_count": len(model.roles),
        "expressions_count": len(model.expressions),
    }


def _build_tables(model: SemanticModel) -> list[dict]:
    tables = []
    for t in model.tables:
        # Skip auto date tables
        if t.name.startswith("DateTableTemplate") or t.name.startswith("LocalDateTable"):
            continue

        columns = []
        for c in t.columns:
            if c.column_type == "rowNumber":
                continue
            columns.append({
                "name": c.name,
                "data_type": c.data_type,
                "type": c.column_type,
                "is_hidden": c.is_hidden,
                "is_key": c.is_key,
                "expression": c.expression if c.column_type == "calculated" else "",
                "description": c.description,
            })

        measures = []
        for m in t.measures:
            measures.append({
                "name": m.name,
                "expression": m.expression,
                "format_string": m.format_string,
                "is_hidden": m.is_hidden,
                "description": m.description,
                "display_folder": m.display_folder,
            })

        mode = t.partitions[0].mode if t.partitions else "import"

        tables.append({
            "name": t.name,
            "is_hidden": t.is_hidden,
            "description": t.description,
            "column_count": len(columns),
            "measure_count": len(measures),
            "columns": columns,
            "measures": measures,
            "mode": mode,
        })

    tables.sort(key=lambda x: x["name"])
    return tables


def _build_measures(model: SemanticModel) -> list[dict]:
    measures = []
    for t in model.tables:
        if t.name.startswith("DateTableTemplate") or t.name.startswith("LocalDateTable"):
            continue
        for m in t.measures:
            # Find dependencies (measure references in expression)
            deps = _extract_measure_refs(m.expression)
            measures.append({
                "name": m.name,
                "table": t.name,
                "expression": m.expression,
                "format_string": m.format_string,
                "description": m.description,
                "display_folder": m.display_folder,
                "is_hidden": m.is_hidden,
                "dependencies": deps,
            })

    measures.sort(key=lambda x: (x["table"], x["name"]))
    return measures


def _build_relationships(model: SemanticModel) -> list[dict]:
    rels = []
    for r in model.relationships:
        rels.append({
            "from_table": r.from_table,
            "from_column": r.from_column,
            "to_table": r.to_table,
            "to_column": r.to_column,
            "from_cardinality": r.from_cardinality,
            "to_cardinality": r.to_cardinality,
            "cross_filtering": r.cross_filtering,
            "is_active": r.is_active,
        })
    rels.sort(key=lambda x: (x["from_table"], x["to_table"]))
    return rels


def _build_sources(model: SemanticModel) -> list[dict]:
    """Extract unique data sources from partition expressions."""
    import re
    from config import DATA_SOURCE_FUNCTIONS

    sources = []
    seen = set()

    for t in model.tables:
        for p in t.partitions:
            if p.source_type != "m" or not p.expression:
                continue
            for func, source_name in DATA_SOURCE_FUNCTIONS.items():
                if func in p.expression and (func, t.name) not in seen:
                    seen.add((func, t.name))
                    # Try to extract connection details
                    detail = _extract_connection_detail(p.expression, func)
                    sources.append({
                        "table": t.name,
                        "source_type": source_name,
                        "function": func,
                        "detail": detail,
                        "mode": p.mode,
                    })

    sources.sort(key=lambda x: (x["source_type"], x["table"]))
    return sources


def _extract_measure_refs(expression: str) -> list[str]:
    """Extract [MeasureName] references from a DAX expression."""
    import re
    refs = re.findall(r'\[([^\]]+)\]', expression)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


def _extract_connection_detail(m_code: str, func: str) -> str:
    """Try to extract server/file/url from M code near the function call."""
    import re
    # Look for the first string literal after the function
    pattern = re.escape(func) + r'\s*\(\s*"([^"]*)"'
    match = re.search(pattern, m_code)
    if match:
        return match.group(1)
    return ""
