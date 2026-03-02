"""SQLite database for analysis history."""

import json
import os
import sqlite3
from datetime import datetime


_IS_VERCEL = bool(os.environ.get("VERCEL"))
DB_PATH = os.path.join("/tmp", "gridpulse.db") if _IS_VERCEL else os.path.join(os.path.dirname(__file__), "gridpulse.db")


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize database schema."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            model_format TEXT,
            report_format TEXT,
            total_score REAL,
            grade TEXT,
            category_scores TEXT,
            findings TEXT,
            documentation TEXT,
            kpi_suggestions TEXT,
            dax_improvements TEXT,
            file_hash TEXT,
            file_size INTEGER,
            tables_count INTEGER,
            measures_count INTEGER,
            findings_count INTEGER
        )
    """)
    # Migration: add new columns to existing databases
    _migrate_columns = [
        ("exec_summary", "TEXT"),
        ("dax_complexity", "TEXT"),
        ("unused_measures", "TEXT"),
        ("lineage", "TEXT"),
        ("theme_analysis", "TEXT"),
        ("diagram_data", "TEXT"),
        ("performance", "TEXT"),
        ("analysis_mode", "TEXT DEFAULT 'full'"),
        ("source_zip_path", "TEXT"),
        ("editor_data", "TEXT"),
        ("report_stats", "TEXT"),
        ("pq_lineage", "TEXT"),
    ]
    for col_name, col_type in _migrate_columns:
        try:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS branding (
            id INTEGER PRIMARY KEY DEFAULT 1,
            company_name TEXT DEFAULT '',
            logo_path TEXT DEFAULT '',
            primary_color TEXT DEFAULT '#0077CC',
            secondary_color TEXT DEFAULT '#00bfff',
            footer_text TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            is_builtin INTEGER DEFAULT 0,
            disabled_rules TEXT DEFAULT '[]',
            thresholds TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_setting(key: str) -> str | None:
    """Get a setting value by key."""
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def save_setting(key: str, value: str):
    """Save a setting (upsert)."""
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_branding() -> dict | None:
    """Get branding configuration."""
    conn = get_db()
    row = conn.execute("SELECT * FROM branding WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def save_branding(config: dict):
    """Save branding configuration (upsert)."""
    conn = get_db()
    existing = conn.execute("SELECT id FROM branding WHERE id = 1").fetchone()
    if existing:
        conn.execute("""
            UPDATE branding SET company_name=?, logo_path=?, primary_color=?,
            secondary_color=?, footer_text=? WHERE id=1
        """, (
            config.get("company_name", ""),
            config.get("logo_path", ""),
            config.get("primary_color", "#0077CC"),
            config.get("secondary_color", "#00bfff"),
            config.get("footer_text", ""),
        ))
    else:
        conn.execute("""
            INSERT INTO branding (id, company_name, logo_path, primary_color, secondary_color, footer_text)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (
            config.get("company_name", ""),
            config.get("logo_path", ""),
            config.get("primary_color", "#0077CC"),
            config.get("secondary_color", "#00bfff"),
            config.get("footer_text", ""),
        ))
    conn.commit()
    conn.close()


def _serialize_finding(f):
    """Convert a Finding object or dict to a JSON-safe dict."""
    if isinstance(f, dict):
        return f
    return {
        "rule_id": f.rule_id,
        "category": f.category,
        "severity": f.severity,
        "message": f.message,
        "location": f.location,
        "details": f.details,
    }


