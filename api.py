"""REST API Blueprint for GridPulse."""

import os
import tempfile

from flask import Blueprint, request, jsonify

api_bp = Blueprint("api", __name__)

# Optional API key authentication
API_KEY = os.environ.get("GRIDPULSE_API_KEY", "")


def _check_api_key():
    """Validate API key if configured. Returns error response or None."""
    if not API_KEY:
        return None  # No auth required
    provided = request.headers.get("X-API-Key", "")
    if provided != API_KEY:
        return jsonify({"status": "error", "message": "Invalid or missing API key"}), 401
    return None


def _api_response(data, status_code=200):
    """Standard API response wrapper."""
    resp = jsonify({"status": "ok", "data": data})
    resp.status_code = status_code
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def _api_error(message, status_code=400):
    """Standard API error response."""
    resp = jsonify({"status": "error", "message": message})
    resp.status_code = status_code
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def _serialize_findings(findings):
    """Convert Finding objects or dicts to JSON-safe dicts."""
    result = []
    for f in findings:
        if isinstance(f, dict):
            result.append(f)
        else:
            result.append({
                "rule_id": f.rule_id,
                "category": f.category,
                "severity": f.severity,
                "message": f.message,
                "location": f.location,
                "details": f.details,
            })
    return result


@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return _api_response({"status": "healthy", "version": "2.0"})


@api_bp.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    """Analyze a PBIP ZIP file."""
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        return resp

    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    file = request.files.get("file")
    if not file or not file.filename:
        return _api_error("No file uploaded", 400)

    if not file.filename.lower().endswith(".zip"):
        return _api_error("File must be a ZIP archive", 400)

    lang = request.form.get("lang", "en")
    disabled_rules = request.form.getlist("disabled_rules")

    # Import here to avoid circular imports
    from app import _run_analysis

    result = _run_analysis(file, lang, disabled_rules or None)

    if "error" in result:
        return _api_error(result["error"], 422)

    # Serialize for JSON response
    output = {
        "project_name": result["project_name"],
        "model_format": result["model_format"],
        "report_format": result["report_format"],
        "score": {
            "total_score": result["score"]["total_score"],
            "grade": result["score"]["grade"],
            "category_scores": result["score"].get("category_scores", {}),
        },
        "findings_count": len(result.get("findings", [])),
        "findings": _serialize_findings(result.get("findings", [])),
        "documentation": result.get("documentation", {}),
        "kpi_suggestions": result.get("kpi_suggestions", []),
        "dax_improvements": _serialize_findings(result.get("dax_improvements", [])),
        "dax_complexity": result.get("dax_complexity", []),
        "unused_measures": result.get("unused_measures", []),
        "performance": result.get("performance", {}),
        "parse_errors": result.get("parse_errors", []),
    }

    return _api_response(output)


@api_bp.route("/history", methods=["GET"])
def history():
    """List all analyses."""
    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    from database import get_all_analyses
    analyses = get_all_analyses()
    return _api_response(analyses)


@api_bp.route("/history/<int:analysis_id>", methods=["GET"])
def history_detail(analysis_id):
    """Get a single analysis."""
    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    from database import get_analysis
    data = get_analysis(analysis_id)
    if not data:
        return _api_error("Analysis not found", 404)

    return _api_response(data)


@api_bp.route("/history/<int:analysis_id>", methods=["DELETE", "OPTIONS"])
def history_delete(analysis_id):
    """Delete an analysis."""
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "X-API-Key"
        return resp

    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    from database import delete_analysis
    deleted = delete_analysis(analysis_id)
    if not deleted:
        return _api_error("Analysis not found", 404)

    return _api_response({"deleted": True})


@api_bp.route("/compare", methods=["POST", "OPTIONS"])
def compare():
    """Compare two PBIP ZIP files."""
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        return resp

    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    file1 = request.files.get("file1")
    file2 = request.files.get("file2")

    if not file1 or not file2:
        return _api_error("Two files required (file1 and file2)", 400)

    lang = request.form.get("lang", "en")

    from app import _run_analysis

    r1 = _run_analysis(file1, lang)
    r2 = _run_analysis(file2, lang)

    if "error" in r1:
        return _api_error(f"File 1: {r1['error']}", 422)
    if "error" in r2:
        return _api_error(f"File 2: {r2['error']}", 422)

    from analyzers.comparison import compare_analyses
    comparison = compare_analyses([r1, r2])

    return _api_response(comparison)


@api_bp.route("/diff", methods=["POST", "OPTIONS"])
def diff():
    """Version diff between two PBIP ZIP files."""
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        return resp

    auth_err = _check_api_key()
    if auth_err:
        return auth_err

    file1 = request.files.get("file1")
    file2 = request.files.get("file2")

    if not file1 or not file2:
        return _api_error("Two files required (file1 and file2)", 400)

    # Save to temp files
    tmp1 = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp2 = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        file1.save(tmp1.name)
        file2.save(tmp2.name)
        tmp1.close()
        tmp2.close()

        from parsers.pbip_parser import parse_pbip_zip
        from analyzers.version_diff import compare_versions

        r1 = parse_pbip_zip(tmp1.name)
        r2 = parse_pbip_zip(tmp2.name)

        diff_result = compare_versions(
            r1.semantic_model, r1.report,
            r2.semantic_model, r2.report,
        )
        diff_result["project1"] = r1.project_name
        diff_result["project2"] = r2.project_name

        return _api_response(diff_result)
    finally:
        for p in (tmp1.name, tmp2.name):
            if os.path.exists(p):
                os.unlink(p)
