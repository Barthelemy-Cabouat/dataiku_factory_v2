"""
Resolve a DSS dataset to its physical SQL location, and aggregate it in-database.

Why this module exists
----------------------
A DSS dataset name is *not* the name of the underlying table. ``BURUNDI_BIZOPS``
holds a dataset called ``26B_Distribution_AppSheet_View``; the PostgreSQL table
behind it lives at some ``schema.table`` that DSS records in the dataset's
settings and that may itself contain unresolved variables such as
``${projectKey}``.

Without that mapping an agent asked for a total has two bad options: guess the
table name (``relation "..." does not exist``) or read a sample and extrapolate.
The second is worse, because it silently returns a plausible wrong number --
a 1,000-row read of this dataset reports 3.9% nulls and a mean of 107,714, while
a 5,000-row read of the same column reports 21.1% and 112,526.

:func:`resolve_dataset_sql_location` closes the gap, and
:func:`aggregate_dataset` uses it to push aggregates down to the database, where
they are computed over every row.

Safety
------
:func:`aggregate_dataset` composes SQL from an allowlisted set of aggregate
functions and from column names validated against the dataset's own schema, so
it can be enabled for an agent that is *not* allowed to run ``execute_sql_query``.
The single exception is the optional ``where`` argument, which is forwarded
verbatim -- see its note in the docstring.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from dataiku_mcp.client import get_project
from dataiku_mcp.tools.sql_execution import _execute, _render_table


# Aggregate functions this module is willing to emit. Anything outside this set
# is rejected rather than passed through, which is what keeps the tool safe to
# expose without also exposing arbitrary SQL execution.
_ALLOWED_AGGREGATES = {
    "COUNT": "COUNT({col})",
    "COUNT_DISTINCT": "COUNT(DISTINCT {col})",
    "SUM": "SUM({col})",
    "AVG": "AVG({col})",
    "MIN": "MIN({col})",
    "MAX": "MAX({col})",
    "STDDEV": "STDDEV({col})",
}

# Identifier quoting differs by engine. Getting this wrong is not cosmetic:
# unquoted identifiers are case-folded (lower in PostgreSQL, upper in Snowflake),
# so a mixed-case table such as 26B_Distribution_AppSheet_View is unreachable
# unless it is quoted exactly as DSS recorded it.
_BRACKET_DIALECTS = {"sqlserver", "synapse", "azuresynapse"}
_BACKTICK_DIALECTS = {"mysql", "mariadb", "bigquery"}

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _quote_style(dataset_type: Optional[str]) -> str:
    t = (dataset_type or "").strip().lower()
    if t in _BRACKET_DIALECTS:
        return "bracket"
    if t in _BACKTICK_DIALECTS:
        return "backtick"
    return "double"


def _quote_ident(name: str, style: str) -> str:
    """Quote one identifier, escaping any embedded closing quote character."""
    if style == "bracket":
        return "[" + name.replace("]", "]]") + "]"
    if style == "backtick":
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


def _resolve_variables(
    text: Optional[str],
    project_key: str,
    variables: Dict[str, Any],
) -> Optional[str]:
    """
    Expand ``${...}`` placeholders in a DSS table/schema name.

    DSS stores naming rules verbatim, so a Snowflake dataset commonly records
    its schema as the literal string ``${projectKey}``. Substituting these here
    means the caller gets a name it can actually send to the database.
    Placeholders with no known value are left untouched and reported via
    ``unresolved_variables`` so the failure is visible rather than silent.
    """
    if not text:
        return text

    def replace(match: "re.Match[str]") -> str:
        key = match.group(1).strip()
        if key == "projectKey":
            return project_key
        if key in variables and variables[key] is not None:
            return str(variables[key])
        return match.group(0)

    return _VAR_PATTERN.sub(replace, text)


def _project_variables(project) -> Dict[str, Any]:
    try:
        raw = project.get_variables() or {}
    except Exception:
        return {}
    merged: Dict[str, Any] = {}
    for scope in ("standard", "local"):
        section = raw.get(scope)
        if isinstance(section, dict):
            merged.update(section)
    return merged


def resolve_dataset_sql_location(
    project_key: str,
    dataset_name: str,
) -> Dict[str, Any]:
    """
    Return the physical SQL location backing a DSS dataset.

    Answers "which table do I actually query?" for a SQL-backed dataset, with
    ``${projectKey}``-style variables expanded and identifiers quoted for the
    right engine. ``sql_from`` is ready to drop straight after ``FROM``.

    Args:
        project_key: The project key
        dataset_name: Name of the dataset

    Returns:
        Dict with connection, catalog/schema/table (raw and resolved),
        ``sql_from``, and ``is_sql``. For a non-SQL dataset ``is_sql`` is False
        and ``sql_from`` is None.
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        settings = dataset.get_settings()
        raw = settings.get_raw() if hasattr(settings, "get_raw") else {}
        params = raw.get("params") or {}
        dataset_type = raw.get("type")

        mode = params.get("mode")
        raw_table = params.get("table")
        custom_query = params.get("customQuery")

        # Structural detection rather than a hard-coded list of engine names:
        # a dataset is SQL-addressable if DSS recorded a table for it, or if it
        # is a query dataset carrying its own SELECT.
        is_sql = bool(raw_table) or bool(custom_query)

        result: Dict[str, Any] = {
            "status": "ok",
            "project_key": project_key,
            "dataset_name": dataset_name,
            "dataset_type": dataset_type,
            "is_sql": is_sql,
            "connection": params.get("connection"),
            "mode": mode,
        }

        if not is_sql:
            result.update({
                "sql_from": None,
                "note": (
                    f"Dataset '{dataset_name}' is of type '{dataset_type}' and is not "
                    "backed by a SQL table, so it cannot be queried with SQL. Use "
                    "get_dataset_sample for its contents."
                ),
            })
            return result

        variables = _project_variables(project)
        style = _quote_style(dataset_type)

        raw_catalog = params.get("catalog")
        raw_schema = params.get("schema")

        catalog = _resolve_variables(raw_catalog, project_key, variables)
        schema = _resolve_variables(raw_schema, project_key, variables)
        table = _resolve_variables(raw_table, project_key, variables)

        unresolved = sorted({
            m for value in (catalog, schema, table, custom_query)
            for m in _VAR_PATTERN.findall(value or "")
        })

        result.update({
            "catalog": catalog,
            "schema": schema,
            "table": table,
            "raw_names": {
                "catalog": raw_catalog,
                "schema": raw_schema,
                "table": raw_table,
            },
        })

        if custom_query and mode == "query":
            # A query dataset has no table of its own; wrap its SELECT so the
            # caller can still aggregate over it.
            result["custom_query"] = custom_query
            result["sql_from"] = f"({custom_query}) AS dss_src"
            result["note"] = (
                "Query-mode dataset: sql_from wraps the dataset's own SELECT as a "
                "subquery. There is no physical table to reference directly."
            )
        else:
            parts = [p for p in (catalog, schema, table) if p]
            result["sql_from"] = ".".join(_quote_ident(p, style) for p in parts)

        if unresolved:
            result["unresolved_variables"] = unresolved
            result["warning"] = (
                "Some ${...} placeholders could not be resolved from project "
                f"variables: {unresolved}. sql_from may not be valid as-is."
            )

        return result

    except Exception as e:
        return {
            "status": "error",
            "message": (
                f"Failed to resolve SQL location for dataset "
                f"'{dataset_name}' in project '{project_key}': {e}"
            ),
        }


