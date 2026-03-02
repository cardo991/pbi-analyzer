"""
AI-powered insights generator for Power BI analysis results.

Sends a compact summary of the analysis to an LLM (OpenAI or Anthropic)
and returns prioritized recommendations, risk assessment, and quick wins.
"""

LANG_MAP = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
}

SYSTEM_PROMPT = (
    "You are an expert Power BI consultant. Analyze the following Power BI model "
    "audit results and provide actionable insights. Be concise and specific. "
    "Reference actual finding messages when possible."
)

USER_PROMPT_TEMPLATE = """\
Respond entirely in {language}.

## Power BI Model Audit Summary

**Overall score**: {score}/100 (Grade: {grade})

### Category Scores
- Data Model: {dm_score}/{dm_max}
- DAX: {dax_score}/{dax_max}
- Power Query: {pq_score}/{pq_max}
- Report: {rpt_score}/{rpt_max}

### Executive Summary Stats
- Tables: {tables}
- Measures: {measures}
- Columns: {columns}
- Relationships: {relationships}
- Total findings: {total_findings} (Errors: {errors}, Warnings: {warnings}, Info: {infos})

### Top Findings (by severity)
{top_findings}

---

Based on the audit above, provide:

1. **5 Prioritized Recommendations** — numbered, most impactful first. Each should have a clear action and expected benefit.
2. **Risk Assessment** — one of: low, medium, high, critical. Justify in one sentence.
3. **3 Quick Wins** — changes that are easy to implement and yield immediate improvement.

Format your response in Markdown.
"""


def _compute_grade(score):
    """Return letter grade for a numeric score."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _build_prompt(documentation, score, findings, exec_summary, lang):
    """Build a compact prompt (~800 tokens) from the analysis results."""
    language = LANG_MAP.get(lang, "English")
    grade = _compute_grade(score)

    # Extract executive summary stats with safe defaults
    tables = exec_summary.get("tables", 0)
    measures = exec_summary.get("measures", 0)
    columns = exec_summary.get("columns", 0)
    relationships = exec_summary.get("relationships", 0)

    # Category scores
    categories = exec_summary.get("categories", {})
    dm = categories.get("data_model", {})
    dax = categories.get("dax", {})
    pq = categories.get("power_query", {})
    rpt = categories.get("report", {})

    # Count findings by severity
    severity_order = {"error": 0, "warning": 1, "info": 2}
    errors = sum(1 for f in findings if f.get("severity") == "error")
    warnings = sum(1 for f in findings if f.get("severity") == "warning")
    infos = sum(1 for f in findings if f.get("severity") == "info")

    # Sort findings: error first, then warning, then info — take top 10
    sorted_findings = sorted(
        findings,
        key=lambda f: severity_order.get(f.get("severity", "info"), 9),
    )
    top_10 = sorted_findings[:10]
    top_findings_text = "\n".join(
        f"- [{f.get('severity', 'info').upper()}] [{f.get('category', '')}] "
        f"{f.get('message', f.get('description', ''))}"
        for f in top_10
    )
    if not top_findings_text:
        top_findings_text = "- No findings reported."

    return USER_PROMPT_TEMPLATE.format(
        language=language,
        score=score,
        grade=grade,
        dm_score=dm.get("score", 0),
        dm_max=dm.get("max", 0),
        dax_score=dax.get("score", 0),
        dax_max=dax.get("max", 0),
        pq_score=pq.get("score", 0),
        pq_max=pq.get("max", 0),
        rpt_score=rpt.get("score", 0),
        rpt_max=rpt.get("max", 0),
        tables=tables,
        measures=measures,
        columns=columns,
        relationships=relationships,
        total_findings=len(findings),
        errors=errors,
        warnings=warnings,
        infos=infos,
        top_findings=top_findings_text,
    )


def _call_openai(api_key, model, system_prompt, user_prompt):
    """Call OpenAI chat completions API. Returns the assistant message text."""
    try:
        import openai
    except ImportError:
        raise RuntimeError(
            "The 'openai' package is not installed. "
            "Run: pip install openai"
        )

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1024,
    )
    return response.choices[0].message.content


def _call_anthropic(api_key, model, system_prompt, user_prompt):
    """Call Anthropic messages API. Returns the assistant message text."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "The 'anthropic' package is not installed. "
            "Run: pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.content[0].text


def _parse_response(text):
    """Extract recommendations list from the raw LLM markdown response."""
    recommendations = []
    for line in text.splitlines():
        stripped = line.strip()
        # Match numbered lines like "1. ..." or "1) ..."
        if stripped and len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)" :
            recommendations.append(stripped[2:].strip().lstrip(" "))
        elif stripped and len(stripped) > 3 and stripped[:2].replace(".", "").replace(")", "").isdigit():
            idx = stripped.index(".") if "." in stripped[:3] else stripped.index(")")
            recommendations.append(stripped[idx + 1:].strip())

    # Deduplicate while keeping order, cap at 8
    seen = set()
    unique = []
    for r in recommendations:
        key = r[:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    recommendations = unique[:8]

    # Extract risk assessment keyword
    risk = "medium"
    text_lower = text.lower()
    for level in ("critical", "high", "medium", "low"):
        if f"**risk assessment**" in text_lower or f"risk assessment" in text_lower:
            # Look near the risk assessment section
            ra_start = text_lower.find("risk assessment")
            if ra_start != -1:
                snippet = text_lower[ra_start: ra_start + 200]
                if level in snippet:
                    risk = level
                    break

    return recommendations, risk


def generate_ai_insights(
    documentation,
    score,
    findings,
    exec_summary,
    provider="openai",
    api_key="",
    model="gpt-4o-mini",
    lang="en",
):
    """
    Generate AI-powered insights for a Power BI analysis.

    Parameters
    ----------
    documentation : dict
        Full documentation dict produced by the documentation generator.
    score : int | float
        Overall analysis score (0-100).
    findings : list[dict]
        List of finding dicts with keys: severity, category, message/description.
    exec_summary : dict
        Executive summary with tables, measures, columns, relationships, categories.
    provider : str
        LLM provider — "openai" or "anthropic".
    api_key : str
        API key for the chosen provider.
    model : str
        Model identifier (e.g. "gpt-4o-mini", "claude-sonnet-4-20250514").
    lang : str
        Response language code — "en", "es", or "pt".

    Returns
    -------
    dict
        {
            "insights": str (markdown),
            "recommendations": list[str],
            "risk_assessment": str,
            "provider": str,
            "model": str,
            "error": str | None,
        }
    """
    result = {
        "insights": "",
        "recommendations": [],
        "risk_assessment": "",
        "provider": provider,
        "model": model,
        "error": None,
    }

    if not api_key:
        result["error"] = "No API key provided. Please set your API key in Settings."
        return result

    provider_lower = provider.lower().strip()
    if provider_lower not in ("openai", "anthropic"):
        result["error"] = f"Unsupported provider: '{provider}'. Use 'openai' or 'anthropic'."
        return result

    # Build the prompt
    user_prompt = _build_prompt(documentation, score, findings, exec_summary, lang)

    try:
        if provider_lower == "openai":
            raw = _call_openai(api_key, model, SYSTEM_PROMPT, user_prompt)
        else:
            raw = _call_anthropic(api_key, model, SYSTEM_PROMPT, user_prompt)

        result["insights"] = raw
        recommendations, risk = _parse_response(raw)
        result["recommendations"] = recommendations
        result["risk_assessment"] = risk

    except RuntimeError as exc:
        # Library not installed
        result["error"] = str(exc)
    except Exception as exc:
        result["error"] = f"API call failed ({provider}): {exc}"

    return result
