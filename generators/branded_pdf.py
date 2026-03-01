"""Branding configuration for PDF/Excel/Markdown exports."""

import os


DEFAULT_BRANDING = {
    "company_name": "",
    "logo_path": "",
    "primary_color": "#0077CC",
    "secondary_color": "#00bfff",
    "footer_text": "",
}

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "branding")


def get_branding_config() -> dict:
    """Get current branding configuration from database."""
    try:
        from database import get_branding
        branding = get_branding()
        if branding:
            return branding
    except Exception:
        pass
    return dict(DEFAULT_BRANDING)


def save_branding_config(company_name: str = "", logo_file=None,
                         primary_color: str = "#0077CC",
                         secondary_color: str = "#00bfff",
                         footer_text: str = "") -> dict:
    """Save branding configuration.

    Args:
        company_name: Company/organization name
        logo_file: File-like object for logo upload (or None to keep existing)
        primary_color: Primary brand color (hex)
        secondary_color: Secondary brand color (hex)
        footer_text: Custom footer text for exports

    Returns the saved branding config dict.
    """
    logo_path = ""

    # Handle logo upload
    if logo_file and logo_file.filename:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        # Sanitize filename
        ext = os.path.splitext(logo_file.filename)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".svg", ".gif"):
            safe_name = f"logo{ext}"
            full_path = os.path.join(UPLOAD_DIR, safe_name)
            logo_file.save(full_path)
            logo_path = f"uploads/branding/{safe_name}"

    config = {
        "company_name": company_name.strip(),
        "logo_path": logo_path,
        "primary_color": primary_color if primary_color.startswith("#") else "#0077CC",
        "secondary_color": secondary_color if secondary_color.startswith("#") else "#00bfff",
        "footer_text": footer_text.strip(),
    }

    # If no new logo uploaded, keep existing
    if not logo_path:
        try:
            from database import get_branding
            existing = get_branding()
            if existing:
                config["logo_path"] = existing.get("logo_path", "")
        except Exception:
            pass

    # Save to database
    try:
        from database import save_branding
        save_branding(config)
    except Exception:
        pass

    return config


def generate_branding_css(branding: dict) -> str:
    """Generate CSS overrides for branding colors."""
    primary = branding.get("primary_color", "#0077CC")
    secondary = branding.get("secondary_color", "#00bfff")

    return f"""
    .branding-header {{
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem;
        border-bottom: 2px solid {primary};
        margin-bottom: 1rem;
    }}
    .branding-header img {{
        max-height: 48px;
        width: auto;
    }}
    .branding-header .company-name {{
        font-size: 1.1rem;
        font-weight: 700;
        color: {primary};
    }}
    .branding-footer {{
        text-align: center;
        padding: 0.5rem;
        font-size: 0.75rem;
        color: #666;
        border-top: 1px solid #ddd;
        margin-top: 1rem;
    }}
    @media print {{
        .branding-header {{ display: flex !important; }}
        .branding-footer {{ display: block !important; }}
    }}
    """


def generate_branding_html(branding: dict) -> dict:
    """Generate HTML snippets for branding header and footer.

    Returns dict with 'header' and 'footer' HTML strings.
    """
    header = ""
    footer = ""

    company = branding.get("company_name", "")
    logo = branding.get("logo_path", "")
    footer_text = branding.get("footer_text", "")

    if company or logo:
        logo_html = ""
        if logo:
            logo_html = f'<img src="/static/{logo}" alt="{company}">'
        header = f"""
        <div class="branding-header" id="branding-header">
            {logo_html}
            <span class="company-name">{company}</span>
        </div>
        """

    if footer_text:
        footer = f"""
        <div class="branding-footer" id="branding-footer">
            {footer_text}
        </div>
        """

    return {"header": header, "footer": footer}
