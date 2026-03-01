"""Version diff: compare two versions of a PBIP project."""

from models import SemanticModel, ReportDefinition


def compare_versions(model1: SemanticModel, report1: ReportDefinition,
                     model2: SemanticModel, report2: ReportDefinition) -> dict:
    """Compare two versions of a PBIP project.

    Returns a diff summary with changes to tables, measures, columns,
    relationships, roles, and pages.
    """
    diff = {
        "has_changes": False,
        "summary": {},
        "table_changes": [],
        "measure_changes": [],
        "column_changes": [],
        "relationship_changes": [],
        "role_changes": [],
        "page_changes": [],
    }

    # --- Tables ---
    tables1 = {t.name: t for t in model1.tables if not _skip_table(t.name)}
    tables2 = {t.name: t for t in model2.tables if not _skip_table(t.name)}

    added_tables = set(tables2.keys()) - set(tables1.keys())
    removed_tables = set(tables1.keys()) - set(tables2.keys())
    common_tables = set(tables1.keys()) & set(tables2.keys())

    for name in sorted(added_tables):
        diff["table_changes"].append({
            "name": name, "status": "added",
            "details": f"{len(tables2[name].columns)} columns, {len(tables2[name].measures)} measures",
        })
    for name in sorted(removed_tables):
        diff["table_changes"].append({
            "name": name, "status": "removed",
            "details": f"{len(tables1[name].columns)} columns, {len(tables1[name].measures)} measures",
        })

    # --- Measures ---
    measures1 = {}
    measures2 = {}
    for t in model1.tables:
        if _skip_table(t.name):
            continue
        for m in t.measures:
            measures1[f"{t.name}.{m.name}"] = m
    for t in model2.tables:
        if _skip_table(t.name):
            continue
        for m in t.measures:
            measures2[f"{t.name}.{m.name}"] = m

    added_measures = set(measures2.keys()) - set(measures1.keys())
    removed_measures = set(measures1.keys()) - set(measures2.keys())
    common_measures = set(measures1.keys()) & set(measures2.keys())

    for key in sorted(added_measures):
        m = measures2[key]
        diff["measure_changes"].append({
            "name": key, "status": "added",
            "expression": m.expression[:200],
        })
    for key in sorted(removed_measures):
        m = measures1[key]
        diff["measure_changes"].append({
            "name": key, "status": "removed",
            "expression": m.expression[:200],
        })
    for key in sorted(common_measures):
        m1 = measures1[key]
        m2 = measures2[key]
        if m1.expression.strip() != m2.expression.strip():
            diff["measure_changes"].append({
                "name": key, "status": "modified",
                "old_expression": m1.expression[:200],
                "new_expression": m2.expression[:200],
            })

    # --- Columns ---
    for table_name in common_tables:
        t1 = tables1[table_name]
        t2 = tables2[table_name]
        cols1 = {c.name: c for c in t1.columns if c.column_type != "rowNumber"}
        cols2 = {c.name: c for c in t2.columns if c.column_type != "rowNumber"}

        added_cols = set(cols2.keys()) - set(cols1.keys())
        removed_cols = set(cols1.keys()) - set(cols2.keys())
        common_cols = set(cols1.keys()) & set(cols2.keys())

        for name in sorted(added_cols):
            diff["column_changes"].append({
                "table": table_name, "name": name, "status": "added",
                "details": f"type: {cols2[name].data_type}",
            })
        for name in sorted(removed_cols):
            diff["column_changes"].append({
                "table": table_name, "name": name, "status": "removed",
                "details": f"type: {cols1[name].data_type}",
            })
        for name in sorted(common_cols):
            c1, c2 = cols1[name], cols2[name]
            changes = []
            if c1.data_type != c2.data_type:
                changes.append(f"type: {c1.data_type} → {c2.data_type}")
            if c1.is_hidden != c2.is_hidden:
                changes.append(f"hidden: {c1.is_hidden} → {c2.is_hidden}")
            if c1.column_type != c2.column_type:
                changes.append(f"column type: {c1.column_type} → {c2.column_type}")
            if changes:
                diff["column_changes"].append({
                    "table": table_name, "name": name, "status": "modified",
                    "details": "; ".join(changes),
                })

    # --- Relationships ---
    rels1 = {_rel_key(r): r for r in model1.relationships}
    rels2 = {_rel_key(r): r for r in model2.relationships}

    added_rels = set(rels2.keys()) - set(rels1.keys())
    removed_rels = set(rels1.keys()) - set(rels2.keys())
    common_rels = set(rels1.keys()) & set(rels2.keys())

    for key in sorted(added_rels):
        r = rels2[key]
        diff["relationship_changes"].append({
            "name": key, "status": "added",
            "details": f"{r.from_cardinality}:{r.to_cardinality}, cross={r.cross_filtering}",
        })
    for key in sorted(removed_rels):
        diff["relationship_changes"].append({
            "name": key, "status": "removed", "details": "",
        })
    for key in sorted(common_rels):
        r1, r2 = rels1[key], rels2[key]
        changes = []
        if r1.cross_filtering != r2.cross_filtering:
            changes.append(f"cross filter: {r1.cross_filtering} → {r2.cross_filtering}")
        if r1.is_active != r2.is_active:
            changes.append(f"active: {r1.is_active} → {r2.is_active}")
        if changes:
            diff["relationship_changes"].append({
                "name": key, "status": "modified",
                "details": "; ".join(changes),
            })

    # --- Roles ---
    roles1 = {r.name: r for r in model1.roles}
    roles2 = {r.name: r for r in model2.roles}

    for name in sorted(set(roles2.keys()) - set(roles1.keys())):
        diff["role_changes"].append({"name": name, "status": "added"})
    for name in sorted(set(roles1.keys()) - set(roles2.keys())):
        diff["role_changes"].append({"name": name, "status": "removed"})
    for name in sorted(set(roles1.keys()) & set(roles2.keys())):
        r1, r2 = roles1[name], roles2[name]
        if r1.table_permissions != r2.table_permissions:
            diff["role_changes"].append({"name": name, "status": "modified"})

    # --- Pages ---
    pages1 = {p.name: p for p in report1.pages}
    pages2 = {p.name: p for p in report2.pages}

    for name in sorted(set(pages2.keys()) - set(pages1.keys())):
        p = pages2[name]
        diff["page_changes"].append({
            "name": p.display_name or name, "status": "added",
            "details": f"{len(p.visuals)} visuals",
        })
    for name in sorted(set(pages1.keys()) - set(pages2.keys())):
        p = pages1[name]
        diff["page_changes"].append({
            "name": p.display_name or name, "status": "removed",
            "details": f"{len(p.visuals)} visuals",
        })
    for name in sorted(set(pages1.keys()) & set(pages2.keys())):
        p1, p2 = pages1[name], pages2[name]
        changes = []
        if len(p1.visuals) != len(p2.visuals):
            changes.append(f"visuals: {len(p1.visuals)} → {len(p2.visuals)}")
        if p1.display_name != p2.display_name:
            changes.append(f"renamed: {p1.display_name} → {p2.display_name}")
        if changes:
            diff["page_changes"].append({
                "name": p1.display_name or name, "status": "modified",
                "details": "; ".join(changes),
            })

    # --- Summary ---
    diff["summary"] = {
        "tables_added": len(added_tables),
        "tables_removed": len(removed_tables),
        "tables_modified": len([c for c in diff["table_changes"] if c["status"] == "modified"]),
        "measures_added": len(added_measures),
        "measures_removed": len(removed_measures),
        "measures_modified": len([c for c in diff["measure_changes"] if c["status"] == "modified"]),
        "columns_added": len([c for c in diff["column_changes"] if c["status"] == "added"]),
        "columns_removed": len([c for c in diff["column_changes"] if c["status"] == "removed"]),
        "columns_modified": len([c for c in diff["column_changes"] if c["status"] == "modified"]),
        "relationships_added": len(added_rels),
        "relationships_removed": len(removed_rels),
        "relationships_modified": len([c for c in diff["relationship_changes"] if c["status"] == "modified"]),
        "roles_changed": len(diff["role_changes"]),
        "pages_added": len([c for c in diff["page_changes"] if c["status"] == "added"]),
        "pages_removed": len([c for c in diff["page_changes"] if c["status"] == "removed"]),
        "pages_modified": len([c for c in diff["page_changes"] if c["status"] == "modified"]),
    }

    diff["has_changes"] = any(v > 0 for v in diff["summary"].values())

    return diff


def _skip_table(name: str) -> bool:
    return name.startswith(("DateTableTemplate", "LocalDateTable"))


def _rel_key(r) -> str:
    return f"{r.from_table}[{r.from_column}] → {r.to_table}[{r.to_column}]"
