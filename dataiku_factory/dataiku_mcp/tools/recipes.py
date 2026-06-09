"""
Recipe management tools for Dataiku DSS.

This module provides functions for creating, updating, deleting, and running recipes
in Dataiku DSS projects through the dataiku-api-client.
"""

from typing import Dict, List, Optional, Union, Any
import dataikuapi
import dataikuapi.dss.project
import dataikuapi.dss.recipe
from dataiku_mcp.client import get_client, get_project


def _recipe_type(recipe: dataikuapi.dss.recipe.DSSRecipe) -> Optional[str]:
    """Return the recipe type using public client APIs."""
    try:
        definition = recipe.get_definition_and_payload()
        return getattr(definition, "type", None)
    except Exception:
        return None


def create_recipe(
    project_key: str,
    recipe_type: str,
    recipe_name: str,
    inputs: List[str],
    outputs: List[Union[str, Dict[str, Any]]],
    code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new recipe in a Dataiku DSS project.
    
    Args:
        project_key: The project key where the recipe will be created
        recipe_type: Type of recipe (e.g., 'python', 'r', 'sql', 'grouping', 'sync', etc.)
        recipe_name: Name of the recipe to create
        inputs: List of input dataset names
        outputs: List of output specifications. Can be:
            - String: name of existing dataset
            - Dict: {"name": str, "new": bool, "connection": str, "append": bool}
        code: Optional code content for code recipes (python, r, sql)
    
    Returns:
        Dict with status and recipe details or error message
    """
    try:
        project = get_project(project_key)
        
        # Create recipe builder
        builder = project.new_recipe(recipe_type, name=recipe_name)
        
        # Add inputs
        for input_name in inputs:
            builder = builder.with_input(input_name)
        
        def _add_new_output(b, name, connection):
            """Attach a new managed output dataset, handling differing builder APIs.

            Code recipes (python/r/sql_script/pyspark/shell/...) use
            ``with_new_output_dataset(name, connection)`` on CodeRecipeCreator, while
            single-output visual recipes (grouping/sync/...) use
            ``with_new_output(name, connection)``.
            """
            if hasattr(b, "with_new_output_dataset"):
                return b.with_new_output_dataset(name, connection)
            if hasattr(b, "with_new_output"):
                return b.with_new_output(name, connection)
            raise AttributeError(
                f"Recipe type '{recipe_type}' does not support creating new outputs "
                f"via this builder ({type(b).__name__})"
            )

        # Add outputs
        for output_spec in outputs:
            if isinstance(output_spec, str):
                # Simple string output - existing dataset
                builder = builder.with_output(output_spec)
            elif isinstance(output_spec, dict):
                output_name = output_spec.get("name")
                if not output_name:
                    return {
                        "status": "error",
                        "message": "Output specification must include 'name' field"
                    }

                if output_spec.get("new", False):
                    # Create new dataset output
                    connection = output_spec.get("connection", "filesystem_managed")
                    builder = _add_new_output(builder, output_name, connection)
                else:
                    # Use existing dataset
                    append = output_spec.get("append", False)
                    builder = builder.with_output(output_name, append=append)
            else:
                return {
                    "status": "error",
                    "message": f"Invalid output specification: {output_spec}"
                }

        # For code recipes, set the script on the builder before building so the
        # recipe is created with its code in place.
        if code and hasattr(builder, "with_script"):
            builder = builder.with_script(code)

        # Build the recipe
        recipe = builder.build()

        # Set code if provided. Covers code recipes whose builder lacked with_script
        # (e.g. sql_query) and re-affirms the payload for the rest.
        if code:
            try:
                def_and_payload = recipe.get_definition_and_payload()
                def_and_payload.set_payload(code)
                def_and_payload.save()
            except Exception:
                settings = recipe.get_settings()
                if hasattr(settings, "set_code"):
                    settings.set_code(code)
                else:
                    settings.data["payload"] = code
                settings.save()
        
        return {
            "status": "ok",
            "recipe_id": recipe.id,
            "recipe_name": recipe_name,
            "recipe_type": recipe_type,
            "inputs": inputs,
            "outputs": [out if isinstance(out, str) else out.get("name") for out in outputs]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create recipe '{recipe_name}': {str(e)}"
        }


def update_recipe(
    project_key: str,
    recipe_name: str,
    code: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
    engine_type: Optional[str] = None,
    container_conf: Optional[Dict[str, Any]] = None,
    resource_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update an existing recipe's settings or code.
    
    Args:
        project_key: The project key containing the recipe
        recipe_name: Name of the recipe to update
        code: New code content (for code recipes)
        description: Recipe description
        tags: List of tags
        custom_fields: Dict of custom metadata fields
        engine_type: Updated engine selection
        container_conf: Updated container configuration
        resource_settings: Updated execution resource settings
    
    Returns:
        Dict with status and update details or error message
    """
    try:
        project = get_project(project_key)
        recipe = project.get_recipe(recipe_name)
        
        updated_fields = []
        
        # Update code if provided
        if code is not None:
            def_and_payload = recipe.get_definition_and_payload()
            if def_and_payload.type in ["sql", "sql_query", "sparksql", "hive"]:
                # SQL query recipes store code as the payload
                def_and_payload.set_payload(code)
                def_and_payload.save()
            else:
                settings = recipe.get_settings()
                settings.set_code(code)
                settings.save()
            updated_fields.append('code')
        
        # Update metadata if provided
        if any(value is not None for value in [description, tags, custom_fields]):
            metadata = recipe.get_metadata()
            
            if description is not None:
                metadata['description'] = description
                updated_fields.append('description')
            
            if tags is not None:
                metadata['tags'] = tags
                updated_fields.append('tags')
            
            if custom_fields is not None:
                if 'customFields' not in metadata:
                    metadata['customFields'] = {}
                metadata['customFields'].update(custom_fields)
                updated_fields.append('custom_fields')
            
            recipe.set_metadata(metadata)
        
        # Handle recipe-specific settings updates
        if any(value is not None for value in [engine_type, container_conf, resource_settings]):
            settings = recipe.get_settings()
            
            if engine_type is not None:
                settings.set_engine_type(engine_type)
                updated_fields.append('engine_type')
            
            if container_conf is not None:
                settings.set_container_conf(container_conf)
                updated_fields.append('container_conf')
            
            if resource_settings is not None:
                settings.set_resource_settings(resource_settings)
                updated_fields.append('resource_settings')
            
            settings.save()
        
        return {
            "status": "ok",
            "recipe_name": recipe_name,
            "updated_fields": updated_fields,
            "message": f"Recipe '{recipe_name}' updated successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to update recipe '{recipe_name}': {str(e)}"
        }


def delete_recipe(
    project_key: str,
    recipe_name: str
) -> Dict[str, Any]:
    """
    Delete a recipe from a Dataiku DSS project.
    
    Args:
        project_key: The project key containing the recipe
        recipe_name: Name of the recipe to delete
    
    Returns:
        Dict with status and deletion details or error message
    """
    try:
        project = get_project(project_key)
        recipe = project.get_recipe(recipe_name)
        
        # Store recipe info before deletion
        recipe_info = {
            "id": recipe.id,
            "type": _recipe_type(recipe),
            "name": recipe_name
        }
        
        # Delete the recipe
        recipe.delete()
        
        return {
            "status": "ok",
            "deleted_recipe": recipe_info,
            "message": f"Recipe '{recipe_name}' deleted successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete recipe '{recipe_name}': {str(e)}"
        }


def run_recipe(
    project_key: str,
    recipe_name: str,
    build_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a recipe to build its outputs.
    
    Args:
        project_key: The project key containing the recipe
        recipe_name: Name of the recipe to run
        build_mode: Optional build mode:
            - "RECURSIVE_BUILD": Default recursive build
            - "NON_RECURSIVE_FORCED_BUILD": Force build without recursion
            - "RECURSIVE_FORCED_BUILD": Force build with recursion
    
    Returns:
        Dict with status and job details or error message
    """
    try:
        project = get_project(project_key)
        recipe = project.get_recipe(recipe_name)
        
        # Prepare run parameters
        run_params = {}
        if build_mode:
            valid_modes = [
                "RECURSIVE_BUILD",
                "NON_RECURSIVE_FORCED_BUILD", 
                "RECURSIVE_FORCED_BUILD"
            ]
            if build_mode not in valid_modes:
                return {
                    "status": "error",
                    "message": f"Invalid build_mode. Must be one of: {valid_modes}"
                }
            run_params["job_type"] = build_mode
        
        # Run the recipe (returns a DSSJob)
        job = recipe.run(**run_params)

        # DSSJob has no wait_for_completion; poll get_status() until terminal state
        import time
        terminal_states = {"DONE", "FAILED", "ABORTED", "CANCELLED"}
        base = {}
        for _ in range(7200):  # up to ~2 hours at 1s polling
            try:
                status = job.get_status() or {}
                base = status.get("baseStatus", {}) or {}
                state = base.get("state")
                if state in terminal_states:
                    break
            except Exception:
                pass
            time.sleep(1)

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
                "message": f"Failed to run recipe '{recipe_name}': {error_msg}",
                "job_state": state,
                "job_start_time": start_str,
                "job_end_time": end_str,
            }

        return {
            "status": "ok",
            "recipe_name": recipe_name,
            "job_status": state,
            "job_start_time": start_str,
            "job_end_time": end_str,
            "message": f"Recipe '{recipe_name}' executed successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to run recipe '{recipe_name}': {str(e)}"
        }


def get_recipe_info(
    project_key: str,
    recipe_name: str
) -> Dict[str, Any]:
    """
    Get detailed information about a recipe.
    
    Args:
        project_key: The project key containing the recipe
        recipe_name: Name of the recipe to inspect
    
    Returns:
        Dict with recipe information or error message
    """
    try:
        project = get_project(project_key)
        recipe = project.get_recipe(recipe_name)
        
        # Get recipe metadata
        metadata = recipe.get_metadata()
        
        # Get recipe settings
        settings = recipe.get_settings()
        
        # Get inputs and outputs
        inputs = recipe.get_inputs()
        outputs = recipe.get_outputs()
        
        return {
            "status": "ok",
            "recipe_info": {
                "id": recipe.id,
                "name": recipe_name,
                "type": _recipe_type(recipe),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "inputs": [{"name": inp["ref"], "project": inp.get("projectKey", project_key)} for inp in inputs],
                "outputs": [{"name": out["ref"], "project": out.get("projectKey", project_key)} for out in outputs],
                "creation_date": metadata.get("creationDate"),
                "last_modified": metadata.get("lastModifiedDate"),
                "last_modified_by": metadata.get("lastModifiedBy", {}).get("login"),
                "custom_fields": metadata.get("customFields", {})
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get recipe info for '{recipe_name}': {str(e)}"
        }


def list_recipes(
    project_key: str,
    recipe_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all recipes in a project, optionally filtered by type.
    
    Args:
        project_key: The project key to list recipes from
        recipe_type: Optional filter by recipe type
    
    Returns:
        Dict with list of recipes or error message
    """
    try:
        project = get_project(project_key)
        
        # Get all recipes
        all_recipes = project.list_recipes()
        
        # Filter by type if specified
        if recipe_type:
            filtered_recipes = [r for r in all_recipes if r.get("type") == recipe_type]
        else:
            filtered_recipes = all_recipes
        
        return {
            "status": "ok",
            "recipes": [
                {
                    "name": recipe.get("name"),
                    "type": recipe.get("type"),
                    "id": recipe.get("id"),
                    "inputs": recipe.get("inputs", []),
                    "outputs": recipe.get("outputs", [])
                }
                for recipe in filtered_recipes
            ],
            "total_count": len(filtered_recipes),
            "project_key": project_key
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list recipes in project '{project_key}': {str(e)}"
        }
