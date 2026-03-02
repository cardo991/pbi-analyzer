"""KPI suggestions engine + DAX improvement suggestions."""

import re
from models import SemanticModel, Finding


# -------------------------------------------------------
# KPI Suggestion Templates
# -------------------------------------------------------
KPI_TEMPLATES = [
    {
        "id": "kpi-total-sales",
        "name_en": "Total Sales",
        "name_es": "Ventas Totales",
        "name_pt": "Vendas Totais",
        "desc_en": "Sum of sales/revenue amount. Essential for any sales report.",
        "desc_es": "Suma del monto de ventas/ingresos. Esencial para cualquier reporte de ventas.",
        "desc_pt": "Soma do valor de vendas/receita. Essencial para qualquer relatorio de vendas.",
        "icon": "bi-currency-dollar",
        "triggers": {"columns": ["amount", "revenue", "sales", "total", "value", "price", "importe", "venta", "ingreso", "monto"]},
        "dax": "Total Sales = SUM({table}[{column}])",
        "format": "$#,##0.00",
        "existing_patterns": ["total sales", "sum of sales", "total revenue", "ventas totales"],
    },
    {
        "id": "kpi-total-quantity",
        "name_en": "Total Quantity",
        "name_es": "Cantidad Total",
        "name_pt": "Quantidade Total",
        "desc_en": "Sum of quantity/units sold. Key metric for volume analysis.",
        "desc_es": "Suma de cantidad/unidades vendidas. Metrica clave para analisis de volumen.",
        "desc_pt": "Soma de quantidade/unidades vendidas. Metrica chave para analise de volume.",
        "icon": "bi-box-seam",
        "triggers": {"columns": ["quantity", "qty", "units", "count", "cantidad", "unidades"]},
        "dax": "Total Quantity = SUM({table}[{column}])",
        "format": "#,##0",
        "existing_patterns": ["total quantity", "total qty", "cantidad total"],
    },
    {
        "id": "kpi-avg-order-value",
        "name_en": "Average Order Value",
        "name_es": "Valor Promedio por Orden",
        "name_pt": "Valor Medio por Pedido",
        "desc_en": "Average amount per transaction. Helps understand customer spending patterns.",
        "desc_es": "Monto promedio por transaccion. Ayuda a entender patrones de gasto.",
        "desc_pt": "Valor medio por transacao. Ajuda a entender padroes de gastos.",
        "icon": "bi-cart-check",
        "triggers": {"columns": ["amount", "revenue", "total", "sales", "importe", "monto"]},
        "dax": "Avg Order Value = AVERAGE({table}[{column}])",
        "format": "$#,##0.00",
        "existing_patterns": ["avg order", "average order", "aov", "valor promedio"],
    },
    {
        "id": "kpi-distinct-customers",
        "name_en": "Distinct Customers",
        "name_es": "Clientes Unicos",
        "name_pt": "Clientes Distintos",
        "desc_en": "Count of unique customers. Core metric for customer base analysis.",
        "desc_es": "Conteo de clientes unicos. Metrica central para analisis de base de clientes.",
        "desc_pt": "Contagem de clientes unicos. Metrica central para analise de base de clientes.",
        "icon": "bi-people",
        "triggers": {"columns": ["customerid", "customerkey", "customer_id", "customer_key", "clienteid", "cliente_id", "customername"]},
        "dax": "Distinct Customers = DISTINCTCOUNT({table}[{column}])",
        "format": "#,##0",
        "existing_patterns": ["distinct customer", "unique customer", "customer count", "clientes unicos"],
    },
    {
        "id": "kpi-yoy-growth",
        "name_en": "Year-over-Year Growth %",
        "name_es": "Crecimiento Interanual %",
        "name_pt": "Crescimento Ano a Ano %",
        "desc_en": "Percentage change compared to the same period last year. Requires a date table.",
        "desc_es": "Cambio porcentual respecto al mismo periodo del ano anterior. Requiere tabla de fechas.",
        "desc_pt": "Mudanca percentual comparada ao mesmo periodo do ano anterior. Requer tabela de datas.",
        "icon": "bi-graph-up-arrow",
        "triggers": {"requires_date_table": True, "requires_base_measure": True},
        "dax": "YoY Growth % =\nVAR _Current = [{base_measure}]\nVAR _Previous = CALCULATE([{base_measure}], DATEADD({date_table}[{date_column}], -1, YEAR))\nRETURN\nIF(NOT ISBLANK(_Previous), DIVIDE(_Current - _Previous, _Previous))",
        "format": "0.00%",
        "existing_patterns": ["yoy", "year over year", "interanual", "crecimiento"],
    },
    {
        "id": "kpi-mtd",
        "name_en": "Month-to-Date Total",
        "name_es": "Acumulado del Mes",
        "name_pt": "Acumulado do Mes",
        "desc_en": "Running total from the start of the current month. Useful for tracking monthly targets.",
        "desc_es": "Total acumulado desde el inicio del mes actual. Util para seguimiento de metas mensuales.",
        "desc_pt": "Total acumulado desde o inicio do mes atual. Util para acompanhamento de metas mensais.",
        "icon": "bi-calendar-month",
        "triggers": {"requires_date_table": True, "requires_base_measure": True},
        "dax": "MTD = TOTALMTD([{base_measure}], {date_table}[{date_column}])",
        "format": "$#,##0.00",
        "existing_patterns": ["mtd", "month to date", "acumulado mes"],
    },
    {
        "id": "kpi-ytd",
        "name_en": "Year-to-Date Total",
        "name_es": "Acumulado del Ano",
        "name_pt": "Acumulado do Ano",
        "desc_en": "Running total from the start of the current year.",
        "desc_es": "Total acumulado desde el inicio del ano actual.",
        "desc_pt": "Total acumulado desde o inicio do ano atual.",
        "icon": "bi-calendar-range",
        "triggers": {"requires_date_table": True, "requires_base_measure": True},
        "dax": "YTD = TOTALYTD([{base_measure}], {date_table}[{date_column}])",
        "format": "$#,##0.00",
        "existing_patterns": ["ytd", "year to date", "acumulado ano"],
    },
    {
        "id": "kpi-profit-margin",
        "name_en": "Profit Margin %",
        "name_es": "Margen de Ganancia %",
        "name_pt": "Margem de Lucro %",
        "desc_en": "Profit as a percentage of revenue. Requires revenue and cost columns.",
        "desc_es": "Ganancia como porcentaje de ingresos. Requiere columnas de ingreso y costo.",
        "desc_pt": "Lucro como porcentagem da receita. Requer colunas de receita e custo.",
        "icon": "bi-percent",
        "triggers": {"columns_pair": [["revenue", "cost"], ["sales", "cost"], ["amount", "cost"], ["ingreso", "costo"], ["venta", "costo"]]},
        "dax": "Profit Margin % = DIVIDE(SUM({table}[{revenue_col}]) - SUM({table}[{cost_col}]), SUM({table}[{revenue_col}]))",
        "format": "0.00%",
        "existing_patterns": ["profit margin", "margen", "margin"],
    },
    {
        "id": "kpi-orders-count",
        "name_en": "Total Orders / Transactions",
        "name_es": "Total de Ordenes / Transacciones",
        "name_pt": "Total de Pedidos / Transacoes",
        "desc_en": "Count of orders or transactions. Basic volume metric.",
        "desc_es": "Conteo de ordenes o transacciones. Metrica basica de volumen.",
        "desc_pt": "Contagem de pedidos ou transacoes. Metrica basica de volume.",
        "icon": "bi-receipt",
        "triggers": {"columns": ["orderid", "order_id", "orderkey", "transactionid", "transaction_id", "invoiceid", "facturaid", "ordenid"]},
        "dax": "Total Orders = DISTINCTCOUNT({table}[{column}])",
        "format": "#,##0",
        "existing_patterns": ["total orders", "order count", "transaction count", "total ordenes"],
    },
]