def save_analysis(project_name: str, model_format: str, report_format: str,
                  score: dict, findings: list, documentation: dict,
                  kpi_suggestions: list, dax_improvements: list,
                  file_hash: str = "", file_size: int = 0,
                  exec_summary=None, dax_complexity=None,
                  unused_measures=None, lineage=None,
                  theme_analysis=None, diagram_data=None,
                  performance=None, report_stats=None,
                  pq_lineage=None,
                  analysis_mode: str = "full",
                  source_zip_path: str = "", editor_data=None) -> int:
    """Save an analysis result to the database. Returns the new row ID."""
    overview = documentation.get("overview", {})

    findings_data = [_serialize_finding(f) for f in findings]
    dax_data = [_serialize_finding(f) for f in dax_improvements]

    # Serialize performance findings separately
    perf_data = None
    if performance:
        perf_copy = dict(performance)
        if "findings" in perf_copy:
            perf_copy["findings"] = [_serialize_finding(f) for f in perf_copy["findings"]]
        perf_data = json.dumps(perf_copy)

    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO analyses (
            project_name, model_format, report_format,
            total_score, grade, category_scores,
            findings, documentation, kpi_suggestions, dax_improvements,
            file_hash, file_size,
            tables_count, measures_count, findings_count,
            exec_summary, dax_complexity, unused_measures,
            lineage, theme_analysis, diagram_data,
            performance, report_stats, pq_lineage, analysis_mode,
            source_zip_path, editor_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_name,
        model_format,
        report_format,
        score.get("total_score", 0),
        score.get("grade", "F"),
        json.dumps(score.get("category_scores", {})),
        json.dumps(findings_data),
        json.dumps(documentation),
        json.dumps(kpi_suggestions),
        json.dumps(dax_data),
        file_hash,
        file_size,
        overview.get("total_tables", 0),
        overview.get("total_measures", 0),
        len(findings),
        json.dumps(exec_summary) if exec_summary else None,
        json.dumps(dax_complexity) if dax_complexity else None,
        json.dumps(unused_measures) if unused_measures else None,
        json.dumps(lineage) if lineage else None,
        json.dumps(theme_analysis) if theme_analysis else None,
        json.dumps(diagram_data) if diagram_data else None,
        perf_data,
        json.dumps(report_stats) if report_stats else None,
        json.dumps(pq_lineage) if pq_lineage else None,
        analysis_mode,
        source_zip_path,
        json.dumps(editor_data) if editor_data else None,
    ))
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_all_analyses() -> list[dict]:
    """Get all analyses ordered by date descending."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, project_name, analyzed_at, model_format, report_format, "
        "total_score, grade, tables_count, measures_count, findings_count "
        "FROM analyses ORDER BY analyzed_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analysis(analysis_id: int) -> dict | None:
    """Get a single analysis by ID with full data."""
    conn = get_db()
    row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    conn.close()
    if not row:
        return None

    data = dict(row)
    # Deserialize JSON fields
    dict_fields = ("category_scores", "documentation", "exec_summary",
                   "theme_analysis", "diagram_data", "performance", "lineage",
                   "editor_data", "report_stats", "pq_lineage")
    list_fields = ("findings", "kpi_suggestions", "dax_improvements",
                   "dax_complexity", "unused_measures")
    for field in dict_fields:
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                data[field] = {}
    for field in list_fields:
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                data[field] = []
    return data


def delete_analysis(analysis_id: int) -> bool:
    """Delete an analysis by ID, including stored ZIP file."""
    conn = get_db()
    row = conn.execute("SELECT source_zip_path FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    if deleted and row and row["source_zip_path"]:
        _uploads = "/tmp/uploads" if _IS_VERCEL else os.path.join(os.path.dirname(__file__), "uploads")
        zip_path = os.path.join(_uploads, row["source_zip_path"])
        if os.path.exists(zip_path):
            os.unlink(zip_path)
    return deleted


def compare_analyses(id1: int, id2: int) -> dict | None:
    """Compare two analyses and return differences."""
    a1 = get_analysis(id1)
    a2 = get_analysis(id2)
    if not a1 or not a2:
        return None

    # Score delta
    score_delta = a2["total_score"] - a1["total_score"]

    # Find new and removed findings by rule_id + location
    findings1 = {(f["rule_id"], f.get("location", "")) for f in (a1.get("findings") or [])}
    findings2 = {(f["rule_id"], f.get("location", "")) for f in (a2.get("findings") or [])}

    new_findings = []
    for f in (a2.get("findings") or []):
        key = (f["rule_id"], f.get("location", ""))
        if key not in findings1:
            new_findings.append(f)

    removed_findings = []
    for f in (a1.get("findings") or []):
        key = (f["rule_id"], f.get("location", ""))
        if key not in findings2:
            removed_findings.append(f)

    # Category score changes
    cat_scores1 = a1.get("category_scores") or {}
    cat_scores2 = a2.get("category_scores") or {}
    cat_changes = {}
    for cat in set(list(cat_scores1.keys()) + list(cat_scores2.keys())):
        s1 = cat_scores1.get(cat, 0)
        s2 = cat_scores2.get(cat, 0)
        cat_changes[cat] = {"before": s1, "after": s2, "delta": s2 - s1}

    return {
        "analysis1": a1,
        "analysis2": a2,
        "score_delta": round(score_delta, 1),
        "new_findings": new_findings,
        "removed_findings": removed_findings,
        "category_changes": cat_changes,
    }


# --- Dashboard ---

def get_dashboard_data() -> dict:
    """Build aggregated dashboard data for all projects."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, project_name, analyzed_at, total_score, grade, category_scores "
        "FROM analyses ORDER BY analyzed_at ASC"
    ).fetchall()
    conn.close()

    if not rows:
        return {"projects": [], "total_analyses": 0, "unique_projects": 0, "avg_score": 0}

    # Group by project name
    projects_map = {}
    for r in rows:
        name = r["project_name"]
        if name not in projects_map:
            projects_map[name] = {
                "name": name,
                "scores": [],
                "analyses_count": 0,
                "last_score": 0,
                "last_grade": "F",
                "last_analyzed": "",
                "category_scores": {},
            }
        proj = projects_map[name]
        proj["scores"].append(r["total_score"] or 0)
        proj["analyses_count"] += 1
        proj["last_score"] = r["total_score"] or 0
        proj["last_grade"] = r["grade"] or "F"
        proj["last_analyzed"] = r["analyzed_at"] or ""
        # Parse category scores
        try:
            cs = json.loads(r["category_scores"]) if r["category_scores"] else {}
            proj["category_scores"] = cs
        except (json.JSONDecodeError, TypeError):
            pass

    projects = sorted(projects_map.values(), key=lambda p: p["last_score"], reverse=True)
    total = len(rows)
    unique = len(projects)
    avg = round(sum(r["total_score"] or 0 for r in rows) / total, 1) if total else 0

    return {
        "projects": projects,
        "total_analyses": total,
        "unique_projects": unique,
        "avg_score": avg,
    }


