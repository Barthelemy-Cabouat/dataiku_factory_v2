"""
Dataset management tools for Dataiku DSS.

This module provides functions for creating, updating, deleting, building, and inspecting datasets
in Dataiku DSS projects through the dataiku-api-client.
"""

from typing import Dict, List, Optional, Union, Any
import dataikuapi
import dataikuapi.dss.project
import dataikuapi.dss.dataset
from dataiku_mcp.client import get_client, get_project


def _dataset_type(dataset: dataikuapi.dss.dataset.DSSDataset) -> Optional[str]:
    """Return the dataset type using public client APIs."""
    try:
        settings = dataset.get_settings()
        raw = settings.get_raw() if hasattr(settings, "get_raw") else {}
        return getattr(settings, "type", None) or raw.get("type")
    except Exception:
        return None


def create_dataset(
    project_key: str,
    dataset_name: str,
    dataset_type: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new dataset in a Dataiku DSS project.
    
    Args:
        project_key: The project key where the dataset will be created
        dataset_name: Name of the dataset to create
        dataset_type: Type of dataset (e.g., 'filesystem', 'sql', 'uploaded', 'managed', 's3', 'hdfs')
        params: Optional parameters dict containing:
            - connection: Connection name (for sql, s3, hdfs, etc.)
            - path: Path in connection (for filesystem, s3, hdfs)
            - table: Table name (for sql)
            - schema: Schema name (for sql)
            - catalog: Catalog name (for sql, optional)
            - bucket: Bucket name (for s3, optional)
            - format_type: Format type (csv, json, parquet, etc.)
            - format_params: Format-specific parameters
            - store_into: Connection for managed datasets
    
    Returns:
        Dict with status and dataset details or error message
    """
    try:
        project = get_project(project_key)
        params = params or {}
        
        # Handle managed datasets
        if dataset_type.lower() == 'managed':
            builder = project.new_managed_dataset(dataset_name)
            store_into = params.get('store_into', 'filesystem_managed')
            builder = builder.with_store_into(store_into)
            
            # Set format if provided
            format_type = params.get('format_type')
            if format_type:
                format_params = params.get('format_params', {})
                builder = builder.with_format(format_type, **format_params)
            
            dataset = builder.create()
            
        # Handle filesystem datasets
        elif dataset_type.lower() == 'filesystem':
            connection = params.get('connection', 'filesystem_managed')
            path = params.get('path')
            if not path:
                return {
                    "status": "error",
                    "message": "Path is required for filesystem datasets"
                }
            
            dataset = project.create_filesystem_dataset(
                dataset_name,
                connection,
                path
            )
            
        # Handle SQL datasets
        elif dataset_type.lower() == 'sql':
            connection = params.get('connection')
            table = params.get('table')
            schema = params.get('schema')
            catalog = params.get('catalog')
            
            if not all([connection, table]):
                return {
                    "status": "error",
                    "message": "Connection and table are required for SQL datasets"
                }
            
            dataset = project.create_sql_table_dataset(
                dataset_name,
                'sql',
                connection,
                table,
                schema,
                catalog
            )
            
        # Handle S3 datasets
        elif dataset_type.lower() == 's3':
            connection = params.get('connection')
            path = params.get('path')
            bucket = params.get('bucket')
            
            if not all([connection, path]):
                return {
                    "status": "error",
                    "message": "Connection and path are required for S3 datasets"
                }
            
            dataset = project.create_s3_dataset(
                dataset_name,
                connection,
                path,
                bucket
            )
            
        # Handle upload datasets
        elif dataset_type.lower() == 'uploaded':
            connection = params.get('connection')
            dataset = project.create_upload_dataset(dataset_name, connection)
            
        # Handle generic datasets
        else:
            format_type = params.get('format_type')
            format_params = params.get('format_params', {})
            
            dataset = project.create_dataset(
                dataset_name,
                dataset_type,
                params,
                format_type,
                format_params
            )
        
        # Set additional format parameters if provided
        if params.get('format_type') and dataset_type.lower() != 'managed':
            settings = dataset.get_settings()
            settings.set_format_type(params['format_type'])
            if params.get('format_params'):
                settings.set_format_params(params['format_params'])
            settings.save()
        
        return {
            "status": "ok",
            "dataset_name": dataset_name,
            "dataset_type": dataset_type,
            "dataset_id": dataset.id,
            "project_key": project_key,
            "message": f"Dataset '{dataset_name}' created successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create dataset '{dataset_name}': {str(e)}"
        }


def update_dataset(
    project_key: str,
    dataset_name: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Update an existing dataset's settings.
    
    Args:
        project_key: The project key containing the dataset
        dataset_name: Name of the dataset to update
        **kwargs: Update parameters including:
            - description: Dataset description
            - tags: List of tags
            - custom_fields: Dict of custom metadata fields
            - format_type: Format type (csv, json, parquet, etc.)
            - format_params: Format-specific parameters
            - connection: Connection name (for applicable datasets)
            - path: Path in connection (for applicable datasets)
            - table: Table name (for SQL datasets)
            - schema: Schema name (for SQL datasets)
    
    Returns:
        Dict with status and update details or error message
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        updated_fields = []
        
        # Update metadata if provided
        if any(key in kwargs for key in ['description', 'tags', 'custom_fields']):
            metadata = dataset.get_metadata()
            
            if 'description' in kwargs:
                metadata['description'] = kwargs['description']
                updated_fields.append('description')
            
            if 'tags' in kwargs:
                metadata['tags'] = kwargs['tags']
                updated_fields.append('tags')
            
            if 'custom_fields' in kwargs:
                if 'customFields' not in metadata:
                    metadata['customFields'] = {}
                metadata['customFields'].update(kwargs['custom_fields'])
                updated_fields.append('custom_fields')
            
            dataset.set_metadata(metadata)
        
        # Update column schema if provided (dict with a 'columns' key)
        if 'schema' in kwargs and isinstance(kwargs['schema'], dict):
            current_schema = dataset.get_schema()
            current_schema['columns'] = kwargs['schema']['columns']
            dataset.set_schema(current_schema)
            updated_fields.append('schema')

        # Update settings if provided
        if any(key in kwargs for key in ['format_type', 'format_params', 'connection', 'path', 'table', 'schema']):
            settings = dataset.get_settings()
            
            if 'format_type' in kwargs:
                settings.set_format_type(kwargs['format_type'])
                updated_fields.append('format_type')
            
            if 'format_params' in kwargs:
                settings.set_format_params(kwargs['format_params'])
                updated_fields.append('format_params')
            
            # Update connection settings based on dataset type
            if hasattr(settings, 'set_connection') and 'connection' in kwargs:
                settings.set_connection(kwargs['connection'])
                updated_fields.append('connection')
            
            if hasattr(settings, 'set_path') and 'path' in kwargs:
                settings.set_path(kwargs['path'])
                updated_fields.append('path')
            
            # SQL-specific settings ('schema' here is the SQL schema name string, e.g. "dbo")
            sql_schema_name = kwargs.get('schema') if isinstance(kwargs.get('schema'), str) else None
            if hasattr(settings, 'set_table') and any(key in kwargs for key in ['table']) or sql_schema_name:
                connection = getattr(settings, 'connection', kwargs.get('connection'))
                table = kwargs.get('table', getattr(settings, 'table', None))
                schema = sql_schema_name or getattr(settings, 'schema', None)
                
                if connection and table:
                    settings.set_table(connection, schema, table)
                    updated_fields.extend(['table', 'schema'])
            
            settings.save()
        
        return {
            "status": "ok",
            "dataset_name": dataset_name,
            "updated_fields": updated_fields,
            "message": f"Dataset '{dataset_name}' updated successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to update dataset '{dataset_name}': {str(e)}"
        }


def delete_dataset(
    project_key: str,
    dataset_name: str,
    drop_data: bool = False
) -> Dict[str, Any]:
    """
    Delete a dataset from a Dataiku DSS project.
    
    Args:
        project_key: The project key containing the dataset
        dataset_name: Name of the dataset to delete
        drop_data: Whether to also drop the underlying data (default: False)
    
    Returns:
        Dict with status and deletion details or error message
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        # Store dataset info before deletion
        dataset_info = {
            "name": dataset_name,
            "type": _dataset_type(dataset),
            "id": dataset.id
        }
        
        # Delete the dataset
        dataset.delete(drop_data=drop_data)
        
        return {
            "status": "ok",
            "deleted_dataset": dataset_info,
            "drop_data": drop_data,
            "message": f"Dataset '{dataset_name}' deleted successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete dataset '{dataset_name}': {str(e)}"
        }


def build_dataset(
    project_key: str,
    dataset_name: str,
    mode: Optional[str] = None,
    partition: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a dataset to refresh its content.
    
    Args:
        project_key: The project key containing the dataset
        dataset_name: Name of the dataset to build
        mode: Optional build mode:
            - "NON_RECURSIVE_FORCED_BUILD": Default non-recursive forced build
            - "RECURSIVE_BUILD": Recursive build
            - "RECURSIVE_FORCED_BUILD": Recursive forced build
        partition: Optional partition to build (for partitioned datasets)
    
    Returns:
        Dict with status and build job details or error message
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        # Prepare build parameters
        build_params = {
            "wait": True,
            "no_fail": False
        }
        
        if mode:
            valid_modes = [
                "RECURSIVE_BUILD",
                "NON_RECURSIVE_FORCED_BUILD",
                "RECURSIVE_FORCED_BUILD"
            ]
            if mode not in valid_modes:
                return {
                    "status": "error",
                    "message": f"Invalid build mode. Must be one of: {valid_modes}"
                }
            build_params["job_type"] = mode
        
        if partition:
            build_params["partitions"] = partition
        
        # Build the dataset (wait=True makes dataset.build poll internally)
        job = dataset.build(**build_params)

        # job is a DSSJob; with wait=True it has already reached a terminal state.
        # DSSJob has no wait_for_completion; read final state via get_status().
        try:
            status = job.get_status() or {}
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read job status for dataset '{dataset_name}': {str(e)}",
            }
        base = status.get("baseStatus", {}) or {}
        state = base.get("state", "UNKNOWN")
        start_ms = base.get("startTime")
        end_ms = base.get("endTime")
        from datetime import datetime as _dt
        start_str = _dt.fromtimestamp(start_ms / 1000).isoformat() if start_ms else None
        end_str = _dt.fromtimestamp(end_ms / 1000).isoformat() if end_ms else None

        if state != "DONE":
            error_msg = f"Job ended with state {state}"
            try:
                log = job.get_log()
                if log:
                    log_lines = log.strip().split('\n')
                    error_msg += "\n\nJob log (last 50 lines):\n" + "\n".join(log_lines[-50:])
            except Exception:
                pass
            return {
                "status": "error",
                "message": f"Failed to build dataset '{dataset_name}': {error_msg}",
                "job_state": state,
                "job_start_time": start_str,
                "job_end_time": end_str,
            }

        return {
            "status": "ok",
            "dataset_name": dataset_name,
            "job_status": state,
            "job_start_time": start_str,
            "job_end_time": end_str,
            "build_mode": mode,
            "partition": partition,
            "message": f"Dataset '{dataset_name}' built successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to build dataset '{dataset_name}': {str(e)}"
        }


def inspect_dataset_schema(
    project_key: str,
    dataset_name: str
) -> Dict[str, Any]:
    """
    Inspect the schema of a dataset.
    
    Args:
        project_key: The project key containing the dataset
        dataset_name: Name of the dataset to inspect
    
    Returns:
        Dict with dataset schema information or error message
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        # Get the schema
        schema = dataset.get_schema()
        
        # Process schema columns
        columns = []
        for col in schema.get('columns', []):
            column_info = {
                "name": col.get('name'),
                "type": col.get('type'),
                "meaning": col.get('meaning'),
                "comment": col.get('comment', ''),
                "nullable": col.get('nullable', True)
            }
            
            # Add type-specific information
            if col.get('type') == 'string':
                column_info['max_length'] = col.get('maxLength')
            elif col.get('type') in ['int', 'bigint', 'float', 'double']:
                column_info['min_value'] = col.get('minValue')
                column_info['max_value'] = col.get('maxValue')
            elif col.get('type') == 'array':
                column_info['array_type'] = col.get('arrayType')
            elif col.get('type') == 'map':
                column_info['key_type'] = col.get('keyType')
                column_info['value_type'] = col.get('valueType')
            elif col.get('type') == 'object':
                column_info['object_fields'] = col.get('objectFields', [])
            
            columns.append(column_info)
        
        return {
            "status": "ok",
            "dataset_name": dataset_name,
            "schema": {
                "columns": columns,
                "user_modified": schema.get('userModified', False),
                "column_count": len(columns)
            },
            "message": f"Schema for dataset '{dataset_name}' retrieved successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to inspect schema for dataset '{dataset_name}': {str(e)}"
        }


def check_dataset_metrics(
    project_key: str,
    dataset_name: str
) -> Dict[str, Any]:
    """
    Check the metrics of a dataset.
    
    Args:
        project_key: The project key containing the dataset
        dataset_name: Name of the dataset to check metrics for
    
    Returns:
        Dict with dataset metrics information or error message
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        # get_last_metric_values() returns a ComputedMetrics object, not a plain dict.
        # Use .get_raw() to obtain the underlying dict.
        metrics_obj = dataset.get_last_metric_values()
        metrics = metrics_obj.get_raw() if hasattr(metrics_obj, 'get_raw') else (metrics_obj or {})

        # Process metrics data
        processed_metrics = {}

        if metrics:
            # Basic metrics — stored as a flat list of metric dicts under 'metrics'
            raw_list = metrics.get('metrics', [])
            for entry in raw_list:
                metric_id = entry.get('metricDef', {}).get('id', '')
                value = entry.get('lastValues', [{}])[0].get('value') if entry.get('lastValues') else None
                if not metric_id:
                    continue
                # Flatten into a readable dict keyed by metric id
                processed_metrics[metric_id] = value

        return {
            "status": "ok",
            "dataset_name": dataset_name,
            "metrics": processed_metrics,
            "has_metrics": bool(processed_metrics),
            "message": f"Metrics for dataset '{dataset_name}' retrieved successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to check metrics for dataset '{dataset_name}': {str(e)}"
        }


def list_datasets(
    project_key: str,
    dataset_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all datasets in a project, optionally filtered by type.
    
    Args:
        project_key: The project key to list datasets from
        dataset_type: Optional filter by dataset type
    
    Returns:
        Dict with list of datasets or error message
    """
    try:
        project = get_project(project_key)
        
        # Get all datasets
        all_datasets = project.list_datasets()
        
        # Filter by type if specified
        if dataset_type:
            filtered_datasets = [d for d in all_datasets if d.get("type") == dataset_type]
        else:
            filtered_datasets = all_datasets
        
        return {
            "status": "ok",
            "datasets": [
                {
                    "name": dataset.get("name"),
                    "type": dataset.get("type"),
                    "id": dataset.get("id"),
                    "tags": dataset.get("tags", []),
                    "managed": dataset.get("managed", False),
                    "flow_options": dataset.get("flowOptions", {}),
                    "connection": dataset.get("params", {}).get("connection")
                }
                for dataset in filtered_datasets
            ],
            "total_count": len(filtered_datasets),
            "project_key": project_key
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list datasets in project '{project_key}': {str(e)}"
        }


def get_dataset_info(
    project_key: str,
    dataset_name: str
) -> Dict[str, Any]:
    """
    Get detailed information about a dataset.
    
    Args:
        project_key: The project key containing the dataset
        dataset_name: Name of the dataset to inspect
    
    Returns:
        Dict with dataset information or error message
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        # Get dataset metadata
        metadata = dataset.get_metadata()
        
        # Get dataset settings
        settings = dataset.get_settings()
        
        # Get dataset type and configuration
        dataset_type = _dataset_type(dataset)
        
        return {
            "status": "ok",
            "dataset_info": {
                "name": dataset_name,
                "type": dataset_type,
                "id": dataset.id,
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "managed": dataset_type == "Managed",
                "creation_date": metadata.get("creationDate"),
                "last_modified": metadata.get("lastModifiedDate"),
                "last_modified_by": metadata.get("lastModifiedBy", {}).get("login"),
                "custom_fields": metadata.get("customFields", {}),
                "flow_options": metadata.get("flowOptions", {}),
                "settings": {
                    "format_type": getattr(settings, 'format_type', None),
                    "connection": getattr(settings, 'connection', None),
                    "path": getattr(settings, 'path', None),
                    "table": getattr(settings, 'table', None),
                    "schema": getattr(settings, 'schema', None)
                }
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get dataset info for '{dataset_name}': {str(e)}"
        }


def clear_dataset(
    project_key: str,
    dataset_name: str,
    partition: Optional[str] = None
) -> Dict[str, Any]:
    """
    Clear the data from a dataset.
    
    Args:
        project_key: The project key containing the dataset
        dataset_name: Name of the dataset to clear
        partition: Optional partition to clear (for partitioned datasets)
    
    Returns:
        Dict with status and clear operation details or error message
    """
    try:
        project = get_project(project_key)
        dataset = project.get_dataset(dataset_name)
        
        # Prepare clear parameters
        clear_params = {}
        if partition:
            clear_params["partitions"] = partition
        
        # Clear the dataset
        result = dataset.clear(**clear_params)
        
        return {
            "status": "ok",
            "dataset_name": dataset_name,
            "partition": partition,
            "clear_result": result,
            "message": f"Dataset '{dataset_name}' cleared successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to clear dataset '{dataset_name}': {str(e)}"
        }