# -------------------------------------------------------
# DAX Improvement Suggestions
# -------------------------------------------------------
DAX_IMPROVEMENTS = {
    "DAX-001": {
        "en": "Suggested improvement: extract the inner CALCULATE into a separate measure.",
        "es": "Mejora sugerida: extraer el CALCULATE interno en una medida separada.",
        "pt": "Melhoria sugerida: extrair o CALCULATE interno em uma medida separada.",
    },
    "DAX-002": {
        "build_suggestion": True,
    },
    "DAX-004": {
        "en": "Remove the IF wrapper and use the condition directly.",
        "es": "Elimine el IF y use la condicion directamente.",
        "pt": "Remova o IF e use a condicao diretamente.",
    },
    "DAX-005": {
        "build_suggestion": True,
    },
    "DAX-009": {
        "en": "Move the filter condition directly into CALCULATE as a filter argument.",
        "es": "Mueva la condicion del filtro directamente a CALCULATE como argumento de filtro.",
        "pt": "Mova a condicao do filtro diretamente para o CALCULATE como argumento de filtro.",
    },
    "DAX-010": {
        "build_suggestion": True,
    },
    "DAX-011": {
        "en": "Replace raw division with DIVIDE(numerator, denominator, 0).",
        "es": "Reemplace la division directa con DIVIDE(numerador, denominador, 0).",
        "pt": "Substitua a divisao direta por DIVIDE(numerador, denominador, 0).",
    },
}