def _normalise_aggregations(
    aggregations: List[Any],
    valid_columns: Dict[str, str],
) -> tuple:
    """
    Validate requested aggregations against the dataset schema.

    Accepts either a dict ``{"function": "SUM", "column": "x", "alias": "y"}``
    or the shorthand string ``"SUM(x)"``. Returns (specs, errors).
    """
    specs: List[Dict[str, str]] = []
    errors: List[str] = []

    for item in aggregations:
        function: Optional[str] = None
        column: Optional[str] = None
        alias: Optional[str] = None

        if isinstance(item, dict):
            function = str(item.get("function", "")).strip().upper()
            column = item.get("column")
            alias = item.get("alias")
        elif isinstance(item, str):
            match = re.fullmatch(r"\s*([A-Za-z_]+)\s*\(\s*(.+?)\s*\)\s*", item)
            if not match:
                errors.append(
                    f"Could not parse aggregation '{item}'. Use 'SUM(column)' or "
                    "{'function': 'SUM', 'column': 'column'}."
                )
                continue
            function = match.group(1).strip().upper()
            column = match.group(2).strip().strip('"').strip("`").strip("[]")
        else:
            errors.append(f"Unsupported aggregation entry: {item!r}")
            continue

        if function == "COUNTDISTINCT":
            function = "COUNT_DISTINCT"

        if function not in _ALLOWED_AGGREGATES:
            errors.append(
                f"Aggregate function '{function}' is not allowed. "
                f"Supported: {', '.join(sorted(_ALLOWED_AGGREGATES))}."
            )
            continue

        # COUNT(*) is the one case with no column to validate.
        if column in (None, "", "*"):
            if function != "COUNT":
                errors.append(f"{function} requires a column name.")
                continue
            specs.append({
                "function": "COUNT",
                "column": "*",
                "alias": alias or "row_count",
            })
            continue

        if column not in valid_columns:
            errors.append(
                f"Column '{column}' does not exist in the dataset. "
                f"Available: {', '.join(sorted(valid_columns))}."
            )
            continue

        specs.append({
            "function": function,
            "column": column,
            "alias": alias or f"{function.lower()}_{column}",
        })

    return specs, errors


