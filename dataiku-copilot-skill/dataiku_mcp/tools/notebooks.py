"""
Notebook tools for Dataiku DSS.

These functions wrap the public dataiku-api-client notebook APIs for Jupyter
and SQL notebooks. They accept raw Dataiku notebook content dictionaries, and
also provide simple cell-based convenience inputs for common MCP usage.
"""

from typing import Any, Dict, List, Optional

from dataiku_mcp.client import get_project


def _source_lines(source: Any) -> List[str]:
    if source is None:
        return []
    if isinstance(source, list):
        return source
    if isinstance(source, str):
        return source.splitlines(keepends=True) or [source]
    return [str(source)]


def _jupyter_cell(cell: Any) -> Dict[str, Any]:
    if isinstance(cell, dict):
        normalized = dict(cell)
        normalized.setdefault("cell_type", "code")
        normalized.setdefault("metadata", {})
        if normalized["cell_type"] == "code":
            normalized.setdefault("outputs", [])
            normalized.setdefault("execution_count", None)
        if "source" in normalized:
            normalized["source"] = _source_lines(normalized["source"])
        else:
            normalized["source"] = []
        return normalized

    return {
        "cell_type": "code",
        "metadata": {},
        "source": _source_lines(cell),
        "outputs": [],
        "execution_count": None,
    }


def _jupyter_content(
    notebook_content: Optional[Dict[str, Any]],
    cells: Optional[List[Any]],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if notebook_content is not None:
        return notebook_content

    return {
        "cells": [_jupyter_cell(cell) for cell in (cells or [])],
        "metadata": metadata or {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _sql_cell(cell: Any, idx: int) -> Dict[str, Any]:
    if isinstance(cell, dict):
        normalized = dict(cell)
        normalized.setdefault("id", f"cell_{idx + 1}")
        normalized.setdefault("type", "QUERY")
        normalized.setdefault("name", f"Query {idx + 1}")
        normalized.setdefault("code", "")
        if isinstance(normalized["code"], list):
            normalized["code"] = "\n".join(str(line) for line in normalized["code"])
        return normalized

    return {
        "id": f"cell_{idx + 1}",
        "type": "QUERY",
        "name": f"Query {idx + 1}",
        "code": str(cell),
    }


def _sql_content(
    notebook_content: Optional[Dict[str, Any]],
    cells: Optional[List[Any]],
    connection: Optional[str],
    language: str,
) -> Dict[str, Any]:
    if notebook_content is not None:
        content = dict(notebook_content)
        content["cells"] = [
            _sql_cell(cell, idx)
            for idx, cell in enumerate(content.get("cells") or [])
        ]
        return content

    content: Dict[str, Any] = {
        "cells": [_sql_cell(cell, idx) for idx, cell in enumerate(cells or [])],
        "language": language,
    }
    if connection:
        content["connection"] = connection
    return content


def list_jupyter_notebooks(
    project_key: str,
    active: bool = False,
) -> Dict[str, Any]:
    """List Jupyter notebooks in a project."""
    try:
        project = get_project(project_key)
        items = project.list_jupyter_notebooks(active=active, as_type="listitems")
        notebooks_list = []
        for item in items:
            raw = dict(item)
            # kernelSpec may be absent on some DSS versions; fall back to raw dict access
            try:
                kernel_spec = item.kernel_spec
            except (KeyError, AttributeError):
                kernel_spec = raw.get("kernelSpec") or raw.get("kernel_spec")
            try:
                language = item.language
            except (KeyError, AttributeError):
                language = raw.get("language")
            notebooks_list.append({
                "name": item.name,
                "language": language,
                "kernel_spec": kernel_spec,
                "tags": item.tags,
                "last_modified_on": raw.get("lastModifiedOn"),
            })
        return {
            "status": "ok",
            "project_key": project_key,
            "active": active,
            "notebooks": notebooks_list,
            "total_count": len(notebooks_list),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list Jupyter notebooks in project '{project_key}': {str(e)}",
        }


def get_jupyter_notebook(
    project_key: str,
    notebook_name: str,
    include_outputs: bool = True,
) -> Dict[str, Any]:
    """Get the full content of a Jupyter notebook."""
    try:
        project = get_project(project_key)
        notebook = project.get_jupyter_notebook(notebook_name)
        content = notebook.get_content().get_raw()

        if not include_outputs:
            content = dict(content)
            content["cells"] = [dict(cell) for cell in content.get("cells", [])]
            for cell in content["cells"]:
                cell.pop("outputs", None)

        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_name": notebook_name,
            "content": content,
            "cell_count": len(content.get("cells", [])),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get Jupyter notebook '{notebook_name}': {str(e)}",
        }


def create_jupyter_notebook(
    project_key: str,
    notebook_name: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a Jupyter notebook from raw notebook JSON or a list of cells."""
    try:
        project = get_project(project_key)
        content = _jupyter_content(notebook_content, cells, metadata)
        notebook = project.create_jupyter_notebook(notebook_name, content)
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_name": notebook.notebook_name,
            "cell_count": len(content.get("cells", [])),
            "message": f"Jupyter notebook '{notebook_name}' created successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create Jupyter notebook '{notebook_name}': {str(e)}",
        }


def update_jupyter_notebook(
    project_key: str,
    notebook_name: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Replace the content of an existing Jupyter notebook."""
    try:
        project = get_project(project_key)
        notebook = project.get_jupyter_notebook(notebook_name)
        content_obj = notebook.get_content()
        content_obj.content = _jupyter_content(notebook_content, cells, metadata)
        content_obj.save()
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_name": notebook_name,
            "cell_count": len(content_obj.content.get("cells", [])),
            "message": f"Jupyter notebook '{notebook_name}' updated successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to update Jupyter notebook '{notebook_name}': {str(e)}",
        }


def edit_jupyter_notebook_cells(
    project_key: str,
    notebook_name: str,
    operation: str,
    cells: Optional[List[Any]] = None,
    index: Optional[int] = None,
    count: int = 1,
) -> Dict[str, Any]:
    """Edit cells in an existing Jupyter notebook without recreating it."""
    try:
        project = get_project(project_key)
        notebook = project.get_jupyter_notebook(notebook_name)
        content_obj = notebook.get_content()
        content = content_obj.get_raw()
        existing_cells = content.setdefault("cells", [])
        normalized_cells = [_jupyter_cell(cell) for cell in (cells or [])]

        op = operation.lower()
        if op == "append":
            existing_cells.extend(normalized_cells)
        elif op == "insert":
            if index is None:
                return {"status": "error", "message": "index is required for insert"}
            existing_cells[index:index] = normalized_cells
        elif op == "replace":
            if index is None:
                return {"status": "error", "message": "index is required for replace"}
            existing_cells[index:index + count] = normalized_cells
        elif op == "delete":
            if index is None:
                return {"status": "error", "message": "index is required for delete"}
            del existing_cells[index:index + count]
        else:
            return {
                "status": "error",
                "message": "operation must be one of: append, insert, replace, delete",
            }

        content_obj.save()
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_name": notebook_name,
            "operation": op,
            "cell_count": len(existing_cells),
            "message": f"Jupyter notebook '{notebook_name}' cells edited successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to edit Jupyter notebook '{notebook_name}': {str(e)}",
        }


def delete_jupyter_notebook(
    project_key: str,
    notebook_name: str,
) -> Dict[str, Any]:
    """Delete a Jupyter notebook and stop any active sessions."""
    try:
        project = get_project(project_key)
        project.get_jupyter_notebook(notebook_name).delete()
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_name": notebook_name,
            "message": f"Jupyter notebook '{notebook_name}' deleted successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete Jupyter notebook '{notebook_name}': {str(e)}",
        }


