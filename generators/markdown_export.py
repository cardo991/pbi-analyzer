"""Markdown export generator."""


def generate_markdown(project_name: str, score: dict, findings: list,
                      documentation: dict, kpi_suggestions: list) -> str:
    """Generate a complete Markdown document from analysis results."""
    lines = []

    # Header
    lines.append(f"# GridPulse Report: {project_name}")
    lines.append("")

    # Score
    lines.append("## Health Score")
    lines.append("")
    lines.append(f"**Total Score:** {score.get('total_score', 0)} / 100")
    lines.append(f"**Grade:** {score.get('grade', 'F')}")
    lines.append("")

    # Category Scores
    lines.append("### Category Scores")
    lines.append("")
    lines.append("| Category | Score | Max |")
    lines.append("|----------|-------|-----|")
    cat_labels = {
        "data_model": "Data Model",
        "dax": "DAX Measures",
        "power_query": "Power Query",
        "report": "Report / Visuals",
    }
    for cat, cat_score in score.get("category_scores", {}).items():
        cat_max = score.get("category_max", {}).get(cat, 0)
        lines.append(f"| {cat_labels.get(cat, cat)} | {cat_score} | {cat_max} |")
    lines.append("")

    # Overview
    overview = documentation.get("overview", {})
    lines.append("## Model Overview")
    lines.append("")
    lines.append(f"- **Tables:** {overview.get('total_tables', 0)}")
    lines.append(f"- **Columns:** {overview.get('total_columns', 0)}")
    lines.append(f"- **Measures:** {overview.get('total_measures', 0)}")
    lines.append(f"- **Calculated Columns:** {overview.get('total_calc_columns', 0)}")
    lines.append(f"- **Relationships:** {overview.get('total_relationships', 0)}")
    lines.append(f"- **Pages:** {overview.get('total_pages', 0)}")
    lines.append("")

    # Findings
    lines.append("## Findings")
    lines.append("")
    findings_data = findings if isinstance(findings, list) else []
    if findings_data:
        lines.append(f"Total: {len(findings_data)} findings")
        lines.append("")
        lines.append("| Rule | Severity | Message | Location |")
        lines.append("|------|----------|---------|----------|")
        for f in findings_data:
            if hasattr(f, 'rule_id'):
                msg = f.message.replace("|", "\\|").replace("\n", " ")
                loc = f.location.replace("|", "\\|")
                sev_icon = {"error": "!!!", "warning": "!!", "info": "i"}.get(f.severity, "")
                lines.append(f"| {f.rule_id} | {sev_icon} {f.severity} | {msg} | {loc} |")
            elif isinstance(f, dict):
                msg = f.get("message", "").replace("|", "\\|").replace("\n", " ")
                loc = f.get("location", "").replace("|", "\\|")
                lines.append(f"| {f.get('rule_id', '')} | {f.get('severity', '')} | {msg} | {loc} |")
    else:
        lines.append("No findings - great job!")
    lines.append("")

    # Tables
    lines.append("## Tables")
    lines.append("")
    for t in documentation.get("tables", []):
        hidden = " (Hidden)" if t.get("is_hidden") else ""
        lines.append(f"### {t['name']}{hidden}")
        lines.append("")
        lines.append(f"Mode: `{t.get('mode', 'import')}` | Columns: {t.get('column_count', 0)} | Measures: {t.get('measure_count', 0)}")
        lines.append("")

        if t.get("columns"):
            lines.append("| Column | Type | Data Type | Key |")
            lines.append("|--------|------|-----------|-----|")
            for c in t["columns"]:
                key = "Yes" if c.get("is_key") else ""
                lines.append(f"| {c['name']} | {c.get('type', 'data')} | `{c.get('data_type', '')}` | {key} |")
            lines.append("")

        if t.get("measures"):
            lines.append("**Measures:**")
            lines.append("")
            for m in t["measures"]:
                lines.append(f"- **{m['name']}**" + (f" (Format: `{m['format_string']}`)" if m.get("format_string") else ""))
                if m.get("expression"):
                    lines.append(f"  ```dax")
                    lines.append(f"  {m['expression']}")
                    lines.append(f"  ```")
            lines.append("")

    # Measure Dictionary
    lines.append("## Measure Dictionary")
    lines.append("")
    measures = documentation.get("measures", [])
    if measures:
        lines.append("| Measure | Table | Expression | Format |")
        lines.append("|---------|-------|------------|--------|")
        for m in measures:
            expr = m.get("expression", "")[:80]
            if len(m.get("expression", "")) > 80:
                expr += "..."
            expr = expr.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {m['name']} | {m.get('table', '')} | `{expr}` | `{m.get('format_string', '')}` |")
    lines.append("")

    # Relationships
    lines.append("## Relationships")
    lines.append("")
    rels = documentation.get("relationships", [])
    if rels:
        lines.append("| From | To | Cardinality | Cross Filter | Active |")
        lines.append("|------|----|-------------|--------------|--------|")
        for r in rels:
            card = f"{r.get('from_cardinality', '')}:{r.get('to_cardinality', '')}"
            active = "Yes" if r.get("is_active") else "No"
            lines.append(f"| {r['from_table']}[{r['from_column']}] | {r['to_table']}[{r['to_column']}] | {card} | {r.get('cross_filtering', '')} | {active} |")
    lines.append("")

    # Data Sources
    lines.append("## Data Sources")
    lines.append("")
    sources = documentation.get("sources", [])
    if sources:
        lines.append("| Table | Source | Detail | Mode |")
        lines.append("|-------|--------|--------|------|")
        for s in sources:
            lines.append(f"| {s.get('table', '')} | {s.get('source_type', '')} | {s.get('detail', '')} | {s.get('mode', '')} |")
    lines.append("")

    # KPI Suggestions
    if kpi_suggestions:
        lines.append("## Suggested KPIs")
        lines.append("")
        for kpi in kpi_suggestions:
            lines.append(f"### {kpi.get('name', '')}")
            lines.append(f"{kpi.get('description', '')}")
            lines.append("")
            lines.append("```dax")
            lines.append(kpi.get("dax", ""))
            lines.append("```")
            if kpi.get("format"):
                lines.append(f"Format: `{kpi['format']}`")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Generated by GridPulse*")

    return "\n".join(lines)
