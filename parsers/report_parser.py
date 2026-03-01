"""Parser for Power BI report definitions (PBIR-Legacy and PBIR)."""

import json
import os
from models import ReportDefinition, Page, Visual, Bookmark


def parse_report(report_dir: str) -> ReportDefinition:
    """Parse report from either PBIR-Legacy or PBIR format."""
    definition_dir = os.path.join(report_dir, "definition")
    pages_dir = os.path.join(definition_dir, "pages")

    # Check for PBIR enhanced format (definition/pages/ folder)
    if os.path.isdir(pages_dir):
        return _parse_pbir(definition_dir)

    # Fallback: PBIR-Legacy (single report.json)
    report_json_path = os.path.join(report_dir, "report.json")
    if os.path.exists(report_json_path):
        return _parse_pbir_legacy(report_json_path)

    # Also check definition/report.json (some PBIR-Legacy variants)
    report_json_def = os.path.join(definition_dir, "report.json")
    if os.path.exists(report_json_def):
        return _parse_pbir_legacy(report_json_def)

    return ReportDefinition()


def _parse_pbir(definition_dir: str) -> ReportDefinition:
    """Parse PBIR enhanced format with individual page/visual JSON files."""
    report = ReportDefinition()
    pages_dir = os.path.join(definition_dir, "pages")

    # Read report-level filters
    report_json_path = os.path.join(definition_dir, "report.json")
    if os.path.exists(report_json_path):
        with open(report_json_path, "r", encoding="utf-8-sig") as f:
            try:
                rdata = json.load(f)
                report.filters = rdata.get("filterConfig", {}).get("filters", [])
            except (json.JSONDecodeError, AttributeError):
                pass

    # Read page order
    pages_meta_path = os.path.join(pages_dir, "pages.json")
    page_order = []
    if os.path.exists(pages_meta_path):
        with open(pages_meta_path, "r", encoding="utf-8-sig") as f:
            try:
                pmeta = json.load(f)
                page_order = pmeta.get("pageOrder", [])
            except (json.JSONDecodeError, AttributeError):
                pass

    # Read bookmarks (PBIR)
    bookmarks_dir = os.path.join(definition_dir, "bookmarks")
    if os.path.isdir(bookmarks_dir):
        for bk_name in os.listdir(bookmarks_dir):
            bk_dir = os.path.join(bookmarks_dir, bk_name)
            bk_json = os.path.join(bk_dir, "bookmark.json") if os.path.isdir(bk_dir) else None
            if not bk_json:
                # Maybe it's a .json file directly
                if bk_name.endswith(".json"):
                    bk_json = os.path.join(bookmarks_dir, bk_name)
            if bk_json and os.path.exists(bk_json):
                try:
                    with open(bk_json, "r", encoding="utf-8-sig") as f:
                        bk_data = json.load(f)
                    report.bookmarks.append(Bookmark(
                        name=bk_data.get("name", bk_name),
                        display_name=bk_data.get("displayName", bk_data.get("name", bk_name)),
                        report_page=bk_data.get("explorationState", {}).get("activeSection", ""),
                    ))
                except (json.JSONDecodeError, AttributeError):
                    pass

    # Discover page folders
    page_folders = []
    if page_order:
        page_folders = page_order
    else:
        # Fallback: list directories
        for item in os.listdir(pages_dir):
            if os.path.isdir(os.path.join(pages_dir, item)):
                page_folders.append(item)

    for page_name in page_folders:
        page_dir = os.path.join(pages_dir, page_name)
        if not os.path.isdir(page_dir):
            continue

        page = Page(name=page_name)

        # Parse page.json
        page_json_path = os.path.join(page_dir, "page.json")
        if os.path.exists(page_json_path):
            with open(page_json_path, "r", encoding="utf-8-sig") as f:
                try:
                    pdata = json.load(f)
                    page.display_name = pdata.get("displayName", page_name)
                    page.filters = pdata.get("filterConfig", {}).get("filters", [])
                    page.visibility = pdata.get("visibility", "visible")

                    # Check for drillthrough/tooltip
                    if pdata.get("pageBinding"):
                        binding_type = pdata["pageBinding"].get("type", "")
                        if binding_type == "Drillthrough":
                            page.has_drillthrough = True
                        elif binding_type == "Tooltip":
                            page.is_tooltip = True
                except (json.JSONDecodeError, AttributeError):
                    page.display_name = page_name

        # Parse visuals
        visuals_dir = os.path.join(page_dir, "visuals")
        if os.path.isdir(visuals_dir):
            for visual_name in os.listdir(visuals_dir):
                visual_dir = os.path.join(visuals_dir, visual_name)
                if not os.path.isdir(visual_dir):
                    continue

                visual_json_path = os.path.join(visual_dir, "visual.json")
                if os.path.exists(visual_json_path):
                    visual = _parse_visual_json(visual_json_path, visual_name)
                    page.visuals.append(visual)

        report.pages.append(page)

    return report


