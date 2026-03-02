"""GridPulse - Flask web application."""

import hashlib
import json
import os
import re
import sys
import tempfile

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_file, jsonify,
)

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from parsers.pbip_parser import parse_pbip_zip
from parsers.theme_parser import parse_theme
from analyzers.dax_analyzer import analyze_dax
from analyzers.pq_analyzer import analyze_power_query
from analyzers.model_analyzer import analyze_model
from analyzers.report_analyzer import analyze_report
from analyzers.scoring import calculate_score
from analyzers.suggestions import generate_kpi_suggestions, generate_dax_improvements
from analyzers.dax_complexity import analyze_dax_complexity
from analyzers.unused_measures import analyze_unused_measures
from analyzers.lineage import build_lineage
from analyzers.theme_analyzer import analyze_theme
from analyzers.comparison import compare_analyses as compare_multi
from analyzers.rls_analyzer import analyze_rls
from analyzers.naming_analyzer import analyze_naming
from analyzers.performance_analyzer import analyze_performance
from analyzers.security_analyzer import analyze_security
from analyzers.bookmark_analyzer import analyze_bookmarks
from analyzers.version_diff import compare_versions
from generators.documentation import generate_documentation
from generators.executive_summary import generate_executive_summary
from generators.excel_export import generate_excel
from generators.markdown_export import generate_markdown
from generators.branded_pdf import get_branding_config, save_branding_config, generate_branding_html
from generators.pbip_modifier import apply_changes as apply_pbip_changes
from generators.dax_formatter import format_dax
from database import init_db, save_analysis, get_all_analyses, get_analysis, delete_analysis, compare_analyses
from config import MAX_UPLOAD_SIZE_MB

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Initialize database
init_db()

# Ensure uploads directory exists (use /tmp on Vercel)
_IS_VERCEL = bool(os.environ.get("VERCEL"))
_UPLOADS_BASE = "/tmp/uploads" if _IS_VERCEL else os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(os.path.join(_UPLOADS_BASE, "pbip"), exist_ok=True)

# Register API blueprint
from api import api_bp
app.register_blueprint(api_bp, url_prefix="/api")

