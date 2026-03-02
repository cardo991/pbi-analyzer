"""PBIP Modifier: applies DAX, relationship, and new measure changes to PBIP ZIPs.

Works by extracting the original ZIP, patching files in-place (preserving all
metadata we didn't parse), then re-zipping the result.
"""

import io
import json
import os
import re
import tempfile
import zipfile


def apply_changes(zip_path: str, dax_changes: list[dict] = None,
                  relationship_changes: list[dict] = None,
                  new_measures: list[dict] = None,
                  pq_changes: list[dict] = None) -> io.BytesIO:
    """Apply modifications to a PBIP ZIP and return the modified ZIP as BytesIO.

    Args:
        zip_path: path to the original stored ZIP
        dax_changes: list of {"table_name", "measure_name", "new_expression"}
        relationship_changes: list of {"index", "cross_filtering", "is_active"}
        new_measures: list of {"table_name", "name", "expression", "format_string"}
        pq_changes: list of {"table_name", "query_name", "new_m_code"}

    Returns:
        BytesIO containing the modified ZIP ready for send_file()
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        semantic_dir, model_format = _find_semantic_model(tmp_dir)
        if not semantic_dir:
            raise ValueError("No semantic model found in ZIP")

        if dax_changes:
            if model_format == "tmsl":
                _apply_dax_tmsl(semantic_dir, dax_changes)
            else:
                _apply_dax_tmdl(semantic_dir, dax_changes)

        if new_measures:
            if model_format == "tmsl":
                _add_measures_tmsl(semantic_dir, new_measures)
            else:
                _add_measures_tmdl(semantic_dir, new_measures)

        if relationship_changes:
            if model_format == "tmsl":
                _apply_relationships_tmsl(semantic_dir, relationship_changes)
            else:
                _apply_relationships_tmdl(semantic_dir, relationship_changes)

        if pq_changes:
            if model_format == "tmsl":
                _apply_pq_tmsl(semantic_dir, pq_changes)
            else:
                _apply_pq_tmdl(semantic_dir, pq_changes)

        # Re-zip preserving structure
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(tmp_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    arcname = os.path.relpath(full_path, tmp_dir)
                    zout.write(full_path, arcname)
        output.seek(0)
        return output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_semantic_model(root: str) -> tuple[str | None, str]:
    """Find the semantic model directory and detect format (tmsl or tmdl)."""
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.replace(root, "").count(os.sep)
        if depth > 3:
            continue
        for d in dirnames:
            if d.endswith(".SemanticModel") or d.endswith(".Dataset"):
                sem_dir = os.path.join(dirpath, d)
                def_dir = os.path.join(sem_dir, "definition")
                tables_dir = os.path.join(def_dir, "tables")
                if os.path.isdir(tables_dir):
                    tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
                    if tmdl_files:
                        return sem_dir, "tmdl"
                for bim_loc in (os.path.join(sem_dir, "model.bim"),
                                os.path.join(def_dir, "model.bim")):
                    if os.path.exists(bim_loc):
                        return sem_dir, "tmsl"
    return None, ""


def _find_bim_path(semantic_dir: str) -> str:
    for loc in (os.path.join(semantic_dir, "model.bim"),
                os.path.join(semantic_dir, "definition", "model.bim")):
        if os.path.exists(loc):
            return loc
    raise FileNotFoundError("model.bim not found")


def _load_bim(semantic_dir: str) -> tuple[dict, str]:
    """Load model.bim JSON and return (data, path)."""
    path = _find_bim_path(semantic_dir)
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return data, path


def _save_bim(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _expr_to_bim(expression: str):
    """Convert expression string to model.bim format (string or list)."""
    if "\n" in expression:
        return expression.split("\n")
    return expression


# ---------------------------------------------------------------------------
# TMSL (model.bim) — DAX patching
# ---------------------------------------------------------------------------

def _apply_dax_tmsl(semantic_dir: str, changes: list[dict]):
    data, path = _load_bim(semantic_dir)
    model = data.get("model", data)
    change_map = {(c["table_name"], c["measure_name"]): c["new_expression"] for c in changes}

    for table in model.get("tables", []):
        table_name = table.get("name", "")
        for measure in table.get("measures", []):
            key = (table_name, measure.get("name", ""))
            if key in change_map:
                measure["expression"] = _expr_to_bim(change_map[key])

    _save_bim(data, path)


# ---------------------------------------------------------------------------
# TMSL — Add new measures
# ---------------------------------------------------------------------------

def _add_measures_tmsl(semantic_dir: str, new_measures: list[dict]):
    data, path = _load_bim(semantic_dir)
    model = data.get("model", data)

    by_table = {}
    for m in new_measures:
        by_table.setdefault(m["table_name"], []).append(m)

    for table in model.get("tables", []):
        table_name = table.get("name", "")
        if table_name in by_table:
            if "measures" not in table:
                table["measures"] = []
            for m in by_table[table_name]:
                new_m = {"name": m["name"], "expression": _expr_to_bim(m["expression"])}
                if m.get("format_string"):
                    new_m["formatString"] = m["format_string"]
                table["measures"].append(new_m)

    _save_bim(data, path)


# ---------------------------------------------------------------------------
# TMSL — Relationship patching
# ---------------------------------------------------------------------------

def _apply_relationships_tmsl(semantic_dir: str, changes: list[dict]):
    data, path = _load_bim(semantic_dir)
    model = data.get("model", data)
    relationships = model.get("relationships", [])

    for change in changes:
        idx = change.get("index", -1)
        if 0 <= idx < len(relationships):
            rel = relationships[idx]
            if "cross_filtering" in change:
                if change["cross_filtering"] == "bothDirections":
                    rel["crossFilteringBehavior"] = "bothDirections"
                else:
                    rel.pop("crossFilteringBehavior", None)
            if "is_active" in change:
                if change["is_active"]:
                    rel.pop("isActive", None)
                else:
                    rel["isActive"] = False

    _save_bim(data, path)


# ---------------------------------------------------------------------------
# TMDL — DAX patching
# ---------------------------------------------------------------------------

def _find_tmdl_file(tables_dir: str, table_name: str) -> str | None:
    if not os.path.isdir(tables_dir):
        return None
    for fname in os.listdir(tables_dir):
        if fname.endswith(".tmdl") and fname[:-5] == table_name:
            return os.path.join(tables_dir, fname)
    return None


def _apply_dax_tmdl(semantic_dir: str, changes: list[dict]):
    tables_dir = os.path.join(semantic_dir, "definition", "tables")
    by_table = {}
    for c in changes:
        by_table.setdefault(c["table_name"], []).append(c)

    for table_name, table_changes in by_table.items():
        tmdl_path = _find_tmdl_file(tables_dir, table_name)
        if not tmdl_path:
            continue
        with open(tmdl_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        for change in table_changes:
            content = _replace_tmdl_measure_expr(content, change["measure_name"], change["new_expression"])
        with open(tmdl_path, "w", encoding="utf-8") as f:
            f.write(content)


def _replace_tmdl_measure_expr(content: str, measure_name: str, new_expression: str) -> str:
    """Replace a measure's expression in TMDL content.

    Handles single-line and multi-line (backtick block) expressions.
    """
    lines = content.split("\n")
    result = []
    i = 0
    # Build patterns for both quoted and unquoted names
    escaped = re.escape(measure_name)
    patterns = [
        re.compile(r"^(\t)measure\s+'" + escaped + r"'\s*=\s*(.*)$"),
        re.compile(r"^(\t)measure\s+" + escaped + r"\s*=\s*(.*)$"),
    ]

    while i < len(lines):
        matched = None
        for pat in patterns:
            m = pat.match(lines[i])
            if m:
                matched = m
                break

        if not matched:
            result.append(lines[i])
            i += 1
            continue

        indent = matched.group(1)
        inline_expr = (matched.group(2) or "").strip()

        # Skip the old expression lines
        i += 1
        in_backtick = inline_expr == "" or inline_expr == "```"
        if inline_expr == "```":
            # Multi-line: skip until closing backtick
            while i < len(lines):
                if lines[i].strip() == "```":
                    i += 1
                    break
                i += 1
        elif inline_expr == "":
            # Expression starts on next line — check if backtick block
            if i < len(lines) and lines[i].strip() == "```":
                i += 1  # skip opening backtick
                while i < len(lines):
                    if lines[i].strip() == "```":
                        i += 1
                        break
                    i += 1

        # Write new measure declaration
        if "\n" in new_expression:
            result.append(f"{indent}measure '{measure_name}' =")
            result.append(f"{indent}\t```")
            for expr_line in new_expression.split("\n"):
                result.append(f"{indent}\t{expr_line}")
            result.append(f"{indent}\t```")
        else:
            result.append(f"{indent}measure '{measure_name}' = {new_expression}")

        # Collect remaining property lines (formatString:, description:, etc.)
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == "" or lines[i].startswith("\t\t"):
                result.append(lines[i])
                i += 1
            else:
                break

    return "\n".join(result)


# ---------------------------------------------------------------------------
# TMDL — Add new measures
# ---------------------------------------------------------------------------

def _add_measures_tmdl(semantic_dir: str, new_measures: list[dict]):
    tables_dir = os.path.join(semantic_dir, "definition", "tables")
    by_table = {}
    for m in new_measures:
        by_table.setdefault(m["table_name"], []).append(m)

    for table_name, measures in by_table.items():
        tmdl_path = _find_tmdl_file(tables_dir, table_name)
        if not tmdl_path:
            continue
        with open(tmdl_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        # Append new measures at end of file
        additions = []
        for m in measures:
            expr = m["expression"]
            if "\n" in expr:
                additions.append(f"\tmeasure '{m['name']}' =")
                additions.append("\t\t```")
                for line in expr.split("\n"):
                    additions.append(f"\t\t{line}")
                additions.append("\t\t```")
            else:
                additions.append(f"\tmeasure '{m['name']}' = {expr}")
            if m.get("format_string"):
                additions.append(f"\t\tformatString: {m['format_string']}")
            additions.append("")

        if additions:
            content = content.rstrip("\n") + "\n\n" + "\n".join(additions) + "\n"

        with open(tmdl_path, "w", encoding="utf-8") as f:
            f.write(content)


# ---------------------------------------------------------------------------
# TMDL — Relationship patching
# ---------------------------------------------------------------------------

def _apply_relationships_tmdl(semantic_dir: str, changes: list[dict]):
    rel_path = os.path.join(semantic_dir, "definition", "relationships.tmdl")
    if not os.path.exists(rel_path):
        return

    with open(rel_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    # Split into relationship blocks
    blocks = re.split(r"(?=^relationship\s)", content, flags=re.MULTILINE)
    header = blocks[0] if blocks and not blocks[0].startswith("relationship") else ""
    rel_blocks = [b for b in blocks if b.startswith("relationship")]

    change_map = {c["index"]: c for c in changes}

    for idx, block in enumerate(rel_blocks):
        if idx not in change_map:
            continue
        change = change_map[idx]
        lines = block.split("\n")
        new_lines = []
        found_cross = False
        found_active = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("crossFilteringBehavior:"):
                found_cross = True
                if "cross_filtering" in change:
                    new_lines.append(f"\tcrossFilteringBehavior: {change['cross_filtering']}")
                else:
                    new_lines.append(line)
            elif stripped.startswith("isActive:"):
                found_active = True
                if "is_active" in change:
                    new_lines.append(f"\tisActive: {'true' if change['is_active'] else 'false'}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Add properties if not found in original
        if "cross_filtering" in change and not found_cross:
            # Insert after the last property line
            insert_idx = len(new_lines) - 1
            while insert_idx > 0 and new_lines[insert_idx].strip() == "":
                insert_idx -= 1
            new_lines.insert(insert_idx + 1, f"\tcrossFilteringBehavior: {change['cross_filtering']}")
        if "is_active" in change and not found_active and not change["is_active"]:
            insert_idx = len(new_lines) - 1
            while insert_idx > 0 and new_lines[insert_idx].strip() == "":
                insert_idx -= 1
            new_lines.insert(insert_idx + 1, f"\tisActive: false")

        rel_blocks[idx] = "\n".join(new_lines)

    result = header + "".join(rel_blocks)
    with open(rel_path, "w", encoding="utf-8") as f:
        f.write(result)


# ---------------------------------------------------------------------------
# TMSL (model.bim) — PQ / M code patching
# ---------------------------------------------------------------------------

def _apply_pq_tmsl(semantic_dir: str, changes: list[dict]):
    """Patch M code in model.bim partition sources."""
    data, path = _load_bim(semantic_dir)
    model = data.get("model", data)

    change_map = {(c["table_name"], c["query_name"]): c["new_m_code"] for c in changes}

    for table in model.get("tables", []):
        table_name = table.get("name", "")
        for partition in table.get("partitions", []):
            key = (table_name, partition.get("name", ""))
            if key in change_map:
                source = partition.get("source", {})
                if source.get("type") in ("m", "M", None):
                    source["expression"] = _expr_to_bim(change_map[key])

    _save_bim(data, path)


# ---------------------------------------------------------------------------
# TMDL — PQ / M code patching
# ---------------------------------------------------------------------------

def _apply_pq_tmdl(semantic_dir: str, changes: list[dict]):
    """Patch M code in .tmdl partition source blocks."""
    tables_dir = os.path.join(semantic_dir, "definition", "tables")
    by_table = {}
    for c in changes:
        by_table.setdefault(c["table_name"], []).append(c)

    for table_name, table_changes in by_table.items():
        tmdl_path = _find_tmdl_file(tables_dir, table_name)
        if not tmdl_path:
            continue
        with open(tmdl_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        for change in table_changes:
            content = _replace_tmdl_partition_source(
                content, change["query_name"], change["new_m_code"]
            )
        with open(tmdl_path, "w", encoding="utf-8") as f:
            f.write(content)


def _replace_tmdl_partition_source(content: str, partition_name: str, new_m_code: str) -> str:
    """Replace a partition's source expression in TMDL content.

    TMDL partition format:
        \\tpartition 'PartitionName' = m
        \\t\\tmode: import
        \\t\\tsource =
        \\t\\t\\t```
        \\t\\t\\t<M code lines>
        \\t\\t\\t```
    """
    lines = content.split("\n")
    result = []
    i = 0
    escaped = re.escape(partition_name)

    part_patterns = [
        re.compile(r"^\tpartition\s+'" + escaped + r"'\s*=\s*m"),
        re.compile(r"^\tpartition\s+" + escaped + r"\s*=\s*m"),
    ]

    while i < len(lines):
        matched = any(pat.match(lines[i]) for pat in part_patterns)

        if not matched:
            result.append(lines[i])
            i += 1
            continue

        # Found the partition line — keep it
        result.append(lines[i])
        i += 1

        # Copy property lines until we find "source ="
        while i < len(lines):
            if re.match(r"^\t\tsource\s*=\s*$", lines[i]):
                result.append(lines[i])
                i += 1
                # Skip old source content (backtick block)
                if i < len(lines) and lines[i].strip() == "```":
                    i += 1  # skip opening backtick
                    while i < len(lines):
                        if lines[i].strip() == "```":
                            i += 1
                            break
                        i += 1
                # Write new M code in backtick block
                result.append("\t\t\t```")
                for m_line in new_m_code.split("\n"):
                    result.append(f"\t\t\t{m_line}")
                result.append("\t\t\t```")
                break
            else:
                result.append(lines[i])
                i += 1

    return "\n".join(result)
