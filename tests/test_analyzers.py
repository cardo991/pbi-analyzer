"""Test all analyzers with sample data."""

import os
import sys
import zipfile
import tempfile

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parsers.pbip_parser import parse_pbip_zip
from analyzers.dax_analyzer import analyze_dax
from analyzers.pq_analyzer import analyze_power_query
from analyzers.model_analyzer import analyze_model
from analyzers.report_analyzer import analyze_report
from analyzers.scoring import calculate_score


def create_test_zip():
    """Create a ZIP from the sample_data folder."""
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(sample_dir):
            for f in files:
                full_path = os.path.join(root, f)
                arcname = os.path.relpath(full_path, sample_dir)
                zf.write(full_path, arcname)

    return tmp.name


def main():
    print("=" * 60)
    print("PBI Analyzer - Test Run")
    print("=" * 60)

    # Create ZIP and parse
    zip_path = create_test_zip()
    try:
        result = parse_pbip_zip(zip_path)
    finally:
        os.unlink(zip_path)

    print(f"\nProject: {result.project_name}")
    print(f"Model format: {result.model_format}")
    print(f"Report format: {result.report_format}")
    print(f"Parse errors: {result.errors}")

    model = result.semantic_model
    report = result.report

    print(f"\nTables: {len(model.tables)}")
    for t in model.tables:
        print(f"  - {t.name}: {len(t.columns)} cols, {len(t.measures)} measures")

    print(f"Relationships: {len(model.relationships)}")
    print(f"Pages: {len(report.pages)}")
    for p in report.pages:
        print(f"  - {p.display_name}: {len(p.visuals)} visuals")

    # Run analyzers
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)

    findings = []
    dax_findings = analyze_dax(model)
    pq_findings = analyze_power_query(model)
    model_findings = analyze_model(model)
    report_findings = analyze_report(report)
    findings.extend(dax_findings)
    findings.extend(pq_findings)
    findings.extend(model_findings)
    findings.extend(report_findings)

    print(f"\nDAX findings: {len(dax_findings)}")
    for f in dax_findings:
        print(f"  [{f.severity}] {f.rule_id}: {f.location}")

    print(f"\nPQ findings: {len(pq_findings)}")
    for f in pq_findings:
        print(f"  [{f.severity}] {f.rule_id}: {f.location} {f.details}")

    print(f"\nModel findings: {len(model_findings)}")
    for f in model_findings:
        print(f"  [{f.severity}] {f.rule_id}: {f.location}")

    print(f"\nReport findings: {len(report_findings)}")
    for f in report_findings:
        print(f"  [{f.severity}] {f.rule_id}: {f.location}")

    # Score
    score = calculate_score(findings)
    print(f"\n{'=' * 60}")
    print(f"HEALTH SCORE: {score['total_score']}/100 (Grade: {score['grade']})")
    print(f"{'=' * 60}")
    for cat, s in score["category_scores"].items():
        mx = score["category_max"][cat]
        print(f"  {cat}: {s}/{mx}")

    print(f"\nTotal findings: {len(findings)}")
    print("DONE!")


if __name__ == "__main__":
    main()