# Load translations (auto-discover from i18n directory)
_translations = {}
i18n_dir = os.path.join(os.path.dirname(__file__), "i18n")
for lang_file in os.listdir(i18n_dir):
    if lang_file.endswith(".json"):
        lang_code = lang_file.split(".")[0]
        path = os.path.join(i18n_dir, lang_file)
        with open(path, "r", encoding="utf-8") as f:
            _translations[lang_code] = json.load(f)


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string, with optional format kwargs."""
    text = _translations.get(lang, _translations["en"]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


@app.context_processor
def inject_helpers():
    """Make translation function and lang available in all templates."""
    lang = request.args.get("lang", session.get("lang", "en"))
    session["lang"] = lang

    def translate(key, **kwargs):
        return t(key, lang, **kwargs)

    return {"t": translate, "lang": lang}


def _run_analysis(file_obj, lang, disabled_rules=None, thresholds=None):
    """Core analysis pipeline used by web route, multi-file, and CLI.

    Args:
        file_obj: file-like object or path to ZIP
        lang: language code
        disabled_rules: list of rule IDs to skip
        thresholds: dict of custom threshold overrides

    Returns dict with all analysis data.
    """
    # Apply custom thresholds if provided
    if thresholds:
        import config
        if "max_visuals" in thresholds:
            config.MAX_VISUALS_PER_PAGE = thresholds["max_visuals"]
        if "max_pages" in thresholds:
            config.MAX_PAGES = thresholds["max_pages"]
        if "max_steps" in thresholds:
            config.MAX_STEPS_PER_QUERY = thresholds["max_steps"]
        if "complex_measure" in thresholds:
            config.COMPLEX_MEASURE_CHAR_THRESHOLD = thresholds["complex_measure"]

    # Save to temp file if needed
    if isinstance(file_obj, str):
        tmp_path = file_obj
        should_cleanup = False
    else:
        ext = os.path.splitext(getattr(file_obj, 'filename', '') or '')[1].lower() or ".zip"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        file_obj.save(tmp.name)
        tmp_path = tmp.name
        tmp.close()
        should_cleanup = True

    try:
        # Compute file hash
        with open(tmp_path, "rb") as fh:
            file_hash = hashlib.md5(fh.read()).hexdigest()
        file_size = os.path.getsize(tmp_path)

        result = parse_pbip_zip(tmp_path)
    except Exception as e:
        if should_cleanup and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return {"error": str(e)}

    if result.errors and not result.semantic_model.tables and not result.report.pages:
        error_msg = result.errors[0] if result.errors else t("error_no_pbip", lang)
        return {"error": error_msg}

    # Detect analysis mode
    analysis_mode = "full"
    if result.model_format == "pbix":
        analysis_mode = "light"

    # Run analyzers
    findings = []
    if analysis_mode == "light":
        # Light mode: only PQ, report, bookmarks, and M-code security rules
        findings.extend(analyze_power_query(result.semantic_model))
        findings.extend(analyze_report(result.report))
        findings.extend(analyze_bookmarks(result.report))
        sec_findings = analyze_security(result.semantic_model, result.report)
        findings.extend([f for f in sec_findings if f.rule_id in ("SEC-005", "SEC-006")])
    else:
        findings.extend(analyze_dax(result.semantic_model))
        findings.extend(analyze_power_query(result.semantic_model))
        findings.extend(analyze_model(result.semantic_model))
        findings.extend(analyze_report(result.report))
        findings.extend(analyze_rls(result.semantic_model))
        findings.extend(analyze_security(result.semantic_model, result.report))
        findings.extend(analyze_bookmarks(result.report))
        naming_convention = "title_case"
        if thresholds and "naming_convention" in thresholds:
            naming_convention = thresholds["naming_convention"]
        findings.extend(analyze_naming(result.semantic_model, naming_convention))

    # Filter disabled rules
    if disabled_rules:
        findings = [f for f in findings if f.rule_id not in disabled_rules]

    # Add DAX improvement suggestions (full mode only)
    if analysis_mode == "full":
        findings = generate_dax_improvements(findings, result.semantic_model, lang)

    # Translate finding messages
    for f in findings:
        f.message = t(f.rule_id, lang, **f.details)

    # Calculate score
    score = calculate_score(findings)

    # Generate documentation
    documentation = generate_documentation(result.semantic_model, result.report)

    # Generate KPI suggestions (only meaningful with full model)
    kpi_suggestions = generate_kpi_suggestions(result.semantic_model, lang) if analysis_mode == "full" else []

    # DAX improvements list
    dax_improvements = [f for f in findings if f.category == "dax" and f.details.get("suggestion")] if analysis_mode == "full" else []

    # Executive summary
    exec_summary = generate_executive_summary(documentation, score, findings, lang)

    # Full-mode only analyses
    dax_complexity = []
    unused_measures = []
    lineage = None
    theme_analysis = None
    performance = None

    if analysis_mode == "full":
        dax_complexity = analyze_dax_complexity(result.semantic_model)
        unused_measures = analyze_unused_measures(result.semantic_model, result.report)
        lineage = build_lineage(result.semantic_model)
        theme_info = None
        if hasattr(result, '_report_dir') and result._report_dir:
            theme_info = parse_theme(result._report_dir)
        theme_analysis = analyze_theme(theme_info)
        performance = analyze_performance(result.semantic_model)
        findings.extend(performance["findings"])

    # Relationship diagram data
    diagram_data = _build_diagram_data(result.semantic_model)

    # Branding
    branding = get_branding_config()
    branding_html = generate_branding_html(branding)

    # Report health stats
    report_stats = _build_report_stats(result.report, result.semantic_model)

    # Build editor data for full-mode PBIP analyses
    editor_data = None
    if analysis_mode == "full":
        pq_findings = [f for f in findings if f.category == "power_query"]
        editor_data = _build_editor_data(result.semantic_model, dax_improvements, pq_findings)

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
        "exec_summary": exec_summary,
        "dax_complexity": dax_complexity,
        "unused_measures": unused_measures,
        "lineage": lineage,
        "theme_analysis": theme_analysis,
        "diagram_data": diagram_data,
        "performance": performance,
        "branding": branding,
        "branding_html": branding_html,
        "report_stats": report_stats,
        "file_hash": file_hash if 'file_hash' in dir() else "",
        "file_size": file_size if 'file_size' in dir() else 0,
        "analysis_mode": analysis_mode,
        "editor_data": editor_data,
        "_tmp_path": tmp_path if should_cleanup else None,
    }


def _build_diagram_data(model):
    """Build D3-compatible graph data for relationship diagram."""
    # Build node list with column/measure counts
    table_map = {}
    for i, table in enumerate(model.tables):
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        table_map[table.name] = i

    nodes = []
    node_ids = {}
    idx = 0
    for table in model.tables:
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        node_ids[table.name] = idx
        nodes.append({
            "id": idx,
            "name": table.name,
            "columns": len(table.columns),
            "measures": len(table.measures),
        })
        idx += 1

    links = []
    for r in model.relationships:
        if r.from_table in node_ids and r.to_table in node_ids:
            links.append({
                "source": node_ids[r.from_table],
                "target": node_ids[r.to_table],
                "from_cardinality": r.from_cardinality,
                "to_cardinality": r.to_cardinality,
                "cross_filtering": r.cross_filtering,
                "is_active": r.is_active,
            })

    return {"nodes": nodes, "links": links}


def _build_report_stats(report, model):
    """Build report health statistics panel data (inspired by powerbi_analyzer)."""
    # Per-page metrics
    pages_data = []
    all_visual_types = {}
    custom_visuals = []
    total_filters = 0

    for page in report.pages:
        vis_count = len(page.visuals)
        filter_count = len(page.filters) if page.filters else 0
        total_filters += filter_count

        # Count visual types
        page_types = {}
        for v in page.visuals:
            vtype = v.visual_type or "unknown"
            all_visual_types[vtype] = all_visual_types.get(vtype, 0) + 1
            page_types[vtype] = page_types.get(vtype, 0) + 1

            # Detect custom/marketplace visuals (non-standard types)
            if vtype and "_" in vtype and not vtype.startswith("text"):
                if vtype not in [cv["type"] for cv in custom_visuals]:
                    custom_visuals.append({"type": vtype, "page": page.display_name or page.name})

        pages_data.append({
            "name": page.display_name or page.name,
            "visuals": vis_count,
            "filters": filter_count,
            "visibility": page.visibility,
            "is_tooltip": page.is_tooltip,
            "has_drillthrough": page.has_drillthrough,
            "visual_types": page_types,
        })

    total_visuals = sum(p["visuals"] for p in pages_data)
    total_pages = len(pages_data)
    avg_visuals = round(total_visuals / total_pages, 1) if total_pages else 0
    max_visuals = max((p["visuals"] for p in pages_data), default=0)
    avg_filters = round(total_filters / total_pages, 1) if total_pages else 0
    max_filters = max((p["filters"] for p in pages_data), default=0)

    # Model stats
    total_tables = len([t for t in model.tables
                        if not t.name.startswith("DateTableTemplate")
                        and not t.name.startswith("LocalDateTable")])
    total_measures = sum(len(t.measures) for t in model.tables)
    total_columns = sum(len(t.columns) for t in model.tables
                        if not t.name.startswith("DateTableTemplate")
                        and not t.name.startswith("LocalDateTable"))
    total_relationships = len(model.relationships)

    # Sort visual types by count
    sorted_types = sorted(all_visual_types.items(), key=lambda x: -x[1])

    # Health scores per metric (traffic light)
    health = []
    health.append(_metric_health("visuals_per_page", avg_visuals, 10, 15, 20))
    health.append(_metric_health("filters_per_page", avg_filters, 5, 8, 12))
    health.append(_metric_health("total_pages", total_pages, 10, 20, 30))
    health.append(_metric_health("total_tables", total_tables, 15, 30, 50))
    health.append(_metric_health("total_measures", total_measures, 30, 60, 100))
    health.append(_metric_health("relationships", total_relationships, 20, 40, 60))
    health.append(_metric_health("custom_visuals", len(custom_visuals), 3, 5, 8))

    return {
        "pages": pages_data,
        "total_pages": total_pages,
        "total_visuals": total_visuals,
        "avg_visuals_per_page": avg_visuals,
        "max_visuals_per_page": max_visuals,
        "total_filters": total_filters,
        "avg_filters_per_page": avg_filters,
        "max_filters_per_page": max_filters,
        "visual_types": sorted_types,
        "custom_visuals": custom_visuals,
        "total_tables": total_tables,
        "total_measures": total_measures,
        "total_columns": total_columns,
        "total_relationships": total_relationships,
        "health": health,
    }


def _metric_health(name, value, good, warning, critical):
    """Evaluate a metric against thresholds. Returns traffic-light status."""
    if value <= good:
        status = "good"
        score = 100
    elif value <= warning:
        status = "warning"
        score = 70
    else:
        status = "critical"
        score = 30
    return {"name": name, "value": value, "status": status, "score": score,
            "good": good, "warning": warning, "critical": critical}


def _build_editor_data(model, dax_improvements, pq_findings=None):
    """Build editor data with measures (+ suggestions), PQ queries, and relationships."""
    from analyzers.dax_optimizer import optimize_measure

    # Build suggestion map from findings: (table_name, measure_name) -> suggestion info
    suggestion_map = {}
    for f in dax_improvements:
        if isinstance(f, dict):
            d = f.get("details", {})
            rule_id = f.get("rule_id", "")
        else:
            d = f.details
            rule_id = f.rule_id

        table = d.get("table_name", "")
        measure = d.get("measure_name", "")
        suggestion = d.get("suggestion", "")
        if table and measure and suggestion:
            if (table, measure) not in suggestion_map:
                suggestion_map[(table, measure)] = {"suggestion": suggestion, "rule_id": rule_id}

    # Collect all measures
    measures = []
    for table in model.tables:
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        for m in table.measures:
            entry = {
                "table_name": table.name,
                "name": m.name,
                "expression": m.expression,
            }
            key = (table.name, m.name)
            if key in suggestion_map:
                entry["suggestion"] = suggestion_map[key]["suggestion"]
                entry["rule_id"] = suggestion_map[key]["rule_id"]
            else:
                # Try optimizer directly for measures not covered by findings
                optimized = optimize_measure(m.expression)
                if optimized:
                    entry["suggestion"] = optimized
                    entry["rule_id"] = "OPT"
            measures.append(entry)

    # Collect relationships
    relationships = []
    for idx, r in enumerate(model.relationships):
        relationships.append({
            "index": idx,
            "from_table": r.from_table,
            "from_column": r.from_column,
            "to_table": r.to_table,
            "to_column": r.to_column,
            "from_cardinality": r.from_cardinality,
            "to_cardinality": r.to_cardinality,
            "cross_filtering": r.cross_filtering,
            "is_active": r.is_active,
        })

    # Build PQ editor data
    queries = _build_pq_editor_data(model, pq_findings) if pq_findings is not None else []

    return {"measures": measures, "relationships": relationships, "queries": queries}


def _build_pq_editor_data(model, pq_findings):
    """Build Power Query data for the editor tab."""
    from analyzers.pq_analyzer import parse_m_steps

    # Build findings map: (table_name, query_name) -> list of finding rule_ids
    pq_finding_map = {}
    for f in pq_findings:
        loc = f.location if hasattr(f, "location") else f.get("location", "")
        rule_id = f.rule_id if hasattr(f, "rule_id") else f.get("rule_id", "")

        table_match = re.search(r"Table\s+'([^']+)'", loc)
        query_match = re.search(r"Query\s+'([^']+)'", loc)
        table_name = table_match.group(1) if table_match else "(Shared)"
        query_name = query_match.group(1) if query_match else ""

        key = (table_name, query_name)
        pq_finding_map.setdefault(key, []).append(rule_id)

    queries = []
    for table in model.tables:
        if table.name.startswith("DateTableTemplate") or table.name.startswith("LocalDateTable"):
            continue
        for p in table.partitions:
            if p.source_type == "m" and p.expression:
                steps = parse_m_steps(p.expression)
                finding_rules = pq_finding_map.get((table.name, p.name), [])
                queries.append({
                    "table_name": table.name,
                    "query_name": p.name,
                    "m_code": p.expression,
                    "steps": steps,
                    "step_count": len([s for s in steps if s["name"] != "(result)"]),
                    "findings": finding_rules,
                })

    # Shared expressions
    for expr_obj in model.expressions:
        if expr_obj.expression:
            steps = parse_m_steps(expr_obj.expression)
            finding_rules = pq_finding_map.get(("(Shared)", expr_obj.name), [])
            queries.append({
                "table_name": "(Shared)",
                "query_name": expr_obj.name,
                "m_code": expr_obj.expression,
                "steps": steps,
                "step_count": len([s for s in steps if s["name"] != "(result)"]),
                "findings": finding_rules,
            })

    return queries


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    lang = request.args.get("lang", session.get("lang", "en"))

    # Parse rules config from form
    rules_config_str = request.form.get("rules_config", "{}")
    try:
        rules_config = json.loads(rules_config_str)
    except (json.JSONDecodeError, TypeError):
        rules_config = {}
    disabled_rules = rules_config.get("disabled_rules", [])
    thresholds = rules_config.get("thresholds", {})

    # Validate upload
    files = request.files.getlist("file")
    if not files or not files[0].filename:
        return render_template("index.html", error=t("error_no_file", lang))

    # Filter valid ZIP files
    valid_files = [f for f in files if f.filename and f.filename.lower().endswith((".zip", ".pbix"))]
    if not valid_files:
        return render_template("index.html", error=t("error_not_zip", lang))

    # Single file analysis
    if len(valid_files) == 1:
        result = _run_analysis(valid_files[0], lang, disabled_rules, thresholds)

        if "error" in result:
            # Cleanup temp file on error
            tmp_path = result.get("_tmp_path")
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return render_template("index.html", error=result["error"])

        # Save to history (with all data for full results on reload)
        try:
            row_id = save_analysis(
                project_name=result["project_name"],
                model_format=result["model_format"],
                report_format=result["report_format"],
                score=result["score"],
                findings=result["findings"],
                documentation=result["documentation"],
                kpi_suggestions=result["kpi_suggestions"],
                dax_improvements=result["dax_improvements"],
                file_hash=result.get("file_hash", ""),
                file_size=result.get("file_size", 0),
                exec_summary=result.get("exec_summary"),
                dax_complexity=result.get("dax_complexity"),
                unused_measures=result.get("unused_measures"),
                lineage=result.get("lineage"),
                theme_analysis=result.get("theme_analysis"),
                diagram_data=result.get("diagram_data"),
                performance=result.get("performance"),
                report_stats=result.get("report_stats"),
                analysis_mode=result.get("analysis_mode", "full"),
                editor_data=result.get("editor_data"),
            )
        except Exception:
            row_id = None

        # Persist uploaded ZIP for editor (full mode only)
        tmp_path = result.get("_tmp_path")
        source_zip_path = ""
        if row_id and tmp_path and os.path.exists(tmp_path) and result.get("analysis_mode") == "full":
            import shutil
            dest = os.path.join(_UPLOADS_BASE, "pbip", f"{row_id}.zip")
            shutil.copy2(tmp_path, dest)
            source_zip_path = f"pbip/{row_id}.zip"
            # Update DB with ZIP path
            from database import get_db
            conn = get_db()
            conn.execute("UPDATE analyses SET source_zip_path = ? WHERE id = ?", (source_zip_path, row_id))
            conn.commit()
            conn.close()

        # Cleanup temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

        # Store last result in session for export
        session["last_analysis"] = {
            "project_name": result["project_name"],
            "model_format": result["model_format"],
            "report_format": result["report_format"],
        }

        # Redirect to history detail (GET-accessible, language switch works)
        if row_id:
            return redirect(url_for("history_detail", id=row_id, lang=lang))

        # Fallback: render directly if DB save failed
        return render_template(
            "results.html",
            project_name=result["project_name"],
            model_format=result["model_format"],
            report_format=result["report_format"],
            score=result["score"],
            findings=result["findings"],
            documentation=result["documentation"],
            kpi_suggestions=result["kpi_suggestions"],
            dax_improvements=result["dax_improvements"],
            parse_errors=result["parse_errors"],
            exec_summary=result["exec_summary"],
            dax_complexity=result["dax_complexity"],
            unused_measures=result["unused_measures"],
            lineage=result["lineage"],
            theme_analysis=result["theme_analysis"],
            diagram_data=result["diagram_data"],
            performance=result["performance"],
            report_stats=result.get("report_stats"),
            branding=result.get("branding", {}),
            branding_html=result.get("branding_html", {}),
            analysis_mode=result.get("analysis_mode", "full"),
            editor_data=result.get("editor_data"),
            has_source_zip=False,
        )

    # Multi-file analysis
    results = []
    for f in valid_files:
        r = _run_analysis(f, lang, disabled_rules, thresholds)
        # Cleanup temp files for multi-file (no editor support)
        tmp_path = r.get("_tmp_path")
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if "error" not in r:
            results.append(r)

    if not results:
        return render_template("index.html", error=t("error_parse", lang))

    multi = compare_multi(results)

    if multi["mode"] == "comparison":
        return render_template(
            "comparison.html",
            comparison=multi,
        )
    else:
        return render_template(
            "consolidated.html",
            multi=multi,
        )


# --- History routes ---

@app.route("/history")
def history():
    analyses = get_all_analyses()
    return render_template("history.html", analyses=analyses)


@app.route("/history/<int:id>")
def history_detail(id):
    """View a saved analysis."""
    data = get_analysis(id)
    if not data:
        return redirect(url_for("history"))

    # Reconstruct score dict from stored data
    score = {
        "total_score": data.get("total_score", 0),
        "grade": data.get("grade", "F"),
        "grade_key": f"grade_{data.get('grade', 'F')}",
        "category_scores": data.get("category_scores", {}),
        "category_max": {"data_model": 35, "dax": 25, "power_query": 20, "report": 20},
        "category_findings": {},
    }

    # Group findings by category
    findings = data.get("findings", [])
    category_findings = {}
    for f in findings:
        cat = f.get("category", "")
        category_findings.setdefault(cat, []).append(f)
    score["category_findings"] = category_findings

    # Branding (always fresh from DB)
    branding = get_branding_config()
    branding_html = generate_branding_html(branding)

    return render_template(
        "results.html",
        project_name=data.get("project_name", ""),
        model_format=data.get("model_format", ""),
        report_format=data.get("report_format", ""),
        score=score,
        findings=findings,
        documentation=data.get("documentation", {}),
        kpi_suggestions=data.get("kpi_suggestions", []),
        dax_improvements=data.get("dax_improvements", []),
        parse_errors=[],
        exec_summary=data.get("exec_summary"),
        dax_complexity=data.get("dax_complexity", []),
        unused_measures=data.get("unused_measures", []),
        lineage=data.get("lineage") or {"has_lineage": False, "trees": [], "nodes": [], "links": []},
        theme_analysis=data.get("theme_analysis"),
        diagram_data=data.get("diagram_data") or {"nodes": [], "links": []},
        performance=data.get("performance"),
        report_stats=data.get("report_stats"),
        branding=branding,
        branding_html=branding_html,
        analysis_mode=data.get("analysis_mode", "full"),
        from_history=True,
        editor_data=data.get("editor_data"),
        analysis_id=id,
        has_source_zip=bool(data.get("source_zip_path")),
    )


@app.route("/history/<int:id>/delete", methods=["POST"])
def history_delete(id):
    delete_analysis(id)
    return redirect(url_for("history"))


@app.route("/compare/<int:id1>/<int:id2>")
def compare(id1, id2):
    comparison = compare_analyses(id1, id2)
    if not comparison:
        return redirect(url_for("history"))
    return render_template("comparison.html", comparison=comparison)


# --- Editor routes ---

@app.route("/editor/apply/<int:id>", methods=["POST"])
def editor_apply(id):
    """Apply DAX/relationship/measure changes and return modified PBIP ZIP."""
    data = get_analysis(id)
    if not data or not data.get("source_zip_path"):
        return jsonify({"error": "No source ZIP available for this analysis"}), 404

    zip_path = os.path.join(_UPLOADS_BASE, data["source_zip_path"])
    if not os.path.exists(zip_path):
        return jsonify({"error": "Source ZIP file not found"}), 404

    payload = request.get_json(silent=True) or {}
    dax_changes = payload.get("dax_changes", [])
    relationship_changes = payload.get("relationship_changes", [])
    new_measures = payload.get("new_measures", [])
    pq_changes = payload.get("pq_changes", [])

    if not dax_changes and not relationship_changes and not new_measures and not pq_changes:
        return jsonify({"error": "No changes provided"}), 400

    try:
        output = apply_pbip_changes(
            zip_path=zip_path,
            dax_changes=dax_changes or None,
            relationship_changes=relationship_changes or None,
            new_measures=new_measures or None,
            pq_changes=pq_changes or None,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    filename = f"{data.get('project_name', 'project')}-modified.zip"
    return send_file(
        output,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/editor/format-dax", methods=["POST"])
def format_dax_route():
    """Format a DAX expression with proper indentation."""
    payload = request.get_json(silent=True) or {}
    expression = payload.get("expression", "")
    if not expression:
        return jsonify({"formatted": ""})

    try:
        formatted = format_dax(expression)
        return jsonify({"formatted": formatted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Export routes ---

@app.route("/export/excel")
def export_excel():
    """Export last analysis as Excel."""
    lang = request.args.get("lang", session.get("lang", "en"))
    analysis_id = request.args.get("id")

    if analysis_id:
        data = get_analysis(int(analysis_id))
    else:
        # Get the most recent analysis
        analyses = get_all_analyses()
        if not analyses:
            return redirect(url_for("index"))
        data = get_analysis(analyses[0]["id"])

    if not data:
        return redirect(url_for("index"))

    score = {
        "total_score": data.get("total_score", 0),
        "grade": data.get("grade", "F"),
        "category_scores": data.get("category_scores", {}),
        "category_max": {"data_model": 35, "dax": 25, "power_query": 20, "report": 20},
    }

    output = generate_excel(
        project_name=data.get("project_name", ""),
        score=score,
        findings=data.get("findings", []),
        documentation=data.get("documentation", {}),
        kpi_suggestions=data.get("kpi_suggestions", []),
        dax_improvements=data.get("dax_improvements", []),
    )

    if output is None:
        return "openpyxl not installed", 500

    filename = f"pbi-analysis-{data.get('project_name', 'report')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/export/markdown")
def export_markdown():
    """Export last analysis as Markdown."""
    lang = request.args.get("lang", session.get("lang", "en"))
    analysis_id = request.args.get("id")

    if analysis_id:
        data = get_analysis(int(analysis_id))
    else:
        analyses = get_all_analyses()
        if not analyses:
            return redirect(url_for("index"))
        data = get_analysis(analyses[0]["id"])

    if not data:
        return redirect(url_for("index"))

    score = {
        "total_score": data.get("total_score", 0),
        "grade": data.get("grade", "F"),
        "category_scores": data.get("category_scores", {}),
        "category_max": {"data_model": 35, "dax": 25, "power_query": 20, "report": 20},
    }

    md_content = generate_markdown(
        project_name=data.get("project_name", ""),
        score=score,
        findings=data.get("findings", []),
        documentation=data.get("documentation", {}),
        kpi_suggestions=data.get("kpi_suggestions", []),
    )

    filename = f"pbi-analysis-{data.get('project_name', 'report')}.md"
    import io
    output = io.BytesIO(md_content.encode("utf-8"))
    output.seek(0)
    return send_file(
        output,
        mimetype="text/markdown",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/export/json")
def export_json():
    """Export analysis as JSON."""
    analysis_id = request.args.get("id")

    if analysis_id:
        data = get_analysis(int(analysis_id))
    else:
        analyses = get_all_analyses()
        if not analyses:
            return jsonify({"error": "No analyses found"}), 404
        data = get_analysis(analyses[0]["id"])

    if not data:
        return jsonify({"error": "Analysis not found"}), 404

    # Build clean export dict
    score = {
        "total_score": data.get("total_score", 0),
        "grade": data.get("grade", "F"),
        "category_scores": data.get("category_scores", {}),
    }

    export = {
        "project_name": data.get("project_name", ""),
        "analyzed_at": data.get("analyzed_at", ""),
        "model_format": data.get("model_format", ""),
        "report_format": data.get("report_format", ""),
        "analysis_mode": data.get("analysis_mode", "full"),
        "score": score,
        "findings": data.get("findings", []),
        "documentation": data.get("documentation", {}),
        "kpi_suggestions": data.get("kpi_suggestions", []),
        "dax_improvements": data.get("dax_improvements", []),
        "exec_summary": data.get("exec_summary"),
        "dax_complexity": data.get("dax_complexity"),
        "unused_measures": data.get("unused_measures"),
        "performance": data.get("performance"),
        "report_stats": data.get("report_stats"),
        "theme_analysis": data.get("theme_analysis"),
    }

    return jsonify(export)


@app.route("/diff", methods=["POST"])
def diff():
    """Version diff between two PBIP ZIPs."""
    lang = request.args.get("lang", session.get("lang", "en"))

    file1 = request.files.get("file1")
    file2 = request.files.get("file2")
    if not file1 or not file2:
        return render_template("index.html", error=t("error_no_file", lang))

    import tempfile as _tf
    from parsers.pbip_parser import parse_pbip_zip as _parse

    tmp1 = _tf.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp2 = _tf.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        file1.save(tmp1.name)
        file2.save(tmp2.name)
        tmp1.close()
        tmp2.close()

        r1 = _parse(tmp1.name)
        r2 = _parse(tmp2.name)

        diff_result = compare_versions(
            r1.semantic_model, r1.report,
            r2.semantic_model, r2.report,
        )
        diff_result["project1"] = r1.project_name
        diff_result["project2"] = r2.project_name

        return render_template("version_diff.html", diff=diff_result)
    finally:
        for p in (tmp1.name, tmp2.name):
            if os.path.exists(p):
                os.unlink(p)


@app.route("/settings/branding", methods=["GET", "POST"])
def save_branding():
    """Save branding configuration."""
    if request.method == "POST":
        save_branding_config(
            company_name=request.form.get("company_name", ""),
            logo_file=request.files.get("logo"),
            primary_color=request.form.get("primary_color", "#0077CC"),
            secondary_color=request.form.get("secondary_color", "#00bfff"),
            footer_text=request.form.get("footer_text", ""),
        )
    return redirect(url_for("index"))


@app.context_processor
def inject_branding():
    """Make branding config available in all templates."""
    return {"branding": get_branding_config()}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