def aggregate_dataset(
    project_key: str,
    dataset_name: str,
    aggregations: List[Any],
    group_by: Optional[List[str]] = None,
    where: Optional[str] = None,
    max_rows: int = 1000,
    max_output_chars: int = 8000,
) -> Dict[str, Any]:
    """
    Compute aggregates over a SQL-backed dataset, in the database, over all rows.

    Use this -- never get_dataset_sample -- for any total, average, count or
    other whole-dataset figure. A sample answers a different question and will
    silently under-report.

    Every result also carries ``total_row_count`` and, for each aggregated
    column, a ``<column>__non_null_count``, so a figure can be read against the
    number of rows that actually contributed to it.

    Args:
        project_key: The project key
        dataset_name: Name of the dataset
        aggregations: List of aggregations. Each entry is either the shorthand
            string ``"SUM(Credit_avec_CET)"`` or a dict
            ``{"function": "SUM", "column": "Credit_avec_CET", "alias": "total"}``.
            Allowed functions: COUNT, COUNT_DISTINCT, SUM, AVG, MIN, MAX, STDDEV.
        group_by: Optional list of column names to group by. Validated against
            the dataset schema.
        where: Optional raw SQL predicate, inserted verbatim after WHERE. This
            is the only argument that is not validated; omit it if the caller
            is not trusted with SQL.
        max_rows: Max result rows to return (default 1000)
        max_output_chars: Size cap for the rendered text preview

    Returns:
        Dict with columns, rows, a rendered preview, and the SQL that was run.
    """
    try:
        location = resolve_dataset_sql_location(project_key, dataset_name)
        if location.get("status") == "error":
            return location

        if not location.get("is_sql"):
            return {
                "status": "error",
                "dataset_name": dataset_name,
                "message": location.get("note")
                or f"Dataset '{dataset_name}' is not backed by a SQL table.",
            }

        connection = location.get("connection")
        if not connection:
            return {
                "status": "error",
                "dataset_name": dataset_name,
                "message": (
                    f"Dataset '{dataset_name}' has no connection recorded in its "
                    "settings; cannot run SQL against it."
                ),
            }

        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        schema_columns = (dataset.get_schema() or {}).get("columns", [])
        valid_columns = {
            c.get("name"): c.get("type") for c in schema_columns if c.get("name")
        }

        if not aggregations:
            return {
                "status": "error",
                "message": "aggregations must contain at least one entry.",
            }

        specs, errors = _normalise_aggregations(aggregations, valid_columns)
        if errors:
            return {
                "status": "error",
                "dataset_name": dataset_name,
                "message": "; ".join(errors),
            }

        group_by = group_by or []
        bad_group = [c for c in group_by if c not in valid_columns]
        if bad_group:
            return {
                "status": "error",
                "dataset_name": dataset_name,
                "message": (
                    f"group_by columns not in dataset: {bad_group}. "
                    f"Available: {', '.join(sorted(valid_columns))}."
                ),
            }

        style = _quote_style(location.get("dataset_type"))

        select_parts: List[str] = [
            f"{_quote_ident(c, style)}" for c in group_by
        ]

        # Always report the denominator. The null-rate surprise in a sample is
        # exactly what makes sampled totals misleading, so make it explicit.
        select_parts.append(f"COUNT(*) AS {_quote_ident('total_row_count', style)}")

        for spec in specs:
            if spec["column"] == "*":
                expr = "COUNT(*)"
            else:
                expr = _ALLOWED_AGGREGATES[spec["function"]].format(
                    col=_quote_ident(spec["column"], style)
                )
            select_parts.append(f"{expr} AS {_quote_ident(spec['alias'], style)}")

        for column in sorted({s["column"] for s in specs if s["column"] != "*"}):
            select_parts.append(
                f"COUNT({_quote_ident(column, style)}) AS "
                f"{_quote_ident(column + '__non_null_count', style)}"
            )

        sql = f"SELECT {', '.join(select_parts)}\nFROM {location['sql_from']}"
        if where:
            sql += f"\nWHERE {where}"
        if group_by:
            grouped = ", ".join(_quote_ident(c, style) for c in group_by)
            sql += f"\nGROUP BY {grouped}\nORDER BY {grouped}"

        result = _execute(sql, connection, "sql", project_key, max_rows)
        result["preview"] = _render_table(
            result["columns"], result["rows"], max_output_chars
        )
        result.update({
            "status": "ok",
            "project_key": project_key,
            "dataset_name": dataset_name,
            "connection": connection,
            "sql_from": location["sql_from"],
            "sql": sql,
            "computed_over": "all rows (in-database aggregate, not a sample)",
        })
        return result

    except Exception as e:
        return {
            "status": "error",
            "dataset_name": dataset_name,
            "message": f"Failed to aggregate dataset '{dataset_name}': {e}",
        }
