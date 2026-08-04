"""
Environment and configuration tools for Dataiku MCP integration.
"""

import json
from typing import Dict, Any, List, Optional
from dataiku_mcp.client import get_client, get_project
from dataiku_mcp.tools.api_helpers import is_sensitive_name, item_get, recipe_io


def _summarize_code_env(env_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a compact summary from a code env's raw settings (the result of
    DSSCodeEnv.get_settings().get_raw()), instead of returning the full raw
    settings (which include permissions, container configs, and a full
    installed-package list).
    """
    desc = env_raw.get("desc", {})
    spec_packages = [p for p in env_raw.get("specPackageList", "").splitlines() if p.strip()]
    actual_packages = [p for p in env_raw.get("actualPackageList", "").splitlines() if p.strip()]

    return {
        "python_interpreter": desc.get("pythonInterpreter", "unknown"),
        "conda": desc.get("conda", False),
        "spec_packages": spec_packages,
        "actual_package_count": len(actual_packages),
        "sample_actual_packages": actual_packages[:10]
    }


def get_code_environments(
    project_key: Optional[str] = None,
    scope: str = "project"
) -> Dict[str, Any]:
    """
    List Python/R code environments.

    scope="project" (default) avoids the instance-wide admin enumeration
    (GET /admin/code-envs/), which lists every code env on the instance and
    fetches per-env details and packages for each one. On instances with
    many code envs -- or when the configured API key lacks admin rights --
    that enumeration can be very slow or hang. Instead, scope="project"
    reads only this project's code env settings (default Python/R envs and
    any per-object overrides) and fetches details for just those few envs.

    scope="instance" restores the old behaviour: a full admin-level listing
    of every code env on the instance, with per-env details and a sample of
    installed packages. Expect this to be slow on instances with many code
    envs and to require admin rights.

    Args:
        project_key: Project identifier. Required when scope="project".
        scope: "project" (default, fast/filtered to this project's envs)
            or "instance" (full admin-level instance listing).

    Returns:
        Dict containing code environment information
    """
    try:
        client = get_client()

        if scope == "instance":
            return _get_code_environments_instance_wide(client, project_key)

        if scope != "project":
            return {
                "status": "error",
                "message": f"Invalid scope '{scope}'. Use 'project' or 'instance'."
            }

        if not project_key:
            return {
                "status": "error",
                "message": (
                    "scope='project' requires project_key. Pass project_key to get "
                    "this project's code environment settings, or use scope='instance' "
                    "for a full admin-level listing of every code env on the instance "
                    "(slow on instances with many envs, requires admin rights)."
                )
            }

        try:
            project = get_project(project_key)
            code_envs_settings = project.get_settings().get_raw().get("settings", {}).get("codeEnvs", {})
        except Exception as e:
            return {
                "status": "error",
                "message": f"Could not get project code environment settings: {str(e)}"
            }

        python_settings = code_envs_settings.get("python", {})
        r_settings = code_envs_settings.get("r", {})

        project_env_info = {
            "project_key": project_key,
            "python": {
                "mode": python_settings.get("mode", "INHERIT"),
                "env_name": python_settings.get("envName")
            },
            "r": {
                "mode": r_settings.get("mode", "INHERIT"),
                "env_name": r_settings.get("envName")
            }
        }

        env_overrides = code_envs_settings.get("envOverrides", {})
        project_env_info["environment_overrides"] = env_overrides
        project_env_info["override_count"] = len(env_overrides)

        # Only describe the handful of envs this project actually references
        # (i.e. has an explicit env configured), not every env on the instance.
        envs_to_describe = []
        for lang, lang_settings in (("PYTHON", python_settings), ("R", r_settings)):
            env_name = lang_settings.get("envName")
            if lang_settings.get("mode") == "EXPLICIT_ENV" and env_name:
                envs_to_describe.append((lang, env_name))

        environments = []
        for lang, env_name in envs_to_describe:
            env_info = {"name": env_name, "language": lang}
            try:
                env_raw = client.get_code_env(lang, env_name).get_settings().get_raw()
                env_info.update(_summarize_code_env(env_raw))
            except Exception as e:
                env_info["error"] = f"Could not get detailed info: {str(e)}"

            environments.append(env_info)

        return {
            "status": "ok",
            "scope": "project",
            "project_environment_info": project_env_info,
            "environments": environments,
            "environment_count": len(environments)
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get code environments: {str(e)}"
        }


def _get_code_environments_instance_wide(
    client, project_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Full admin-level listing of every code env on the instance, with
    per-env details and a sample of installed packages.

    Calls GET /admin/code-envs/ plus one detail call per env -- requires
    admin rights and can be slow/hang on instances with many code envs.
    """
    global_environments = []
    global_environment_error = None
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
                env_raw = client.get_code_env(env["envLang"], env["envName"]).get_settings().get_raw()
                env_info.update(_summarize_code_env(env_raw))
            except Exception as e:
                env_info["error"] = f"Could not get detailed info: {str(e)}"

            global_environments.append(env_info)

    except Exception as e:
        global_environment_error = f"Could not list global environments: {str(e)}"

    result = {
        "status": "ok",
        "scope": "instance",
        "global_environments": global_environments,
        "global_environment_count": len(global_environments)
    }
    if global_environment_error:
        result["global_environment_error"] = global_environment_error

    # Get project-specific environment settings if project_key provided
    if project_key:
        try:
            project = get_project(project_key)
            code_envs_settings = project.get_settings().get_raw().get("settings", {}).get("codeEnvs", {})
            python_settings = code_envs_settings.get("python", {})
            r_settings = code_envs_settings.get("r", {})

            project_env_info = {
                "project_key": project_key,
                "python": {
                    "mode": python_settings.get("mode", "INHERIT"),
                    "env_name": python_settings.get("envName")
                },
                "r": {
                    "mode": r_settings.get("mode", "INHERIT"),
                    "env_name": r_settings.get("envName")
                }
            }

            env_overrides = code_envs_settings.get("envOverrides", {})
            project_env_info["environment_overrides"] = env_overrides
            project_env_info["override_count"] = len(env_overrides)

            result["project_environment_info"] = project_env_info

        except Exception as e:
            result["project_environment_error"] = f"Could not get project environment settings: {str(e)}"

    return result


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
            if is_sensitive_name(key):
                processed_standard[key] = {"type": type(value).__name__, "value": "***HIDDEN***"}
            else:
                processed_standard[key] = {"type": type(value).__name__, "value": value}
        
        processed_custom = {}
        for key, value in custom_variables.items():
            if is_sensitive_name(key):
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
    project_key: Optional[str] = None,
    scope: str = "project",
    include_usage: bool = False
) -> Dict[str, Any]:
    """
    List available data connections.

    scope="project" (default) avoids the instance-wide admin enumeration
    (GET /admin/connections/), which requires admin rights and fetches
    per-connection settings for every connection on the instance. On
    instances with many connections -- or when the configured API key lacks
    admin rights -- that enumeration can be very slow or hang. Instead,
    scope="project" lists connection names via the lightweight, non-admin
    /connections/get-names endpoint and, when project_key is given, filters
    them down to the connections actually used by that project's datasets
    and recipes (derived from project-scoped APIs only).

    scope="instance" restores the old behaviour: a full admin-level listing
    of every connection on the instance, with per-connection settings.
    Expect this to be slow on instances with many connections and to require
    admin rights.

    ``connection_usage`` -- the per-connection inventory naming every dataset
    and recipe -- is omitted unless ``include_usage=True``. On a project the
    size of BURUNDI_BIZOPS (1,065 datasets, 975 recipes) that inventory is tens
    of thousands of tokens, and an agent framework replays the whole tool result
    on every subsequent turn, so returning it by default multiplies the cost of
    one lookup across the rest of the conversation. Counts are always returned.

    Args:
        project_key: Project identifier. With scope="project", filters
            connections down to those used by this project.
        scope: "project" (default, fast/filtered) or "instance"
            (full admin-level instance listing).
        include_usage: Include the full per-connection lists of dataset and
            recipe names. Off by default; very large on big projects.

    Returns:
        Dict containing connection information
    """
    try:
        client = get_client()

        if scope == "instance":
            return _get_connections_instance_wide(client, project_key)


        if scope != "project":
            return {
                "status": "error",
                "message": f"Invalid scope '{scope}'. Use 'project' or 'instance'."
            }

        try:
            connection_names = client.list_connections_names("all")
        except Exception as e:
            return {
                "status": "error",
                "message": f"Could not list connection names: {str(e)}"
            }

        result = {
            "status": "ok",
            "scope": "project",
            "available_connection_names": connection_names,
            "available_connection_count": len(connection_names)
        }

        if not project_key:
            result["note"] = (
                "No project_key given: returning connection names only, with no "
                "per-connection details. Pass project_key to filter to the "
                "connections used by a project (with details), or use "
                "scope='instance' for a full admin-level listing of every "
                "connection on the instance."
            )
            return result

        try:
            project = get_project(project_key)
            connection_usage, total_datasets, total_recipes = _compute_connection_usage(
                project, include_recipes=include_usage
            )
        except Exception as e:
            result["project_connection_error"] = f"Could not get project connection info: {str(e)}"
            return result

        # Only describe the connections this project actually uses, not
        # every connection on the instance.
        used_connection_names = [name for name in connection_names if name in connection_usage]

        connections = []
        for name in used_connection_names:
            conn_info = {"name": name}
            try:
                info = client.get_connection(name).get_info(contextual_project_key=project_key)
                conn_info["type"] = info.get_type()
                conn_info["credentials_mode"] = info.get_credential_mode()

                # Filter out sensitive parameters
                params = info.get_params() or {}
                conn_info["parameters"] = {
                    key: ("***HIDDEN***" if is_sensitive_name(key) else value)
                    for key, value in params.items()
                }
            except Exception as e:
                conn_info["error"] = f"Could not get connection info: {str(e)}"

            connections.append(conn_info)

        # Group connections by type
        connection_types: Dict[str, List[str]] = {}
        for conn in connections:
            connection_types.setdefault(conn.get("type", "unknown"), []).append(conn["name"])

        # Counts always; the name-by-name inventory only on request. Recipe
        # counts are reported only when the recipe pass actually ran, so a
        # skipped walk never masquerades as "zero recipes".
        usage_summary = {}
        for name, usage in connection_usage.items():
            entry = {"dataset_count": len(usage.get("datasets", []))}
            if include_usage:
                entry["recipe_count"] = len(usage.get("used_by_recipes", []))
            usage_summary[name] = entry

        result.update({
            "project_key": project_key,
            "connections": connections,
            "connection_count": len(connections),
            "connection_types": connection_types,
            "connection_type_count": len(connection_types),
            "connection_usage_summary": usage_summary,
            "unique_connections_used": len(connection_usage),
            "total_datasets": total_datasets,
        })
        if total_recipes is not None:
            result["total_recipes"] = total_recipes

        if include_usage:
            result["connection_usage"] = connection_usage
        else:
            result["connection_usage_note"] = (
                "Per-connection dataset and recipe names omitted, and the recipe "
                "scan skipped, to keep this response small and fast; dataset "
                "counts are in connection_usage_summary. Pass include_usage=true "
                "for the full inventory (slow on large projects), or use "
                "search_project_objects to find specific objects."
            )

        return result

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get connections: {str(e)}"
        }


