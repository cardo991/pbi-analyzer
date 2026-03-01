"""Configuration and thresholds for GridPulse."""

# --- Scoring weights (must sum to 100) ---
CATEGORY_WEIGHTS = {
    "data_model": 35,
    "dax": 25,
    "power_query": 20,
    "report": 20,
}

# --- Severity deductions ---
SEVERITY_DEDUCTIONS = {
    "error": {"per_occurrence": 5.0, "max_per_rule": 15.0},
    "warning": {"per_occurrence": 2.0, "max_per_rule": 10.0},
    "info": {"per_occurrence": 0.5, "max_per_rule": 3.0},
}

# --- Thresholds ---
MAX_VISUALS_PER_PAGE = 20
MAX_PAGES = 15
MAX_STEPS_PER_QUERY = 25
MAX_FILTERS_PER_VISUAL = 5
COMPLEX_MEASURE_CHAR_THRESHOLD = 300

# --- Grade boundaries ---
GRADE_BOUNDARIES = [
    (90, "A"),
    (75, "B"),
    (60, "C"),
    (40, "D"),
    (0, "F"),
]

# --- Heavy visual types ---
HEAVY_VISUAL_TYPES = {
    "map", "esriMap", "decompositionTreeVisual",
    "keyDriversVisual", "scriptVisual",
}

# --- Date table name patterns ---
DATE_TABLE_PATTERNS = [
    "date", "calendar", "dim_date", "dimdate", "dim_calendar",
    "dimcalendar", "fecha", "calendario", "dates", "calendars",
]

# --- Data source function patterns ---
DATA_SOURCE_FUNCTIONS = {
    "Sql.Database": "SQL Server",
    "Sql.Databases": "SQL Server",
    "Oracle.Database": "Oracle",
    "Odbc.DataSource": "ODBC",
    "OleDb.DataSource": "OLE DB",
    "File.Contents": "Local File",
    "Excel.Workbook": "Excel",
    "Csv.Document": "CSV",
    "Web.Contents": "Web/API",
    "SharePoint.Tables": "SharePoint",
    "SharePoint.Contents": "SharePoint",
    "OData.Feed": "OData",
    "AzureStorage.Blobs": "Azure Blob Storage",
    "Sql.Native": "SQL Native Query",
    "AnalysisServices.Database": "Analysis Services",
    "PowerBI.Dataflows": "Power BI Dataflows",
    "Lakehouse.Contents": "Fabric Lakehouse",
    "GoogleBigQuery.Database": "Google BigQuery",
    "Snowflake.Databases": "Snowflake",
    "PostgreSQL.Database": "PostgreSQL",
    "MySQL.Database": "MySQL",
}

# --- Query folding breakers ---
FOLDING_BREAKERS = [
    "Table.AddColumn", "Table.Buffer", "Table.TransformColumns",
    "Table.FillDown", "Table.FillUp", "Table.Pivot", "Table.Unpivot",
    "List.Generate", "Table.FromList",
]

# --- Aggregation functions (for DM-005) ---
AGGREGATION_FUNCTIONS = [
    "SUM", "COUNT", "COUNTROWS", "AVERAGE", "CALCULATE",
    "DISTINCTCOUNT", "SUMX", "AVERAGEX", "MAXX", "MINX",
    "RANKX", "COUNTAX", "COUNTBLANK",
]

# --- Upload config ---
MAX_UPLOAD_SIZE_MB = 100
ALLOWED_EXTENSIONS = {".zip"}

# --- Configurable thresholds (for F7 rules panel) ---
CONFIGURABLE_THRESHOLDS = {
    "max_visuals": MAX_VISUALS_PER_PAGE,
    "max_pages": MAX_PAGES,
    "max_steps": MAX_STEPS_PER_QUERY,
    "complex_measure": COMPLEX_MEASURE_CHAR_THRESHOLD,
    "naming_convention": "title_case",  # title_case, camelCase, snake_case, none
    "max_bookmarks": 20,
    "max_columns_per_table": 100,
}

