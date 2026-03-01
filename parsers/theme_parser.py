"""Parser for Power BI report theme/color palette."""

import json
import os


def parse_theme(report_dir: str) -> dict | None:
    """Parse theme information from report definition.

    Returns a dict with:
        data_colors: list of hex color strings
        background: hex color or None
        foreground: hex color or None
        name: theme name
    Or None if no theme found.
    """
    # Try PBIR format: definition/theme.json
    definition_dir = os.path.join(report_dir, "definition")
    theme_paths = [
        os.path.join(definition_dir, "theme.json"),
        os.path.join(report_dir, "theme.json"),
    ]

    for path in theme_paths:
        if os.path.exists(path):
            result = _parse_theme_file(path)
            if result:
                return result

    # Try embedded theme in report.json
    report_paths = [
        os.path.join(definition_dir, "report.json"),
        os.path.join(report_dir, "report.json"),
    ]

    for path in report_paths:
        if os.path.exists(path):
            result = _parse_embedded_theme(path)
            if result:
                return result

    # Try scanning for any theme JSON in the report directory
    for root, dirs, files in os.walk(report_dir):
        for f in files:
            if "theme" in f.lower() and f.endswith(".json"):
                result = _parse_theme_file(os.path.join(root, f))
                if result:
                    return result
        # Don't recurse too deep
        if root.count(os.sep) - report_dir.count(os.sep) > 3:
            break

    return None


def _parse_theme_file(path: str) -> dict | None:
    """Parse a standalone theme JSON file."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError):
        return None

    return _extract_theme_info(data)


def _parse_embedded_theme(report_json_path: str) -> dict | None:
    """Extract theme from an embedded theme in report.json."""
    try:
        with open(report_json_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError):
        return None

    # Look for theme config in various locations
    theme_data = data.get("theme", data.get("themeCollection", {}).get("baseTheme"))
    if isinstance(theme_data, str):
        try:
            theme_data = json.loads(theme_data)
        except json.JSONDecodeError:
            return None

    if theme_data and isinstance(theme_data, dict):
        return _extract_theme_info(theme_data)

    # Check config string
    config_str = data.get("config", "")
    if isinstance(config_str, str) and config_str:
        try:
            config = json.loads(config_str)
            theme_data = config.get("theme", config.get("themeCollection", {}).get("baseTheme"))
            if theme_data:
                return _extract_theme_info(theme_data)
        except json.JSONDecodeError:
            pass

    return None


def _extract_theme_info(data: dict) -> dict | None:
    """Extract color info from theme JSON structure."""
    data_colors = data.get("dataColors", [])

    # Also try Power BI report theme format
    if not data_colors:
        palette = data.get("palette", data.get("colors", []))
        if isinstance(palette, list):
            data_colors = palette

    # Try nested format
    if not data_colors:
        visual_styles = data.get("visualStyles", {})
        if visual_styles:
            # Some themes embed colors in visualStyles
            pass

    if not data_colors:
        return None

    background = data.get("background", data.get("tableAccent"))
    foreground = data.get("foreground", data.get("textClasses", {}).get("label", {}).get("color"))
    name = data.get("name", "Custom Theme")

    return {
        "data_colors": data_colors[:20],  # Cap at 20 colors
        "background": background,
        "foreground": foreground,
        "name": name,
    }