# --- Schedules ---

def _init_schedule_tables():
    """Create schedule tables if not exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            source_zip_path TEXT NOT NULL,
            cron_expression TEXT DEFAULT '0 8 * * 1',
            email_to TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            last_run_at TIMESTAMP,
            last_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schedule_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER REFERENCES schedules(id),
            analysis_id INTEGER,
            score REAL,
            score_delta REAL,
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'success',
            error_message TEXT
        )
    """)
    conn.commit()
    conn.close()


# Auto-init schedule tables
_init_schedule_tables()


def get_all_schedules() -> list[dict]:
    """Get all schedules."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_schedule(sid: int) -> dict | None:
    """Get a single schedule."""
    conn = get_db()
    row = conn.execute("SELECT * FROM schedules WHERE id = ?", (sid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_schedule(project_name: str, source_zip_path: str,
                    cron_expression: str = "0 8 * * 1", email_to: str = "") -> int:
    """Create a new schedule."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO schedules (project_name, source_zip_path, cron_expression, email_to) VALUES (?, ?, ?, ?)",
        (project_name, source_zip_path, cron_expression, email_to),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def toggle_schedule(sid: int) -> bool:
    """Toggle schedule active state. Returns new state."""
    conn = get_db()
    row = conn.execute("SELECT is_active FROM schedules WHERE id = ?", (sid,)).fetchone()
    if not row:
        conn.close()
        return False
    new_state = 0 if row["is_active"] else 1
    conn.execute("UPDATE schedules SET is_active = ? WHERE id = ?", (new_state, sid))
    conn.commit()
    conn.close()
    return bool(new_state)


def delete_schedule(sid: int) -> bool:
    """Delete a schedule and its runs."""
    conn = get_db()
    conn.execute("DELETE FROM schedule_runs WHERE schedule_id = ?", (sid,))
    cursor = conn.execute("DELETE FROM schedules WHERE id = ?", (sid,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def save_schedule_run(schedule_id: int, analysis_id: int | None,
                      score: float, score_delta: float,
                      status: str = "success", error_message: str = ""):
    """Record a schedule run."""
    conn = get_db()
    conn.execute(
        "INSERT INTO schedule_runs (schedule_id, analysis_id, score, score_delta, status, error_message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (schedule_id, analysis_id, score, score_delta, status, error_message),
    )
    conn.execute(
        "UPDATE schedules SET last_run_at = CURRENT_TIMESTAMP, last_score = ? WHERE id = ?",
        (score, schedule_id),
    )
    conn.commit()
    conn.close()


def get_schedule_runs(schedule_id: int) -> list[dict]:
    """Get runs for a schedule."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM schedule_runs WHERE schedule_id = ? ORDER BY run_at DESC LIMIT 20",
        (schedule_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
