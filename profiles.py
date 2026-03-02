"""Compliance profiles for rule configuration."""

import json
from database import get_db

BUILTIN_PROFILES = {
    "enterprise": {
        "name": "Enterprise",
        "description": "Strict rules for production enterprise reports",
        "disabled_rules": [],
        "thresholds": {
            "max_visuals": 12,
            "max_pages": 10,
            "max_steps": 15,
            "complex_measure": 200,
            "naming_convention": "title_case",
            "max_bookmarks": 10,
            "max_columns_per_table": 60,
        },
    },
    "standard": {
        "name": "Standard",
        "description": "Balanced rules for typical Power BI projects",
        "disabled_rules": ["DM-006", "DM-007", "DM-008"],
        "thresholds": {
            "max_visuals": 20,
            "max_pages": 15,
            "max_steps": 25,
            "complex_measure": 300,
            "naming_convention": "title_case",
            "max_bookmarks": 20,
            "max_columns_per_table": 100,
        },
    },
    "personal": {
        "name": "Personal",
        "description": "Relaxed rules for personal or prototype reports",
        "disabled_rules": [
            "DM-006", "DM-007", "DM-008", "DM-009", "DM-010",
            "DAX-003", "DAX-006", "DAX-007", "DAX-008",
            "NC-001", "NC-002", "NC-003",
            "SEC-001", "SEC-003", "SEC-007",
            "BK-001", "BK-002", "BK-003",
        ],
        "thresholds": {
            "max_visuals": 30,
            "max_pages": 25,
            "max_steps": 40,
            "complex_measure": 500,
            "naming_convention": "none",
            "max_bookmarks": 50,
            "max_columns_per_table": 200,
        },
    },
}


def init_profiles():
    """Seed builtin profiles if they don't exist."""
    conn = get_db()
    for key, profile in BUILTIN_PROFILES.items():
        existing = conn.execute(
            "SELECT id FROM profiles WHERE name = ?", (profile["name"],)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO profiles (name, description, is_builtin, disabled_rules, thresholds) "
                "VALUES (?, ?, 1, ?, ?)",
                (profile["name"], profile["description"],
                 json.dumps(profile["disabled_rules"]),
                 json.dumps(profile["thresholds"])),
            )
    conn.commit()
    conn.close()


def get_all_profiles() -> list[dict]:
    """Get all profiles (builtin + custom)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, description, is_builtin, disabled_rules, thresholds "
        "FROM profiles ORDER BY is_builtin DESC, name"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["disabled_rules"] = json.loads(d["disabled_rules"] or "[]")
        d["thresholds"] = json.loads(d["thresholds"] or "{}")
        result.append(d)
    return result


def get_profile(profile_id: int) -> dict | None:
    """Get a single profile by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["disabled_rules"] = json.loads(d["disabled_rules"] or "[]")
    d["thresholds"] = json.loads(d["thresholds"] or "{}")
    return d


def save_custom_profile(name: str, description: str,
                        disabled_rules: list, thresholds: dict) -> int:
    """Save a custom profile. Returns new row ID."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO profiles (name, description, is_builtin, disabled_rules, thresholds) "
        "VALUES (?, ?, 0, ?, ?)",
        (name, description, json.dumps(disabled_rules), json.dumps(thresholds)),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def delete_custom_profile(profile_id: int) -> bool:
    """Delete a custom profile (cannot delete builtins)."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM profiles WHERE id = ? AND is_builtin = 0", (profile_id,)
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def export_profile(profile_id: int) -> dict | None:
    """Export a profile as JSON-serializable dict."""
    p = get_profile(profile_id)
    if not p:
        return None
    return {
        "name": p["name"],
        "description": p["description"],
        "disabled_rules": p["disabled_rules"],
        "thresholds": p["thresholds"],
    }


def import_profile(data: dict) -> int:
    """Import a profile from JSON dict. Returns new row ID."""
    return save_custom_profile(
        name=data.get("name", "Imported Profile"),
        description=data.get("description", ""),
        disabled_rules=data.get("disabled_rules", []),
        thresholds=data.get("thresholds", {}),
    )