def clear_jupyter_notebook_outputs(
    project_key: str,
    notebook_name: str,
) -> Dict[str, Any]:
    """Clear outputs from a Jupyter notebook."""
    try:
        project = get_project(project_key)
        project.get_jupyter_notebook(notebook_name).clear_outputs()
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_name": notebook_name,
            "message": f"Outputs cleared for Jupyter notebook '{notebook_name}'",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to clear outputs for Jupyter notebook '{notebook_name}': {str(e)}",
        }


def list_sql_notebooks(project_key: str) -> Dict[str, Any]:
    """List SQL notebooks in a project."""
    try:
        project = get_project(project_key)
        items = project.list_sql_notebooks(as_type="listitems")
        notebooks = [
            {
                "id": item.id,
                "language": item.language,
                "connection": item.connection,
                "tags": item.tags,
            }
            for item in items
        ]
        return {
            "status": "ok",
            "project_key": project_key,
            "notebooks": notebooks,
            "total_count": len(notebooks),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list SQL notebooks in project '{project_key}': {str(e)}",
        }


def get_sql_notebook(
    project_key: str,
    notebook_id: str,
    include_history: bool = False,
) -> Dict[str, Any]:
    """Get the content of a SQL notebook, optionally with raw run history."""
    try:
        project = get_project(project_key)
        notebook = project.get_sql_notebook(notebook_id)
        content = notebook.get_content().get_raw()
        result = {
            "status": "ok",
            "project_key": project_key,
            "notebook_id": notebook_id,
            "content": content,
            "cell_count": len(content.get("cells", [])),
        }
        if include_history:
            result["history"] = notebook.get_history().get_raw()
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get SQL notebook '{notebook_id}': {str(e)}",
        }


