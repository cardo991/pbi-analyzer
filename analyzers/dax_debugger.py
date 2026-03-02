"""DAX expression debugger and simulator."""

import re
from collections import Counter

# DAX function categories
_FUNC_CATEGORIES = {
    "aggregation": {"SUM", "AVERAGE", "COUNT", "COUNTROWS", "MIN", "MAX",
                    "DISTINCTCOUNT", "COUNTBLANK", "COUNTA", "COUNTX",
                    "SUMX", "AVERAGEX", "MINX", "MAXX", "RANKX", "COUNTAX",
                    "PRODUCTX", "MEDIANX", "PERCENTILE.INC", "PERCENTILE.EXC"},
    "filter": {"CALCULATE", "CALCULATETABLE", "FILTER", "ALL", "ALLEXCEPT",
               "ALLSELECTED", "ALLNOBLANKROW", "KEEPFILTERS", "REMOVEFILTERS",
               "VALUES", "DISTINCT", "SELECTEDVALUE", "HASONEVALUE",
               "HASONEFILTER", "ISFILTERED", "ISCROSSFILTERED"},
    "table": {"ADDCOLUMNS", "SELECTCOLUMNS", "SUMMARIZE", "SUMMARIZECOLUMNS",
              "GROUPBY", "CROSSJOIN", "UNION", "INTERSECT", "EXCEPT",
              "NATURALINNERJOIN", "NATURALLEFTOUTERJOIN", "TREATAS",
              "DATATABLE", "ROW", "TOPN", "SAMPLE", "GENERATE", "GENERATEALL"},
    "time_intelligence": {"DATESYTD", "DATESMTD", "DATESQTD", "TOTALYTD",
                          "TOTALMTD", "TOTALQTD", "SAMEPERIODLASTYEAR",
                          "PREVIOUSMONTH", "PREVIOUSQUARTER", "PREVIOUSYEAR",
                          "NEXTMONTH", "NEXTQUARTER", "NEXTYEAR",
                          "DATEADD", "DATESBETWEEN", "DATESINPERIOD",
                          "PARALLELPERIOD", "OPENINGBALANCEMONTH",
                          "CLOSINGBALANCEMONTH", "CLOSINGBALANCEYEAR"},
    "logical": {"IF", "SWITCH", "AND", "OR", "NOT", "TRUE", "FALSE",
                "IFERROR", "IFBLANK", "COALESCE", "IN"},
    "text": {"CONCATENATE", "CONCATENATEX", "FORMAT", "LEFT", "RIGHT",
             "MID", "LEN", "FIND", "SEARCH", "REPLACE", "SUBSTITUTE",
             "UPPER", "LOWER", "TRIM", "BLANK", "UNICHAR", "COMBINEVALUES"},
    "math": {"DIVIDE", "MOD", "INT", "ROUND", "ROUNDUP", "ROUNDDOWN",
             "ABS", "SIGN", "SQRT", "POWER", "LOG", "LN", "EXP",
             "CEILING", "FLOOR", "RAND", "RANDBETWEEN", "CURRENCY"},
    "information": {"ISBLANK", "ISERROR", "ISLOGICAL", "ISNONTEXT",
                    "ISNUMBER", "ISTEXT", "USERNAME", "USERPRINCIPALNAME",
                    "RELATED", "RELATEDTABLE", "LOOKUPVALUE", "USERELATIONSHIP",
                    "CROSSFILTER", "PATH", "PATHCONTAINS", "PATHITEM"},
    "date": {"DATE", "YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND",
             "NOW", "TODAY", "EDATE", "EOMONTH", "DATEDIFF", "CALENDAR",
             "CALENDARAUTO", "WEEKDAY", "WEEKNUM"},
}

# Flatten for lookup
_FUNC_TO_CATEGORY = {}
for cat, funcs in _FUNC_CATEGORIES.items():
    for f in funcs:
        _FUNC_TO_CATEGORY[f] = cat

# Iterators that create row context
_ITERATORS = {"SUMX", "AVERAGEX", "MINX", "MAXX", "COUNTX", "COUNTAX",
              "RANKX", "PRODUCTX", "MEDIANX", "CONCATENATEX",
              "FILTER", "ADDCOLUMNS", "SELECTCOLUMNS", "GENERATE",
              "GENERATEALL"}

# Context transition functions
_CONTEXT_TRANSITIONS = {"CALCULATE", "CALCULATETABLE"}


