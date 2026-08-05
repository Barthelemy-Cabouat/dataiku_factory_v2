"""
Execute SQL against DSS connections, and run the query cells of SQL notebooks.

The public ``dataikuapi`` client can author SQL notebooks but cannot *run* them:
``DSSSQLNotebook`` exposes only content/history/delete. DSS does, however,
expose a generic query runner at ``POST /sql/queries/`` (wrapped by
``DSSClient.sql_query`` -> :class:`dataikuapi.dss.sqlquery.DSSSQLQuery`), which
executes a statement on a named connection and streams the result set back.

This module drives that endpoint:

1. Read the notebook content to obtain its ``connection`` and ``language``.
2. For each ``QUERY`` cell (or a single selected cell), submit the cell's SQL
   with ``client.sql_query(..., connection=<notebook connection>)``.
3. Stream rows back, capped at ``max_rows``, and return them as columns + rows
   together with a rendered text preview.

Notes and deliberate limitations
--------------------------------
* **Results are not written into the notebook's run history.** The DSS history
  payload for a query run is not a documented public structure, and fabricating
  one risks corrupting the notebook. Cells run here therefore execute correctly
  but do not appear in the DSS UI's per-cell history.
* **One statement per cell.** DSS notebooks may split a cell on ``;`` client
  side (``statementsParseMode: SPLIT``); ``/sql/queries/`` runs a single
  statement. A single trailing semicolon is stripped; anything beyond that is
  forwarded verbatim and the database driver decides.
* **``max_rows`` truncation short-circuits the stream.** When a result set is
  truncated the trailing ``finish-streaming`` verification is skipped, because
  abandoning the stream early makes that call unreliable. Truncated cells are
  flagged with ``truncated: true``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from dataiku_mcp.client import get_client, get_project


# Notebook language -> /sql/queries/ query type
_LANGUAGE_TO_QUERY_TYPE = {
    "SQL": "sql",
    "HIVE": "hive",
    "IMPALA": "impala",
}

_MAX_SQL_ECHO = 2000


def _cell_code(cell: Any) -> str:
    """Return a cell's SQL as a single string."""
    if not isinstance(cell, dict):
        return str(cell or "")
    code = cell.get("code", "")
    if isinstance(code, list):
        return "\n".join(str(line) for line in code)
    return str(code or "")


def _is_runnable(code: str) -> bool:
    """False for blank cells and cells that contain only SQL line comments."""
    for line in code.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return True
    return False


def _strip_trailing_semicolon(code: str) -> str:
    stripped = code.rstrip()
    while stripped.endswith(";"):
        stripped = stripped[:-1].rstrip()
    return stripped


def _schema_columns(schema: Any) -> List[Dict[str, Any]]:
    """
    Normalise the result of ``DSSSQLQuery.get_schema()`` to a list of columns.

    The dataikuapi docstring documents ``{"columns": [...]}``, but DSS instances
    are observed returning the bare ``[...]`` list. Both are accepted here;
    assuming either one alone silently yields zero columns on the other.
    """
    if isinstance(schema, list):
        return [c for c in schema if isinstance(c, dict)]
    if isinstance(schema, dict):
        return [c for c in (schema.get("columns") or []) if isinstance(c, dict)]
    return []


def _render_table(columns: List[str], rows: List[List[Any]], max_chars: int) -> str:
    """Render a small fixed-width preview of a result set."""
    if not columns:
        return ""
    widths = [len(c) for c in columns]
    for row in rows:
        for i, value in enumerate(row[:len(widths)]):
            widths[i] = max(widths[i], len(("" if value is None else str(value))))
    widths = [min(w, 40) for w in widths]

    def fmt(values: List[Any]) -> str:
        cells = []
        for i, value in enumerate(values[:len(widths)]):
            text = "" if value is None else str(value)
            if len(text) > widths[i]:
                text = text[:widths[i] - 1] + "…"
            cells.append(text.ljust(widths[i]))
        return " | ".join(cells).rstrip()

    lines = [fmt(columns), "-+-".join("-" * w for w in widths)]
    for row in rows:
        lines.append(fmt(row))
        if sum(len(line) + 1 for line in lines) > max_chars:
            lines.append("...[preview truncated]")
            break
    return "\n".join(lines)


def _execute(
    sql: str,
    connection: str,
    query_type: str,
    project_key: Optional[str],
    max_rows: int,
) -> Dict[str, Any]:
    """Run one statement and collect up to ``max_rows`` rows."""
    client = get_client()
    query = client.sql_query(
        sql,
        connection=connection,
        type=query_type,
        project_key=project_key,
    )

    schema_columns = _schema_columns(query.get_schema())
    columns = [c.get("name") for c in schema_columns]
    column_types = {
        c.get("name"): c.get("originalType") or c.get("type")
        for c in schema_columns
    }

    rows: List[List[Any]] = []
    truncated = False
    for row in query.iter_rows():
        if len(rows) >= max_rows:
            truncated = True
            break
        rows.append(list(row))

    verified = False
    verify_warning = None
    if truncated:
        # The result stream was abandoned mid-flight; finish-streaming would
        # report a spurious failure, so it is deliberately not called.
        verify_warning = (
            f"result truncated at max_rows={max_rows}; "
            "stream verification skipped"
        )
    else:
        try:
            query.verify()
            verified = True
        except Exception as e:
            verify_warning = f"stream verification failed: {e}"

    return {
        "columns": columns,
        "column_types": column_types,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "verified": verified,
        "verify_warning": verify_warning,
    }


