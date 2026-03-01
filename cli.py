#!/usr/bin/env python3
"""PBI Analyzer - CLI Mode.

Usage:
    python cli.py analyze project.zip [options]

Options:
    --format json|text    Output format (default: text)
    --lang en|es|pt       Language for messages (default: en)
    --output FILE         Write output to file instead of stdout
    --min-score N         Exit with code 1 if score is below N (for CI/CD)
"""

import argparse
import json
import os
import sys
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from parsers.pbip_parser import parse_pbip_zip
from analyzers.dax_analyzer import analyze_dax
from analyzers.pq_analyzer import analyze_power_query
from analyzers.model_analyzer import analyze_model
from analyzers.report_analyzer import analyze_report
from analyzers.scoring import calculate_score
from analyzers.suggestions import generate_kpi_suggestions, generate_dax_improvements
from analyzers.rls_analyzer import analyze_rls
from analyzers.naming_analyzer import analyze_naming
from analyzers.performance_analyzer import analyze_performance
from analyzers.security_analyzer import analyze_security
from analyzers.bookmark_analyzer import analyze_bookmarks
from generators.documentation import generate_documentation


def _load_translations(lang: str) -> dict:
    """Load translation file for the given language."""
    i18n_dir = os.path.join(os.path.dirname(__file__), "i18n")
    lang_path = os.path.join(i18n_dir, f"{lang}.json")
    if not os.path.exists(lang_path):
        lang_path = os.path.join(i18n_dir, "en.json")
    with open(lang_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _translate(translations: dict, key: str, **kwargs) -> str:
    """Get translated string."""
    text = translations.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def run_analysis(zip_path: str, lang: str = "en", disabled_rules: list | None = None) -> dict:
    """Run the full analysis pipeline on a ZIP file.

    Returns a dict with all analysis results.
    """
    translations = _load_translations(lang)

    result = parse_pbip_zip(zip_path)

    if result.errors and not result.semantic_model.tables:
        return {"error": result.errors[0] if result.errors else "No valid PBIP project found"}

    # Run analyzers
    findings = []
    findings.extend(analyze_dax(result.semantic_model))
    findings.extend(analyze_power_query(result.semantic_model))
    findings.extend(analyze_model(result.semantic_model))
    findings.extend(analyze_report(result.report))
    findings.extend(analyze_rls(result.semantic_model))
    findings.extend(analyze_security(result.semantic_model, result.report))
    findings.extend(analyze_bookmarks(result.report))
    findings.extend(analyze_naming(result.semantic_model))

    # Performance
    perf = analyze_performance(result.semantic_model)
    findings.extend(perf["findings"])

    # Filter disabled rules
    if disabled_rules:
        findings = [f for f in findings if f.rule_id not in disabled_rules]

    # Enrich with DAX improvements
    findings = generate_dax_improvements(findings, result.semantic_model, lang)

    # Translate messages
    for f in findings:
        f.message = _translate(translations, f.rule_id, **f.details)

    # Score
    score = calculate_score(findings)

    # Documentation
    documentation = generate_documentation(result.semantic_model, result.report)

    # KPI suggestions
    kpi_suggestions = generate_kpi_suggestions(result.semantic_model, lang)

    # DAX improvements
    dax_improvements = [f for f in findings if f.category == "dax" and f.details.get("suggestion")]

    return {
        "project_name": result.project_name,
        "model_format": result.model_format,
        "report_format": result.report_format,
        "score": score,
        "findings": findings,
        "documentation": documentation,
        "kpi_suggestions": kpi_suggestions,
        "dax_improvements": dax_improvements,
        "parse_errors": result.errors,
    }


def format_text(result: dict) -> str:
    """Format analysis results as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  PBI Analyzer - {result['project_name']}")
    lines.append("=" * 60)
    lines.append("")

    score = result["score"]
    lines.append(f"  Score: {score['total_score']}/100  Grade: {score['grade']}")
    lines.append("")

    lines.append("  Category Scores:")
    cat_labels = {"data_model": "Data Model", "dax": "DAX", "power_query": "Power Query", "report": "Report"}
    for cat, cat_score in score.get("category_scores", {}).items():
        cat_max = score.get("category_max", {}).get(cat, 0)
        bar_len = int(cat_score / cat_max * 20) if cat_max > 0 else 0
        bar = "#" * bar_len + "-" * (20 - bar_len)
        lines.append(f"    {cat_labels.get(cat, cat):15s} [{bar}] {cat_score}/{cat_max}")
    lines.append("")

    # Overview
    overview = result.get("documentation", {}).get("overview", {})
    lines.append(f"  Tables: {overview.get('total_tables', 0)}  "
                 f"Measures: {overview.get('total_measures', 0)}  "
                 f"Relationships: {overview.get('total_relationships', 0)}  "
                 f"Pages: {overview.get('total_pages', 0)}")
    lines.append("")

    # Findings
    findings = result.get("findings", [])
    lines.append(f"  Findings: {len(findings)}")
    lines.append("-" * 60)
    for f in findings:
        sev_icon = {"error": "[!]", "warning": "[W]", "info": "[i]"}.get(f.severity, "[ ]")
        lines.append(f"  {sev_icon} {f.rule_id:8s} {f.message}")
        if f.location:
            lines.append(f"      @ {f.location}")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def format_json(result: dict) -> str:
    """Format analysis results as JSON."""
    output = {
        "project_name": result["project_name"],
        "model_format": result.get("model_format"),
        "report_format": result.get("report_format"),
        "score": {
            "total_score": result["score"]["total_score"],
            "grade": result["score"]["grade"],
            "category_scores": result["score"].get("category_scores", {}),
        },
        "overview": result.get("documentation", {}).get("overview", {}),
        "findings_count": len(result.get("findings", [])),
        "findings": [
            {
                "rule_id": f.rule_id,
                "category": f.category,
                "severity": f.severity,
                "message": f.message,
                "location": f.location,
            }
            for f in result.get("findings", [])
        ],
        "kpi_suggestions": result.get("kpi_suggestions", []),
        "parse_errors": result.get("parse_errors", []),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="PBI Analyzer - Power BI Report Health Check (CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a PBIP project ZIP")
    analyze_parser.add_argument("file", help="Path to the PBIP project ZIP file")
    analyze_parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")
    analyze_parser.add_argument("--lang", choices=["en", "es", "pt"], default="en", help="Language")
    analyze_parser.add_argument("--output", "-o", help="Output file path")
    analyze_parser.add_argument("--min-score", type=int, help="Minimum score threshold (exit 1 if below)")
    analyze_parser.add_argument("--disable-rules", nargs="*", help="Rule IDs to disable")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "analyze":
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(2)

        if not args.file.lower().endswith(".zip"):
            print("Error: File must be a ZIP archive", file=sys.stderr)
            sys.exit(2)

        # Run analysis
        result = run_analysis(args.file, lang=args.lang, disabled_rules=args.disable_rules)

        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(2)

        # Format output
        if args.format == "json":
            output = format_json(result)
        else:
            output = format_text(result)

        # Write output
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Output written to: {args.output}")
        else:
            print(output)

        # Check min-score threshold
        if args.min_score is not None:
            actual_score = result["score"]["total_score"]
            if actual_score < args.min_score:
                print(f"\nScore {actual_score} is below minimum threshold {args.min_score}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
