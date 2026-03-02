"""Unified data models for GridPulse."""

from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    data_type: str = "string"
    source_column: str = ""
    column_type: str = "data"  # data, calculated, calculatedTableColumn, rowNumber
    expression: str = ""  # DAX expression for calculated columns
    is_hidden: bool = False
    is_key: bool = False
    format_string: str = ""
    description: str = ""
    display_folder: str = ""
    summarize_by: str = "default"
    sort_by_column: str = ""


@dataclass
class Measure:
    name: str
    table_name: str = ""
    expression: str = ""
    format_string: str = ""
    description: str = ""
    display_folder: str = ""
    is_hidden: bool = False


@dataclass
class Partition:
    name: str
    mode: str = "import"  # import, directQuery, dual
    source_type: str = "m"  # m, calculated, query
    expression: str = ""  # M code or DAX


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    partitions: list[Partition] = field(default_factory=list)
    is_hidden: bool = False
    description: str = ""
    data_category: str = ""
    refresh_policy: dict = field(default_factory=dict)


@dataclass
class Relationship:
    name: str = ""
    from_table: str = ""
    from_column: str = ""
    to_table: str = ""
    to_column: str = ""
    from_cardinality: str = "many"
    to_cardinality: str = "one"
    cross_filtering: str = "oneDirection"  # oneDirection, bothDirections
    is_active: bool = True


@dataclass
class Expression:
    name: str
    expression: str = ""
    description: str = ""


@dataclass
class Role:
    name: str
    table_permissions: dict = field(default_factory=dict)  # {table_name: filter_expression}


@dataclass
class SemanticModel:
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    expressions: list[Expression] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    culture: str = "en-US"
    default_mode: str = "import"


@dataclass
class Visual:
    name: str = ""
    visual_type: str = ""
    filters: list = field(default_factory=list)
    has_alt_text: bool = False
    title: str = ""
    field_references: list[str] = field(default_factory=list)


@dataclass
class Page:
    name: str = ""
    display_name: str = ""
    visuals: list[Visual] = field(default_factory=list)
    filters: list = field(default_factory=list)
    visibility: str = "visible"  # visible, HiddenInViewMode
    has_drillthrough: bool = False
    is_tooltip: bool = False


@dataclass
class Bookmark:
    name: str = ""
    display_name: str = ""
    report_page: str = ""  # target page
    visual_states: list[dict] = field(default_factory=list)


@dataclass
class ReportDefinition:
    pages: list[Page] = field(default_factory=list)
    filters: list = field(default_factory=list)
    bookmarks: list[Bookmark] = field(default_factory=list)


@dataclass
class Finding:
    rule_id: str
    category: str  # data_model, dax, power_query, report
    severity: str  # error, warning, info
    message: str  # The populated recommendation message
    location: str = ""  # e.g., "Table 'Sales', Measure 'Total Sales'"
    details: dict = field(default_factory=dict)  # Extra context for template formatting
