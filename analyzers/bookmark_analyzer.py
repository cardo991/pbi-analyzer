"""Bookmark and interaction analysis for Power BI reports."""

from models import ReportDefinition, Finding

MAX_BOOKMARKS = 20


def analyze_bookmarks(report: ReportDefinition) -> list[Finding]:
    """Analyze bookmarks in the report.

    Rules:
        BK-001: Bookmark not linked to any visual action (orphan)
        BK-002: Bookmark targets a non-existent page
        BK-003: Too many bookmarks (>20)
    """
    findings = []

    if not report.bookmarks:
        return findings

    # BK-003: Too many bookmarks
    if len(report.bookmarks) > MAX_BOOKMARKS:
        findings.append(Finding(
            rule_id="BK-003",
            category="report",
            severity="info",
            message="",
            location="Report bookmarks",
            details={"count": len(report.bookmarks), "threshold": MAX_BOOKMARKS},
        ))

    # Build set of existing page names
    page_names = {p.name for p in report.pages}
    page_display_names = {p.display_name for p in report.pages}
    all_page_ids = page_names | page_display_names

    # Collect bookmark names referenced by visuals (actions/navigation)
    referenced_bookmarks = set()
    for page in report.pages:
        for visual in page.visuals:
            # field_references may contain bookmark references from action configs
            # We also need to check visual configs for action/bookmark bindings
            for ref in visual.field_references:
                referenced_bookmarks.add(ref.lower())

    for bookmark in report.bookmarks:
        bk_name = bookmark.name
        bk_display = bookmark.display_name or bk_name

        # BK-002: Bookmark targets non-existent page
        if bookmark.report_page and bookmark.report_page not in all_page_ids:
            findings.append(Finding(
                rule_id="BK-002",
                category="report",
                severity="info",
                message="",
                location=f"Bookmark '{bk_display}'",
                details={"name": bk_display, "page": bookmark.report_page},
            ))

        # BK-001: Orphan bookmark (not referenced by any visual)
        # Check if bookmark name appears in any visual references
        is_referenced = (
            bk_name.lower() in referenced_bookmarks
            or bk_display.lower() in referenced_bookmarks
        )
        if not is_referenced:
            findings.append(Finding(
                rule_id="BK-001",
                category="report",
                severity="info",
                message="",
                location=f"Bookmark '{bk_display}'",
                details={"name": bk_display},
            ))

    return findings
