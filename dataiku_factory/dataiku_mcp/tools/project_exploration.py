"""
Project exploration tools for Dataiku MCP integration.
"""

import re
import json
from typing import Dict, Any, List, Optional
from dataiku_mcp.client import get_client, get_project
from dataiku_mcp.tools.api_helpers import item_get, recipe_io, scenario_list_item_id

def get_project_flow(
    project_key: str
) -> Dict[str, Any]:
    """
    Get complete data flow/pipeline structure.
    
    Args:
        project_key: The project key
        
    Returns:
        Dict containing flow structure and dependencies
    """
    try:
        project = get_project(project_key)
        
        # Get all project objects
        datasets = project.list_datasets()
        recipes = project.list_recipes()
        
        # Build flow structure
        flow_nodes = []
        flow_edges = []
        
        # Add datasets as nodes
        for dataset in datasets:
            dataset_name = item_get(dataset, "name")
            dataset_info = {
                "id": dataset_name,
                "name": dataset_name,
                "type": "dataset",
                "dataset_type": item_get(dataset, "type"),
                "tags": item_get(dataset, "tags", [])
            }
            flow_nodes.append(dataset_info)
        
        # Add recipes as nodes and create edges
        for recipe in recipes:
            recipe_name = item_get(recipe, "name")
            recipe_info = {
                "id": recipe_name,
                "name": recipe_name,
                "type": "recipe",
                "recipe_type": item_get(recipe, "type"),
                "tags": item_get(recipe, "tags", [])
            }
            flow_nodes.append(recipe_info)
            
            # Get recipe details for inputs/outputs
            try:
                recipe_obj = project.get_recipe(recipe_name)
                refs = recipe_io(recipe_obj)
                
                # Create edges from inputs to recipe
                for input_ref in refs["inputs"]:
                    flow_edges.append({
                        "from": input_ref,
                        "to": recipe_name,
                        "type": "input"
                    })
                
                # Create edges from recipe to outputs
                for output_ref in refs["outputs"]:
                    flow_edges.append({
                        "from": recipe_name,
                        "to": output_ref,
                        "type": "output"
                    })
                    
            except Exception as e:
                # Skip recipes that can't be accessed
                continue
        
        # Calculate dependencies
        dependencies = {}
        for edge in flow_edges:
            if edge["type"] == "input":
                # Recipe depends on dataset
                recipe_name = edge["to"]
                dataset_name = edge["from"]
                
                if recipe_name not in dependencies:
                    dependencies[recipe_name] = {"depends_on": [], "used_by": []}
                dependencies[recipe_name]["depends_on"].append(dataset_name)
                
                if dataset_name not in dependencies:
                    dependencies[dataset_name] = {"depends_on": [], "used_by": []}
                dependencies[dataset_name]["used_by"].append(recipe_name)
            
            elif edge["type"] == "output":
                # Dataset depends on recipe
                recipe_name = edge["from"]
                dataset_name = edge["to"]
                
                if dataset_name not in dependencies:
                    dependencies[dataset_name] = {"depends_on": [], "used_by": []}
                dependencies[dataset_name]["depends_on"].append(recipe_name)
                
                if recipe_name not in dependencies:
                    dependencies[recipe_name] = {"depends_on": [], "used_by": []}
                dependencies[recipe_name]["used_by"].append(dataset_name)
        
        # Find root nodes (no dependencies) and leaf nodes (no dependents)
        root_nodes = []
        leaf_nodes = []
        
        for node_id, deps in dependencies.items():
            if not deps["depends_on"]:
                root_nodes.append(node_id)
            if not deps["used_by"]:
                leaf_nodes.append(node_id)
        
        # Calculate flow statistics
        flow_stats = {
            "total_nodes": len(flow_nodes),
            "total_edges": len(flow_edges),
            "datasets": len(datasets),
            "recipes": len(recipes),
            "root_nodes": len(root_nodes),
            "leaf_nodes": len(leaf_nodes)
        }
        
        return {
            "status": "ok",
            "project_key": project_key,
            "flow": {
                "nodes": flow_nodes,
                "edges": flow_edges
            },
            "dependencies": dependencies,
            "root_nodes": root_nodes,
            "leaf_nodes": leaf_nodes,
            "flow_stats": flow_stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get project flow: {str(e)}"
        }


