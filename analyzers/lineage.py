"""Measure lineage tree builder for D3 visualization."""

import re
from models import SemanticModel


def build_lineage(model: SemanticModel) -> dict:
    """Build a lineage graph of measure dependencies.

    Returns a dict with:
        nodes: list of {id, name, table, has_deps}
        links: list of {source, target}
        tree: hierarchical tree structure for D3.tree()
    """
    # Collect all measures
    measures = {}
    for table in model.tables:
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        for m in table.measures:
            measures[m.name] = {
                "name": m.name,
                "table": table.name,
                "expression": m.expression,
            }

    # Build dependency graph
    deps = {}  # measure -> list of measures it depends on
    for name, info in measures.items():
        refs = _extract_measure_refs(info["expression"], measures)
        deps[name] = refs

    # Build nodes and links for D3
    nodes = []
    node_ids = {}
    for i, (name, info) in enumerate(measures.items()):
        node_ids[name] = i
        nodes.append({
            "id": i,
            "name": name,
            "table": info["table"],
            "has_deps": len(deps.get(name, [])) > 0,
        })

    links = []
    for name, ref_list in deps.items():
        if name not in node_ids:
            continue
        for ref in ref_list:
            if ref in node_ids:
                links.append({
                    "source": node_ids[name],
                    "target": node_ids[ref],
                })

    # Build hierarchical tree for each root measure (no parents)
    children_map = {}  # measure -> list of children (measures that depend on it)
    for name, ref_list in deps.items():
        for ref in ref_list:
            children_map.setdefault(ref, []).append(name)

    # Find root nodes (measures that are referenced but don't reference others)
    # Or just build tree from measures that have dependencies
    trees = []
    visited = set()

    def build_tree_node(name, depth=0):
        if depth > 10 or name in visited:
            return {"name": name, "table": measures.get(name, {}).get("table", ""), "children": []}
        visited.add(name)
        children = []
        for child in children_map.get(name, []):
            children.append(build_tree_node(child, depth + 1))
        node = {"name": name, "table": measures.get(name, {}).get("table", ""), "children": children}
        visited.discard(name)
        return node

    # Root measures: referenced by others but don't reference any measures
    roots = set()
    for name in measures:
        if not deps.get(name) and children_map.get(name):
            roots.add(name)

    # If no pure roots, use measures that have children
    if not roots:
        roots = set(children_map.keys())

    for root in sorted(roots):
        trees.append(build_tree_node(root))

    return {
        "nodes": nodes,
        "links": links,
        "trees": trees,
        "has_lineage": len(links) > 0,
    }


def _extract_measure_refs(expression: str, known_measures: dict) -> list[str]:
    """Extract measure references from a DAX expression."""
    if not expression:
        return []
    refs = re.findall(r'\[([^\]]+)\]', expression)
    # Only keep references that are known measures
    seen = set()
    result = []
    for r in refs:
        if r in known_measures and r not in seen:
            seen.add(r)
            result.append(r)
    return result
