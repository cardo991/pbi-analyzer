"""Report/visual analysis rules (RP-001 through RP-006)."""

from models import ReportDefinition, Finding
from config import MAX_VISUALS_PER_PAGE, MAX_PAGES, MAX_FILTERS_PER_VISUAL, HEAVY_VISUAL_TYPES


def analyze_report(report: ReportDefinition) -> list[Finding]:
    """Run all report rules against the report definition."""
    findings = []

    findings.extend(_check_rp001(report))
    findings.extend(_check_rp002(report))
    findings.extend(_check_rp003(report))
    findings.extend(_check_rp004(report))
    findings.extend(_check_rp005(report))
    findings.extend(_check_rp006(report))

    return findings


def _check_rp001(report: ReportDefinition) -> list[Finding]:
    """RP-001: Too many visuals per page."""
    results = []
    for page in report.pages:
        count = len(page.visuals)
        if count > MAX_VISUALS_PER_PAGE:
            results.append(Finding(
                rule_id="RP-001",
                category="report",
                severity="warning",
                message="RP-001",
                location=f"Page '{page.display_name or page.name}'",
                details={
                    "page": page.display_name or page.name,
                    "count": count,
                    "threshold": MAX_VISUALS_PER_PAGE,
                },
            ))
    return results


def _check_rp002(report: ReportDefinition) -> list[Finding]:
    """RP-002: Too many pages."""
    count = len(report.pages)
    if count > MAX_PAGES:
        return [Finding(
            rule_id="RP-002",
            category="report",
            severity="info",
            message="RP-002",
            location="Report",
            details={"count": count, "threshold": MAX_PAGES},
        )]
    return []


def _check_rp003(report: ReportDefinition) -> list[Finding]:
    """RP-003: Heavy visual types."""
    results = []
    for page in report.pages:
        for visual in page.visuals:
            if visual.visual_type in HEAVY_VISUAL_TYPES:
                results.append(Finding(
                    rule_id="RP-003",
                    category="report",
                    severity="info",
                    message="RP-003",
                    location=f"Page '{page.display_name or page.name}'",
                    details={
                        "type": visual.visual_type,
                        "page": page.display_name or page.name,
                    },
                ))
    return results


def _check_rp004(report: ReportDefinition) -> list[Finding]:
    """RP-004: Complex visual-level filters."""
    results = []
    for page in report.pages:
        for visual in page.visuals:
            filter_count = len(visual.filters) if visual.filters else 0
            if filter_count > MAX_FILTERS_PER_VISUAL:
                results.append(Finding(
                    rule_id="RP-004",
                    category="report",
                    severity="info",
                    message="RP-004",
                    location=f"Page '{page.display_name or page.name}'",
                    details={
                        "page": page.display_name or page.name,
                        "count": filter_count,
                        "threshold": MAX_FILTERS_PER_VISUAL,
                    },
                ))
    return results


def _check_rp005(report: ReportDefinition) -> list[Finding]:
    """RP-005: Tooltip/drillthrough page not hidden."""
    results = []
    for page in report.pages:
        is_special = page.has_drillthrough or page.is_tooltip
        is_hidden = page.visibility.lower() in ("hiddeninviewmode", "hidden")
        if is_special and not is_hidden:
            results.append(Finding(
                rule_id="RP-005",
                category="report",
                severity="info",
                message="RP-005",
                location=f"Page '{page.display_name or page.name}'",
                details={"page": page.display_name or page.name},
            ))
    return results


def _check_rp006(report: ReportDefinition) -> list[Finding]:
    """RP-006: Missing alt text."""
    results = []
    for page in report.pages:
        for visual in page.visuals:
            if not visual.has_alt_text and visual.visual_type:
                results.append(Finding(
                    rule_id="RP-006",
                    category="report",
                    severity="info",
                    message="RP-006",
                    location=f"Page '{page.display_name or page.name}'",
                    details={"page": page.display_name or page.name},
                ))
    return results
