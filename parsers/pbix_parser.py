"""PBIX parser: extracts report layout and Power Query M code from .pbix files.

A .pbix is a ZIP containing:
- Report/Layout: JSON report definition (pages, visuals, filters)
- DataMashup: Binary blob with embedded ZIP containing M code
- DataModel: Binary VertiPaq (NOT parseable without commercial tools)

This parser provides a "light" analysis with report + PQ data only.
"""

import io
import json
import re
import zipfile

from models import (
    SemanticModel, ReportDefinition, Table, Partition,
    Page, Visual, Bookmark,
)
from parsers.pbip_parser import PBIPParseResult


def parse_pbix(zip_path: str) -> PBIPParseResult:
    """Parse a .pbix file extracting report layout and M code."""
    result = PBIPParseResult()
    result.model_format = "pbix"
    result.report_format = "pbix"

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Extract project name from filename
            import os
            result.project_name = os.path.splitext(os.path.basename(zip_path))[0]

            # 1. Extract report layout
            report = _extract_report_layout(zf, names)
            if report:
                result.report = report

            # 2. Extract Power Query M code from DataMashup
            m_code = _extract_data_mashup(zf, names)
            tables = []
            if m_code:
                tables = _parse_m_code_to_tables(m_code)

            result.semantic_model = SemanticModel(tables=tables)

            if not tables and not report:
                result.errors.append(
                    "Could not extract data from PBIX file. "
                    "The file may be corrupted or in an unsupported format."
                )

    except zipfile.BadZipFile:
        result.errors.append("Invalid PBIX file (not a valid ZIP archive)")
    except Exception as e:
        result.errors.append(f"Error parsing PBIX: {e}")

    return result