def debug_dax_expression(expression: str, model_context: dict = None) -> dict:
    """Analyze a DAX expression and return debug information."""
    if not expression or not expression.strip():
        return {"error": "Empty expression"}

    expr = expression.strip()

    # 1. Extract referenced columns: Table[Column]
    col_refs = re.findall(r"'?([A-Za-z_][\w\s]*?)'?\[([^\]]+)\]", expr)
    referenced_columns = []
    seen_cols = set()
    for table, col in col_refs:
        table = table.strip().strip("'")
        key = (table, col)
        if key not in seen_cols:
            seen_cols.add(key)
            referenced_columns.append({"table": table, "column": col})

    # 2. Extract referenced measures: [MeasureName]
    measure_refs = re.findall(r"(?<!\w)\[([^\]]+)\]", expr)
    # Filter out column refs (those preceded by Table name)
    col_names = {col for _, col in col_refs}
    referenced_measures = []
    seen_measures = set()
    for m in measure_refs:
        if m not in col_names and m not in seen_measures:
            seen_measures.add(m)
            referenced_measures.append({"name": m})

    # If model_context provided, enrich with table info
    if model_context:
        measures_dict = {}
        for tbl in model_context.get("tables", []):
            tbl_name = tbl.get("name", "")
            for meas in tbl.get("measures", []):
                measures_dict[meas.get("name", "")] = tbl_name
        for ref in referenced_measures:
            if ref["name"] in measures_dict:
                ref["table"] = measures_dict[ref["name"]]

    # 3. Count functions used
    func_pattern = re.compile(r'\b([A-Z][A-Z0-9_.]+)\s*\(', re.IGNORECASE)
    func_matches = func_pattern.findall(expr)
    func_counter = Counter(f.upper() for f in func_matches)
    functions_used = []
    for func_name, count in func_counter.most_common():
        category = _FUNC_TO_CATEGORY.get(func_name, "other")
        functions_used.append({
            "name": func_name,
            "count": count,
            "category": category,
        })

    # 4. Detect evaluation context
    funcs_upper = {f.upper() for f in func_matches}
    iterators_found = sorted(funcs_upper & _ITERATORS)
    transitions_found = sorted(funcs_upper & _CONTEXT_TRANSITIONS)

    has_row_context = bool(iterators_found)
    has_filter_context = bool(transitions_found)

    # 5. Build context warnings
    warnings = []
    if has_row_context and has_filter_context:
        warnings.append("Context transition detected: CALCULATE inside an iterator switches from row to filter context")
    if "FILTER" in funcs_upper and "CALCULATE" in funcs_upper:
        warnings.append("FILTER inside CALCULATE may be inefficient — consider using direct filter arguments")
    if len(iterators_found) > 2:
        warnings.append(f"Multiple iterators detected ({', '.join(iterators_found)}). This may impact performance.")

    # 6. Complexity score
    nesting = _max_nesting(expr)
    func_count = sum(func_counter.values())
    complexity_score = min(100, func_count * 5 + nesting * 15 + len(referenced_columns) * 2)
    if complexity_score <= 20:
        level = "low"
    elif complexity_score <= 50:
        level = "medium"
    elif complexity_score <= 80:
        level = "high"
    else:
        level = "very_high"

    # 7. Build simplified flowchart
    flowchart_nodes = []
    flowchart_edges = []
    node_id = 0

    # Source columns as input nodes
    for col_ref in referenced_columns:
        flowchart_nodes.append({
            "id": f"col_{node_id}",
            "label": f"{col_ref['table']}[{col_ref['column']}]",
            "type": "column",
        })
        node_id += 1

    # Measures as input nodes
    for m_ref in referenced_measures:
        flowchart_nodes.append({
            "id": f"meas_{node_id}",
            "label": f"[{m_ref['name']}]",
            "type": "measure",
        })
        node_id += 1

    # Function nodes (top functions)
    for func_info in functions_used[:5]:
        f_id = f"func_{node_id}"
        flowchart_nodes.append({
            "id": f_id,
            "label": func_info["name"],
            "type": "function",
        })
        node_id += 1

    # Output node
    flowchart_nodes.append({
        "id": "output",
        "label": "Result",
        "type": "output",
    })

    # Simple edges: inputs -> functions -> output
    func_node_ids = [n["id"] for n in flowchart_nodes if n["type"] == "function"]
    input_node_ids = [n["id"] for n in flowchart_nodes if n["type"] in ("column", "measure")]

    if func_node_ids:
        for inp in input_node_ids:
            flowchart_edges.append({"source": inp, "target": func_node_ids[0], "label": ""})
        for i in range(len(func_node_ids) - 1):
            flowchart_edges.append({"source": func_node_ids[i], "target": func_node_ids[i + 1], "label": ""})
        flowchart_edges.append({"source": func_node_ids[-1], "target": "output", "label": ""})
    elif input_node_ids:
        for inp in input_node_ids:
            flowchart_edges.append({"source": inp, "target": "output", "label": ""})

    return {
        "referenced_columns": referenced_columns,
        "referenced_measures": referenced_measures,
        "functions_used": functions_used,
        "context_info": {
            "has_row_context": has_row_context,
            "has_filter_context": has_filter_context,
            "context_transitions": transitions_found,
            "iterators": iterators_found,
        },
        "complexity": {
            "score": complexity_score,
            "level": level,
            "nesting_depth": nesting,
            "function_count": func_count,
        },
        "warnings": warnings,
        "flowchart_nodes": flowchart_nodes,
        "flowchart_edges": flowchart_edges,
    }


def _max_nesting(expr: str) -> int:
    """Calculate maximum parenthesis nesting depth."""
    max_depth = 0
    depth = 0
    for ch in expr:
        if ch == '(':
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == ')':
            depth = max(0, depth - 1)
    return max_depth