def generate_kpi_suggestions(model: SemanticModel, lang: str = "en") -> list[dict]:
    """Analyze the model and suggest KPIs that are missing."""
    suggestions = []
    existing_measures = _get_all_measures_lower(model)

    # Find date table info
    date_info = _find_date_table(model)
    # Find the first "base" measure (typically a SUM)
    base_measure = _find_base_measure(model)

    for kpi in KPI_TEMPLATES:
        # Check if a similar measure already exists
        if _measure_exists(kpi["existing_patterns"], existing_measures):
            continue

        triggers = kpi["triggers"]

        # Column-based triggers
        if "columns" in triggers:
            match = _find_matching_column(model, triggers["columns"])
            if match:
                table_name, col_name = match
                dax = kpi["dax"].format(table=table_name, column=col_name)
                suggestions.append(_build_suggestion(kpi, dax, lang))
                continue

        # Column pair triggers (revenue + cost)
        if "columns_pair" in triggers:
            for pair in triggers["columns_pair"]:
                match = _find_column_pair(model, pair[0], pair[1])
                if match:
                    table_name, rev_col, cost_col = match
                    dax = kpi["dax"].format(table=table_name, revenue_col=rev_col, cost_col=cost_col)
                    suggestions.append(_build_suggestion(kpi, dax, lang))
                    break
            continue

        # Time intelligence triggers
        if triggers.get("requires_date_table") and triggers.get("requires_base_measure"):
            if date_info and base_measure:
                dax = kpi["dax"].format(
                    base_measure=base_measure,
                    date_table=date_info["table"],
                    date_column=date_info["column"],
                )
                suggestions.append(_build_suggestion(kpi, dax, lang))

    return suggestions


def generate_dax_improvements(findings: list[Finding], model: SemanticModel, lang: str = "en") -> list[Finding]:
    """Enrich DAX findings with improvement suggestions (code rewrites)."""
    from analyzers.dax_optimizer import optimize_measure

    # Build measure expression map: (table_name, measure_name) -> expression
    measure_map = {}
    for t in model.tables:
        for m in t.measures:
            tname = m.table_name or t.name
            measure_map[(tname, m.name)] = m.expression

    for f in findings:
        if f.category != "dax":
            continue

        # Parse location to extract table_name and measure_name
        table_name, measure_name = _parse_location(f.location)
        if table_name and measure_name:
            f.details["table_name"] = table_name
            f.details["measure_name"] = measure_name

        # Try concrete optimizer first
        expression = measure_map.get((table_name, measure_name), "")
        if expression:
            optimized = optimize_measure(expression)
            if optimized:
                f.details["suggestion"] = optimized
                continue

        # Fall back to text tips
        improvement = DAX_IMPROVEMENTS.get(f.rule_id)
        if not improvement:
            continue

        if improvement.get("build_suggestion"):
            suggested = _build_dax_rewrite(f, model, lang)
            if suggested:
                f.details["suggestion"] = suggested
        else:
            tip = improvement.get(lang, improvement.get("en", ""))
            if tip:
                f.details["suggestion"] = tip

    return findings


# -------------------------------------------------------
# Internal helpers
# -------------------------------------------------------

def _parse_location(location: str) -> tuple[str, str]:
    """Extract table name and measure name from a location string.

    Expected format: "Table 'TableName', Measure 'MeasureName'"
    """
    table_match = re.search(r"Table\s+'([^']+)'", location)
    measure_match = re.search(r"Measure\s+'([^']+)'", location)
    table_name = table_match.group(1) if table_match else ""
    measure_name = measure_match.group(1) if measure_match else ""
    return table_name, measure_name


