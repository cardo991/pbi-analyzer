"""Main PBIP parser: extracts ZIP, detects format, routes to correct parsers."""

import os
import tempfile
import zipfile

from models import SemanticModel, ReportDefinition
from parsers.bim_parser import parse_bim
from parsers.tmdl_parser import parse_tmdl
from parsers.report_parser import parse_report


class PBIPParseResult:
    """Result of parsing a PBIP project."""

    def __init__(self):
        self.semantic_model: SemanticModel = SemanticModel()
        self.report: ReportDefinition = ReportDefinition()
        self.project_name: str = ""
        self.model_format: str = ""  # "tmsl" or "tmdl"
        self.report_format: str = ""  # "pbir-legacy" or "pbir"
        self.errors: list[str] = []


def parse_pbip_zip(zip_path: str) -> PBIPParseResult:
    """Extract and parse a PBIP project from a ZIP file."""
    result = PBIPParseResult()

    # Detect PBIX format (contains DataMashup/Report/Layout instead of PBIP structure)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names_lower = [n.lower().replace("\\", "/") for n in zf.namelist()]
            is_pbix = any(
                n in ("datamashup", "report/layout", "layout")
                for n in names_lower
            )
            if is_pbix:
                from parsers.pbix_parser import parse_pbix
                return parse_pbix(zip_path)
    except zipfile.BadZipFile:
        result.errors.append("Invalid ZIP file")
        return result

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Extract ZIP
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)
        except zipfile.BadZipFile:
            result.errors.append("Invalid ZIP file")
            return result

        # Find the project root (look for .SemanticModel and .Report folders)
        semantic_dir, report_dir, project_name = _find_project_dirs(tmp_dir)

        if not semantic_dir and not report_dir:
            result.errors.append(
                "No valid PBIP project found. Expected folders ending with "
                "'.SemanticModel' and/or '.Report'."
            )
            return result

        result.project_name = project_name

        # Parse semantic model
        if semantic_dir:
            try:
                result.semantic_model, result.model_format = _parse_semantic_model(semantic_dir)
            except Exception as e:
                result.errors.append(f"Error parsing semantic model: {e}")

        # Parse report
        if report_dir:
            try:
                result.report = parse_report(report_dir)
                # Detect report format
                definition_dir = os.path.join(report_dir, "definition")
                pages_dir = os.path.join(definition_dir, "pages")
                result.report_format = "pbir" if os.path.isdir(pages_dir) else "pbir-legacy"
            except Exception as e:
                result.errors.append(f"Error parsing report: {e}")

    return result


def _find_project_dirs(root: str) -> tuple[str | None, str | None, str]:
    """Walk directory tree to find .SemanticModel and .Report folders."""
    semantic_dir = None
    report_dir = None
    project_name = ""

    # Walk up to 3 levels deep to find the folders
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.replace(root, "").count(os.sep)
        if depth > 3:
            dirnames.clear()
            continue

        for d in dirnames:
            full_path = os.path.join(dirpath, d)
            if d.endswith(".SemanticModel"):
                semantic_dir = full_path
                project_name = d.replace(".SemanticModel", "")
            elif d.endswith(".Dataset"):
                semantic_dir = full_path
                if not project_name:
                    project_name = d.replace(".Dataset", "")
            elif d.endswith(".Report"):
                report_dir = full_path
                if not project_name:
                    project_name = d.replace(".Report", "")

        # Also check for .pbip file to get project name
        for f in filenames:
            if f.endswith(".pbip"):
                if not project_name:
                    project_name = f.replace(".pbip", "")

    return semantic_dir, report_dir, project_name


def _parse_semantic_model(semantic_dir: str) -> tuple[SemanticModel, str]:
    """Parse semantic model, auto-detecting TMSL vs TMDL format."""
    # Check for TMDL format (definition/ folder with .tmdl files)
    definition_dir = os.path.join(semantic_dir, "definition")
    tables_dir = os.path.join(definition_dir, "tables")

    if os.path.isdir(tables_dir):
        tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
        if tmdl_files:
            return parse_tmdl(definition_dir), "tmdl"

    # Check for model.tmdl directly in definition/
    if os.path.isdir(definition_dir):
        model_tmdl = os.path.join(definition_dir, "model.tmdl")
        if os.path.exists(model_tmdl):
            return parse_tmdl(definition_dir), "tmdl"

    # Fallback: TMSL format (model.bim)
    bim_path = os.path.join(semantic_dir, "model.bim")
    if os.path.exists(bim_path):
        return parse_bim(bim_path), "tmsl"

    # Also check inside definition/
    bim_path_def = os.path.join(definition_dir, "model.bim")
    if os.path.exists(bim_path_def):
        return parse_bim(bim_path_def), "tmsl"

    raise FileNotFoundError(
        "No model.bim or TMDL definition found in semantic model directory"
    )