def _parse_visual_json(path: str, default_name: str) -> Visual:
    """Parse a single visual.json file."""
    visual = Visual(name=default_name)
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            vdata = json.load(f)

        visual.visual_type = vdata.get("visual", {}).get("visualType", "")
        visual.filters = vdata.get("filterConfig", {}).get("filters", [])

        # Check for alt text
        vcobjects = vdata.get("visualContainerObjects", {})
        general = vcobjects.get("general", [])
        if general:
            for item in general:
                props = item.get("properties", {})
                if "altText" in props:
                    visual.has_alt_text = True
                    break

        # Extract field references for unused measures detection (F8)
        visual.field_references = _extract_field_refs(vdata)

    except (json.JSONDecodeError, KeyError):
        pass

    return visual


def _extract_field_refs(data: dict) -> list[str]:
    """Recursively extract field/measure references from visual config."""
    refs = set()
    _walk_for_refs(data, refs)
    return sorted(refs)


def _walk_for_refs(obj, refs: set):
    """Walk a JSON structure looking for field references."""
    if isinstance(obj, dict):
        # Look for "Column", "Measure", "Property" fields
        for key in ("Column", "Measure", "Property"):
            if key in obj:
                ref = obj[key]
                if isinstance(ref, dict):
                    name = ref.get("Property") or ref.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                    if isinstance(name, str) and name:
                        refs.add(name)
                elif isinstance(ref, str):
                    refs.add(ref)

        # Check for queryRef patterns
        if "queryRef" in obj:
            qr = obj["queryRef"]
            if isinstance(qr, str):
                # queryRef format is typically "Table.Measure"
                parts = qr.split(".")
                if len(parts) >= 2:
                    refs.add(parts[-1])

        for v in obj.values():
            _walk_for_refs(v, refs)
    elif isinstance(obj, list):
        for item in obj:
            _walk_for_refs(item, refs)


def _parse_pbir_legacy(report_json_path: str) -> ReportDefinition:
    """Parse PBIR-Legacy single report.json file."""
    report = ReportDefinition()

    try:
        with open(report_json_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return report

    # Report-level filters
    report.filters = data.get("filters", [])
    if isinstance(report.filters, str):
        try:
            report.filters = json.loads(report.filters)
        except json.JSONDecodeError:
            report.filters = []

    # Parse sections (pages)
    for section in data.get("sections", []):
        page = Page(
            name=section.get("name", ""),
            display_name=section.get("displayName", section.get("name", "")),
        )

        # Parse visual containers
        for vc in section.get("visualContainers", []):
            visual = Visual()

            # Config is a stringified JSON
            config_str = vc.get("config", "{}")
            try:
                config = json.loads(config_str) if isinstance(config_str, str) else config_str
                single_visual = config.get("singleVisual", {})
                visual.visual_type = single_visual.get("visualType", "")
                visual.name = config.get("name", "")
            except json.JSONDecodeError:
                config = {}

            # Filters
            filters_str = vc.get("filters", "[]")
            try:
                if isinstance(filters_str, str):
                    visual.filters = json.loads(filters_str)
                else:
                    visual.filters = filters_str or []
            except json.JSONDecodeError:
                visual.filters = []

            # Alt text check
            vcobjects = config.get("vcObjects", {})
            general = vcobjects.get("general", [])
            if general:
                for item in general:
                    props = item.get("properties", {})
                    if "altText" in props:
                        visual.has_alt_text = True
                        break

            # Extract field references (F8)
            visual.field_references = _extract_field_refs(config)

            page.visuals.append(visual)

        # Check page config for drillthrough/tooltip
        config_str = section.get("config", "{}")
        try:
            sec_config = json.loads(config_str) if isinstance(config_str, str) else config_str
            if sec_config.get("isDrillthrough"):
                page.has_drillthrough = True
            if sec_config.get("isTooltipPage"):
                page.is_tooltip = True
        except json.JSONDecodeError:
            pass

        # Visibility
        display_option = section.get("displayOption", 0)
        if section.get("visibility") == 1:
            page.visibility = "HiddenInViewMode"

        report.pages.append(page)

    # Parse bookmarks (PBIR-Legacy)
    config_str = data.get("config", "{}")
    try:
        report_config = json.loads(config_str) if isinstance(config_str, str) else config_str
        for bk in report_config.get("bookmarks", []):
            report.bookmarks.append(Bookmark(
                name=bk.get("name", ""),
                display_name=bk.get("displayName", bk.get("name", "")),
                report_page=bk.get("explorationState", {}).get("activeSection", ""),
            ))
    except (json.JSONDecodeError, AttributeError):
        pass

    return report
