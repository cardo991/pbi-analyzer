"""Executive summary generator."""


def generate_executive_summary(documentation: dict, score: dict, findings: list, lang: str = "en") -> dict:
    """Generate an executive summary from analysis results.

    Returns a dict with:
        total_tables, total_measures, total_relationships, total_findings,
        score, grade, attention_areas, paragraph
    """
    overview = documentation.get("overview", {})
    tables = overview.get("total_tables", 0)
    measures = overview.get("total_measures", 0)
    relationships = overview.get("total_relationships", 0)
    total_findings = len(findings)

    # Identify attention areas by category
    category_counts = {}
    for f in findings:
        if f.severity in ("error", "warning"):
            cat = f.category
            category_counts[cat] = category_counts.get(cat, 0) + 1

    # Sort by count descending
    sorted_areas = sorted(category_counts.items(), key=lambda x: -x[1])

    cat_labels = {
        "en": {"data_model": "Data Model", "dax": "DAX", "power_query": "Power Query", "report": "Report"},
        "es": {"data_model": "Modelo de Datos", "dax": "DAX", "power_query": "Power Query", "report": "Reporte"},
        "pt": {"data_model": "Modelo de Dados", "dax": "DAX", "power_query": "Power Query", "report": "Relatorio"},
    }
    labels = cat_labels.get(lang, cat_labels["en"])
    attention_areas = [f"{labels.get(cat, cat)} ({count})" for cat, count in sorted_areas]

    return {
        "total_tables": tables,
        "total_measures": measures,
        "total_relationships": relationships,
        "total_findings": total_findings,
        "score": score.get("total_score", 0),
        "grade": score.get("grade", "F"),
        "attention_areas": attention_areas,
        "has_issues": total_findings > 0,
    }