def search_project_objects(
    project_key: str,
    search_term: str,
    object_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Search for datasets, recipes, scenarios by name/pattern.
    
    Args:
        project_key: The project key
        search_term: Search pattern (supports regex)
        object_types: List of object types to search ["datasets", "recipes", "scenarios"]
        
    Returns:
        Dict containing search results
    """
    try:
        project = get_project(project_key)
        
        if object_types is None:
            object_types = ["datasets", "recipes", "scenarios"]
        
        # Compile regex pattern
        try:
            pattern = re.compile(search_term, re.IGNORECASE)
        except re.error:
            # If regex fails, use simple string matching
            pattern = None
        
        search_results = {}
        
        # Search datasets
        if "datasets" in object_types:
            datasets = project.list_datasets()
            matching_datasets = []
            
            for dataset in datasets:
                name = item_get(dataset, "name")
                description = item_get(dataset, "description", "")
                tags = item_get(dataset, "tags", [])
                
                # Check if matches
                matches = False
                if pattern:
                    matches = (pattern.search(name) or 
                              pattern.search(description) or 
                              any(pattern.search(tag) for tag in tags))
                else:
                    matches = (search_term.lower() in name.lower() or 
                              search_term.lower() in description.lower() or 
                              any(search_term.lower() in tag.lower() for tag in tags))
                
                if matches:
                    matching_datasets.append({
                        "name": name,
                        "type": item_get(dataset, "type"),
                        "description": description,
                        "tags": tags,
                        "match_type": "name" if search_term.lower() in name.lower() else "metadata"
                    })
            
            search_results["datasets"] = matching_datasets
        
        # Search recipes
        if "recipes" in object_types:
            recipes = project.list_recipes()
            matching_recipes = []
            
            for recipe in recipes:
                name = item_get(recipe, "name")
                description = item_get(recipe, "description", "")
                tags = item_get(recipe, "tags", [])
                
                # Check if matches
                matches = False
                if pattern:
                    matches = (pattern.search(name) or 
                              pattern.search(description) or 
                              any(pattern.search(tag) for tag in tags))
                else:
                    matches = (search_term.lower() in name.lower() or 
                              search_term.lower() in description.lower() or 
                              any(search_term.lower() in tag.lower() for tag in tags))
                
                if matches:
                    matching_recipes.append({
                        "name": name,
                        "type": item_get(recipe, "type"),
                        "description": description,
                        "tags": tags,
                        "match_type": "name" if search_term.lower() in name.lower() else "metadata"
                    })
            
            search_results["recipes"] = matching_recipes
        
        # Search scenarios
        if "scenarios" in object_types:
            scenarios = project.list_scenarios()
            matching_scenarios = []
            
            for scenario in scenarios:
                name = item_get(scenario, "name")
                description = item_get(scenario, "description", "")
                tags = item_get(scenario, "tags", [])
                
                # Check if matches
                matches = False
                if pattern:
                    matches = (pattern.search(name) or 
                              pattern.search(description) or 
                              any(pattern.search(tag) for tag in tags))
                else:
                    matches = (search_term.lower() in name.lower() or 
                              search_term.lower() in description.lower() or 
                              any(search_term.lower() in tag.lower() for tag in tags))
                
                if matches:
                    matching_scenarios.append({
                        "name": name,
                        "id": scenario_list_item_id(scenario),
                        "type": item_get(scenario, "type"),
                        "description": description,
                        "tags": tags,
                        "active": item_get(scenario, "active", False),
                        "match_type": "name" if search_term.lower() in name.lower() else "metadata"
                    })
            
            search_results["scenarios"] = matching_scenarios
        
        # Calculate search statistics
        total_matches = sum(len(results) for results in search_results.values())
        search_stats = {
            "search_term": search_term,
            "object_types_searched": object_types,
            "total_matches": total_matches,
            "matches_by_type": {obj_type: len(results) for obj_type, results in search_results.items()}
        }
        
        return {
            "status": "ok",
            "project_key": project_key,
            "search_stats": search_stats,
            "results": search_results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to search project objects: {str(e)}"
        }


def _read_rows_bounded(dataset, schema_columns, max_rows, timeout):
    """Read up to `max_rows` rows from a dataset without scanning the whole table.

    ``DSSDataset.iter_rows()`` opens a GET on ``/data/`` that streams the ENTIRE
    dataset (a ``SELECT *`` for SQL/Snowflake datasets). The previous code wrapped
    that in ``itertools.islice`` and broke early, but that left the HTTP response
    open and NEVER called the ``finish-streaming`` endpoint, leaking a server-side
    read session each call. After a few calls the backend stalls new reads — the
    "get_dataset_sample keeps hanging" symptom.

    This reader:
      * streams the same endpoint but stops after `max_rows`,
      * deterministically closes the HTTP response (``gen.close()``), and
      * calls ``finish-streaming`` to release the server-side session.
    The read runs in a worker thread bounded by `timeout` so a genuinely stuck or
    unbuilt backend raises instead of hanging the whole MCP server. On timeout the
    stream is closed in the background and a TimeoutError is raised.
    """
    import uuid
    import itertools
    import threading
    from dataikuapi.dss.dataset import DataikuStreamedHttpUTF8CSVReader

    client = dataset.client
    read_session_id = str(uuid.uuid4())
    holder: Dict[str, Any] = {}

    def _cleanup(gen):
        try:
            gen.close()  # triggers the reader's `with closing(...)` -> closes HTTP response
        except Exception:
            pass
        try:
            client._perform_empty(
                "GET",
                "/projects/%s/datasets/%s/finish-streaming/" % (
                    dataset.project_key, dataset.dataset_name),
                params={"readSessionId": read_session_id},
            )
        except Exception:
            pass

    def _worker():
        try:
            csv_stream = client._perform_raw(
                "GET",
                "/projects/%s/datasets/%s/data/" % (
                    dataset.project_key, dataset.dataset_name),
                params={
                    "format": "tsv-excel-noheader",
                    "partitions": None,
                    "readSessionId": read_session_id,
                },
            )
        except Exception as e:
            holder["error"] = f"failed to open data stream: {e}"
            return
        gen = DataikuStreamedHttpUTF8CSVReader(schema_columns, csv_stream).iter_rows()
        holder["gen"] = gen
        try:
            holder["rows"] = list(itertools.islice(gen, max_rows))
        except Exception as e:
            holder["error"] = f"failed while reading rows: {e}"

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        gen = holder.get("gen")
        if gen is not None:
            threading.Thread(target=_cleanup, args=(gen,), daemon=True).start()
        raise TimeoutError(
            f"reading {max_rows} sample rows exceeded {timeout}s — the dataset "
            f"backend did not return data in time (it may be very large, slow, "
            f"or not built yet)"
        )

    gen = holder.get("gen")
    if gen is not None:
        _cleanup(gen)
    if "error" in holder:
        raise RuntimeError(holder["error"])
    return holder.get("rows", [])


def get_dataset_sample(
    project_key: str,
    dataset_name: str,
    rows: int = 100,
    columns: Optional[List[str]] = None,
    timeout: int = 90,
    max_preview_rows: int = 20,
) -> Dict[str, Any]:
    """
    Get sample data from a dataset, for inspecting shape and typical values.

    NOT for totals. Statistics here describe the first ``rows`` rows only, and
    the leading rows of a dataset are frequently unrepresentative of the whole:
    on 26B_Distribution_AppSheet_View, scanning 1,000 rows reports 3.9% nulls in
    Credit_avec_CET while scanning 5,000 reports 21.1%. For any sum, average or
    count over a whole dataset, use aggregate_dataset, which computes in the
    database over every row.

    ``rows`` controls how many rows are *scanned* for statistics;
    ``max_preview_rows`` controls how many are *returned*. Returning thousands
    of raw rows floods the caller's context for no analytical gain, so the two
    are separate.


    Args:
        project_key: The project key
        dataset_name: Name of the dataset
        rows: Number of rows to scan for statistics
        columns: Specific columns to include (optional)
        timeout: Max seconds to wait for the backend to return rows before
            aborting (default 90). Raise it for very large/slow datasets.
        max_preview_rows: Max rows echoed back in ``sample_data`` (default 20).

    Returns:
        Dict containing sample statistics, schema, and a bounded preview
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        # Get dataset schema
        schema = dataset.get_schema()
        schema_columns = schema.get("columns", [])
        
        # Filter columns if specified
        if columns:
            # Validate that all requested columns exist
            available_columns = [col["name"] for col in schema_columns]
            invalid_columns = [col for col in columns if col not in available_columns]
            
            if invalid_columns:
                return {
                    "status": "error",
                    "message": f"Invalid columns: {invalid_columns}. Available columns: {available_columns}"
                }
            
            # Filter schema to requested columns
            filtered_schema_columns = [col for col in schema_columns if col["name"] in columns]
        else:
            filtered_schema_columns = schema_columns
            columns = [col["name"] for col in schema_columns]
        
        # Get sample data via a bounded streaming read (see _read_rows_bounded):
        # rows are plain lists aligned with schema_columns. Build an index map so
        # we can reconstruct dicts and honour column filtering.
        all_col_names = [c["name"] for c in schema_columns]
        col_indices = {name: i for i, name in enumerate(all_col_names)}
        target_indices = [col_indices[c] for c in columns]  # columns list already validated above

        try:
            raw_rows = _read_rows_bounded(dataset, schema_columns, rows, timeout)
            sample_data = [
                {columns[j]: raw_row[idx] for j, idx in enumerate(target_indices)}
                for raw_row in raw_rows
            ]
            actual_rows = len(sample_data)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read sample data: {str(e)}"
            }
        
        # Calculate sample statistics
        scan_hit_cap = actual_rows >= rows
        sample_stats = {
            "requested_rows": rows,
            "actual_rows": actual_rows,
            "rows_scanned_for_stats": actual_rows,
            "scan_hit_requested_limit": scan_hit_cap,
            "requested_columns": len(columns) if columns else len(schema_columns),
            "total_columns": len(schema_columns),
            "column_names": columns if columns else [col["name"] for col in schema_columns],
            "statistics_scope": (
                "FIRST %d ROWS ONLY - not the whole dataset. Do not report these "
                "figures as dataset totals; use aggregate_dataset for that."
                % actual_rows
            ),
        }
        if scan_hit_cap:
            sample_stats["note"] = (
                f"The scan stopped at the {rows}-row limit, so the dataset has at "
                "least this many rows and its true size is unknown from this call."
            )
        
        # Generate column statistics for numeric columns
        column_stats = []
        for col in filtered_schema_columns:
            col_name = col["name"]
            col_type = col["type"]
            
            col_stat = {
                "name": col_name,
                "type": col_type,
                "meaning": col.get("meaning", ""),
                "description": col.get("description", "")
            }
            
            # Calculate basic statistics for the column
            if sample_data:
                values = [row.get(col_name) for row in sample_data]
                non_null_values = [v for v in values if v is not None]
                
                col_stat["null_count"] = len(values) - len(non_null_values)
                col_stat["null_percentage"] = (len(values) - len(non_null_values)) / len(values) * 100 if values else 0
                
                if non_null_values:
                    if col_type in ["int", "bigint", "float", "double"]:
                        # Numeric statistics
                        try:
                            numeric_values = [float(v) for v in non_null_values if v is not None]
                            if numeric_values:
                                col_stat["min"] = min(numeric_values)
                                col_stat["max"] = max(numeric_values)
                                col_stat["mean"] = sum(numeric_values) / len(numeric_values)
                        except:
                            pass
                    
                    elif col_type == "string":
                        # String statistics
                        string_values = [str(v) for v in non_null_values]
                        if string_values:
                            col_stat["unique_count"] = len(set(string_values))
                            col_stat["avg_length"] = sum(len(s) for s in string_values) / len(string_values)
                            col_stat["max_length"] = max(len(s) for s in string_values)
                            col_stat["min_length"] = min(len(s) for s in string_values)
                            
                            # Most common values
                            from collections import Counter
                            value_counts = Counter(string_values)
                            col_stat["most_common"] = value_counts.most_common(5)
            
            column_stats.append(col_stat)
        
        # Get dataset metadata
        dataset_settings = dataset.get_settings()
        dataset_info = {
            "name": dataset_name,
            "type": dataset_settings.get_raw()["type"],
            "format": dataset_settings.get_raw().get("formatType", "unknown"),
            "connection": dataset_settings.get_raw().get("params", {}).get("connection", "unknown")
        }
        
        # Statistics above were computed over every scanned row; only the echoed
        # preview is capped. Returning thousands of raw rows costs the caller a
        # great deal of context and adds nothing the statistics do not already say.
        preview_cap = max(0, int(max_preview_rows))
        preview_rows = sample_data[:preview_cap]

        result = {
            "status": "ok",
            "project_key": project_key,
            "dataset_info": dataset_info,
            "sample_stats": sample_stats,
            "schema": {
                "columns": filtered_schema_columns,
                "column_count": len(filtered_schema_columns)
            },
            "column_stats": column_stats,
            "sample_data": preview_rows,
            "sample_data_rows_returned": len(preview_rows),
        }
        if len(preview_rows) < actual_rows:
            result["sample_data_truncated"] = True
            result["sample_data_note"] = (
                f"Showing {len(preview_rows)} of {actual_rows} scanned rows. "
                "column_stats covers all scanned rows. Raise max_preview_rows only "
                "if individual row values are genuinely needed."
            )
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get dataset sample: {str(e)}"
        }