def _dataset_connection(project, dataset_item) -> Optional[str]:
    """
    Return the connection a dataset sits on, without a per-dataset HTTP call.

    ``list_datasets`` already returns each dataset's serialized definition,
    ``params`` included, so the connection is normally right there. Only when a
    DSS version omits it do we pay for ``get_settings()``. Fetching settings for
    every dataset unconditionally is what made this tool unusable on a
    thousand-dataset project.
    """
    params = item_get(dataset_item, "params")
    if isinstance(params, dict) and "connection" in params:
        return params.get("connection") or "default"

    name = item_get(dataset_item, "name")
    if not name:
        return None
    try:
        raw = project.get_dataset(name).get_settings().get_raw()
        return (raw.get("params") or {}).get("connection", "default")
    except Exception:
        return None


def _compute_connection_usage(project, include_recipes: bool = True) -> tuple:
    """
    Determine which connections a project's datasets/recipes reference.

    Uses only project-scoped APIs -- no admin/instance-wide calls.

    ``include_recipes=False`` skips the recipe pass entirely. That pass costs one
    ``get_definition_and_payload()`` per recipe (975 on BURUNDI_BIZOPS) and
    exists solely to populate the per-connection ``used_by_recipes`` name lists,
    which callers do not receive unless they ask for them. Skipping it when they
    have not is the difference between a request that returns and one that times
    out.

    Returns:
        Tuple of (connection_usage dict, total_datasets, total_recipes)
    """
    connection_usage: Dict[str, Any] = {}
    dataset_connection: Dict[str, str] = {}

    datasets = project.list_datasets()
    for dataset in datasets:
        try:
            dataset_name = item_get(dataset, "name")
            connection_name = _dataset_connection(project, dataset)
            if connection_name is None:
                continue
            dataset_connection[dataset_name] = connection_name

            usage = connection_usage.setdefault(connection_name, {"datasets": [], "count": 0})
            usage["datasets"].append({
                "name": dataset_name,
                "type": item_get(dataset, "type")
            })
            usage["count"] += 1

        except Exception:
            continue

    if not include_recipes:
        return connection_usage, len(datasets), None

    recipes = project.list_recipes()
    for recipe in recipes:
        try:
            recipe_name = item_get(recipe, "name")
            refs = recipe_io(project.get_recipe(recipe_name))

            for dataset_name in refs["inputs"] + refs["outputs"]:
                # Resolved from the map built above rather than re-fetched: the
                # same datasets appear across many recipes, and each lookup used
                # to be its own round trip.
                connection_name = dataset_connection.get(dataset_name)
                if connection_name is None:
                    continue

                if connection_name in connection_usage:
                    used_by_recipes = connection_usage[connection_name].setdefault("used_by_recipes", [])
                    if recipe_name not in used_by_recipes:
                        used_by_recipes.append(recipe_name)

        except Exception:
            continue

    return connection_usage, len(datasets), len(recipes)


