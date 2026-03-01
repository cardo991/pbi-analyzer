"""Multi-file comparison analyzer."""


def compare_analyses(results: list[dict]) -> dict:
    """Compare multiple analysis results.

    Args:
        results: list of analysis result dicts from _run_analysis()

    Returns:
        For 2 files: side-by-side comparison dict
        For 3+ files: consolidated ranking dict
    """
    if len(results) < 2:
        return {"mode": "single", "results": results}

    if len(results) == 2:
        return _compare_two(results[0], results[1])

    return _consolidate_many(results)


def _compare_two(r1: dict, r2: dict) -> dict:
    """Side-by-side comparison of two analyses."""
    score_delta = r2["score"]["total_score"] - r1["score"]["total_score"]

    # Category deltas
    cat_changes = {}
    for cat in r1["score"].get("category_scores", {}):
        s1 = r1["score"]["category_scores"].get(cat, 0)
        s2 = r2["score"]["category_scores"].get(cat, 0)
        cat_changes[cat] = {"before": s1, "after": s2, "delta": s2 - s1}

    # Finding differences
    findings1_keys = {(f.rule_id, f.location) for f in r1.get("findings", [])}
    findings2_keys = {(f.rule_id, f.location) for f in r2.get("findings", [])}

    new_findings = [f for f in r2.get("findings", []) if (f.rule_id, f.location) not in findings1_keys]
    removed_findings = [f for f in r1.get("findings", []) if (f.rule_id, f.location) not in findings2_keys]

    return {
        "mode": "comparison",
        "result1": r1,
        "result2": r2,
        "score_delta": round(score_delta, 1),
        "category_changes": cat_changes,
        "new_findings": new_findings,
        "removed_findings": removed_findings,
    }


def _consolidate_many(results: list[dict]) -> dict:
    """Consolidated dashboard for 3+ analyses."""
    # Sort by score descending
    ranked = sorted(results, key=lambda r: r["score"]["total_score"], reverse=True)

    summary = []
    for i, r in enumerate(ranked, 1):
        summary.append({
            "rank": i,
            "project_name": r["project_name"],
            "total_score": r["score"]["total_score"],
            "grade": r["score"]["grade"],
            "findings_count": len(r.get("findings", [])),
            "tables_count": r.get("documentation", {}).get("overview", {}).get("total_tables", 0),
            "measures_count": r.get("documentation", {}).get("overview", {}).get("total_measures", 0),
        })

    # Category averages
    cat_averages = {}
    for cat in ("data_model", "dax", "power_query", "report"):
        scores = [r["score"]["category_scores"].get(cat, 0) for r in results]
        cat_averages[cat] = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "mode": "consolidated",
        "results": ranked,
        "ranking": summary,
        "average_score": round(sum(r["score"]["total_score"] for r in results) / len(results), 1),
        "category_averages": cat_averages,
        "total_files": len(results),
    }