def _build_suggestion(kpi: dict, dax: str, lang: str) -> dict:
    name_key = f"name_{lang}"
    desc_key = f"desc_{lang}"
    return {
        "id": kpi["id"],
        "name": kpi.get(name_key, kpi["name_en"]),
        "description": kpi.get(desc_key, kpi["desc_en"]),
        "icon": kpi["icon"],
        "dax": dax,
        "format": kpi.get("format", ""),
    }


def _get_all_measures_lower(model: SemanticModel) -> set[str]:
    names = set()
    for t in model.tables:
        for m in t.measures:
            names.add(m.name.lower())
            if m.expression:
                names.add(m.expression.lower()[:80])
    return names


def _measure_exists(patterns: list[str], existing: set[str]) -> bool:
    for pat in patterns:
        for name in existing:
            if pat in name:
                return True
    return False


def _find_matching_column(model: SemanticModel, keywords: list[str]) -> tuple[str, str] | None:
    """Find first numeric column whose name matches any keyword."""
    for t in model.tables:
        if t.name.startswith("DateTable") or t.name.startswith("LocalDateTable"):
            continue
        for c in t.columns:
            if c.column_type != "data":
                continue
            col_lower = c.name.lower().replace(" ", "").replace("_", "")
            for kw in keywords:
                if kw in col_lower and c.data_type in ("double", "decimal", "int64", "currency"):
                    return (t.name, c.name)
    # Also check string columns for IDs (customer, order)
    for t in model.tables:
        if t.name.startswith("DateTable") or t.name.startswith("LocalDateTable"):
            continue
        for c in t.columns:
            if c.column_type != "data":
                continue
            col_lower = c.name.lower().replace(" ", "").replace("_", "")
            for kw in keywords:
                if kw in col_lower:
                    return (t.name, c.name)
    return None


def _find_column_pair(model, rev_kw: str, cost_kw: str) -> tuple[str, str, str] | None:
    """Find a table with both a revenue-like and cost-like numeric column."""
    for t in model.tables:
        rev_col = None
        cost_col = None
        for c in t.columns:
            if c.data_type not in ("double", "decimal", "int64", "currency"):
                continue
            cl = c.name.lower().replace(" ", "").replace("_", "")
            if rev_kw in cl:
                rev_col = c.name
            if cost_kw in cl:
                cost_col = c.name
        if rev_col and cost_col:
            return (t.name, rev_col, cost_col)
    return None


def _find_date_table(model: SemanticModel) -> dict | None:
    """Find a date table and its main date column."""
    date_patterns = ["date", "calendar", "fecha", "calendario", "dim_date", "dimdate"]
    for t in model.tables:
        name_lower = t.name.lower().replace(" ", "")
        for p in date_patterns:
            if p in name_lower:
                for c in t.columns:
                    if c.data_type in ("dateTime", "date") or "date" in c.name.lower():
                        return {"table": t.name, "column": c.name}
                # If no dateTime column found, look for a Key column
                for c in t.columns:
                    if c.is_key:
                        return {"table": t.name, "column": c.name}
    return None


def _find_base_measure(model: SemanticModel) -> str | None:
    """Find the first SUM-based measure to use as base for time intelligence."""
    for t in model.tables:
        for m in t.measures:
            if m.expression and re.search(r'(?i)\bSUM\s*\(', m.expression):
                return m.name
    # Fallback: first measure
    for t in model.tables:
        if t.measures:
            return t.measures[0].name
    return None


def _build_dax_rewrite(finding: Finding, model: SemanticModel, lang: str) -> str | None:
    """Build a concrete DAX rewrite suggestion for specific rules."""
    rule = finding.rule_id
    details = finding.details

    if rule == "DAX-002":
        func = details.get("func", "SUMX")
        table = details.get("table", "Table")
        col = details.get("col", "Column")
        alt = details.get("alt", "SUM")
        return f"{alt}({table}[{col}])"

    if rule == "DAX-005":
        # Extract the column reference from the location
        return "DISTINCTCOUNT(Table[Column])"

    if rule == "DAX-010":
        if lang == "es":
            return "COALESCE([Medida], ValorPorDefecto)"
        if lang == "pt":
            return "COALESCE([Medida], ValorPadrao)"
        return "COALESCE([Measure], DefaultValue)"

    return None
