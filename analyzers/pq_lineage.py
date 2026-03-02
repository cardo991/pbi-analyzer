"""Power Query lineage builder for D3 force-directed graph visualization."""

import re
from models import SemanticModel
from config import DATA_SOURCE_FUNCTIONS


def build_pq_lineage(model: SemanticModel) -> dict:
    """Build a lineage graph of Power Query dependencies between queries.

    Analyzes M code to discover:
    - References between queries via #"Query Name" patterns
    - Merge operations (Table.NestedJoin)
    - Append operations (Table.Combine)
    - Data source origins (Sql.Database, Excel.Workbook, etc.)

    Returns dict with nodes[], links[], and has_lineage flag.
    """
    # Collect all M queries from partitions and shared expressions
    queries = {}  # name -> {"table": str, "m_code": str}

    for table in model.tables:
        # Skip auto-generated date tables
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        for p in table.partitions:
            if p.source_type == "m" and p.expression:
                queries[table.name] = {
                    "table": table.name,
                    "m_code": p.expression,
                }

    for expr_obj in model.expressions:
        if expr_obj.expression:
            queries[expr_obj.name] = {
                "table": expr_obj.name,
                "m_code": expr_obj.expression,
            }

    if not queries:
        return {"nodes": [], "links": [], "has_lineage": False}

    # Build name-to-index map
    name_list = list(queries.keys())
    name_to_idx = {name: i for i, name in enumerate(name_list)}

    # Detect data source type for each query
    source_types = {}
    for name, info in queries.items():
        source_types[name] = _detect_source_type(info["m_code"])

    # Count M steps per query
    step_counts = {}
    for name, info in queries.items():
        step_counts[name] = _count_steps(info["m_code"])

    # Build links by analyzing M code references
    links = []
    outgoing = {name: False for name in name_list}  # tracks if query feeds others

    for name, info in queries.items():
        m_code = info["m_code"]
        target_idx = name_to_idx[name]

        # 1) Find #"Query Name" references to other queries
        ref_names = re.findall(r'#"([^"]+)"', m_code)
        for ref in ref_names:
            if ref in name_to_idx and ref != name:
                links.append({
                    "source": name_to_idx[ref],
                    "target": target_idx,
                    "type": "reference",
                })
                outgoing[ref] = True

        # 2) Detect merge (Table.NestedJoin)
        merge_matches = re.findall(
            r'Table\.NestedJoin\s*\([^,]*,\s*[^,]*,\s*#?"?([^",\)]+)"?',
            m_code,
        )
        for merged in merge_matches:
            merged_clean = merged.strip().strip('"')
            if merged_clean in name_to_idx and merged_clean != name:
                # Avoid duplicate link if already added as reference
                if not _link_exists(links, name_to_idx[merged_clean], target_idx):
                    links.append({
                        "source": name_to_idx[merged_clean],
                        "target": target_idx,
                        "type": "merge",
                    })
                    outgoing[merged_clean] = True

        # 3) Detect append (Table.Combine)
        combine_match = re.search(r'Table\.Combine\s*\(\s*\{([^}]+)\}', m_code)
        if combine_match:
            combined_refs = re.findall(r'#"([^"]+)"', combine_match.group(1))
            for ref in combined_refs:
                if ref in name_to_idx and ref != name:
                    if not _link_exists(links, name_to_idx[ref], target_idx):
                        links.append({
                            "source": name_to_idx[ref],
                            "target": target_idx,
                            "type": "append",
                        })
                        outgoing[ref] = True

    # Determine which queries are referenced as targets (have incoming links)
    has_incoming = set()
    for link in links:
        has_incoming.add(link["target"])

    # Build nodes with type classification
    nodes = []
    for name in name_list:
        idx = name_to_idx[name]
        src_type = source_types.get(name, "")
        is_source = bool(src_type)
        is_staging = idx in has_incoming and outgoing[name]

        if is_source and not outgoing[name]:
            node_type = "source"
        elif is_source and outgoing[name]:
            node_type = "source"
        elif is_staging:
            node_type = "staging"
        elif outgoing[name]:
            node_type = "staging"
        else:
            node_type = "final"

        nodes.append({
            "id": idx,
            "name": name,
            "table": queries[name]["table"],
            "source_type": src_type,
            "step_count": step_counts.get(name, 0),
            "type": node_type,
        })

    return {
        "nodes": nodes,
        "links": links,
        "has_lineage": len(links) > 0,
    }


def _detect_source_type(m_code: str) -> str:
    """Detect the data source type from M code using DATA_SOURCE_FUNCTIONS."""
    for func, source_name in DATA_SOURCE_FUNCTIONS.items():
        if re.search(re.escape(func), m_code):
            return source_name
    return ""


def _count_steps(m_code: str) -> int:
    """Count the number of steps in a let..in M expression."""
    let_match = re.search(r'(?i)\blet\b', m_code)
    in_match = re.search(r'(?i)(?<!\w)\bin\b(?!\w)(?!\s*")', m_code)

    if not let_match or not in_match:
        return 1

    let_body = m_code[let_match.end():in_match.start()]
    steps = re.findall(r'^\s*(?:#"[^"]*"|\w+)\s*=', let_body, re.MULTILINE)
    return max(len(steps), 1)


def _link_exists(links: list[dict], source: int, target: int) -> bool:
    """Check if a link between source and target already exists."""
    return any(l["source"] == source and l["target"] == target for l in links)
