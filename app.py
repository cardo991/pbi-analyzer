"""GridPulse - Flask web application."""

import hashlib
import json
import os
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
from database import init_db, save_analysis, get_all_analyses, get_analysis, delete_analysis, compare_analyses
from config import MAX_UPLOAD_SIZE_MB

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Initialize database
init_db()

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
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
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
    finally:
        if should_cleanup and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if result.errors and not result.semantic_model.tables:
        error_msg = result.errors[0] if result.errors else t("error_no_pbip", lang)
        return {"error": error_msg}

    # Run analyzers
    findings = []
    findings.extend(analyze_dax(result.semantic_model))
    findings.extend(analyze_power_query(result.semantic_model))
    findings.extend(analyze_model(result.semantic_model))
    findings.extend(analyze_report(result.report))
    findings.extend(analyze_rls(result.semantic_model))
    findings.extend(analyze_security(result.semantic_model, result.report))
    findings.extend(analyze_bookmarks(result.report))

    # Naming conventions (uses configurable convention)
    naming_convention = "title_case"
    if thresholds and "naming_convention" in thresholds:
        naming_convention = thresholds["naming_convention"]
    findings.extend(analyze_naming(result.semantic_model, naming_convention))

    # Filter disabled rules
    if disabled_rules:
        findings = [f for f in findings if f.rule_id not in disabled_rules]

    # Add DAX improvement suggestions to findings
    findings = generate_dax_improvements(findings, result.semantic_model, lang)

    # Translate finding messages
    for f in findings:
        f.message = t(f.rule_id, lang, **f.details)

    # Calculate score
    score = calculate_score(findings)

    # Generate documentation
    documentation = generate_documentation(result.semantic_model, result.report)

    # Generate KPI suggestions
    kpi_suggestions = generate_kpi_suggestions(result.semantic_model, lang)

    # DAX improvements list
    dax_improvements = [f for f in findings if f.category == "dax" and f.details.get("suggestion")]

    # Executive summary
    exec_summary = generate_executive_summary(documentation, score, findings, lang)

    # DAX complexity
    dax_complexity = analyze_dax_complexity(result.semantic_model)

    # Unused measures
    unused_measures = analyze_unused_measures(result.semantic_model, result.report)

    # Measure lineage
    lineage = build_lineage(result.semantic_model)

    # Theme analysis
    theme_info = None
    theme_analysis = None
    if hasattr(result, '_report_dir') and result._report_dir:
        theme_info = parse_theme(result._report_dir)
    theme_analysis = analyze_theme(theme_info)

    # Performance analysis
    performance = analyze_performance(result.semantic_model)
    # Performance findings go into main findings list
    findings.extend(performance["findings"])

    # Relationship diagram data
    diagram_data = _build_diagram_data(result.semantic_model)

    # Branding
    branding = get_branding_config()
    branding_html = generate_branding_html(branding)

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
        "file_hash": file_hash if 'file_hash' in dir() else "",
        "file_size": file_size if 'file_size' in dir() else 0,
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
    valid_files = [f for f in files if f.filename and f.filename.lower().endswith(".zip")]
    if not valid_files:
        return render_template("index.html", error=t("error_not_zip", lang))

    # Single file analysis
    if len(valid_files) == 1:
        result = _run_analysis(valid_files[0], lang, disabled_rules, thresholds)

        if "error" in result:
            return render_template("index.html", error=result["error"])

        # Save to history
        try:
            save_analysis(
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
            )
        except Exception:
            pass  # Don't fail analysis if DB save fails

        # Store last result in session for export
        session["last_analysis"] = {
            "project_name": result["project_name"],
            "model_format": result["model_format"],
            "report_format": result["report_format"],
        }

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
            branding=result.get("branding", {}),
            branding_html=result.get("branding_html", {}),
        )

    # Multi-file analysis
    results = []
    for f in valid_files:
        r = _run_analysis(f, lang, disabled_rules, thresholds)
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

    return render_template(
        "history_detail.html" if os.path.exists(os.path.join(app.template_folder, "history_detail.html")) else "results.html",
        project_name=data.get("project_name", ""),
        model_format=data.get("model_format", ""),
        report_format=data.get("report_format", ""),
        score=score,
        findings=findings,
        documentation=data.get("documentation", {}),
        kpi_suggestions=data.get("kpi_suggestions", []),
        dax_improvements=data.get("dax_improvements", []),
        parse_errors=[],
        exec_summary=None,
        dax_complexity=[],
        unused_measures=[],
        lineage={"has_lineage": False, "trees": [], "nodes": [], "links": []},
        theme_analysis=None,
        diagram_data={"nodes": [], "links": []},
        from_history=True,
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