def execute_sql_query(
    connection: str,
    query: str,
    project_key: Optional[str] = None,
    max_rows: int = 1000,
    query_type: str = "sql",
    max_output_chars: int = 8000,
) -> Dict[str, Any]:
    """Run a single ad-hoc SQL statement on a DSS connection and return rows."""
    try:
        sql = _strip_trailing_semicolon(query)
        if not _is_runnable(sql):
            return {"status": "error", "message": "query is empty or contains only comments"}

        result = _execute(sql, connection, query_type, project_key, max_rows)
        result["preview"] = _render_table(
            result["columns"], result["rows"], max_output_chars
        )
        result.update({
            "status": "ok",
            "connection": connection,
            "project_key": project_key,
        })
        return result
    except Exception as e:
        return {
            "status": "error",
            "connection": connection,
            "message": f"Failed to execute query on connection '{connection}': {e}",
        }


def execute_sql_notebook(
    project_key: str,
    notebook_id: str,
    cell_index: Optional[int] = None,
    cell_id: Optional[str] = None,
    connection: Optional[str] = None,
    max_rows: int = 1000,
    stop_on_error: bool = True,
    max_output_chars: int = 8000,
) -> Dict[str, Any]:
    """Execute the query cells of a SQL notebook and capture their result sets."""
    try:
        project = get_project(project_key)
        notebook = project.get_sql_notebook(notebook_id)
        content = notebook.get_content().get_raw()

        conn = connection or content.get("connection")
        if not conn:
            return {
                "status": "error",
                "message": (
                    f"SQL notebook '{notebook_id}' has no connection set; "
                    "pass connection explicitly"
                ),
            }

        language = (content.get("language") or "SQL").upper()
        query_type = _LANGUAGE_TO_QUERY_TYPE.get(language)
        if query_type is None:
            return {
                "status": "error",
                "message": (
                    f"Notebook language '{language}' is not runnable through "
                    f"/sql/queries/ (supported: {', '.join(sorted(_LANGUAGE_TO_QUERY_TYPE))})"
                ),
            }

        cells = content.get("cells") or []

        # Select the cells to run
        selected: List[int] = []
        if cell_id is not None:
            selected = [
                i for i, c in enumerate(cells)
                if isinstance(c, dict) and c.get("id") == cell_id
            ]
            if not selected:
                return {
                    "status": "error",
                    "message": f"No cell with id '{cell_id}' in notebook '{notebook_id}'",
                }
        elif cell_index is not None:
            if cell_index < 0 or cell_index >= len(cells):
                return {
                    "status": "error",
                    "message": (
                        f"cell_index {cell_index} out of range "
                        f"(notebook has {len(cells)} cells)"
                    ),
                }
            selected = [cell_index]
        else:
            selected = list(range(len(cells)))

        results: List[Dict[str, Any]] = []
        errored = False

        for idx in selected:
            cell = cells[idx]
            entry: Dict[str, Any] = {
                "cell_index": idx,
                "cell_id": cell.get("id") if isinstance(cell, dict) else None,
                "cell_name": cell.get("name") if isinstance(cell, dict) else None,
            }

            if isinstance(cell, dict) and cell.get("type") not in (None, "QUERY"):
                entry.update({"status": "skipped", "reason": f"cell type {cell.get('type')}"})
                results.append(entry)
                continue

            code = _cell_code(cell)
            if not _is_runnable(code):
                entry.update({"status": "skipped", "reason": "empty or comment-only"})
                results.append(entry)
                continue

            entry["sql"] = code if len(code) <= _MAX_SQL_ECHO else code[:_MAX_SQL_ECHO] + "..."

            if errored and stop_on_error:
                entry.update({"status": "skipped", "reason": "previous cell failed"})
                results.append(entry)
                continue

            try:
                result = _execute(
                    _strip_trailing_semicolon(code), conn, query_type, project_key, max_rows
                )
                result["preview"] = _render_table(
                    result["columns"], result["rows"], max_output_chars
                )
                entry.update(result)
                entry["status"] = "ok"
            except Exception as e:
                entry.update({"status": "error", "message": str(e)})
                errored = True

            results.append(entry)

        executed = [r for r in results if r["status"] != "skipped"]
        n_err = sum(1 for r in results if r["status"] == "error")

        return {
            "status": "ok" if n_err == 0 else "error",
            "project_key": project_key,
            "notebook_id": notebook_id,
            "connection": conn,
            "language": language,
            "cells_executed": len(executed),
            "cells_failed": n_err,
            "results": results,
            "message": (
                f"Ran {len(executed)} query cell(s); {n_err} failed."
                if n_err else f"Ran {len(executed)} query cell(s) successfully."
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to execute SQL notebook '{notebook_id}': {e}",
        }