def create_sql_notebook(
    project_key: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    connection: Optional[str] = None,
    language: str = "SQL",
) -> Dict[str, Any]:
    """Create a SQL notebook from raw notebook JSON or a list of query cells."""
    try:
        project = get_project(project_key)
        content = _sql_content(notebook_content, cells, connection, language)
        notebook = project.create_sql_notebook(content)
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_id": notebook.notebook_id,
            "cell_count": len(content.get("cells", [])),
            "message": f"SQL notebook '{notebook.notebook_id}' created successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create SQL notebook: {str(e)}",
        }


def update_sql_notebook(
    project_key: str,
    notebook_id: str,
    notebook_content: Optional[Dict[str, Any]] = None,
    cells: Optional[List[Any]] = None,
    connection: Optional[str] = None,
    language: str = "SQL",
) -> Dict[str, Any]:
    """Replace the content of an existing SQL notebook."""
    try:
        project = get_project(project_key)
        notebook = project.get_sql_notebook(notebook_id)
        content_obj = notebook.get_content()
        content_obj.content = _sql_content(notebook_content, cells, connection, language)
        content_obj.save()
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_id": notebook_id,
            "cell_count": len(content_obj.content.get("cells", [])),
            "message": f"SQL notebook '{notebook_id}' updated successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to update SQL notebook '{notebook_id}': {str(e)}",
        }


def edit_sql_notebook_cells(
    project_key: str,
    notebook_id: str,
    operation: str,
    cells: Optional[List[Any]] = None,
    index: Optional[int] = None,
    count: int = 1,
) -> Dict[str, Any]:
    """Edit cells in an existing SQL notebook without recreating it."""
    try:
        project = get_project(project_key)
        notebook = project.get_sql_notebook(notebook_id)
        content_obj = notebook.get_content()
        content = content_obj.get_raw()
        existing_cells = content.setdefault("cells", [])
        # Backfill ids on any pre-existing cells that lack one — Dataiku rejects
        # save when any cell is missing an id, even on unrelated edit ops.
        existing_ids = {
            cell.get("id") for cell in existing_cells if isinstance(cell, dict) and cell.get("id")
        }
        next_idx = len(existing_cells)
        for cell in existing_cells:
            if isinstance(cell, dict) and not cell.get("id"):
                while f"cell_{next_idx + 1}" in existing_ids:
                    next_idx += 1
                cell["id"] = f"cell_{next_idx + 1}"
                existing_ids.add(cell["id"])
                next_idx += 1
        normalized_cells = [
            _sql_cell(cell, (index or len(existing_cells)) + idx)
            for idx, cell in enumerate(cells or [])
        ]

        op = operation.lower()
        if op == "append":
            existing_cells.extend(normalized_cells)
        elif op == "insert":
            if index is None:
                return {"status": "error", "message": "index is required for insert"}
            existing_cells[index:index] = normalized_cells
        elif op == "replace":
            if index is None:
                return {"status": "error", "message": "index is required for replace"}
            existing_cells[index:index + count] = normalized_cells
        elif op == "delete":
            if index is None:
                return {"status": "error", "message": "index is required for delete"}
            del existing_cells[index:index + count]
        else:
            return {
                "status": "error",
                "message": "operation must be one of: append, insert, replace, delete",
            }

        content_obj.save()
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_id": notebook_id,
            "operation": op,
            "cell_count": len(existing_cells),
            "message": f"SQL notebook '{notebook_id}' cells edited successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to edit SQL notebook '{notebook_id}': {str(e)}",
        }


def delete_sql_notebook(
    project_key: str,
    notebook_id: str,
) -> Dict[str, Any]:
    """Delete a SQL notebook."""
    try:
        project = get_project(project_key)
        project.get_sql_notebook(notebook_id).delete()
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_id": notebook_id,
            "message": f"SQL notebook '{notebook_id}' deleted successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete SQL notebook '{notebook_id}': {str(e)}",
        }


def clear_sql_notebook_history(
    project_key: str,
    notebook_id: str,
    cell_id: Optional[str] = None,
    num_runs_to_retain: int = 0,
) -> Dict[str, Any]:
    """Clear SQL notebook query history."""
    try:
        project = get_project(project_key)
        project.get_sql_notebook(notebook_id).clear_history(
            cell_id=cell_id,
            num_runs_to_retain=num_runs_to_retain,
        )
        return {
            "status": "ok",
            "project_key": project_key,
            "notebook_id": notebook_id,
            "cell_id": cell_id,
            "num_runs_to_retain": num_runs_to_retain,
            "message": f"History cleared for SQL notebook '{notebook_id}'",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to clear history for SQL notebook '{notebook_id}': {str(e)}",
        }
