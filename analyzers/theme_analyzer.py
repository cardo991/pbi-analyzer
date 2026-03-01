"""Theme and color palette analyzer with WCAG contrast checking."""

import math
import re


def analyze_theme(theme_info: dict | None) -> dict | None:
    """Analyze theme colors for accessibility and similarity issues.

    Returns a dict with:
        colors: list of {hex, rgb, warnings}
        contrast_issues: list of {color1, color2, ratio, min_ratio}
        similarity_issues: list of {color1, color2, distance}
        overall_pass: bool
    """
    if not theme_info or not theme_info.get("data_colors"):
        return None

    colors = []
    hex_list = []
    for hex_color in theme_info["data_colors"]:
        hex_clean = _normalize_hex(hex_color)
        if hex_clean:
            rgb = _hex_to_rgb(hex_clean)
            colors.append({"hex": hex_clean, "rgb": rgb, "warnings": []})
            hex_list.append(hex_clean)

    if not colors:
        return None

    # Check WCAG contrast against white and dark backgrounds
    contrast_issues = []
    bg_white = (255, 255, 255)
    bg_dark = (13, 13, 31)  # --bg-surface dark theme

    for c in colors:
        ratio_white = _contrast_ratio(c["rgb"], bg_white)
        ratio_dark = _contrast_ratio(c["rgb"], bg_dark)
        if ratio_white < 4.5 and ratio_dark < 4.5:
            c["warnings"].append("low_contrast")
            contrast_issues.append({
                "color": c["hex"],
                "ratio_white": round(ratio_white, 2),
                "ratio_dark": round(ratio_dark, 2),
                "min_ratio": 4.5,
            })

    # Check for too-similar colors
    similarity_issues = []
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            dist = _color_distance(colors[i]["rgb"], colors[j]["rgb"])
            if dist < 30:
                similarity_issues.append({
                    "color1": colors[i]["hex"],
                    "color2": colors[j]["hex"],
                    "distance": round(dist, 1),
                })
                if "too_similar" not in colors[i]["warnings"]:
                    colors[i]["warnings"].append("too_similar")
                if "too_similar" not in colors[j]["warnings"]:
                    colors[j]["warnings"].append("too_similar")

    return {
        "name": theme_info.get("name", "Custom Theme"),
        "colors": colors,
        "contrast_issues": contrast_issues,
        "similarity_issues": similarity_issues,
        "overall_pass": len(contrast_issues) == 0 and len(similarity_issues) == 0,
        "background": theme_info.get("background"),
        "foreground": theme_info.get("foreground"),
    }


def _normalize_hex(color: str) -> str | None:
    """Normalize a color string to #RRGGBB format."""
    if not isinstance(color, str):
        return None
    color = color.strip()
    if not color.startswith("#"):
        color = "#" + color
    # Remove alpha channel if present
    if len(color) == 9:  # #RRGGBBAA
        color = color[:7]
    if len(color) == 4:  # #RGB -> #RRGGBB
        color = "#" + color[1] * 2 + color[2] * 2 + color[3] * 2
    if re.match(r'^#[0-9a-fA-F]{6}$', color):
        return color.upper()
    return None


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB to (R, G, B) tuple."""
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculate relative luminance per WCAG 2.1."""
    def linearize(val):
        v = val / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(rgb1: tuple, rgb2: tuple) -> float:
    """Calculate WCAG 2.1 contrast ratio between two colors."""
    l1 = _relative_luminance(rgb1)
    l2 = _relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _color_distance(rgb1: tuple, rgb2: tuple) -> float:
    """Calculate Euclidean distance in RGB space."""
    return math.sqrt(
        (rgb1[0] - rgb2[0]) ** 2 +
        (rgb1[1] - rgb2[1]) ** 2 +
        (rgb1[2] - rgb2[2]) ** 2
    )
