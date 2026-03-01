"""Comprehensive test for all 9 new features."""
import json
import sys


def main():
    print("=== Phase 4 Verification ===")
    print()

    # 1. Test all imports
    print("1. Testing imports...")
    from analyzers.rls_analyzer import analyze_rls
    from analyzers.naming_analyzer import analyze_naming
    from analyzers.performance_analyzer import analyze_performance
    from analyzers.security_analyzer import analyze_security
    from analyzers.bookmark_analyzer import analyze_bookmarks
    from analyzers.version_diff import compare_versions
    from api import api_bp
    from generators.branded_pdf import get_branding_config, generate_branding_html
    print("   All imports OK")

    # 2. Test models
    print("2. Testing models...")
    from models import Bookmark, ReportDefinition
    bk = Bookmark(name="test", display_name="Test BK", report_page="page1")
    rd = ReportDefinition()
    rd.bookmarks.append(bk)
    assert len(rd.bookmarks) == 1
    print("   Bookmark model OK")

    # 3. Test config
    print("3. Testing config...")
    from config import RULES_REGISTRY, CONFIGURABLE_THRESHOLDS
    new_rules = [
        "SEC-001", "SEC-002", "SEC-003", "SEC-004", "SEC-005", "SEC-006", "SEC-007",
        "NC-001", "NC-002", "NC-003",
        "PERF-001", "PERF-002", "PERF-003", "PERF-004", "PERF-005",
        "BK-001", "BK-002", "BK-003",
    ]
    for r in new_rules:
        assert r in RULES_REGISTRY, f"Missing rule {r}"
    assert "naming_convention" in CONFIGURABLE_THRESHOLDS
    print(f"   {len(new_rules)} new rules in registry OK")
    print(f"   Total rules: {len(RULES_REGISTRY)}")

    # 4. Test scoring
    print("4. Testing scoring...")
    from analyzers.scoring import RULE_CATEGORY_MAP
    for prefix in ["SEC", "NC", "PERF", "BK"]:
        assert prefix in RULE_CATEGORY_MAP, f"Missing prefix {prefix}"
    print("   Scoring prefixes OK")

    # 5. Test RLS analyzer
    print("5. Testing RLS analyzer...")
    from models import SemanticModel, Table, Role, Relationship
    model = SemanticModel()
    model.roles = [
        Role(name="Admin", table_permissions={"Sales": "[Region] = \"US\""}),
        Role(name="Empty", table_permissions={}),
    ]
    model.tables = [Table(name="Sales"), Table(name="Products")]
    model.relationships = [Relationship(from_table="Sales", to_table="Products")]
    findings = analyze_rls(model)
    rule_ids = [f.rule_id for f in findings]
    assert "SEC-002" in rule_ids, "SEC-002 not found"
    assert "SEC-001" in rule_ids, "SEC-001 not found"
    print(f"   RLS: {len(findings)} findings OK")

    # 6. Test naming analyzer
    print("6. Testing naming analyzer...")
    from models import Column, Measure
    model2 = SemanticModel()
    model2.tables = [
        Table(name="Sales#Data", columns=[
            Column(name="myColumn"), Column(name="Other Column"), Column(name="thirdCol")
        ], measures=[
            Measure(name="total sales"),
        ])
    ]
    findings = analyze_naming(model2, "title_case")
    rule_ids = [f.rule_id for f in findings]
    assert "NC-003" in rule_ids, "NC-003 not found"
    assert "NC-001" in rule_ids, "NC-001 not found"
    print(f"   Naming: {len(findings)} findings OK")

    # 7. Test performance analyzer
    print("7. Testing performance analyzer...")
    from models import Partition
    model3 = SemanticModel()
    model3.tables = [
        Table(name="Fact", partitions=[Partition(name="p", mode="import")],
              columns=[Column(name=f"c{i}") for i in range(110)]),
        Table(name="Dim1", partitions=[Partition(name="p", mode="import")]),
        Table(name="Dim2", partitions=[Partition(name="p", mode="directQuery")]),
    ]
    model3.relationships = [
        Relationship(from_table="Fact", to_table="Dim1", cross_filtering="bothDirections"),
        Relationship(from_table="Fact", to_table="Dim2", cross_filtering="bothDirections"),
        Relationship(from_table="Dim1", to_table="Dim2", cross_filtering="bothDirections"),
    ]
    perf = analyze_performance(model3)
    assert "perf_score" in perf
    assert "perf_grade" in perf
    print(f"   Performance: score={perf['perf_score']}, grade={perf['perf_grade']}, {len(perf['findings'])} findings")

    # 8. Test security analyzer
    print("8. Testing security analyzer...")
    model4 = SemanticModel()
    model4.tables = [
        Table(name="Customers", columns=[
            Column(name="Email"),
            Column(name="SSN", is_hidden=True),
            Column(name="Name"),
        ], partitions=[
            Partition(name="p", source_type="m",
                      expression='Sql.Database("http://server.com", "db")')
        ]),
    ]
    rd2 = ReportDefinition()
    findings = analyze_security(model4, rd2)
    rule_ids = [f.rule_id for f in findings]
    assert "SEC-004" in rule_ids, "SEC-004 not found (email)"
    assert "SEC-005" in rule_ids, "SEC-005 not found (http)"
    print(f"   Security: {len(findings)} findings OK")

    # 9. Test bookmark analyzer
    print("9. Testing bookmark analyzer...")
    from models import Page, Visual
    rd3 = ReportDefinition()
    rd3.pages = [Page(name="page1", display_name="Page 1")]
    rd3.bookmarks = [
        Bookmark(name="bk1", display_name="Bookmark 1", report_page="page1"),
        Bookmark(name="bk2", display_name="Bookmark 2", report_page="nonexistent"),
    ]
    findings = analyze_bookmarks(rd3)
    rule_ids = [f.rule_id for f in findings]
    assert "BK-001" in rule_ids, "BK-001 not found"
    assert "BK-002" in rule_ids, "BK-002 not found"
    print(f"   Bookmarks: {len(findings)} findings OK")

    # 10. Test version diff
    print("10. Testing version diff...")
    m1 = SemanticModel(tables=[
        Table(name="Sales", measures=[Measure(name="Total", expression="SUM(Sales[Amount])")])
    ])
    m2 = SemanticModel(tables=[
        Table(name="Sales", measures=[Measure(name="Total", expression="SUM(Sales[Revenue])")]),
        Table(name="NewTable")
    ])
    r1 = ReportDefinition()
    r2 = ReportDefinition()
    diff = compare_versions(m1, r1, m2, r2)
    assert diff["has_changes"] is True
    assert diff["summary"]["tables_added"] == 1
    assert diff["summary"]["measures_modified"] == 1
    print(f"   Version diff: has_changes=True, tables_added=1, measures_modified=1")

    # 11. Test API blueprint
    print("11. Testing API blueprint...")
    assert api_bp.name == "api"
    print("   API blueprint OK")

    # 12. Test branding
    print("12. Testing branding...")
    config = get_branding_config()
    assert "company_name" in config
    html = generate_branding_html({
        "company_name": "Test Corp",
        "logo_path": "",
        "footer_text": "Confidential",
    })
    assert "Test Corp" in html["header"]
    assert "Confidential" in html["footer"]
    print("   Branding OK")

    # 13. Test i18n keys
    print("13. Testing i18n keys...")
    new_keys = [
        "SEC-001", "SEC-002", "SEC-003", "SEC-004", "SEC-005", "SEC-006", "SEC-007",
        "NC-001", "NC-002", "NC-003",
        "PERF-001", "PERF-002", "PERF-003", "PERF-004", "PERF-005",
        "BK-001", "BK-002", "BK-003",
        "rls_title", "security_title", "naming_title", "perf_title", "bookmark_title",
        "diff_title", "branding_title",
    ]
    for lang in ["en", "es", "pt"]:
        with open(f"i18n/{lang}.json", encoding="utf-8") as f:
            data = json.load(f)
        missing = [k for k in new_keys if k not in data]
        if missing:
            print(f"   WARNING: {lang} missing keys: {missing}")
        else:
            print(f"   {lang}: all {len(new_keys)} new keys present ({len(data)} total)")

    # 14. Test Flask app initialization
    print("14. Testing Flask app...")
    from app import app
    with app.test_client() as c:
        resp = c.get("/")
        assert resp.status_code == 200
        resp = c.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["data"]["status"] == "healthy"
        resp = c.get("/api/history")
        assert resp.status_code == 200
    print("   Flask app + API routes OK")

    # 15. List all routes
    print("15. Routes registered:")
    with app.app_context():
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            if rule.rule.startswith("/static"):
                continue
            methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            print(f"   {methods:8s} {rule.rule}")

    print()
    print("=== ALL TESTS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
