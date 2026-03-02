"""SVG badge and embeddable widget generator."""


GRADE_COLORS = {
    "A": "#22c55e",
    "B": "#3b82f6",
    "C": "#f59e0b",
    "D": "#f97316",
    "F": "#ef4444",
}


def generate_badge_svg(score: float, grade: str) -> str:
    """Generate a shields.io-style SVG badge."""
    color = GRADE_COLORS.get(grade, "#6b7280")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="186" height="20">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="186" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="72" height="20" fill="#555"/>
    <rect x="72" width="78" height="20" fill="#444"/>
    <rect x="150" width="36" height="20" fill="{color}"/>
    <rect width="186" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="36" y="15" fill="#010101" fill-opacity=".3">GridPulse</text>
    <text x="36" y="14">GridPulse</text>
    <text x="111" y="15" fill="#010101" fill-opacity=".3">{score:.0f} / 100</text>
    <text x="111" y="14">{score:.0f} / 100</text>
    <text x="168" y="15" fill="#010101" fill-opacity=".3">{grade}</text>
    <text x="168" y="14">{grade}</text>
  </g>
</svg>'''


def generate_widget_html(score: float, grade: str, project_name: str,
                         analysis_url: str = "") -> str:
    """Generate an embeddable HTML mini score card."""
    color = GRADE_COLORS.get(grade, "#6b7280")
    return f'''<div style="font-family:system-ui,-apple-system,sans-serif;display:inline-block;border:1px solid #e2e8f0;border-radius:8px;padding:12px 18px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1);text-align:center;min-width:160px;">
  <div style="font-size:11px;color:#64748b;margin-bottom:4px;">GridPulse Analysis</div>
  <div style="font-size:13px;font-weight:700;color:#1e293b;margin-bottom:8px;">{project_name}</div>
  <div style="display:flex;align-items:center;justify-content:center;gap:8px;">
    <span style="font-size:28px;font-weight:800;color:#1e293b;">{score:.0f}</span>
    <span style="font-size:18px;font-weight:800;color:{color};background:{color}22;padding:2px 10px;border-radius:4px;">{grade}</span>
  </div>
  {f'<a href="{analysis_url}" style="display:block;margin-top:8px;font-size:11px;color:#3b82f6;text-decoration:none;">View Report &rarr;</a>' if analysis_url else ''}
</div>'''