def _get_connections_instance_wide(
    client, project_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Full admin-level listing of every connection on the instance, with
    per-connection settings.

    Calls GET /admin/connections/ plus one detail call per connection --
    requires admin rights and can be slow/hang on instances with many
    connections.
    """
    global_connections = []
    global_connection_error = None
    try:
        for conn in client.list_connections(as_type="listitems"):
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
                conn_settings = client.get_connection(conn["name"]).get_settings()

                # Filter out sensitive parameters
                params = conn_settings.get_raw().get("params", {})
                safe_params = {}
                for key, value in params.items():
                    if is_sensitive_name(key):
                        safe_params[key] = "***HIDDEN***"
                    else:
                        safe_params[key] = value

                conn_info["parameters"] = safe_params
                conn_info["description"] = conn_settings.get_raw().get("description", "")

            except Exception as e:
                conn_info["error"] = f"Could not get detailed info: {str(e)}"

            global_connections.append(conn_info)

    except Exception as e:
        global_connection_error = f"Could not list global connections: {str(e)}"

    result = {
        "status": "ok",
        "scope": "instance",
        "global_connections": global_connections,
        "global_connection_count": len(global_connections)
    }
    if global_connection_error:
        result["global_connection_error"] = global_connection_error

    # Get project-specific connection usage if project_key provided
    if project_key:
        try:
            project = get_project(project_key)
            connection_usage, total_datasets, total_recipes = _compute_connection_usage(project)

            result["project_connection_info"] = {
                "project_key": project_key,
                "connection_usage": connection_usage,
                "unique_connections_used": len(connection_usage),
                "total_datasets": total_datasets,
                "total_recipes": total_recipes
            }

        except Exception as e:
            result["project_connection_error"] = f"Could not get project connection info: {str(e)}"

    # Group connections by type
    connection_types: Dict[str, List[str]] = {}
    for conn in global_connections:
        connection_types.setdefault(conn["type"], []).append(conn["name"])

    result["connection_types"] = connection_types
    result["connection_type_count"] = len(connection_types)

    return result
