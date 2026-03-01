"""Unused measures detection analyzer."""

import re
from models import SemanticModel, ReportDefinition


def analyze_unused_measures(model: SemanticModel, report: ReportDefinition) -> list[dict]:
    """Find measures that are not referenced by any visual or other measure.

    Returns a list of dicts: {name, table, referenced_by, is_unused}
    """
    # Build list of all measures
    all_measures = {}
    for table in model.tables:
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        for m in table.measures:
            all_measures[m.name] = {
                "name": m.name,
                "table": table.name,
                "expression": m.expression,
            }

    # Build measure-to-measure dependency map
    measure_refs = {}  # measure_name -> set of measures it references
    for name, info in all_measures.items():
        refs = set()
        if info["expression"]:
            # Find [MeasureName] references
            found = re.findall(r'\[([^\]]+)\]', info["expression"])
            for ref in found:
                if ref in all_measures and ref != name:
                    refs.add(ref)
        measure_refs[name] = refs

    # Build reverse map: which measures reference this one
    referenced_by = {name: set() for name in all_measures}
    for name, refs in measure_refs.items():
        for ref in refs:
            if ref in referenced_by:
                referenced_by[ref].add(name)

    # Collect field references from visuals
    visual_refs = set()
    for page in report.pages:
        for visual in page.visuals:
            for ref in getattr(visual, 'field_references', []):
                visual_refs.add(ref)

    # A measure is unused if:
    # 1. Not referenced by any visual
    # 2. Not referenced by any other measure that IS used
    # For simplicity, flag measures not in visual_refs and not referenced by others
    results = []
    for name, info in all_measures.items():
        refs_by = referenced_by.get(name, set())
        in_visual = name in visual_refs

        # Check transitive: if referenced by a measure that's in a visual
        transitive_used = False
        if refs_by:
            for parent in refs_by:
                if parent in visual_refs:
                    transitive_used = True
                    break

        is_unused = not in_visual and not transitive_used and len(refs_by) == 0

        if is_unused:
            results.append({
                "name": name,
                "table": info["table"],
                "referenced_by": sorted(refs_by),
                "is_unused": True,
            })

    results.sort(key=lambda x: (x["table"], x["name"]))
    return results