# --- Rules Registry (all 34 rules) ---
RULES_REGISTRY = {
    "DM-001": {"category": "data_model", "severity": "warning", "desc": "Bidirectional cross-filtering"},
    "DM-002": {"category": "data_model", "severity": "warning", "desc": "Many-to-many relationships"},
    "DM-003": {"category": "data_model", "severity": "warning", "desc": "Disconnected tables"},
    "DM-004": {"category": "data_model", "severity": "warning", "desc": "Missing date table"},
    "DM-005": {"category": "data_model", "severity": "error", "desc": "Calculated column with aggregation"},
    "DM-006": {"category": "data_model", "severity": "info", "desc": "Snowflake schema"},
    "DM-007": {"category": "data_model", "severity": "info", "desc": "High cardinality columns"},
    "DM-008": {"category": "data_model", "severity": "info", "desc": "Mixed storage modes"},
    "DM-009": {"category": "data_model", "severity": "warning", "desc": "Inactive relationships"},
    "DM-010": {"category": "data_model", "severity": "info", "desc": "Fact table without measures"},
    "DAX-001": {"category": "dax", "severity": "warning", "desc": "Nested CALCULATE"},
    "DAX-002": {"category": "dax", "severity": "warning", "desc": "Unnecessary iterator"},
    "DAX-003": {"category": "dax", "severity": "info", "desc": "Missing VAR for repeats"},
    "DAX-004": {"category": "dax", "severity": "info", "desc": "Redundant IF TRUE/FALSE"},
    "DAX-005": {"category": "dax", "severity": "info", "desc": "COUNTROWS(VALUES) pattern"},
    "DAX-006": {"category": "dax", "severity": "info", "desc": "Complex without VAR"},
    "DAX-007": {"category": "dax", "severity": "info", "desc": "Missing format string"},
    "DAX-008": {"category": "dax", "severity": "info", "desc": "Naming conventions"},
    "DAX-009": {"category": "dax", "severity": "warning", "desc": "FILTER on entire table"},
    "DAX-010": {"category": "dax", "severity": "info", "desc": "IF(ISBLANK) pattern"},
    "DAX-011": {"category": "dax", "severity": "warning", "desc": "Division without DIVIDE"},
    "PQ-001": {"category": "power_query", "severity": "warning", "desc": "Query folding breakers"},
    "PQ-002": {"category": "power_query", "severity": "warning", "desc": "Table.Buffer usage"},
    "PQ-003": {"category": "power_query", "severity": "info", "desc": "Sort before filter"},
    "PQ-004": {"category": "power_query", "severity": "warning", "desc": "Hardcoded connections"},
    "PQ-005": {"category": "power_query", "severity": "info", "desc": "Excessive steps"},
    "PQ-006": {"category": "power_query", "severity": "info", "desc": "Data source detection"},
    "PQ-007": {"category": "power_query", "severity": "info", "desc": "Multiple type conversions"},
    "RP-001": {"category": "report", "severity": "warning", "desc": "Too many visuals/page"},
    "RP-002": {"category": "report", "severity": "info", "desc": "Too many pages"},
    "RP-003": {"category": "report", "severity": "info", "desc": "Heavy visual types"},
    "RP-004": {"category": "report", "severity": "info", "desc": "Too many filters/visual"},
    "RP-005": {"category": "report", "severity": "info", "desc": "Unhidden tooltip/drillthrough"},
    "RP-006": {"category": "report", "severity": "info", "desc": "Missing alt text"},
    # Security / RLS (F18)
    "SEC-001": {"category": "data_model", "severity": "warning", "desc": "Table without RLS protection"},
    "SEC-002": {"category": "data_model", "severity": "warning", "desc": "Empty role definition"},
    "SEC-003": {"category": "data_model", "severity": "info", "desc": "Expensive DAX in RLS filter"},
    # Security audit (F25)
    "SEC-004": {"category": "data_model", "severity": "error", "desc": "Sensitive column not hidden"},
    "SEC-005": {"category": "data_model", "severity": "warning", "desc": "HTTP data source (not HTTPS)"},
    "SEC-006": {"category": "data_model", "severity": "warning", "desc": "Credentials in source expression"},
    "SEC-007": {"category": "data_model", "severity": "info", "desc": "Table exposed without filtering"},
    # Naming conventions (F19)
    "NC-001": {"category": "data_model", "severity": "info", "desc": "Measure naming convention"},
    "NC-002": {"category": "data_model", "severity": "info", "desc": "Column naming inconsistency"},
    "NC-003": {"category": "data_model", "severity": "info", "desc": "Table name special characters"},
    # Performance (F20)
    "PERF-001": {"category": "data_model", "severity": "warning", "desc": "Not a star schema"},
    "PERF-002": {"category": "data_model", "severity": "warning", "desc": "Too many bidirectional relationships"},
    "PERF-003": {"category": "data_model", "severity": "info", "desc": "Too many columns per table"},
    "PERF-004": {"category": "dax", "severity": "warning", "desc": "Calc column should be measure"},
    "PERF-005": {"category": "data_model", "severity": "info", "desc": "DirectQuery mixed with Import"},
    # Bookmarks (F21)
    "BK-001": {"category": "report", "severity": "info", "desc": "Orphan bookmark"},
    "BK-002": {"category": "report", "severity": "info", "desc": "Bookmark targets missing page"},
    "BK-003": {"category": "report", "severity": "info", "desc": "Too many bookmarks"},
}