def _extract_report_layout(zf: zipfile.ZipFile, names: list[str]) -> ReportDefinition | None:
    """Extract report definition from Report/Layout entry."""
    # Find the report layout entry
    layout_name = None
    for n in names:
        if n.lower() in ("report/layout", "report\\layout", "layout"):
            layout_name = n
            break

    if not layout_name:
        return None

    try:
        raw = zf.read(layout_name)
    except Exception:
        return None

    # Try multiple encodings (PBIX uses UTF-16-LE commonly)
    report_json = None
    for enc in ("utf-16-le", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            text = text.strip("\x00\ufeff \n\r\t")
            report_json = json.loads(text)
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    if not report_json:
        return None

    return _parse_report_json(report_json)


def _parse_report_json(data: dict) -> ReportDefinition:
    """Convert PBIX report JSON to ReportDefinition model."""
    report = ReportDefinition()

    sections = data.get("sections", [])
    for section in sections:
        page = Page(
            name=section.get("name", ""),
            display_name=section.get("displayName", section.get("name", "")),
        )

        # Parse visuals from visual containers
        containers = section.get("visualContainers", [])
        for vc in containers:
            visual = Visual()
            # Try to parse the config JSON string
            config_str = vc.get("config", "")
            if config_str and isinstance(config_str, str):
                try:
                    config = json.loads(config_str)
                    single_visual = config.get("singleVisual", {})
                    visual.visual_type = single_visual.get("visualType", "")
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(config_str, dict):
                single_visual = config_str.get("singleVisual", {})
                visual.visual_type = single_visual.get("visualType", "")

            # Check for filters
            filters_str = vc.get("filters", "[]")
            if filters_str and isinstance(filters_str, str):
                try:
                    vf = json.loads(filters_str)
                    visual.filters = vf if isinstance(vf, list) else []
                except (json.JSONDecodeError, TypeError):
                    pass

            page.visuals.append(visual)

        # Page-level filters
        page_filters_str = section.get("filters", "[]")
        if page_filters_str and isinstance(page_filters_str, str):
            try:
                pf = json.loads(page_filters_str)
                page.filters = pf if isinstance(pf, list) else []
            except (json.JSONDecodeError, TypeError):
                pass

        # Page visibility
        display_option = section.get("displayOption", 0)
        page.visibility = "hidden" if section.get("visibility", 0) == 1 else "visible"

        report.pages.append(page)

    # Report-level filters
    report_filters_str = data.get("filters", "[]")
    if report_filters_str and isinstance(report_filters_str, str):
        try:
            rf = json.loads(report_filters_str)
            report.filters = rf if isinstance(rf, list) else []
        except (json.JSONDecodeError, TypeError):
            pass

    # Bookmarks
    bookmarks_data = data.get("config", "")
    if bookmarks_data and isinstance(bookmarks_data, str):
        try:
            config = json.loads(bookmarks_data)
            bk_list = config.get("bookmarks", [])
            for bk in bk_list:
                report.bookmarks.append(Bookmark(
                    name=bk.get("name", ""),
                    display_name=bk.get("displayName", bk.get("name", "")),
                    report_page=bk.get("explorationState", {}).get("activeSection", ""),
                ))
        except (json.JSONDecodeError, TypeError):
            pass

    return report


def _extract_data_mashup(zf: zipfile.ZipFile, names: list[str]) -> str | None:
    """Extract M code from DataMashup entry."""
    mashup_name = None
    for n in names:
        if n.lower() in ("datamashup", "data mashup"):
            mashup_name = n
            break

    if not mashup_name:
        return None

    try:
        mashup_bytes = zf.read(mashup_name)
    except Exception:
        return None

    # DataMashup contains an inner ZIP after a binary header
    # Look for the PK signature (ZIP magic bytes)
    pk_idx = mashup_bytes.find(b"PK\x03\x04")
    if pk_idx < 0:
        # Fallback: try to find M code directly in the binary
        return _find_m_code_in_binary(mashup_bytes)

    try:
        inner_zip = zipfile.ZipFile(io.BytesIO(mashup_bytes[pk_idx:]))
        inner_names = inner_zip.namelist()

        # Look for M formula files
        for name in inner_names:
            lower = name.lower()
            if lower.endswith(".m") or "section1" in lower or "formulas" in lower:
                try:
                    content = inner_zip.read(name)
                    return _decode_m_content(content)
                except Exception:
                    continue

        # If no .m files found, try all files for M code
        for name in inner_names:
            try:
                content = inner_zip.read(name)
                decoded = _decode_m_content(content)
                if decoded and ("let" in decoded.lower() or "source" in decoded.lower()):
                    return decoded
            except Exception:
                continue

    except (zipfile.BadZipFile, Exception):
        # Inner ZIP parsing failed, try direct binary extraction
        return _find_m_code_in_binary(mashup_bytes)

    return None


def _decode_m_content(content: bytes) -> str | None:
    """Decode M code content trying multiple encodings."""
    for enc in ("utf-8", "utf-8-sig", "utf-16-le", "latin-1"):
        try:
            text = content.decode(enc)
            text = text.strip("\x00\ufeff")
            if text and len(text) > 5:
                return text
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def _find_m_code_in_binary(data: bytes) -> str | None:
    """Try to extract M code directly from binary DataMashup data."""
    # Look for common M code patterns in the binary
    for enc in ("utf-8", "utf-16-le"):
        try:
            text = data.decode(enc, errors="replace")
            # Find M code sections (starts with "section Section1")
            match = re.search(r"section\s+Section1.*?;(?:\s*$|\Z)", text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(0)

            # Try finding individual "let ... in" blocks
            blocks = re.findall(r"let\s.*?in\s+\w+", text, re.DOTALL | re.IGNORECASE)
            if blocks:
                return "\n\n".join(blocks)
        except Exception:
            continue
    return None


def _parse_m_code_to_tables(m_code: str) -> list[Table]:
    """Parse M code to extract table/query names and create Table objects."""
    tables = []

    # Pattern 1: shared QueryName = let ... in ...
    # Handles both plain names and #"Quoted Names"
    pattern = re.compile(
        r'shared\s+(?:#"([^"]+)"|(\w+))\s*=\s*(let\b.*?)\s*(?=shared\s|$)',
        re.DOTALL | re.IGNORECASE
    )
    matches = pattern.findall(m_code)

    if matches:
        for quoted_name, plain_name, expression in matches:
            name = quoted_name or plain_name
            if _is_internal_query(name):
                continue
            tables.append(Table(
                name=name,
                partitions=[Partition(
                    name="source",
                    mode="import",
                    source_type="m",
                    expression=expression.strip(),
                )],
            ))
    else:
        # Pattern 2: standalone let ... in blocks (no shared prefix)
        let_blocks = re.findall(
            r'(let\s+.*?in\s+\w[\w.]*)',
            m_code, re.DOTALL | re.IGNORECASE
        )
        for i, block in enumerate(let_blocks):
            # Try to extract a name from Source = ... assignments
            source_match = re.search(
                r'Source\s*=\s*\w+\.\w+\([^)]*"([^"]+)"',
                block
            )
            name = source_match.group(1) if source_match else f"Query{i + 1}"
            tables.append(Table(
                name=name,
                partitions=[Partition(
                    name="source",
                    mode="import",
                    source_type="m",
                    expression=block.strip(),
                )],
            ))

    return tables


def _is_internal_query(name: str) -> bool:
    """Check if a query name is an internal/system query."""
    internal_prefixes = (
        "DateTableTemplate", "LocalDateTable", "Calendar",
        "Parameter", "param_", "_"
    )
    return any(name.startswith(p) for p in internal_prefixes)
