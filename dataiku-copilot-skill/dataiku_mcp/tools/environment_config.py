"""
Environment and configuration tools for Dataiku MCP integration.
"""

import json
from typing import Dict, Any, List, Optional
from dataiku_mcp.client import get_client, get_project

def get_code_environments(
    project_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    List available Python/R environments.
    
    Args:
        project_key: Project identifier (optional)
        
    Returns:
        Dict containing code environments information
    """
    try:
        client = get_client()
        
        # Get global code environments
        global_environments = []
        try:
            env_list = client.list_code_envs()
            for env in env_list:
                env_info = {
                    "name": env["envName"],
                    "language": env["envLang"],
                    "type": env["deploymentMode"],
                    "owner": env.get("owner", "unknown"),
                    "usable": env.get("usable", False),
                    "description": env.get("description", "")
                }
                
                # Get detailed environment info
                try:
                    env_details = client.get_code_env(env["envLang"], env["envName"])
                    env_settings = env_details.get_settings()
                    
                    env_info["python_interpreter"] = env_settings.get_raw().get("pythonInterpreter", "unknown")
                    env_info["conda_environment"] = env_settings.get_raw().get("condaEnvironment", "")
                    env_info["desc"] = env_settings.get_raw().get("desc", "")
                    
                    # Get package information
                    try:
                        packages = env_details.list_packages()
                        env_info["package_count"] = len(packages)
                        env_info["sample_packages"] = packages[:10]  # First 10 packages
                    except:
                        env_info["package_count"] = 0
                        env_info["sample_packages"] = []
                    
                except Exception as e:
                    env_info["error"] = f"Could not get detailed info: {str(e)}"
                
                global_environments.append(env_info)
                
        except Exception as e:
            global_environments = []
            global_error = f"Could not list global environments: {str(e)}"
        
        result = {
            "status": "ok",
            "global_environments": global_environments,
            "global_environment_count": len(global_environments)
        }
        
        # Get project-specific environment settings if project_key provided
        if project_key:
            try:
                project = get_project(project_key)
                project_settings = project.get_settings()
                
                # Get code env settings
                code_env_settings = project_settings.get_code_env_settings()
                
                project_env_info = {
                    "project_key": project_key,
                    "default_python_env": code_env_settings.get("python", {}).get("defaultEnv", "INHERIT"),
                    "default_r_env": code_env_settings.get("r", {}).get("defaultEnv", "INHERIT"),
                    "use_builtin_python": code_env_settings.get("python", {}).get("mode", "INHERIT") == "INHERIT",
                    "use_builtin_r": code_env_settings.get("r", {}).get("mode", "INHERIT") == "INHERIT"
                }
                
                # Get environment overrides for specific objects
                env_overrides = code_env_settings.get("envOverrides", {})
                project_env_info["environment_overrides"] = env_overrides
                project_env_info["override_count"] = len(env_overrides)
                
                result["project_environment_info"] = project_env_info
                
            except Exception as e:
                result["project_environment_error"] = f"Could not get project environment settings: {str(e)}"
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get code environments: {str(e)}"
        }


def get_project_variables(
    project_key: str
) -> Dict[str, Any]:
    """
    Get project-level variables and configuration.
    
    Args:
        project_key: The project key
        
    Returns:
        Dict containing project variables and metadata
    """
    try:
        project = get_project(project_key)
        
        # Get project variables
        variables = project.get_variables()
        
        # Separate standard and custom variables
        standard_variables = variables.get("standard", {})
        custom_variables = variables.get("local", {})
        
        # Get project metadata
        metadata = project.get_metadata()
        
        # Get project settings
        settings = project.get_settings()
        
        # Extract key project information
        project_info = {
            "key": project_key,
            "name": metadata.get("name", project_key),
            "description": metadata.get("description", ""),
            "short_description": metadata.get("shortDesc", ""),
            "tags": metadata.get("tags", []),
            "owner": metadata.get("owner", "unknown"),
            "creation_date": metadata.get("creationDate", ""),
            "last_modified": metadata.get("versionTag", {}).get("lastModified", "")
        }
        
        # Get custom fields
        custom_fields = metadata.get("customFields", {})
        
        # Process variables to hide sensitive information
        processed_standard = {}
        for key, value in standard_variables.items():
            if key.lower() in ["password", "secret", "key", "token"]:
                processed_standard[key] = {"type": type(value).__name__, "value": "***HIDDEN***"}
            else:
                processed_standard[key] = {"type": type(value).__name__, "value": value}
        
        processed_custom = {}
        for key, value in custom_variables.items():
            if key.lower() in ["password", "secret", "key", "token"]:
                processed_custom[key] = {"type": type(value).__name__, "value": "***HIDDEN***"}
            else:
                processed_custom[key] = {"type": type(value).__name__, "value": value}
        
        # Get project permissions (if available)
        project_permissions = {}
        try:
            # This might not be available in all DSS versions
            permissions = project.get_permissions()
            project_permissions = permissions
        except Exception:
            project_permissions = {"error": "Permissions not available"}
        
        # Get project settings summary
        settings_summary = {
            "bundle_export_options": settings.get_raw().get("bundleExportOptions", {}),
            "git_reference": settings.get_raw().get("gitReference", {}),
            "flow_display_settings": settings.get_raw().get("flowDisplaySettings", {}),
            "notebook_exports": settings.get_raw().get("notebookExports", {})
        }
        
        # Calculate statistics
        variable_stats = {
            "standard_variable_count": len(standard_variables),
            "custom_variable_count": len(custom_variables),
            "total_variables": len(standard_variables) + len(custom_variables),
            "custom_fields_count": len(custom_fields),
            "tag_count": len(metadata.get("tags", []))
        }
        
        return {
            "status": "ok",
            "project_info": project_info,
            "variables": {
                "standard": processed_standard,
                "custom": processed_custom
            },
            "variable_stats": variable_stats,
            "metadata": {
                "custom_fields": custom_fields,
                "tags": metadata.get("tags", []),
                "checklists": metadata.get("checklists", [])
            },
            "settings_summary": settings_summary,
            "permissions": project_permissions
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get project variables: {str(e)}"
        }


def get_connections(
    project_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    List available data connections.
    
    Args:
        project_key: Project identifier (optional)
        
    Returns:
        Dict containing connection information
    """
    try:
        client = get_client()
        
        # Get global connections
        global_connections = []
        try:
            connections = client.list_connections()
            for conn in connections:
                conn_info = {
                    "name": conn["name"],
                    "type": conn["type"],
                    "usable": conn.get("usable", False),
                    "allow_write": conn.get("allowWrite", False),
                    "allow_managed_datasets": conn.get("allowManagedDatasets", False),
                    "description": conn.get("description", "")
                }
                
                # Get detailed connection info (without sensitive parameters)
                try:
                    conn_details = client.get_connection(conn["name"])
                    conn_settings = conn_details.get_settings()
                    
                    # Get non-sensitive parameters
                    params = conn_settings.get_raw().get("params", {})
                    safe_params = {}
                    
                    # Filter out sensitive parameters
                    sensitive_keys = ["password", "secret", "key", "token", "credentials"]
                    for key, value in params.items():
                        if any(sensitive in key.lower() for sensitive in sensitive_keys):
                            safe_params[key] = "***HIDDEN***"
                        else:
                            safe_params[key] = value
                    
                    conn_info["parameters"] = safe_params
                    conn_info["description"] = conn_settings.get_raw().get("description", "")
                    
                except Exception as e:
                    conn_info["error"] = f"Could not get detailed info: {str(e)}"
                
                global_connections.append(conn_info)
                
        except Exception as e:
            global_connections = []
            global_error = f"Could not list global connections: {str(e)}"
        
        result = {
            "status": "ok",
            "global_connections": global_connections,
            "global_connection_count": len(global_connections)
        }
        
        # Get project-specific connection usage if project_key provided
        if project_key:
            try:
                project = get_project(project_key)
                
                # Get datasets to see which connections are used
                datasets = project.list_datasets()
                connection_usage = {}
                
                for dataset in datasets:
                    try:
                        dataset_obj = project.get_dataset(dataset["name"])
                        dataset_settings = dataset_obj.get_settings()
                        dataset_params = dataset_settings.get_raw().get("params", {})
                        
                        connection_name = dataset_params.get("connection", "default")
                        if connection_name not in connection_usage:
                            connection_usage[connection_name] = {
                                "datasets": [],
                                "count": 0
                            }
                        
                        connection_usage[connection_name]["datasets"].append({
                            "name": dataset["name"],
                            "type": dataset["type"]
                        })
                        connection_usage[connection_name]["count"] += 1
                        
                    except Exception:
                        continue
                
                # Get recipes to see which connections are used
                recipes = project.list_recipes()
                for recipe in recipes:
                    try:
                        recipe_obj = project.get_recipe(recipe["name"])
                        recipe_definition = recipe_obj.get_definition()
                        
                        # Check inputs and outputs for connections
                        for input_def in recipe_definition.get("inputs", []):
                            input_name = input_def["ref"]
                            try:
                                input_dataset = project.get_dataset(input_name)
                                input_settings = input_dataset.get_settings()
                                input_params = input_settings.get_raw().get("params", {})
                                connection_name = input_params.get("connection", "default")
                                
                                if connection_name in connection_usage:
                                    if "used_by_recipes" not in connection_usage[connection_name]:
                                        connection_usage[connection_name]["used_by_recipes"] = []
                                    if recipe["name"] not in connection_usage[connection_name]["used_by_recipes"]:
                                        connection_usage[connection_name]["used_by_recipes"].append(recipe["name"])
                            except:
                                continue
                        
                        for output_def in recipe_definition.get("outputs", []):
                            output_name = output_def["ref"]
                            try:
                                output_dataset = project.get_dataset(output_name)
                                output_settings = output_dataset.get_settings()
                                output_params = output_settings.get_raw().get("params", {})
                                connection_name = output_params.get("connection", "default")
                                
                                if connection_name in connection_usage:
                                    if "used_by_recipes" not in connection_usage[connection_name]:
                                        connection_usage[connection_name]["used_by_recipes"] = []
                                    if recipe["name"] not in connection_usage[connection_name]["used_by_recipes"]:
                                        connection_usage[connection_name]["used_by_recipes"].append(recipe["name"])
                            except:
                                continue
                                
                    except Exception:
                        continue
                
                project_connection_info = {
                    "project_key": project_key,
                    "connection_usage": connection_usage,
                    "unique_connections_used": len(connection_usage),
                    "total_datasets": len(datasets),
                    "total_recipes": len(recipes)
                }
                
                result["project_connection_info"] = project_connection_info
                
            except Exception as e:
                result["project_connection_error"] = f"Could not get project connection info: {str(e)}"
        
        # Group connections by type
        connection_types = {}
        for conn in global_connections:
            conn_type = conn["type"]
            if conn_type not in connection_types:
                connection_types[conn_type] = []
            connection_types[conn_type].append(conn["name"])
        
        result["connection_types"] = connection_types
        result["connection_type_count"] = len(connection_types)
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get connections: {str(e)}"
        }